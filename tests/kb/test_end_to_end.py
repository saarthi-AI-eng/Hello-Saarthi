"""End-to-end test of the full pipeline (normalize -> chunk -> embed ->
upsert -> validate -> export) against synthetic fixtures, with the
embedding model mocked (no real BGE-M3 download) and Qdrant in in-memory
mode (no Docker). Exercises scripts.build_kb_qdrant.run,
scripts.validate_kb_qdrant.run, and scripts.export_kb_qdrant.run
together — the parts individual unit tests don't cover."""
from __future__ import annotations

import sys
import types

import pytest
from qdrant_client import QdrantClient

import scripts.build_kb_qdrant as build_kb_qdrant
import scripts.export_kb_qdrant as export_kb_qdrant
import scripts.validate_kb_qdrant as validate_kb_qdrant
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl


class _FakeBGEM3Model:
    def __init__(self, *a, **k):
        pass

    def encode(self, texts, **kwargs):
        return {"dense_vecs": [[0.1] * 1024 for _ in texts]}


@pytest.fixture(autouse=True)
def fake_flagembedding(monkeypatch):
    module = types.ModuleType("FlagEmbedding")
    module.BGEM3FlagModel = _FakeBGEM3Model
    monkeypatch.setitem(sys.modules, "FlagEmbedding", module)


@pytest.fixture(autouse=True)
def in_memory_qdrant(monkeypatch):
    """Every QdrantKBStore built during this test uses one shared
    in-memory client, so the orchestrator's own store instance and the
    test's assertions see the same collection."""
    shared_client = QdrantClient(":memory:")
    from src.knowledge_base.qdrant_store import QdrantKBStore

    original_ensure_client = QdrantKBStore._ensure_client

    def _patched(self):
        if self._client is None:
            self._client = shared_client
        return self._client

    monkeypatch.setattr(QdrantKBStore, "_ensure_client", _patched)
    yield shared_client


def test_full_pipeline_normalize_through_export(kb_config):
    record = ContentRecord(
        content_id="NOTE_1_PAGE_1", content_type=ContentType.PDF_NOTE, course="DSP",
        source="f.pdf", source_id="F1", page=1,
        text="Filters are useful.\n\nButterworth filters are maximally flat.",
        processing_status=ProcessingStatus.PROCESSED, qa_status=QAStatus.APPROVED,
        metadata={"page_quality": "GOOD"},
    )
    write_jsonl([record], kb_config.ocr_output_dir / "f.jsonl")

    manifest = build_kb_qdrant.run(kb_config, device="cpu")

    assert manifest["normalize"]["docs"] == 1
    assert manifest["chunk"]["chunks_out"] >= 1
    assert manifest["embed"]["failed"] == 0
    assert manifest["qdrant_upsert"]["uploaded"] >= 1

    report = validate_kb_qdrant.run(kb_config)
    assert report["errors"] == []
    assert report["chunks_missing_embedding"] == 0
    assert report["qdrant_point_count"] == manifest["chunk"]["chunks_out"]

    export_result = export_kb_qdrant.run(kb_config)
    assert "chunks.jsonl" in export_result["files"]
    assert "manifest.json" in export_result["files"]
    assert "validation_report.json" in export_result["files"]


def test_rerun_with_unchanged_content_skips_re_upload(kb_config):
    record = ContentRecord(
        content_id="NOTE_1_PAGE_1", content_type=ContentType.PDF_NOTE,
        source="f.pdf", source_id="F1", page=1, text="Stable content that does not change.",
        processing_status=ProcessingStatus.PROCESSED, qa_status=QAStatus.APPROVED,
    )
    write_jsonl([record], kb_config.ocr_output_dir / "f.jsonl")

    first = build_kb_qdrant.run(kb_config, device="cpu")
    second = build_kb_qdrant.run(kb_config, device="cpu", resume=True)

    assert first["qdrant_upsert"]["uploaded"] >= 1
    assert second["qdrant_upsert"]["skipped_unchanged"] == first["qdrant_upsert"]["uploaded"]
    assert second["qdrant_upsert"]["uploaded"] == 0
