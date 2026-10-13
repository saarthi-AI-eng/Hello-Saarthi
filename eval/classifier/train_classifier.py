"""Train the Tier 1 / Tier 2 query classifier and export numpy-only weights.

    python eval/classifier/train_classifier.py

Embeds tier_train.jsonl + tier_test.jsonl with the deployment's embedding model
(src.utils.llm.embeddings — must be the same model the server uses), trains an
L2-regularised logistic regression on [normalised embedding ‖ cue features],
reports accuracy on the held-out 100-query test set against the rule-based
baseline, and writes src/orchestrator/models/tier_classifier.json.
Re-run whenever EMBEDDING_MODEL changes or new labelled queries are added.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "saarthi_backend" / ".env")
except Exception:
    pass

import numpy as np  # noqa: E402

HERE = Path(__file__).parent
OUT = ROOT / "src" / "orchestrator" / "models" / "tier_classifier.json"


def load(name):
    return [json.loads(line) for line in (HERE / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score

    from src.orchestrator.classifier import _heuristic
    from src.orchestrator.tier_features import CUE_NAMES, feature_vector
    from src.utils.llm import embedding_model_name, embeddings

    train, test = load("tier_train.jsonl"), load("tier_test.jsonl")
    emb = embeddings()
    t = time.time()
    tr_vecs = emb.embed_documents([i["query"] for i in train])
    te_vecs = emb.embed_documents([i["query"] for i in test])
    print(f"embedded {len(train) + len(test)} queries in {time.time() - t:.1f}s with {embedding_model_name()}")

    Xtr = np.stack([feature_vector(i["query"], v) for i, v in zip(train, tr_vecs)])
    ytr = np.array([1 if i["tier"] == 2 else 0 for i in train])
    Xte = np.stack([feature_vector(i["query"], v) for i, v in zip(test, te_vecs)])
    yte = np.array([1 if i["tier"] == 2 else 0 for i in test])

    best = None
    for C in (0.3, 1.0, 3.0, 10.0):
        cv = cross_val_score(LogisticRegression(C=C, max_iter=2000), Xtr, ytr, cv=5).mean()
        print(f"  C={C:<5} 5-fold CV accuracy on train: {cv:.3f}")
        if best is None or cv > best[1]:
            best = (C, cv)
    C = best[0]
    model = LogisticRegression(C=C, max_iter=2000).fit(Xtr, ytr)

    pred = model.predict(Xte)
    acc = float((pred == yte).mean())
    heur = np.array([1 if _heuristic(i["query"], None).tier == 2 else 0 for i in test])
    heur_acc = float((heur == yte).mean())
    emb_only = LogisticRegression(C=C, max_iter=2000).fit(Xtr[:, : -len(CUE_NAMES)], ytr)
    emb_acc = float((emb_only.predict(Xte[:, : -len(CUE_NAMES)]) == yte).mean())

    print(f"\nHELD-OUT 100-query test set (spec 3.2.1 gate: >= 0.90)")
    print(f"  rule-based heuristic      {heur_acc:.2f}")
    print(f"  embedding only (LR)       {emb_acc:.2f}")
    print(f"  embedding + cues (LR)     {acc:.2f}   <- exported")
    errors = [(i["query"], i["tier"]) for i, p, y in zip(test, pred, yte) if p != y]
    for q, tier in errors:
        print(f"    miss (want tier {tier}): {q}")

    t = time.perf_counter()
    for _ in range(1000):
        x = Xte[0]
        1.0 / (1.0 + np.exp(-(x @ model.coef_[0] + model.intercept_[0])))
    per_ms = (time.perf_counter() - t)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "version": 1,
        "trained_at": time.strftime("%Y-%m-%d %H:%M"),
        "embedding_model": embedding_model_name(),
        "dim": len(tr_vecs[0]),
        "cues": CUE_NAMES,
        "coef": [round(float(c), 6) for c in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
        "threshold": 0.5,
        "C": C,
        "metrics": {
            "train_items": len(train), "test_items": len(test), "cv_accuracy": round(best[1], 4),
            "test_accuracy": round(acc, 4), "heuristic_test_accuracy": round(heur_acc, 4),
            "embedding_only_test_accuracy": round(emb_acc, 4), "inference_ms": round(per_ms, 4),
        },
    }), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}  (inference {per_ms:.4f} ms per query, excluding the embedding)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
