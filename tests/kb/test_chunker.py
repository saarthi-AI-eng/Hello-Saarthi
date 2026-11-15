from __future__ import annotations

from src.knowledge_base.chunker import (
    build_chunks,
    chunk_documents,
    count_tokens,
    semantic_merge_boundaries,
    stable_chunk_id,
    structural_segment,
)
from src.knowledge_base.config import KBConfig
from src.knowledge_base.schema import NormalizedDoc


def _doc(**overrides):
    base = dict(
        doc_id="D1", source_id="S1", source_type="pdf_note", source_file="f.pdf",
        course="DSP", topic=None, lecture=None, page=1, start_time=None, end_time=None,
        text="Paragraph one.\n\nParagraph two.", qa_status="approved",
    )
    base.update(overrides)
    return NormalizedDoc(**base)


def test_structural_segment_splits_on_blank_line_paragraphs():
    units = structural_segment([_doc()], KBConfig(data_root="/tmp/x"))

    assert [u.text for u in units] == ["Paragraph one.", "Paragraph two."]


def test_stable_chunk_id_is_deterministic_and_content_sensitive():
    id_a = stable_chunk_id("S1", 1, "hash1", "1.0")
    id_b = stable_chunk_id("S1", 1, "hash1", "1.0")
    id_c = stable_chunk_id("S1", 1, "hash2", "1.0")

    assert id_a == id_b  # same inputs -> same id, every time
    assert id_a != id_c  # different content -> different id


def test_video_segments_merge_when_close_and_stay_separate_when_far():
    config = KBConfig(data_root="/tmp/x", video_segment_merge_gap_seconds=2.0)
    close = _doc(doc_id="V1", source_type="video_transcript", text="Hello", start_time=0.0, end_time=5.0)
    adjacent = _doc(doc_id="V2", source_type="video_transcript", text="world", start_time=6.0, end_time=10.0)
    far = _doc(doc_id="V3", source_type="video_transcript", text="later", start_time=50.0, end_time=55.0)

    units = structural_segment([close, adjacent, far], config)

    assert len(units) == 2
    assert units[0].text == "Hello world"
    assert units[0].doc.start_time == 0.0
    assert units[0].doc.end_time == 10.0  # preserves first-start/last-end of the merged run
    assert units[1].text == "later"


def test_equation_bearing_unit_is_not_split_even_if_large():
    config = KBConfig(data_root="/tmp/x", chunk_max_tokens=10, chunk_target_tokens=10, chunk_min_tokens=1)
    long_text = "equation term " * 50  # far more than 10 tokens
    doc = _doc(text=long_text, math_equation_blocks=[{"text": "x^2", "review_required": True}])
    units = structural_segment([doc], config)
    boundaries = [True] * len(units)

    chunks = build_chunks(units, boundaries, config)

    assert len(chunks) == 1
    assert chunks[0].has_equation is True
    assert chunks[0].text == long_text.strip()


def test_oversized_non_equation_unit_is_split_with_overlap():
    config = KBConfig(data_root="/tmp/x", chunk_max_tokens=10, chunk_target_tokens=10, chunk_overlap_tokens=3, chunk_min_tokens=1)
    long_text = " ".join(f"word{i}" for i in range(60))
    doc = _doc(text=long_text)
    units = structural_segment([doc], config)
    boundaries = [True] * len(units)

    chunks = build_chunks(units, boundaries, config)

    assert len(chunks) > 1
    assert all(c.token_count <= config.chunk_max_tokens + 5 for c in chunks)  # tiktoken round-tripping tolerance


def test_small_units_merge_up_to_target_size():
    config = KBConfig(data_root="/tmp/x", chunk_target_tokens=50, chunk_min_tokens=5, chunk_max_tokens=900)
    doc = _doc(text="Short one.\n\nShort two.\n\nShort three.")
    units = structural_segment([doc], config)
    boundaries = [False, False, True]  # no semantic boundaries forcing an early split

    chunks = build_chunks(units, boundaries, config)

    assert len(chunks) == 1  # all three merge into one chunk, well under target
    assert "Short one." in chunks[0].text and "Short three." in chunks[0].text


def test_ocr_review_flag_propagates_from_source_doc():
    config = KBConfig(data_root="/tmp/x")
    doc = _doc(text="Garbled text", ocr_quality="POOR_EXTRACTION", review_reasons=["NEAR_EMPTY_OUTPUT"])

    chunks = chunk_documents([doc], config)

    assert chunks[0].ocr_review_flagged is True


def test_semantic_merge_boundaries_returns_all_true_when_disabled():
    config = KBConfig(data_root="/tmp/x", semantic_boundary_detection=False)
    units = structural_segment([_doc()], config)

    boundaries = semantic_merge_boundaries(units, config, embed_fn=None)

    assert boundaries == [True, True]


def test_count_tokens_is_nonzero_for_real_text():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0
