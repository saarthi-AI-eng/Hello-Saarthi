"""
Shared plumbing for the content-management pipeline scripts: path
constants, a lightweight console logger, append-safe ingestion logging
(Phase 12), and the content fingerprint used for incremental KB updates
(Phase 11).

Deliberately dependency-free (stdlib only) so it can be imported by every
ingestion script regardless of which optional OCR/transcription extras are
installed.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_VIDEOS_DIR = DATA_DIR / "raw" / "videos"
RAW_NOTES_DIR = DATA_DIR / "raw" / "notes"
PROCESSED_TRANSCRIPTS_DIR = DATA_DIR / "processed" / "transcripts"
PROCESSED_OCR_DIR = DATA_DIR / "processed" / "ocr"
CLEANED_TRANSCRIPTS_DIR = DATA_DIR / "cleaned" / "transcripts"
CLEANED_OCR_DIR = DATA_DIR / "cleaned" / "ocr"
CATALOG_DIR = DATA_DIR / "catalog"
EVALUATION_DIR = DATA_DIR / "evaluation"
LOGS_DIR = REPO_ROOT / "logs"
INGESTION_LOG_PATH = LOGS_DIR / "ingestion_log.json"
KNOWLEDGE_BASE_DIR = REPO_ROOT / "knowledge_base"
UNIFIED_KB_DIR = KNOWLEDGE_BASE_DIR / "unified"


def get_logger(name: str) -> logging.Logger:
    """Console logger shared by every pipeline script (stdout, no secrets)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_operation(
    *,
    file: str,
    type_: str,
    operation: str,
    status: str,
    output: Optional[str] = None,
    error: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    log_path: Optional[Path] = None,
    **extra: Any,
) -> None:
    """Append one entry to the ingestion log (a JSON array on disk).

    Read-modify-write with an atomic rename; adequate for the sequential
    CLI usage this pipeline expects (not a concurrent-writer-safe queue).
    Never pass secrets (API keys, credentials) via `extra` or `error`.

    log_path defaults to the module-level INGESTION_LOG_PATH, resolved at
    call time (not at import time) so tests can redirect every caller's
    logging — including callers that never pass log_path explicitly — by
    monkeypatching scripts.content_common.INGESTION_LOG_PATH.
    """
    if log_path is None:
        log_path = INGESTION_LOG_PATH
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file": file,
        "type": type_,
        "operation": operation,
        "status": status,
        "duration_seconds": duration_seconds,
        "output": output,
        "error": error,
    }
    entry.update(extra)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if log_path.exists():
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, OSError):
            entries = []
    entries.append(entry)

    tmp_path = log_path.with_suffix(log_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(log_path)


def content_fingerprint(source: str, source_id: Optional[str], text: str, metadata: dict) -> str:
    """Deterministic fingerprint for a piece of content, used to detect NEW/CHANGED/UNCHANGED records."""
    payload = json.dumps(
        {"source": source, "source_id": source_id, "text": text, "metadata": metadata},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def iter_jsonl_files(*directories: Path):
    """Yield every .jsonl file under the given directories, sorted for determinism."""
    for directory in directories:
        if not directory.exists():
            continue
        yield from sorted(directory.glob("*.jsonl"))


def latest_log_status(filename: str, log_path: Path = INGESTION_LOG_PATH) -> Optional[str]:
    """Status ('success'/'failed') of the most recent ingestion_log.json entry for this filename."""
    if not log_path.exists():
        return None
    try:
        entries = json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    matches = [e for e in entries if isinstance(e, dict) and e.get("file") == filename]
    if not matches:
        return None
    return matches[-1].get("status")
