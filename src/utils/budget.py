"""LLM usage accounting + the cloud budget gate used by tiered routing (WBS 3.2.2).

AI does not own quota middleware (Product 1.2). It only *reads* a budget signal:

  DAILY_CLOUD_TOKEN_BUDGET   int; 0/unset = no daily cap on Tier 2 tokens
  CLOUD_BUDGET_FLAG_FILE     optional JSON written by Product, e.g.
                             {"remaining_tokens": 120000} or {"exhausted": true}

and records usage so Product/UX can plot tokens per tier (spec 9.4).
Usage is persisted per day in knowledge_base/cache/llm_usage.json.
Token counts from providers are used when present, else chars/4 estimates.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from contextvars import ContextVar
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_USAGE_FILE = _PROJECT_ROOT / "knowledge_base" / "cache" / "llm_usage.json"
_lock = threading.Lock()

# Per-request collector so traces can report the tokens one answer cost.
request_usage: ContextVar[list | None] = ContextVar("llm_request_usage", default=None)


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _load() -> dict:
    try:
        return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def record(tier: int, model: str, prompt_tokens: int, completion_tokens: int, estimated: bool = False) -> None:
    entry = {
        "tier": tier,
        "model": model,
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "estimated": estimated,
    }
    bucket = request_usage.get()
    if bucket is not None:
        bucket.append(entry)
    day = date.today().isoformat()
    with _lock:
        data = _load()
        d = data.setdefault(day, {})
        t = d.setdefault(f"tier{tier}", {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
        t["calls"] += 1
        t["prompt_tokens"] += entry["prompt_tokens"]
        t["completion_tokens"] += entry["completion_tokens"]
        # keep ~60 days
        for old in sorted(data)[:-60]:
            data.pop(old, None)
        try:
            _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _USAGE_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except Exception as e:
            logger.debug("usage write failed: %s", e)


def used_today(tier: int) -> int:
    t = _load().get(date.today().isoformat(), {}).get(f"tier{tier}", {})
    return int(t.get("prompt_tokens", 0)) + int(t.get("completion_tokens", 0))


def cloud_allowed() -> tuple[bool, str]:
    """Whether a Tier 2 (cloud / full model) call is within budget right now."""
    flag = os.environ.get("CLOUD_BUDGET_FLAG_FILE", "").strip()
    if flag:
        try:
            info = json.loads(Path(flag).read_text(encoding="utf-8"))
            if info.get("exhausted") or int(info.get("remaining_tokens", 1)) <= 0:
                return False, "product budget flag: exhausted"
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("Unreadable CLOUD_BUDGET_FLAG_FILE %s: %s", flag, e)
    cap = int(os.environ.get("DAILY_CLOUD_TOKEN_BUDGET", "0") or 0)
    if cap > 0 and used_today(2) >= cap:
        return False, f"daily cloud budget {cap} tokens used"
    return True, "ok"


def summary() -> dict:
    return _load().get(date.today().isoformat(), {})


# ── Per-user daily caps (spec §4.6) ──────────────────────────────────────────
# Enforcement and notification belong to Product's middleware; the AI router only
# *obeys* them: a student over the cap is served by Tier 1 for the rest of the day.
#   STUDENT_DAILY_TOKENS (default 20000), INSTRUCTOR_DAILY_TOKENS (default 50000)
#   PER_USER_CAPS=0 disables the check.

def _role_cap(role: str | None) -> int:
    if (role or "student") in ("teacher", "admin"):
        return int(os.environ.get("INSTRUCTOR_DAILY_TOKENS", "50000") or 0)
    return int(os.environ.get("STUDENT_DAILY_TOKENS", "20000") or 0)


def record_user(user_key: str | None, tokens: int) -> None:
    if not user_key or tokens <= 0:
        return
    day = date.today().isoformat()
    with _lock:
        data = _load()
        users = data.setdefault(day, {}).setdefault("users", {})
        users[user_key] = int(users.get(user_key, 0)) + int(tokens)
        try:
            _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _USAGE_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except Exception as e:
            logger.debug("usage write failed: %s", e)


def user_cap_status(user_key: str | None, role: str | None) -> dict:
    """{'used', 'cap', 'over', 'near'} — near = >= 80% of the cap (spec 1.2.1 alert)."""
    if os.environ.get("PER_USER_CAPS", "1").strip().lower() in ("0", "false", "no", "off") or not user_key:
        return {"used": 0, "cap": 0, "over": False, "near": False}
    cap = _role_cap(role)
    used = int(_load().get(date.today().isoformat(), {}).get("users", {}).get(user_key, 0))
    return {"used": used, "cap": cap, "over": bool(cap) and used >= cap, "near": bool(cap) and used >= 0.8 * cap}
