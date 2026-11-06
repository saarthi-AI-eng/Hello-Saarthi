"""
Measure retrieval quality against a hand-written golden question set.
Never claims an accuracy number that wasn't actually measured.

Usage:
    python -m scripts.evaluate_retrieval
    python -m scripts.evaluate_retrieval --questions data/evaluation/golden_questions.jsonl --k 5
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Optional

from scripts.build_knowledge_base import DEFAULT_EMBEDDING_MODEL
from scripts.content_common import EVALUATION_DIR, UNIFIED_KB_DIR, get_logger

logger = get_logger("evaluate_retrieval")


def load_golden_questions(path: Path) -> List[dict]:
    questions = []
    with open(path, "r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(f"{path.name}:{line_number}: skipping malformed line — {exc}")
    return questions


def load_vector_store(index_dir: Path, embedding_model: str):
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    if not (index_dir / "index.faiss").exists():
        raise FileNotFoundError(f"No FAISS index found at {index_dir}. Run scripts.build_knowledge_base first.")

    manifest_path = index_dir.parent / "manifest.json"
    model = embedding_model
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            model = manifest.get("embedding_model", embedding_model)
        except (json.JSONDecodeError, OSError):
            pass

    embeddings = OpenAIEmbeddings(model=model)
    return FAISS.load_local(str(index_dir), embeddings, allow_dangerous_deserialization=True)


def evaluate(questions: List[dict], vector_store: Any, k: int = 5) -> dict:
    total = len(questions)
    top1 = top3 = top5 = topic_correct = content_type_correct = missing = 0
    per_question_results = []

    for q in questions:
        docs = vector_store.similarity_search(q["question"], k=k)
        if not docs:
            missing += 1
            per_question_results.append({"question": q["question"], "matched": False})
            continue

        source_ids = [d.metadata.get("source_id") for d in docs]
        expected_source = q.get("expected_source_id")
        hit1 = expected_source is not None and expected_source in source_ids[:1]
        hit3 = expected_source is not None and expected_source in source_ids[:3]
        hit5 = expected_source is not None and expected_source in source_ids[:5]
        top1 += int(hit1)
        top3 += int(hit3)
        top5 += int(hit5)

        top_doc = docs[0]
        topic_ok = q.get("expected_topic") is not None and top_doc.metadata.get("topic") == q["expected_topic"]
        content_type_ok = (
            q.get("expected_content_type") is not None
            and top_doc.metadata.get("content_type") == q["expected_content_type"]
        )
        topic_correct += int(topic_ok)
        content_type_correct += int(content_type_ok)

        per_question_results.append(
            {
                "question": q["question"],
                "matched": True,
                "top1_hit": hit1,
                "top3_hit": hit3,
                "top5_hit": hit5,
                "topic_correct": topic_ok,
                "content_type_correct": content_type_ok,
                "top_result_source_id": source_ids[0] if source_ids else None,
            }
        )

    def pct(count: int) -> float:
        return round(100.0 * count / total, 2) if total else 0.0

    return {
        "questions": total,
        "top1_source_accuracy": pct(top1),
        "top3_source_accuracy": pct(top3),
        "top5_source_accuracy": pct(top5),
        "topic_accuracy": pct(topic_correct),
        "content_type_accuracy": pct(content_type_correct),
        "missing_content_rate": pct(missing),
        "results": per_question_results,
    }


def print_report(report: dict) -> None:
    print()
    print("RETRIEVAL EVALUATION")
    print("--------------------")
    print(f"Questions: {report['questions']}")
    print(f"Top-1 source accuracy: {report['top1_source_accuracy']}%")
    print(f"Top-3 source accuracy: {report['top3_source_accuracy']}%")
    print(f"Top-5 source accuracy: {report['top5_source_accuracy']}%")
    print(f"Topic accuracy: {report['topic_accuracy']}%")
    print(f"Missing-content rate: {report['missing_content_rate']}%")
    print()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality against golden questions.")
    parser.add_argument("--questions", type=Path, default=EVALUATION_DIR / "golden_questions.jsonl")
    parser.add_argument("--index", type=Path, default=UNIFIED_KB_DIR / "vector_store")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=EVALUATION_DIR / "evaluation_results.json")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not args.questions.exists():
        logger.error(f"Golden question set not found: {args.questions}")
        return 1
    questions = load_golden_questions(args.questions)
    if not questions:
        logger.warning("No golden questions found — nothing to evaluate.")
        return 0

    try:
        vector_store = load_vector_store(args.index, args.embedding_model)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    report = evaluate(questions, vector_store, k=args.k)
    print_report(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
