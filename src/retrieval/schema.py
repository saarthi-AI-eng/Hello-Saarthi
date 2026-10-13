"""Frozen chunk metadata contract (WBS B2: "agree the Chunk metadata fields so
retrieve() does not change").

Every chunk written by any ingestion path (teacher upload, video transcript,
admin KB, future Whisper / MATLAB / exercise parsers owned by Data) carries:

    schema_version  int   CHUNK_SCHEMA_VERSION
    content_type    str   notes | books | video | course_material | exercise | code
    source          str   normalised file/video tag (lowercase, underscores)
    language        str   ISO-639-1 guess: en | hi | te | ta | ...
    course_id       int?  set for course materials
    material_id     int?  set for course materials
    material_title  str?  human title of the material
    page            int?  1-based page / slide number (documents)
    video_id        int?  set for lecture videos
    video_title     str?
    start_sec       int?  transcript window start (videos)
    end_sec         int?  transcript window end (videos)
    chunk_index     int   position inside the source

Readers must tolerate missing optional keys: indexes built before version 1
have no schema_version / language / content_type.
"""
from __future__ import annotations

CHUNK_SCHEMA_VERSION = 1

FIELDS = (
    "schema_version", "content_type", "source", "language",
    "course_id", "material_id", "material_title", "page",
    "video_id", "video_title", "start_sec", "end_sec", "chunk_index",
)

_SCRIPT_RANGES = (
    ("hi", 0x0900, 0x097F),  # Devanagari
    ("bn", 0x0980, 0x09FF),
    ("ta", 0x0B80, 0x0BFF),
    ("te", 0x0C00, 0x0C7F),
    ("kn", 0x0C80, 0x0CFF),
    ("ml", 0x0D00, 0x0D7F),
)


def detect_language(text: str) -> str:
    """Cheap script-based guess; English unless a non-Latin Indic script dominates."""
    counts: dict[str, int] = {}
    letters = 0
    for ch in text[:4000]:
        if not ch.isalpha():
            continue
        letters += 1
        cp = ord(ch)
        for lang, lo, hi in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if letters and counts:
        lang, n = max(counts.items(), key=lambda kv: kv[1])
        if n / letters > 0.3:
            return lang
    return "en"


def chunk_metadata(content_type: str, text: str, **fields) -> dict:
    """Build a metadata dict that follows the frozen contract."""
    md = {
        "schema_version": CHUNK_SCHEMA_VERSION,
        "content_type": content_type,
        "language": detect_language(text),
    }
    for key, value in fields.items():
        if key not in FIELDS:
            raise KeyError(f"'{key}' is not part of the frozen chunk metadata contract")
        md[key] = value
    return md
