from __future__ import annotations

import pytest

from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus
from src.content_qa.config import load_qa_config


@pytest.fixture
def qa_config():
    return load_qa_config()


def pdf_record(**overrides) -> ContentRecord:
    defaults = dict(
        content_id="NOTE_001_PAGE_01",
        content_type=ContentType.PDF_NOTE,
        source="note.pdf",
        source_id="NOTE_001",
        page=1,
        text="This is a perfectly normal, well-recognized page of lecture notes about signals and systems.",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={
            "ocr_engine": "paddleocr",
            "ocr_confidence": 0.95,
            "page_quality": "GOOD",
            "review_reasons": [],
            "math_equation_blocks": [],
        },
    )
    defaults.update(overrides)
    return ContentRecord(**defaults)


def video_record(**overrides) -> ContentRecord:
    defaults = dict(
        content_id="VID_001_SEG_001",
        content_type=ContentType.VIDEO_TRANSCRIPT,
        source="lecture.mp4",
        source_id="VID_001",
        start_time=0.0,
        end_time=4.0,
        text="Welcome back to this lecture on discrete Fourier transforms.",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={
            "transcription_provider": "local_whisper",
            "language": "en",
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
        },
    )
    defaults.update(overrides)
    return ContentRecord(**defaults)
