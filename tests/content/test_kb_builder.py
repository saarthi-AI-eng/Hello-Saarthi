"""QA filtering, metadata preservation, and semantic chunking (Phase 16 items 9, 10, 11, 15).

No real OpenAI embedding call — langchain_openai.OpenAIEmbeddings is
replaced with the deterministic FakeEmbeddings fixture.
"""
from __future__ import annotations

from scripts.build_knowledge_base import (
    DEFAULT_ALLOWED_QA,
    MAX_CHUNK_CHARS,
    build_chunk_metadata,
    build_knowledge_base,
    chunk_note_record,
    chunk_record,
    chunk_video_record,
    qa_gate,
)
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl


def _video(content_id, qa, processing=ProcessingStatus.PROCESSED, text="hello world") -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.VIDEO_TRANSCRIPT,
        course="Signals and Systems",
        topic="Sampling",
        lecture="Lecture 05",
        source="lecture_05.mp4",
        source_id="VID_001",
        start_time=10.0,
        end_time=20.0,
        text=text,
        processing_status=processing,
        qa_status=qa,
        metadata={"language": "en"},
    )


def _note(content_id, qa, page=1, text="notes text") -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.PDF_NOTE,
        course="Signals and Systems",
        topic="Sampling",
        source="notes_012.pdf",
        source_id="NOTE_012",
        page=page,
        text=text,
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=qa,
        metadata={"ocr_engine": "tesseract", "ocr_confidence": 0.9},
    )


# --- QA gate ------------------------------------------------------------------

def test_qa_gate_default_excludes_pending_and_rejected():
    records = [
        _video("V1", QAStatus.APPROVED),
        _video("V2", QAStatus.PENDING),
        _video("V3", QAStatus.REJECTED),
        _video("V4", QAStatus.NOT_REQUIRED),
    ]
    eligible = qa_gate(records, allow_pending=False)
    assert {r.content_id for r in eligible} == {"V1", "V4"}


def test_qa_gate_excludes_unprocessed_records_even_if_approved():
    records = [_video("V1", QAStatus.APPROVED, processing=ProcessingStatus.DISCOVERED)]
    assert qa_gate(records, allow_pending=False) == []


def test_qa_gate_allow_pending_includes_pending_but_never_rejected():
    records = [
        _video("V1", QAStatus.APPROVED),
        _video("V2", QAStatus.PENDING),
        _video("V3", QAStatus.REJECTED),
    ]
    eligible = qa_gate(records, allow_pending=True)
    assert {r.content_id for r in eligible} == {"V1", "V2"}


def test_default_allowed_qa_never_includes_rejected():
    assert QAStatus.REJECTED not in DEFAULT_ALLOWED_QA


# --- Metadata preservation ------------------------------------------------------

def test_build_chunk_metadata_includes_all_required_fields():
    record = _video("V1", QAStatus.APPROVED)
    metadata = build_chunk_metadata(record)
    for field in [
        "content_id", "content_type", "source_id", "source", "course",
        "topic", "lecture", "page", "start_time", "end_time",
        "processing_status", "qa_status",
    ]:
        assert field in metadata
    assert metadata["content_id"] == "V1"
    assert metadata["start_time"] == 10.0
    assert metadata["end_time"] == 20.0
    assert metadata["course"] == "Signals and Systems"


def test_chunk_video_record_preserves_timestamps_in_every_chunk():
    long_text = ("the sampling theorem states that " * 100).strip()
    record = _video("V1", QAStatus.APPROVED, text=long_text)
    documents = chunk_video_record(record)
    assert len(documents) > 1
    for doc in documents:
        assert doc.metadata["start_time"] == 10.0
        assert doc.metadata["end_time"] == 20.0
        assert doc.metadata["content_id"] == "V1"


def test_chunk_note_record_preserves_page_number_in_every_chunk():
    long_text = "\n\n".join(["section " + str(i) * 200 for i in range(5)])
    record = _note("N1", QAStatus.APPROVED, page=4, text=long_text)
    documents = chunk_note_record(record)
    assert len(documents) > 1
    for doc in documents:
        assert doc.metadata["page"] == 4
        assert doc.metadata["content_id"] == "N1"


# --- Semantic chunking ----------------------------------------------------------

def test_short_video_segment_is_a_single_chunk():
    record = _video("V1", QAStatus.APPROVED, text="short segment")
    documents = chunk_video_record(record)
    assert len(documents) == 1
    assert documents[0].page_content == "short segment"
    assert documents[0].metadata["chunk_id"] == "V1"


def test_note_chunks_split_on_paragraph_boundaries_not_mid_section():
    record = _note("N1", QAStatus.APPROVED, text="First paragraph.\n\nSecond paragraph.")
    documents = chunk_note_record(record)
    assert len(documents) == 2
    assert documents[0].page_content == "First paragraph."
    assert documents[1].page_content == "Second paragraph."


def test_chunk_record_dispatches_by_content_type():
    video_docs = chunk_record(_video("V1", QAStatus.APPROVED))
    note_docs = chunk_record(_note("N1", QAStatus.APPROVED))
    assert video_docs[0].metadata["content_type"] == "video_transcript"
    assert note_docs[0].metadata["content_type"] == "pdf_note"


# --- End-to-end build (fake embeddings, no network) ------------------------------

def test_build_knowledge_base_only_indexes_approved_content(tmp_path, fake_embeddings_patch):
    input_dir = tmp_path / "cleaned"
    write_jsonl(
        [_video("V1", QAStatus.APPROVED), _video("V2", QAStatus.PENDING)],
        input_dir / "transcripts" / "lecture_05.jsonl",
    )
    output_dir = tmp_path / "kb" / "vector_store"

    result = build_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    assert result["indexed_records"] == 1
    assert result["skipped_records"] == 1
    assert (output_dir / "index.faiss").exists()

    manifest = (output_dir.parent / "manifest.json")
    assert manifest.exists()


def test_build_knowledge_base_allow_pending_includes_pending(tmp_path, fake_embeddings_patch, capsys):
    input_dir = tmp_path / "cleaned"
    write_jsonl(
        [_video("V1", QAStatus.APPROVED), _video("V2", QAStatus.PENDING)],
        input_dir / "transcripts" / "lecture_05.jsonl",
    )
    output_dir = tmp_path / "kb" / "vector_store"

    result = build_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=True)

    assert result["indexed_records"] == 2
    assert "DEMO MODE" in capsys.readouterr().out


def test_build_knowledge_base_retrieved_documents_carry_full_metadata(tmp_path, fake_embeddings_patch):
    from langchain_community.vectorstores import FAISS
    import langchain_openai

    input_dir = tmp_path / "cleaned"
    write_jsonl([_video("V1", QAStatus.APPROVED)], input_dir / "transcripts" / "lecture_05.jsonl")
    output_dir = tmp_path / "kb" / "vector_store"

    build_knowledge_base(input_dir, output_dir, embedding_model="fake", allow_pending=False)

    vs = FAISS.load_local(str(output_dir), langchain_openai.OpenAIEmbeddings(model="fake"), allow_dangerous_deserialization=True)
    docs = vs.similarity_search("hello world", k=1)
    assert len(docs) == 1
    assert docs[0].metadata["content_id"] == "V1"
    assert docs[0].metadata["start_time"] == 10.0
    assert docs[0].metadata["qa_status"] == "approved"
