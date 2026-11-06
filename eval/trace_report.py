"""Summarise knowledge_base/traces/*.jsonl for Product / the researcher dashboard (spec 9.4).

    python eval/trace_report.py                # all days
    python eval/trace_report.py --days 14      # last 14 trace files
    python eval/trace_report.py --json         # machine-readable

Reports: turns, semantic-cache hit rate (Product target >= 30% after 2 weeks),
tier mix, tokens per turn and per conversation, share of answers with citations,
Socratic stage mix, critic FAIL rate, p50/p95 latency. AI emits; UX plots.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

TRACE_DIR = Path(__file__).resolve().parents[1] / "knowledge_base" / "traces"


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def summarise_feedback(feedback: list[dict]) -> dict:
    up = sum(1 for f in feedback if f.get("rating") == "up")
    down = sum(1 for f in feedback if f.get("rating") == "down")
    n = up + down
    return {
        "ratings": n, "up": up, "down": down,
        "net_satisfaction": round((up - down) / n, 4) if n else None,   # spec 9.5: % positive - % negative
        "cache_evictions": sum(int(f.get("cache_evicted") or 0) for f in feedback),
    }


def summarise(records: list[dict]) -> dict:
    feedback = [r for r in records if r.get("type") == "feedback"]
    records = [r for r in records if r.get("type") != "feedback"]
    n = len(records)
    if not n:
        return {"turns": 0, "feedback": summarise_feedback(feedback)}
    hits = sum(1 for r in records if (r.get("cache") or {}).get("hit"))
    cacheable = sum(1 for r in records if r.get("cacheable"))
    tokens = [((r.get("tokens") or {}).get("prompt", 0) + (r.get("tokens") or {}).get("completion", 0)) for r in records]
    per_conv: dict = defaultdict(int)
    for r, t in zip(records, tokens):
        if r.get("conversation"):
            per_conv[r["conversation"]] += t
    critic = [r.get("critic_ok") for r in records if r.get("critic_ok") is not None]
    lat = [r["latency_ms"] for r in records if isinstance(r.get("latency_ms"), (int, float))]
    return {
        "turns": n,
        "cache": {
            "hits": hits,
            "hit_rate_all_turns": round(hits / n, 4),
            "hit_rate_cacheable_turns": round(hits / cacheable, 4) if cacheable else None,
        },
        "tier_mix": dict(Counter(str(r.get("tier")) for r in records)),
        "class_mix": dict(Counter((r.get("class") or {}).get("kind") for r in records)),
        "socratic_mix": dict(Counter((r.get("socratic") or {}).get("stage") for r in records)),
        "tokens": {
            "mean_per_turn": round(statistics.mean(tokens), 1),
            "mean_per_conversation": round(statistics.mean(per_conv.values()), 1) if per_conv else None,
            "estimated_share": round(sum(1 for r in records if (r.get("tokens") or {}).get("estimated")) / n, 4),
        },
        "answers_with_citations": round(sum(1 for r in records if (r.get("n_citations") or 0) > 0 or r.get("cite_ids")) / n, 4),
        "critic_fail_rate": round(sum(1 for c in critic if c is False) / len(critic), 4) if critic else None,
        "latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95)},
        "models": dict(Counter(r.get("model") for r in records if r.get("model"))),
        "reply_modes": dict(Counter(r.get("reply_mode") for r in records if r.get("reply_mode"))),
        "low_confidence_rate": round(sum(1 for r in records if r.get("confidence") == "low") / n, 4),
        "classifier_sources": dict(Counter((r.get("classifier") or {}).get("source") for r in records if r.get("classifier"))),
        "feedback": summarise_feedback(feedback),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0)
    ap.add_argument("--dir", default=str(TRACE_DIR))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    files = sorted(Path(args.dir).glob("*.jsonl"))
    if args.days:
        files = files[-args.days:]
    records = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    summary = {"files": [f.name for f in files], **summarise(records)}
    if args.json:
        print(json.dumps(summary, indent=1))
        return
    print(f"Traces: {len(files)} file(s), {summary['turns']} turns")
    for k, v in summary.items():
        if k not in ("files", "turns"):
            print(f"  {k:24} {v}")


if __name__ == "__main__":
    main()
