"""Unattended AI evaluation (WBS 3.6 / 5.1, B3) — run from the repo root:

    python eval/run_eval.py                 # retrieval, citation, isolation, classifier
    python eval/run_eval.py --with-router   # + routing accuracy (calls the router LLM)
    python eval/run_eval.py --strict        # exit 1 if a gate below fails (CI)
    python eval/run_eval.py --reviewed-only # score only items a human has reviewed
    python eval/run_eval.py --classifier-set   # + 100-query held-out tier set via the deployed classifier
    python eval/run_eval.py --ablation         # + dense vs BM25 vs fused (spec 3.1.1) and reranker A/B (3.1.2)

Gold file: eval/gold.jsonl (one JSON object per line):
    category  citation | isolation | retrieval | classifier | routing
    status    auto (objective label) | draft (needs educator/Product review) | reviewed
    query, scope {course_id, material_title, video_id}, expected {...}

Metrics
    hit@3 / precision@3 / MRR   relevant = expected material AND an expected keyword
    did_search                  retrieve() returned at least one chunk
    citation regression         unique marker in top-3 AND a citable source attached
    isolation                   course-scoped search never returns another course's chunk
                                nor a forbidden marker ("course_id never opens shared textbooks")
    classifier / routing        exact label match

Gates (--strict): citation 100%, isolation 100%, hit@3 >= 0.8, classifier >= 0.8,
routing >= 0.7. These are AI regression gates, not the spec 1.5 KPIs — do not
report the 90% KPI until the gold file has reviewed labels (B2 / B5).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "saarthi_backend" / ".env")
except Exception:
    pass

GATES = {"citation": 1.0, "isolation": 1.0, "hit@3": 0.8, "classifier": 0.8, "routing": 0.7,
         "grounding": 1.0, "tier_classifier_100": 0.9}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower().replace(" ", "_")


def _material_ok(chunk, materials: list[str]) -> bool:
    if not materials:
        return True
    names = {_norm(chunk.title), _norm(chunk.source_file)}
    return any(_norm(m) in names for m in materials)


def _relevant(chunk, exp: dict) -> bool:
    kws = [k.lower() for k in exp.get("keywords", [])]
    text = (chunk.text or "").lower()
    return _material_ok(chunk, exp.get("materials", [])) and (not kws or any(k in text for k in kws))


def eval_retrieval(item: dict) -> dict:
    from saarthi_backend.ai.adapter import citations_from_chunks
    from src.tools.retrieve import last_trace, retrieve

    sc, exp = item.get("scope", {}), item["expected"]
    t = time.perf_counter()
    chunks = retrieve(
        item["query"], course_id=sc.get("course_id"), material_title=sc.get("material_title"),
        video_id=sc.get("video_id"), k=3,
    )[:3]
    ms = (time.perf_counter() - t) * 1000
    rel = [_relevant(c, exp) for c in chunks]
    first = next((i for i, r in enumerate(rel) if r), None)
    out = {
        "did_search": bool(chunks),
        "hit@3": first is not None,
        "precision@3": (sum(rel) / len(chunks)) if chunks else 0.0,
        "rr": (1.0 / (first + 1)) if first is not None else 0.0,
        "latency_ms": round(ms, 1),
        "legs": [tr.get("legs") for tr in (last_trace.get() or [])],
        "top": [{"title": c.title, "via": c.via, "relevant": r, "text": c.text[:90]} for c, r in zip(chunks, rel)],
    }
    if item["category"] == "citation":
        marker = exp.get("marker")
        cites = citations_from_chunks(chunks)
        out["marker_found"] = any(marker in (c.text or "") for c in chunks) if marker else True
        out["citable"] = bool(cites) and all(c.get("source_file") for c in cites)
        out["pass"] = out["marker_found"] and out["citable"]
    return out


def eval_isolation(item: dict) -> dict:
    from src.tools.retrieve import retrieve

    sc, exp = item.get("scope", {}), item["expected"]
    chunks = retrieve(item["query"], course_id=sc.get("course_id"), k=5)
    want = exp.get("course_id")
    wrong_course = [c.course_id for c in chunks if c.course_id is not None and want is not None and int(c.course_id) != int(want)]
    forbidden = exp.get("forbidden_marker")
    leaked = bool(forbidden) and any(forbidden.lower() in (c.text or "").lower() for c in chunks)
    return {"pass": not wrong_course and not leaked, "returned": len(chunks), "wrong_course": wrong_course, "leaked_marker": leaked}


def eval_classifier(item: dict) -> dict:
    from src.orchestrator.classifier import classify

    qc = classify(item["query"])
    exp = item["expected"]
    ok = qc.kind == exp.get("kind", qc.kind) and qc.tier == exp.get("tier", qc.tier)
    return {"pass": ok, "got": {"kind": qc.kind, "tier": qc.tier}, "want": exp}


def eval_routing(item: dict) -> dict:
    from src.orchestrator.router import decompose_and_route

    t = time.perf_counter()
    try:
        plan = decompose_and_route(item["query"], [])
        got = plan.sub_queries[0].expert.value if plan.sub_queries else None
    except Exception as e:
        got = f"error: {e}"
    exp = item["expected"]
    ok = got in exp.get("expert", []) and got not in exp.get("forbidden_expert", [])
    return {"pass": ok, "got": got, "want": exp.get("expert"), "latency_ms": round((time.perf_counter() - t) * 1000)}


def eval_classifier_set() -> dict:
    """Spec 3.2.1: >= 90% correct tier on a 100-query labelled set, < 50 ms."""
    from src.orchestrator.query_classifier import classify_query

    path = ROOT / "eval" / "classifier" / "tier_test.jsonl"
    items = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    correct, ms, total_ms, sources, misses = 0, [], [], defaultdict(int), []
    for it in items:
        t = time.perf_counter()
        d = classify_query(it["query"])
        total_ms.append((time.perf_counter() - t) * 1000)
        ms.append(d.classify_ms)
        sources[d.source] += 1
        if d.tier == it["tier"]:
            correct += 1
        else:
            misses.append({"query": it["query"], "want": it["tier"], "got": d.tier, "source": d.source})
    ms.sort()
    total_ms.sort()
    return {
        "n": len(items), "accuracy": round(correct / len(items), 4),
        "classify_ms_p95": round(ms[int(0.95 * (len(ms) - 1))], 3),
        "with_embedding_ms_median": round(total_ms[len(total_ms) // 2], 1),
        "with_embedding_ms_p95": round(total_ms[int(0.95 * (len(total_ms) - 1))], 1),
        "sources": dict(sources), "misses": misses,
    }


def eval_grounding_set() -> dict:
    """Grounding rule (DEC-1): in-course questions are covered, off-syllabus ones get NOT_COVERED."""
    from src.tools.grounding import ground

    path = ROOT / "eval" / "grounding_test.jsonl"
    items = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for it in items:
        g = ground(it["query"], course_id=it["scope"].get("course_id"), n=3)
        rows.append({"id": it["id"], "want": it["covered"], "got": g.covered, "terms": g.overlap_terms,
                     "pass": g.covered == it["covered"]})
    return {"n": len(rows), "accuracy": round(sum(r["pass"] for r in rows) / len(rows), 4), "rows": rows}


def eval_ablation(items: list[dict]) -> dict:
    """Spec 3.1.1: fused list beats either leg alone on precision@5. 3.1.2: reranker lift on precision@3."""
    from src.retrieval import rerankers, store
    from src.tools.retrieve import retrieve

    ret = [i for i in items if i["category"] in ("citation", "retrieval")]

    def run(legs: str, rerank: bool = False, k: int = 5) -> dict:
        os.environ["RETRIEVAL_LEGS"] = legs
        os.environ["RETRIEVAL_RERANK"] = "1" if rerank else "0"
        p_at, hits, status = [], [], None
        for it in ret:
            sc, exp = it.get("scope", {}), it["expected"]
            chunks = retrieve(it["query"], course_id=sc.get("course_id"), material_title=sc.get("material_title"), k=k)[:k]
            rel = [_relevant(c, exp) for c in chunks]
            p_at.append(sum(rel) / k)
            hits.append(any(rel[:3]))
        if rerank:
            _, status = rerankers.cross_encoder_order("probe", ["a", "b"])
        return {"precision@%d" % k: round(sum(p_at) / len(p_at), 4), "hit@3": round(sum(hits) / len(hits), 4),
                **({"reranker": status} if rerank else {})}

    try:
        out = {
            "dense_only": run("dense"),
            "bm25_only": run("bm25"),
            "fused_rrf": run("dense,bm25"),
            "fused_rrf_p@3": run("dense,bm25", k=3),
            "fused_rrf_rerank_p@3": run("dense,bm25", rerank=True, k=3),
        }
    finally:
        os.environ.pop("RETRIEVAL_LEGS", None)
        os.environ.pop("RETRIEVAL_RERANK", None)
    f, d, b = out["fused_rrf"]["precision@5"], out["dense_only"]["precision@5"], out["bm25_only"]["precision@5"]
    out["fused_beats_each_leg_p@5"] = f > d and f > b
    rr = out["fused_rrf_rerank_p@3"]
    out["reranker_lift_p@3"] = (None if rr.get("reranker") != "ok" else
                               round(rr["precision@3"] - out["fused_rrf_p@3"]["precision@3"], 4))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(ROOT / "eval" / "gold.jsonl"))
    ap.add_argument("--with-router", action="store_true", help="also score routing (LLM calls)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a gate fails")
    ap.add_argument("--reviewed-only", action="store_true", help="skip items with status=draft")
    ap.add_argument("--out", default=str(ROOT / "eval" / "reports"))
    ap.add_argument("--classifier-set", action="store_true", help="score the 100-query tier test set")
    ap.add_argument("--ablation", action="store_true", help="retrieval A/B: dense vs BM25 vs fused, reranker lift")
    args = ap.parse_args()

    # Eval LLM calls must not count against students' daily usage / the cloud budget.
    from src.utils import budget as _budget
    Path(args.out).mkdir(parents=True, exist_ok=True)
    _budget._USAGE_FILE = Path(args.out) / "llm_usage_eval.json"

    items = [json.loads(line) for line in Path(args.gold).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.reviewed_only:
        items = [i for i in items if i.get("status") in ("auto", "reviewed")]

    results, agg = [], defaultdict(list)
    for item in items:
        cat = item["category"]
        if cat == "routing" and not args.with_router:
            continue
        try:
            if cat in ("citation", "retrieval"):
                r = eval_retrieval(item)
                agg["did_search"].append(r["did_search"])
                agg["hit@3"].append(r["hit@3"])
                agg["precision@3"].append(r["precision@3"])
                agg["mrr"].append(r["rr"])
                agg["retrieval_latency_ms"].append(r["latency_ms"])
                if cat == "citation":
                    agg["citation"].append(r["pass"])
            elif cat == "isolation":
                r = eval_isolation(item)
                agg["isolation"].append(r["pass"])
            elif cat == "classifier":
                r = eval_classifier(item)
                agg["classifier"].append(r["pass"])
            elif cat == "routing":
                r = eval_routing(item)
                agg["routing"].append(r["pass"])
            else:
                continue
        except Exception as e:
            r = {"pass": False, "error": str(e)}
            agg[cat].append(False)
        results.append({"id": item["id"], "category": cat, "status": item.get("status"), **r})
        flag = r.get("pass", r.get("hit@3"))
        print(f"{'PASS' if flag else 'FAIL'}  {item['id']:8} {cat:10} {item['query'][:70]}", flush=True)

    summary = {k: round(sum(map(float, v)) / len(v), 4) for k, v in agg.items() if v}
    summary["n_items"] = len(results)
    extra: dict = {}
    g = eval_grounding_set()
    summary["grounding"] = g["accuracy"]
    extra["grounding"] = g
    print(f"grounding gate: {g['accuracy']:.2f} on {g['n']} in/off-syllabus questions", flush=True)
    if args.classifier_set:
        c = eval_classifier_set()
        summary["tier_classifier_100"] = c["accuracy"]
        summary["tier_classifier_ms_p95"] = c["classify_ms_p95"]
        summary["tier_classifier_with_embedding_ms_median"] = c["with_embedding_ms_median"]
        extra["classifier_set"] = c
        print(f"tier classifier: {c['accuracy']:.2f} on {c['n']} queries; {c['classify_ms_p95']} ms p95 "
              f"(+embedding median {c['with_embedding_ms_median']} ms)", flush=True)
    if args.ablation:
        a = eval_ablation(items)
        extra["ablation"] = a
        summary["fused_beats_each_leg_p@5"] = a["fused_beats_each_leg_p@5"]
        print("ablation:", json.dumps({k: v for k, v in a.items()}), flush=True)
    gates = {k: {"value": summary.get(k), "min": v, "ok": summary.get(k) is None or summary[k] >= v} for k, v in GATES.items()}

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"timestamp": stamp, "summary": summary, "gates": gates, "results": results, **extra}
    (out_dir / f"{stamp}.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    md = ["# Saarthi AI eval " + stamp, "", "| metric | value | gate |", "|---|---|---|"]
    for k, v in summary.items():
        gate = gates.get(k)
        md.append(f"| {k} | {v} | {'≥ ' + str(gate['min']) + (' ✅' if gate['ok'] else ' ❌') if gate else ''} |")
    md += ["", "Failures:", ""] + [f"- {r['id']} ({r['category']}): {json.dumps({k: r[k] for k in r if k not in ('id', 'category', 'top')}, default=str)[:300]}"
                                  for r in results if not r.get("pass", r.get("hit@3", True))]
    (out_dir / f"{stamp}.md").write_text("\n".join(md), encoding="utf-8")

    print("\nSUMMARY", json.dumps(summary, indent=1))
    print("GATES  ", json.dumps({k: g["ok"] for k, g in gates.items()}))
    print(f"report: eval/reports/{stamp}.md")
    if args.strict and not all(g["ok"] for g in gates.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
