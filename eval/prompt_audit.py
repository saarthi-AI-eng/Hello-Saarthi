"""Prompt audit (WBS 3.3 / spec §10.1: "reduce average prompt length by 30%").

Measures the fixed instruction text the system sends on every call — system prompts,
router prompt, expert prompt, critic, follow-up rewrite, Socratic templates — in
estimated tokens (chars / 4). Retrieved excerpts and the student's question are not
counted: they vary per query and are bounded by top-n.

    python eval/prompt_audit.py --save-baseline   # once, before trimming
    python eval/prompt_audit.py                   # compare against the baseline
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
BASELINE = ROOT / "eval" / "prompt_audit_baseline.json"


def _tok(text: str) -> int:
    return max(1, len(text) // 4)


def _string_consts(fn) -> str:
    """Concatenate the string literals inside a function's source (system prompts written inline)."""
    src = inspect.getsource(fn)
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', src)
    return "".join(p for p in parts if len(p) > 25)


def collect() -> dict[str, int]:
    from saarthi_backend.ai import adapter
    from src.experts import mind
    from src.orchestrator import critique, followup
    from src.prompts.loader import PROMPTS
    from src.schemas.models import ExpertName
    from src.tools.kb_ops import get_expert_description

    out: dict[str, int] = {}
    from src.prompts import tutor as _tutor
    grounded = _tutor.grounded_system("Signals and Systems")
    # Prompts actually sent after the grounding rule: main chat + document/video viewer use the
    # grounded system prompt (the old _TUTOR_SYSTEM only survives in an unused fallback).
    out["tutor_system"] = _tok(grounded) if hasattr(_tutor, "grounded_system") else _tok(adapter._TUTOR_SYSTEM)
    descs = "\n".join(f"- {e.value}: {get_expert_description(e.value)}" for e in ExpertName)
    out["router_system"] = _tok(PROMPTS["orchestrator_system"].format(expert_descriptions=descs))
    out["expert_system"] = _tok(PROMPTS["expert_system"])
    out["mind_system"] = _tok(mind.MIND_SYSTEM_PROMPT)
    out["critic"] = _tok(_string_consts(critique.critic_node))
    out["followup_rewrite"] = _tok(_string_consts(followup.rewrite_followup))
    if hasattr(adapter, "_grounded_system_for_legacy"):
        out["document_chat_system"] = _tok(adapter._grounded_system_for_legacy())
        out["video_chat_system"] = _tok(adapter._grounded_system_for_legacy())
    else:
        out["document_chat_system"] = _tok(_string_consts(adapter.run_document_chat))
        out["video_chat_system"] = _tok(_string_consts(adapter.run_video_chat))
    try:
        from src.prompts.socratic_pack import HINT_TEMPLATE, REVEAL_TEMPLATE
        out["socratic_hint"] = _tok(HINT_TEMPLATE)
        out["socratic_reveal"] = _tok(REVEAL_TEMPLATE)
    except Exception:
        pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-baseline", action="store_true")
    args = ap.parse_args()
    now = collect()
    if args.save_baseline:
        BASELINE.write_text(json.dumps(now, indent=1), encoding="utf-8")
        print(f"baseline saved: {sum(now.values())} tokens across {len(now)} prompts")
        for k, v in now.items():
            print(f"  {k:24} {v}")
        return
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    keys = sorted(set(base) | set(now))
    print(f"{'prompt':26}{'baseline':>10}{'now':>8}{'change':>9}")
    for k in keys:
        b, n = base.get(k), now.get(k)
        ch = f"{(n - b) / b:+.0%}" if b and n else ("new" if n else "removed")
        print(f"{k:26}{b if b is not None else '-':>10}{n if n is not None else '-':>8}{ch:>9}")
    # The spec's metric: average length of the prompts actually sent per answer.
    common = [k for k in base if k in now]
    if common:
        b = sum(base[k] for k in common) / len(common)
        n = sum(now[k] for k in common) / len(common)
        print(f"\naverage over {len(common)} prompts present in both: {b:.0f} -> {n:.0f} tokens ({(n - b) / b:+.0%}); target -30%")


if __name__ == "__main__":
    main()
