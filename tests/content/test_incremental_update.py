"""Incremental knowledge-base update detection: NEW/CHANGED/UNCHANGED/FAILED (Phase 16 item 12).

No real OpenAI embedding call — uses the deterministic FakeEmbeddings fixture.
"""
from __future__ import annotations

from scripts.content_common import content_fingerprint
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl
from scripts.update_knowledge_base import classify_records, update_knowledge_base


def _video(content_id, text, source_id="VID_001") -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.VIDEO_TRANSCRIPT,
        source="lecture_05.mp4",
        source_id=source_id,
        start_time=0.0,
        end_time=5.0,
        text=text,
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.APPROVED,
        metadata={},
    )


def test_fingerprint_is_deterministic_and_content_sensitive():
    fp1 = content_fingerprint("a.mp4", "VID_001", "hello", {})
    fp2 = content_fingerprint("a.mp4", "VID_001", "hello", {})
    fp3 = content_fingerprint("a.mp4", "VID_001", "hello world", {})
    assert fp1 == fp2
    assert fp1 != fp3


def test_classify_records_new_when_no_previous_fingerprint():
    records = [_video("V1", "hello")]
    result = classify_records(records, previous_fingerprints={})
    assert [r.content_id for r in result["new"]] == ["V1"]
    assert result["changed"] == []
    assert result["unchanged_ids"] == []


def test_classify_records_unchanged_when_fingerprint_matches():
    record = _video("V1", "hello")
    fingerprint = content_fingerprint(record.source, record.source_id, record.text, record.metadata)
    result = classify_records([record], previous_fingerprints={"V1": fingerprint})
    assert result["new"] == []
    assert result["changed"] == []
    assert result["unchanged_ids"] == ["V1"]


def test_classify_records_changed_when_text_differs():
    record = _video("V1", "hello world, updated")
    result = classify_records([record], previous_fingerprints={"V1": "stale-fingerprint"})
    assert [r.content_id for r in result["changed"]] == ["V1"]
    assert result["new"] == []


def test_update_knowledge_base_first_run_treats_everything_as_new(tmp_path, fake_embeddings_patch):
    input_dir = tmp_path / "cleaned"
    write_jsonl([_video("V1", "hello"), _video("V2", "world")], input_dir / "transcripts" / "lecture_05.jsonl")
    output_dir = tmp_path / "kb" / "vector_store"

    summary = update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    assert summary == {"new": 2, "changed": 0, "unchanged": 0, "failed": 0}
    assert (output_dir / "index.faiss").exists()
    assert (output_dir.parent / "fingerprints.json").exists()


def test_update_knowledge_base_second_run_detects_unchanged_and_new(tmp_path, fake_embeddings_patch):
    input_dir = tmp_path / "cleaned"
    write_jsonl([_video("V1", "hello")], input_dir / "transcripts" / "lecture_05.jsonl")
    output_dir = tmp_path / "kb" / "vector_store"

    first = update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)
    assert first["new"] == 1

    # add a second record; first record's text is unchanged
    write_jsonl(
        [_video("V1", "hello"), _video("V2", "a brand new segment")],
        input_dir / "transcripts" / "lecture_05.jsonl",
    )
    second = update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    assert second["new"] == 1
    assert second["unchanged"] == 1
    assert second["changed"] == 0


def test_update_knowledge_base_detects_changed_and_does_not_duplicate_vectors(tmp_path, fake_embeddings_patch):
    from langchain_community.vectorstores import FAISS
    import langchain_openai

    input_dir = tmp_path / "cleaned"
    write_jsonl([_video("V1", "original text")], input_dir / "transcripts" / "lecture_05.jsonl")
    output_dir = tmp_path / "kb" / "vector_store"

    update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    write_jsonl([_video("V1", "updated text, quite different")], input_dir / "transcripts" / "lecture_05.jsonl")
    second = update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    assert second["changed"] == 1
    assert second["new"] == 0

    vs = FAISS.load_local(str(output_dir), langchain_openai.OpenAIEmbeddings(model="fake"), allow_dangerous_deserialization=True)
    matching_docs = [d for d in vs.docstore._dict.values() if d.metadata.get("content_id") == "V1"]
    assert len(matching_docs) == 1  # old chunk replaced, not duplicated
    assert matching_docs[0].page_content == "updated text, quite different"


def test_update_knowledge_base_running_twice_unchanged_is_idempotent(tmp_path, fake_embeddings_patch):
    input_dir = tmp_path / "cleaned"
    write_jsonl([_video("V1", "hello")], input_dir / "transcripts" / "lecture_05.jsonl")
    output_dir = tmp_path / "kb" / "vector_store"

    update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)
    second = update_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    assert second == {"new": 0, "changed": 0, "unchanged": 1, "failed": 0}
