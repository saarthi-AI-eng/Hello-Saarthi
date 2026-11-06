"""
Incrementally update the unified knowledge base: only re-embed content
that is NEW or CHANGED since the last run, detected via a deterministic
content fingerprint (not file mtime).

Usage:
    python -m scripts.update_knowledge_base
    python -m scripts.update_knowledge_base --allow-pending
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from scripts.build_knowledge_base import (
    DEFAULT_EMBEDDING_MODEL,
    build_chunk_metadata,
    chunk_record,
    load_cleaned_records,
    qa_gate,
)
from scripts.content_common import DATA_DIR, UNIFIED_KB_DIR, content_fingerprint, get_logger, log_operation
from scripts.schemas import ContentRecord

logger = get_logger("update_knowledge_base")

FINGERPRINTS_FILENAME = "fingerprints.json"


def load_fingerprints(kb_dir: Path) -> Dict[str, str]:
    path = kb_dir / FINGERPRINTS_FILENAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_fingerprints(kb_dir: Path, fingerprints: Dict[str, str]) -> None:
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / FINGERPRINTS_FILENAME).write_text(json.dumps(fingerprints, indent=2, ensure_ascii=False), encoding="utf-8")


def classify_records(records: List[ContentRecord], previous_fingerprints: Dict[str, str]) -> Dict[str, list]:
    new_records, changed_records, unchanged_ids = [], [], []
    new_fingerprints: Dict[str, str] = {}

    for record in records:
        fingerprint = content_fingerprint(record.source, record.source_id, record.text, record.metadata)
        new_fingerprints[record.content_id] = fingerprint
        previous = previous_fingerprints.get(record.content_id)
        if previous is None:
            new_records.append(record)
        elif previous != fingerprint:
            changed_records.append(record)
        else:
            unchanged_ids.append(record.content_id)

    return {
        "new": new_records,
        "changed": changed_records,
        "unchanged_ids": unchanged_ids,
        "fingerprints": new_fingerprints,
    }


def _delete_content_id_chunks(vector_store, content_id: str) -> int:
    """Remove every chunk belonging to this content_id (mirrors the docstore-filter pattern
    already used by saarthi_backend/service/indexing_service.py's delete_material_from_index)."""
    ids_to_remove = [
        doc_id
        for doc_id, doc in vector_store.docstore._dict.items()
        if doc.metadata.get("content_id") == content_id
    ]
    if ids_to_remove:
        vector_store.delete(ids_to_remove)
    return len(ids_to_remove)


def update_knowledge_base(
    input_dir: Path,
    output_dir: Path,
    embedding_model: str,
    allow_pending: bool,
) -> dict:
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    kb_dir = output_dir.parent
    all_records = load_cleaned_records(input_dir)
    eligible = qa_gate(all_records, allow_pending)

    if allow_pending:
        print("DEMO MODE: indexing QA-pending content.")
        logger.warning("DEMO MODE: indexing QA-pending content.")

    previous_fingerprints = load_fingerprints(kb_dir)
    classification = classify_records(eligible, previous_fingerprints)
    new_records = classification["new"]
    changed_records = classification["changed"]
    unchanged_ids = classification["unchanged_ids"]
    failed: List[str] = []

    to_upsert = new_records + changed_records
    embeddings = OpenAIEmbeddings(model=embedding_model)
    index_exists = (output_dir / "index.faiss").exists()

    if not to_upsert and index_exists:
        logger.info("Nothing new or changed — knowledge base already up to date.")
    elif not index_exists:
        # First build: everything eligible is "new" by definition.
        documents = []
        for record in eligible:
            try:
                documents.extend(chunk_record(record))
            except Exception as exc:  # noqa: BLE001
                failed.append(record.content_id)
                logger.error(f"{record.content_id}: chunking failed — {exc}")
        if documents:
            vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)
            output_dir.mkdir(parents=True, exist_ok=True)
            vector_store.save_local(str(output_dir))
    else:
        vector_store = FAISS.load_local(str(output_dir), embeddings, allow_dangerous_deserialization=True)
        for record in changed_records:
            _delete_content_id_chunks(vector_store, record.content_id)

        new_documents = []
        for record in to_upsert:
            try:
                new_documents.extend(chunk_record(record))
            except Exception as exc:  # noqa: BLE001
                failed.append(record.content_id)
                logger.error(f"{record.content_id}: chunking failed — {exc}")

        if new_documents:
            vector_store.add_documents(new_documents)
        vector_store.save_local(str(output_dir))

    # Never persist a fingerprint for a record that failed to embed — it must be retried next run.
    failed_set = set(failed)
    fingerprints_to_save = dict(previous_fingerprints)
    for content_id, fp in classification["fingerprints"].items():
        if content_id not in failed_set:
            fingerprints_to_save[content_id] = fp
    save_fingerprints(kb_dir, fingerprints_to_save)

    manifest_path = kb_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}
    manifest.update({"embedding_model": embedding_model, "allow_pending": allow_pending})
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "new": len(new_records),
        "changed": len(changed_records),
        "unchanged": len(unchanged_ids),
        "failed": len(failed),
    }
    log_operation(
        file=str(input_dir),
        type_="knowledge_base",
        operation="update",
        status="success" if not failed else "partial_failure",
        output=str(output_dir),
        **summary,
    )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incrementally update the unified knowledge base.")
    parser.add_argument("--input", type=Path, default=DATA_DIR / "cleaned")
    parser.add_argument("--output", type=Path, default=UNIFIED_KB_DIR / "vector_store")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--allow-pending", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}")
        return 1
    summary = update_knowledge_base(args.input, args.output, args.embedding_model, args.allow_pending)
    print(f"NEW: {summary['new']}")
    print(f"CHANGED: {summary['changed']}")
    print(f"UNCHANGED: {summary['unchanged']}")
    print(f"FAILED: {summary['failed']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
