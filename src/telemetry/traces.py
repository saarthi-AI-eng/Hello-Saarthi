"""Per-answer traces for the researcher dashboard (WBS 4.3 / 9.x, spec 9.4).

AI emits; Product/UX plot. One JSON line per answered turn in
knowledge_base/traces/YYYY-MM-DD.jsonl:

    ts, path (stream|message), scope, class (kind/complexity), tier, model,
    cache {hit, similarity}, socratic stage, expert/plan, cite_ids,
    retrieval legs, critic_ok, tokens {prompt, completion, estimated},
    latency_ms, user (salted hash, never the raw id), query (unless disabled)

TRACES=0 disables writing. TRACE_QUERY_TEXT=0 drops the raw question text.
These files are also the export for any later fine-tuning (B4: "SFT on traces").
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACE_DIR = _PROJECT_ROOT / "knowledge_base" / "traces"
_lock = threading.Lock()


def _enabled() -> bool:
    return os.environ.get("TRACES", "1").strip().lower() not in ("0", "false", "no", "off")


def hash_user(user_id) -> str | None:
    if user_id is None:
        return None
    salt = os.environ.get("TRACE_SALT") or os.environ.get("JWT_SECRET", "saarthi")
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


def summarize_usage(usage: list[dict] | None) -> dict:
    usage = usage or []
    return {
        "calls": len(usage),
        "prompt": sum(u.get("prompt_tokens", 0) for u in usage),
        "completion": sum(u.get("completion_tokens", 0) for u in usage),
        "estimated": any(u.get("estimated") for u in usage),
        "by_tier": {
            str(t): sum(u.get("prompt_tokens", 0) + u.get("completion_tokens", 0) for u in usage if u.get("tier") == t)
            for t in sorted({u.get("tier") for u in usage if u.get("tier") is not None})
        },
    }


def write_trace(record: dict) -> None:
    if not _enabled():
        return
    rec = {"ts": round(time.time(), 3), **record}
    if os.environ.get("TRACE_QUERY_TEXT", "1").strip().lower() in ("0", "false", "no", "off"):
        rec.pop("query", None)
    try:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(rec, default=str, ensure_ascii=False)
        with _lock, open(TRACE_DIR / f"{date.today().isoformat()}.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logger.debug("trace write failed: %s", e)
