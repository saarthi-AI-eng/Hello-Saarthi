"""
Canonical content schema for the Saarthi Content Management / Data Ingestion pipeline.

Every ingestion stage (video transcription, notes OCR, cleaning, cataloging,
QA, and knowledge-base construction) reads and writes this single record
shape as JSONL. This keeps OCR, transcription, and KB construction
independent of one another: any stage can change its internals as long as
it still emits/consumes ContentRecord-shaped JSONL.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Union

from pydantic import BaseModel, Field, ValidationError


class ContentType(str, Enum):
    VIDEO_TRANSCRIPT = "video_transcript"
    HANDWRITTEN_NOTE = "handwritten_note"
    PDF_NOTE = "pdf_note"
    EXERCISE = "exercise"
    CODE = "code"
    SLIDE = "slide"


class ProcessingStatus(str, Enum):
    DISCOVERED = "discovered"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class QAStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ContentRecord(BaseModel):
    """Canonical, source-agnostic unit of ingested content."""

    content_id: str = Field(description="Stable unique id, e.g. 'VID_001_SEG_023' or 'NOTE_012_PAGE_04'.")
    content_type: ContentType
    course: Optional[str] = None
    topic: Optional[str] = None
    source: str = Field(description="Original file name/path this record was derived from.")
    source_id: Optional[str] = Field(default=None, description="Id of the parent source document/video (e.g. 'VID_001').")
    lecture: Optional[str] = None
    page: Optional[int] = Field(default=None, ge=1)
    start_time: Optional[float] = Field(default=None, ge=0)
    end_time: Optional[float] = Field(default=None, ge=0)
    text: str
    processing_status: ProcessingStatus = ProcessingStatus.DISCOVERED
    qa_status: QAStatus = QAStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": False}


def validate_record(data: dict) -> ContentRecord:
    """Parse and validate a raw dict into a ContentRecord. Raises pydantic.ValidationError on failure."""
    return ContentRecord(**data)


def record_to_dict(record: ContentRecord) -> dict:
    """Serialize a ContentRecord to a plain JSON-compatible dict."""
    return record.model_dump(mode="json")


def record_from_dict(data: dict) -> ContentRecord:
    """Alias of validate_record, kept for readability at call sites that already have a dict."""
    return validate_record(data)


def write_jsonl(records: Iterable[ContentRecord], path: Union[str, Path]) -> int:
    """Write records as JSONL (one JSON object per line). Returns the number of records written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record_to_dict(record), ensure_ascii=False))
            f.write("\n")
            count += 1
    return count


def read_jsonl(path: Union[str, Path], skip_invalid: bool = False) -> Iterator[ContentRecord]:
    """Read a JSONL file of canonical records, yielding validated ContentRecord objects.

    If skip_invalid is False (default), a malformed line raises ValidationError/JSONDecodeError.
    If True, malformed lines are skipped silently by the caller's own try/except is expected instead;
    this function simply surfaces the line number in the raised error for easier debugging.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                yield validate_record(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                if skip_invalid:
                    continue
                raise ValueError(f"{path}:{line_number}: invalid ContentRecord — {exc}") from exc
