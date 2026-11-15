"""Export/backup: bundles chunks.jsonl + chunk schema + latest manifest +
config snapshot + latest validation report into one timestamped export
directory under config.exports_dir, and (optionally) triggers a Qdrant
collection snapshot via its HTTP API.

Embeddings are deliberately NOT included in the export bundle — they can
always be regenerated deterministically from chunks.jsonl + the pinned
embedding_model/embedding_revision (see docs/KB_PIPELINE_SETUP.md), and
leaving them out keeps the export small. The Qdrant snapshot (if
requested) is the actual vector backup.

Usage:
    python -m scripts.export_kb_qdrant
    python -m scripts.export_kb_qdrant --qdrant-snapshot
"""
from __future__ import annotations

import argparse
import inspect
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.knowledge_base.config import KBConfig, load_config
from src.knowledge_base.schema import CHUNK_SCHEMA_VERSION

logger = logging.getLogger("export_kb_qdrant")

_CHUNK_SCHEMA_DOC = """\
Chunk schema version: {version}
Fields (see src/knowledge_base/schema.py:Chunk for the authoritative definition):
{fields}
"""


def _chunk_schema_text() -> str:
    from src.knowledge_base.schema import Chunk

    field_lines = "\n".join(f"  - {name}" for name in inspect.signature(Chunk).parameters)
    return _CHUNK_SCHEMA_DOC.format(version=CHUNK_SCHEMA_VERSION, fields=field_lines)


def run(config: KBConfig, qdrant_snapshot: bool = False) -> dict:
    config.ensure_directories()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir = config.exports_dir / f"export_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    chunks_path = config.chunks_dir / "chunks.jsonl"
    if chunks_path.exists():
        shutil.copy2(chunks_path, export_dir / "chunks.jsonl")
        copied.append("chunks.jsonl")

    (export_dir / "chunk_schema.txt").write_text(_chunk_schema_text(), encoding="utf-8")
    copied.append("chunk_schema.txt")

    manifest_path = config.manifests_dir / "latest_manifest.json"
    if manifest_path.exists():
        shutil.copy2(manifest_path, export_dir / "manifest.json")
        copied.append("manifest.json")

    report_path = config.reports_dir / "latest_validation_report.json"
    if report_path.exists():
        shutil.copy2(report_path, export_dir / "validation_report.json")
        copied.append("validation_report.json")

    (export_dir / "config_snapshot.json").write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    copied.append("config_snapshot.json")

    snapshot_info = None
    if qdrant_snapshot:
        try:
            from src.knowledge_base.qdrant_store import QdrantKBStore

            store = QdrantKBStore(config)
            client = store._ensure_client()
            snapshot = client.create_snapshot(collection_name=config.qdrant_collection)
            snapshot_info = {"name": snapshot.name, "created_at": str(getattr(snapshot, "creation_time", None))}
            (export_dir / "qdrant_snapshot_info.json").write_text(json.dumps(snapshot_info, indent=2), encoding="utf-8")
            logger.info(
                f"Qdrant snapshot created: {snapshot.name!r}. Download it from the running "
                f"Qdrant server (e.g. `curl {config.qdrant_url}/collections/{config.qdrant_collection}/snapshots/{snapshot.name} -o {export_dir / snapshot.name}`) "
                "— this script only records the snapshot's existence/name, since the snapshot "
                "itself lives on the Qdrant server's own disk, not in this export directory."
            )
        except Exception as exc:  # noqa: BLE001 — snapshot is best-effort; the rest of the export must still succeed
            logger.error(f"Qdrant snapshot failed: {exc}")

    result = {"export_dir": str(export_dir), "files": copied, "qdrant_snapshot": snapshot_info}
    logger.info(f"Export complete -> {export_dir} ({len(copied)} file(s))")
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export/backup the BGE-M3 + Qdrant knowledge base.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--qdrant-snapshot", action="store_true", help="Also trigger a Qdrant collection snapshot (requires a reachable Qdrant server).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(config, qdrant_snapshot=args.qdrant_snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
