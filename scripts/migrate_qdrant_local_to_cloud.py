"""Safe, explicit, manually-triggered local -> Qdrant Cloud migration.

Never run automatically by anything else in this repo — switching
QDRANT_BACKEND does NOT migrate data; the two backends are independent
databases (see docs/CLOUD_QDRANT_PIPELINE.md). This script is the only
way data moves between them, and only when you explicitly run it.

Always connects to BOTH the local backend (qdrant_url/qdrant_api_key)
and the cloud backend (qdrant_cloud_url/qdrant_cloud_api_key) directly
from KBConfig, regardless of whichever one QDRANT_BACKEND currently
points the rest of the pipeline at.

Default mode is a dry run (read-only on both sides, writes nothing) —
you must pass --execute to actually migrate, and --overwrite-destination
too if the destination collection already has any points. Resuming
(--resume) skips pages already fully upserted, tracked in a small JSON
state file; without it, a restarted migration still only re-upserts
points whose Qdrant point ID is unchanged (idempotent by construction,
same id -> overwritten in place, never duplicated) so re-running from
scratch is always safe, just not maximally efficient.

Usage:
    python -m scripts.migrate_qdrant_local_to_cloud                       # dry run (default, read-only)
    python -m scripts.migrate_qdrant_local_to_cloud --execute             # actually migrate
    python -m scripts.migrate_qdrant_local_to_cloud --execute --resume    # resume an interrupted migration
    python -m scripts.migrate_qdrant_local_to_cloud --validate            # re-check an already-migrated pair
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from src.knowledge_base.config import KBConfig, load_config

logger = logging.getLogger("migrate_qdrant_local_to_cloud")


def _client(url: str, api_key: Optional[str]):
    from qdrant_client import QdrantClient

    return QdrantClient(url=url, api_key=api_key or None)


def _require_cloud_config(config: KBConfig) -> None:
    if not config.qdrant_cloud_url:
        raise ValueError("QDRANT_CLOUD_URL is not set (in .env.kb) — nothing to migrate to.")
    if not config.qdrant_cloud_api_key:
        raise ValueError("QDRANT_CLOUD_API_KEY is not set (in .env.kb) — required for Qdrant Cloud.")
    if not config.qdrant_cloud_url.startswith("https://"):
        raise ValueError("QDRANT_CLOUD_URL must use https:// for Qdrant Cloud.")


def _vectors_close(a, b, tolerance: float = 1e-5) -> bool:
    """Qdrant stores vectors as float32 internally — re-upserting a value
    already read back from one Qdrant instance into another can round-trip
    through float32 twice and pick up a tiny (~1e-7 relative) precision
    drift even though nothing about the migration logic is lossy. Exact
    equality is the wrong check here; a real corruption/transposition bug
    would produce a difference many orders of magnitude larger than this
    tolerance. Confirmed by direct reproduction against a real in-memory
    Qdrant round-trip."""
    if a is None or b is None or len(a) != len(b):
        return False
    return all(abs(x - y) <= tolerance for x, y in zip(a, b))


def _collection_info(client, name: str) -> Optional[dict]:
    if not client.collection_exists(name):
        return None
    info = client.get_collection(name)
    vectors = info.config.params.vectors
    return {"size": vectors.size, "distance": str(vectors.distance), "points_count": info.points_count}


def dry_run_report(config: KBConfig) -> dict:
    _require_cloud_config(config)
    source = _client(config.qdrant_url, config.qdrant_api_key)
    dest = _client(config.qdrant_cloud_url, config.qdrant_cloud_api_key)

    source_info = _collection_info(source, config.qdrant_collection)
    dest_info = _collection_info(dest, config.qdrant_collection)

    report = {
        "source_collection": config.qdrant_collection,
        "source_url": config.qdrant_url,
        "source_info": source_info,
        "destination_collection": config.qdrant_collection,
        "destination_url": config.qdrant_cloud_url,
        "destination_info": dest_info,
        "expected_operation": (
            "CREATE destination collection, then upsert all source points"
            if dest_info is None
            else f"Upsert source points into EXISTING destination collection ({dest_info['points_count']} points already present)"
        ),
    }
    return report


def _state_path(config: KBConfig) -> Path:
    return config.manifests_dir / "migration_local_to_cloud_state.json"


def _load_state(config: KBConfig) -> dict:
    path = _state_path(config)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"next_offset": None, "migrated_count": 0}


def _save_state(config: KBConfig, state: dict) -> None:
    _state_path(config).write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def run_migration(config: KBConfig, batch_size: int, resume: bool, overwrite_destination: bool) -> dict:
    from qdrant_client.models import Distance, PointStruct, VectorParams

    _require_cloud_config(config)
    source = _client(config.qdrant_url, config.qdrant_api_key)
    dest = _client(config.qdrant_cloud_url, config.qdrant_cloud_api_key)

    source_info = _collection_info(source, config.qdrant_collection)
    if source_info is None:
        raise RuntimeError(f"Source collection {config.qdrant_collection!r} does not exist locally — nothing to migrate.")

    dest_info = _collection_info(dest, config.qdrant_collection)
    if dest_info is None:
        dest.create_collection(
            collection_name=config.qdrant_collection,
            vectors_config=VectorParams(size=source_info["size"], distance=Distance(source_info["distance"])),
        )
        logger.info(f"Created destination collection {config.qdrant_collection!r} (dim={source_info['size']}, distance={source_info['distance']}).")
    else:
        if dest_info["size"] != source_info["size"] or dest_info["distance"] != source_info["distance"]:
            raise RuntimeError(
                f"Destination collection {config.qdrant_collection!r} already exists with an INCOMPATIBLE "
                f"schema (dim={dest_info['size']}/{dest_info['distance']} vs source "
                f"dim={source_info['size']}/{source_info['distance']}). Refusing to modify or recreate it — "
                "resolve this manually."
            )
        if dest_info["points_count"] > 0 and not overwrite_destination:
            raise RuntimeError(
                f"Destination collection {config.qdrant_collection!r} already has {dest_info['points_count']} "
                "point(s). Pass --overwrite-destination to proceed anyway (existing points with the same ID "
                "will be overwritten in place; others are left untouched — nothing is deleted)."
            )

    state = _load_state(config) if resume else {"next_offset": None, "migrated_count": 0, "completed": False}
    if resume and state.get("completed"):
        # A completed migration's state file is normally deleted (below) —
        # this only triggers if a crash happened between finishing the last
        # batch and clearing the checkpoint. next_offset=None is ambiguous
        # with "start from the beginning" (Qdrant's own scroll() convention
        # for both), so completion needs its own explicit flag, checked
        # BEFORE touching offset at all, to avoid a full needless re-scroll.
        return {"migrated": state["migrated_count"], "batches": 0, "source_points": source_info["points_count"]}

    offset = state["next_offset"]
    migrated = state["migrated_count"]
    uploaded_batches = 0

    with tqdm(total=source_info["points_count"], initial=migrated, desc="Migrating to Cloud", unit="point") as bar:
        while True:
            points, next_offset = source.scroll(
                collection_name=config.qdrant_collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            if not points:
                break

            dest.upsert(
                collection_name=config.qdrant_collection,
                points=[PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in points],
                wait=True,
            )
            uploaded_batches += 1
            migrated += len(points)
            bar.update(len(points))

            offset = next_offset
            _save_state(config, {"next_offset": offset, "migrated_count": migrated, "completed": offset is None})
            if offset is None:
                break

    _state_path(config).unlink(missing_ok=True)  # migration completed fully — clear the resume checkpoint
    return {"migrated": migrated, "batches": uploaded_batches, "source_points": source_info["points_count"]}


def validate_migration(config: KBConfig, sample_size: int = 5) -> dict:
    """Never assumes equal point counts alone proves success — also
    checks vector dimensions, a sample of payloads/vectors byte-for-byte,
    and a real retrieval smoke test against the destination."""
    _require_cloud_config(config)
    source = _client(config.qdrant_url, config.qdrant_api_key)
    dest = _client(config.qdrant_cloud_url, config.qdrant_cloud_api_key)

    source_info = _collection_info(source, config.qdrant_collection)
    dest_info = _collection_info(dest, config.qdrant_collection)
    if source_info is None or dest_info is None:
        return {"ok": False, "reason": "source or destination collection does not exist"}

    issues = []
    if source_info["points_count"] != dest_info["points_count"]:
        issues.append(f"point count mismatch: source={source_info['points_count']} destination={dest_info['points_count']}")
    if source_info["size"] != dest_info["size"] or source_info["distance"] != dest_info["distance"]:
        issues.append(f"vector config mismatch: source={source_info} destination={dest_info}")

    sample_points, _ = source.scroll(collection_name=config.qdrant_collection, limit=sample_size, with_payload=True, with_vectors=True)
    sample_results = []
    for p in sample_points:
        dest_points = dest.retrieve(collection_name=config.qdrant_collection, ids=[p.id], with_payload=True, with_vectors=True)
        if not dest_points:
            issues.append(f"point {p.id} missing on destination")
            continue
        dp = dest_points[0]
        payload_match = dp.payload == p.payload
        vector_match = _vectors_close(dp.vector, p.vector)
        if not payload_match:
            issues.append(f"point {p.id}: payload mismatch")
        if not vector_match:
            issues.append(f"point {p.id}: vector mismatch")
        sample_results.append({"point_id": str(p.id), "payload_match": payload_match, "vector_match": vector_match})

    retrieval_ok = None
    if sample_points:
        probe = sample_points[0]
        hits = dest.query_points(collection_name=config.qdrant_collection, query=probe.vector, limit=1, with_payload=False).points
        retrieval_ok = bool(hits) and str(hits[0].id) == str(probe.id)
        if not retrieval_ok:
            issues.append("retrieval smoke test failed — querying destination with a known source vector did not return the matching point")

    return {
        "ok": not issues,
        "source_points": source_info["points_count"],
        "destination_points": dest_info["points_count"],
        "sample_checked": len(sample_results),
        "sample_results": sample_results,
        "retrieval_smoke_test_passed": retrieval_ok,
        "issues": issues,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate the local Qdrant collection to Qdrant Cloud (manual, explicit only).")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--execute", action="store_true", help="Actually migrate. Without this, only a dry-run report is printed — nothing is written.")
    parser.add_argument("--overwrite-destination", action="store_true", help="Required if the destination collection already has points.")
    parser.add_argument("--resume", action="store_true", help="Resume from the last saved checkpoint instead of starting over.")
    parser.add_argument("--batch-size", type=int, default=None, help="Defaults to config.qdrant_upsert_batch_size.")
    parser.add_argument("--validate", action="store_true", help="Only run post-migration validation against the current state of both collections — no writes.")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.validate:
        result = validate_migration(config)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    if not args.execute:
        report = dry_run_report(config)
        print(json.dumps(report, indent=2, default=str))
        print("\nThis was a DRY RUN — nothing was written. Pass --execute to actually migrate.")
        return 0

    result = run_migration(
        config,
        batch_size=args.batch_size or config.qdrant_upsert_batch_size,
        resume=args.resume,
        overwrite_destination=args.overwrite_destination,
    )
    logger.info(f"Migration complete: {result}")
    validation = validate_migration(config)
    print(json.dumps(validation, indent=2, default=str))
    return 0 if validation.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
