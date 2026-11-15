"""Migration utility tests — uses qdrant-client's real in-memory mode for
BOTH "source" and "destination" (two separate :memory: instances), via
monkeypatching scripts.migrate_qdrant_local_to_cloud._client. No real
Qdrant Cloud cluster is used or required."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import scripts.migrate_qdrant_local_to_cloud as migrate


@pytest.fixture
def cloud_config(kb_config):
    kb_config.qdrant_cloud_url = "https://example.cloud.qdrant.io"
    kb_config.qdrant_cloud_api_key = "fake-test-key"
    return kb_config


def _seed_source(config, n=5):
    client = QdrantClient(":memory:")
    client.create_collection(config.qdrant_collection, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    def _vector(i: int) -> list[float]:
        # Near-one-hot, cycling through dimensions: distinct DIRECTIONS
        # (not just distinct magnitudes along one shared direction, which
        # cosine similarity can't tell apart) and never an all-zero vector
        # — both of which would make a retrieval smoke test meaningless.
        return [float(d == i % 4) + 0.01 * i for d in range(4)]

    client.upsert(
        config.qdrant_collection,
        points=[PointStruct(id=i, vector=_vector(i), payload={"chunk_id": f"c{i}"}) for i in range(n)],
        wait=True,
    )
    return client


def _empty_dest():
    client = QdrantClient(":memory:")
    return client


def _two_clients(source_client, dest_client):
    def fake(url, api_key):
        return source_client if api_key is None else dest_client
    return fake


def test_dry_run_reports_counts_without_writing(cloud_config):
    source = _seed_source(cloud_config, 5)
    dest = _empty_dest()
    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        report = migrate.dry_run_report(cloud_config)

    assert report["source_info"]["points_count"] == 5
    assert report["destination_info"] is None
    assert dest.collection_exists(cloud_config.qdrant_collection) is False  # dry run wrote nothing


def test_dry_run_requires_cloud_config(kb_config):
    kb_config.qdrant_cloud_url = ""
    with pytest.raises(ValueError, match="QDRANT_CLOUD_URL"):
        migrate.dry_run_report(kb_config)


def test_migration_creates_destination_and_copies_all_points(cloud_config):
    source = _seed_source(cloud_config, 5)
    dest = _empty_dest()
    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        result = migrate.run_migration(cloud_config, batch_size=2, resume=False, overwrite_destination=False)

    assert result["migrated"] == 5
    assert dest.count(cloud_config.qdrant_collection, exact=True).count == 5


def test_migration_preserves_point_ids_vectors_and_payloads(cloud_config):
    source = _seed_source(cloud_config, 3)
    dest = _empty_dest()
    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        migrate.run_migration(cloud_config, batch_size=10, resume=False, overwrite_destination=False)

    src_points, _ = source.scroll(cloud_config.qdrant_collection, limit=10, with_payload=True, with_vectors=True)
    for p in src_points:
        dp = dest.retrieve(cloud_config.qdrant_collection, ids=[p.id], with_payload=True, with_vectors=True)[0]
        assert dp.payload == p.payload
        assert migrate._vectors_close(dp.vector, p.vector)  # float32 storage round-trip, not a logic bug — see migrate.py


def test_migration_batches_according_to_batch_size(cloud_config):
    source = _seed_source(cloud_config, 10)
    dest = _empty_dest()
    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)), patch.object(dest, "upsert", wraps=dest.upsert) as spy:
        migrate.run_migration(cloud_config, batch_size=3, resume=False, overwrite_destination=False)
    # 10 points at batch_size=3 -> 4 upsert calls (3,3,3,1)
    assert spy.call_count == 4


def test_never_overwrites_nonempty_destination_without_explicit_flag(cloud_config):
    source = _seed_source(cloud_config, 3)
    dest = _empty_dest()
    dest.create_collection(cloud_config.qdrant_collection, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    dest.upsert(cloud_config.qdrant_collection, points=[PointStruct(id=999, vector=[0.0] * 4, payload={})], wait=True)

    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        with pytest.raises(RuntimeError, match="overwrite-destination"):
            migrate.run_migration(cloud_config, batch_size=10, resume=False, overwrite_destination=False)


def test_overwrite_destination_flag_allows_proceeding(cloud_config):
    source = _seed_source(cloud_config, 3)
    dest = _empty_dest()
    dest.create_collection(cloud_config.qdrant_collection, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    dest.upsert(cloud_config.qdrant_collection, points=[PointStruct(id=999, vector=[0.0] * 4, payload={})], wait=True)

    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        result = migrate.run_migration(cloud_config, batch_size=10, resume=False, overwrite_destination=True)

    assert result["migrated"] == 3
    assert dest.retrieve(cloud_config.qdrant_collection, ids=[999])  # untouched existing point still there


def test_incompatible_destination_schema_is_refused_not_recreated(cloud_config):
    source = _seed_source(cloud_config, 3)
    dest = _empty_dest()
    dest.create_collection(cloud_config.qdrant_collection, vectors_config=VectorParams(size=99, distance=Distance.COSINE))

    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        with pytest.raises(RuntimeError, match="INCOMPATIBLE"):
            migrate.run_migration(cloud_config, batch_size=10, resume=False, overwrite_destination=True)
    # must not have been deleted/recreated
    assert dest.get_collection(cloud_config.qdrant_collection).config.params.vectors.size == 99


def test_resume_skips_already_migrated_pages(cloud_config):
    source = _seed_source(cloud_config, 6)
    dest = _empty_dest()

    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        # Simulate a partial migration having already happened and been checkpointed.
        migrate._save_state(cloud_config, {"next_offset": None, "migrated_count": 6, "completed": True})
        dest.create_collection(cloud_config.qdrant_collection, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
        result = migrate.run_migration(cloud_config, batch_size=2, resume=True, overwrite_destination=True)

    # Resuming from a checkpoint claiming "already fully migrated" (next_offset=None)
    # must not re-scroll from the beginning — zero additional points migrated.
    assert result["migrated"] == 6


def test_source_points_are_never_modified_or_deleted(cloud_config):
    source = _seed_source(cloud_config, 5)
    dest = _empty_dest()
    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)), patch.object(source, "delete") as delete_spy, patch.object(source, "upsert") as upsert_spy:
        migrate.run_migration(cloud_config, batch_size=2, resume=False, overwrite_destination=False)

    delete_spy.assert_not_called()
    upsert_spy.assert_not_called()


def test_validate_migration_detects_count_mismatch(cloud_config):
    source = _seed_source(cloud_config, 5)
    dest = _empty_dest()
    dest.create_collection(cloud_config.qdrant_collection, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    dest.upsert(cloud_config.qdrant_collection, points=[PointStruct(id=0, vector=[0.0] * 4, payload={})], wait=True)

    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        result = migrate.validate_migration(cloud_config)

    assert result["ok"] is False
    assert any("point count mismatch" in issue for issue in result["issues"])


def test_validate_migration_passes_after_a_clean_migration(cloud_config):
    source = _seed_source(cloud_config, 4)
    dest = _empty_dest()
    with patch.object(migrate, "_client", side_effect=_two_clients(source, dest)):
        migrate.run_migration(cloud_config, batch_size=10, resume=False, overwrite_destination=False)
        result = migrate.validate_migration(cloud_config)

    assert result["ok"] is True
    assert result["retrieval_smoke_test_passed"] is True
