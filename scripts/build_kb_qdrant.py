"""Single-command orchestrator for the BGE-M3 + Qdrant KB pipeline:
normalize -> chunk -> embed -> upsert -> manifest.

Each stage is also independently runnable (scripts.normalize_content_kb,
scripts.chunk_content_kb, scripts.embed_chunks_kb) — this just chains
them with shared config and a combined manifest/timing record.

Usage:
    python -m scripts.build_kb_qdrant --config configs/kb_pipeline.yaml
    python -m scripts.build_kb_qdrant --sample 2          # only the first 2 input files, for a quick local test
    python -m scripts.build_kb_qdrant --force-rebuild      # re-embed and re-upsert every chunk, ignoring content-hash matches
    python -m scripts.build_kb_qdrant --skip-embeddings --skip-qdrant   # normalize + chunk only, e.g. to inspect chunks.jsonl first
    python -m scripts.build_kb_qdrant --run-ingestion     # also OCR raw notes + transcribe raw videos first, then build the KB

Note on --resume: content-hash-aware skipping of unchanged chunks (both
in embedding and in the Qdrant upsert) is the unconditional default on
every run, interrupted-and-restarted or not — there is nothing extra
--resume needs to enable. The flag is kept, accepted, and currently a
no-op for CLI-shape compatibility with the spec; --force-rebuild is the
one that actually changes behavior (bypasses the hash check entirely).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import scripts.chunk_content_kb as chunk_content_kb
import scripts.embed_chunks_kb as embed_chunks_kb
import scripts.normalize_content_kb as normalize_content_kb
import scripts.run_content_qa as run_content_qa
from src.content_qa.config import load_qa_config
from src.knowledge_base.config import KBConfig, load_config

import logging

logger = logging.getLogger("build_kb_qdrant")
REPO_ROOT = Path(__file__).resolve().parents[1]


def _ocr_python_executable() -> str:
    """Picks the Python to run ingestion (scripts.ingest_notes/ingest_videos)
    with. Must NOT be this process's own interpreter if that interpreter also
    has a CUDA-enabled torch installed (needed here for BGE-M3): PaddleOCR's
    handwriting fallback (SAARTHI_HANDWRITING_OCR=paddleocr) imports paddle,
    and paddleocr's own paddlex->modelscope dependency unconditionally imports
    torch too — paddle's and torch's bundled cudnn DLLs collide in the same
    process on Windows (confirmed: WinError 127, either import order).
    SAARTHI_OCR_VENV_PYTHON overrides; otherwise defaults to a sibling
    .venv-ocr (see docs/KB_PIPELINE_SETUP.md) if present, else falls back to
    this process's own interpreter with a warning (safe as long as
    SAARTHI_HANDWRITING_OCR is unset)."""
    override = os.environ.get("SAARTHI_OCR_VENV_PYTHON")
    if override:
        return override
    candidate = REPO_ROOT.parent / ".venv-ocr" / "Scripts" / "python.exe"
    if candidate.exists():
        return str(candidate)
    logger.warning(
        "No .venv-ocr found and SAARTHI_OCR_VENV_PYTHON not set — running ingestion with this "
        "process's own interpreter. Safe only if SAARTHI_HANDWRITING_OCR is unset; see "
        "docs/KB_PIPELINE_SETUP.md for why PaddleOCR needs its own venv alongside a CUDA torch."
    )
    return sys.executable


def _git_commit() -> Optional[str]:
    import subprocess

    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, timeout=5).strip()
    except Exception:  # noqa: BLE001 — manifest metadata only; must never block the pipeline
        return None


def _installed_versions() -> dict:
    versions = {}
    for pkg in ("qdrant_client", "FlagEmbedding", "torch", "tiktoken"):
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg] = None
    return versions


def run(
    config: KBConfig,
    sample: Optional[int] = None,
    resume: bool = False,
    force_rebuild: bool = False,
    allow_pending: bool = False,
    run_ingestion: bool = False,
    skip_qa: bool = False,
    qa_force: bool = False,
    skip_normalize: bool = False,
    skip_chunk: bool = False,
    skip_embeddings: bool = False,
    skip_qdrant: bool = False,
    device: Optional[str] = None,
) -> dict:
    if device:
        config.embedding_device = device
    config.ensure_directories()

    stage_timings = {}
    t_start = time.perf_counter()

    ingestion_result: dict = {"skipped": True}
    if run_ingestion:
        # Run as separate subprocesses, not in-process calls: PaddleOCR's
        # handwriting fallback (SAARTHI_HANDWRITING_OCR=paddleocr) imports
        # paddle, and paddleocr's own dependency chain (paddlex -> modelscope)
        # unconditionally imports torch too — whichever of paddle/torch's
        # bundled cudnn_cnn64_9.dll loads second in the SAME process crashes
        # with WinError 127 on Windows (confirmed: fails both orders). Since
        # this script also loads torch for BGE-M3 embedding later in the run,
        # ingestion must happen in its own process to avoid that collision.
        import subprocess

        ocr_python = _ocr_python_executable()
        t0 = time.perf_counter()
        notes_status = subprocess.run(
            [ocr_python, "-m", "scripts.ingest_notes", "--output", str(config.ocr_output_dir)], cwd=REPO_ROOT
        ).returncode
        videos_status = subprocess.run(
            [ocr_python, "-m", "scripts.ingest_videos", "--output", str(config.transcripts_dir)], cwd=REPO_ROOT
        ).returncode
        stage_timings["ingestion"] = round(time.perf_counter() - t0, 2)
        ingestion_result = {"notes_exit_code": notes_status, "videos_exit_code": videos_status}

    qa_result: dict = {"skipped": True}
    if not skip_qa:
        t0 = time.perf_counter()
        qa_result = run_content_qa.run(config, load_qa_config(), force=qa_force)
        stage_timings["qa"] = round(time.perf_counter() - t0, 2)

    if not skip_normalize:
        t0 = time.perf_counter()
        normalize_result = normalize_content_kb.run(config, sample=sample, allow_pending=allow_pending)
        stage_timings["normalize"] = round(time.perf_counter() - t0, 2)
    else:
        normalize_result = {"skipped": True}

    if not skip_chunk:
        t0 = time.perf_counter()
        chunk_result = chunk_content_kb.run(config)
        stage_timings["chunk"] = round(time.perf_counter() - t0, 2)
    else:
        chunk_result = {"skipped": True}

    embed_result: dict = {"skipped": True}
    upsert_result: dict = {"skipped": True}

    if not skip_embeddings:
        t0 = time.perf_counter()
        embed_result = embed_chunks_kb.run(config, force=force_rebuild)
        stage_timings["embed"] = round(time.perf_counter() - t0, 2)

        if not skip_qdrant:
            t0 = time.perf_counter()
            from src.knowledge_base.qdrant_store import QdrantKBStore
            from src.knowledge_base.schema import Chunk

            chunks = []
            with open(config.chunks_dir / "chunks.jsonl", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        chunks.append(Chunk(**json.loads(line)))
            embeddings_by_id = {}
            with open(config.embeddings_dir / "embeddings.jsonl", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        row = json.loads(line)
                        embeddings_by_id[row["chunk_id"]] = row["vector"]

            store = QdrantKBStore(config)
            upsert_result = store.upsert_chunks(chunks, embeddings_by_id, force=force_rebuild)
            stage_timings["qdrant_upsert"] = round(time.perf_counter() - t0, 2)

    diagnostics_lines = ["========== KB PIPELINE DIAGNOSTICS =========="]
    if not ingestion_result.get("skipped"):
        diagnostics_lines.append(f"Ingestion: notes exit code={ingestion_result['notes_exit_code']}  videos exit code={ingestion_result['videos_exit_code']}")
    if not qa_result.get("skipped"):
        diagnostics_lines.append(
            f"Automated QA: files={qa_result['files']}  scored={qa_result['records_scored']}  "
            f"skipped(unchanged)={qa_result['records_skipped_unchanged']}  counts={qa_result['counts']}"
        )
    if not normalize_result.get("skipped"):
        diagnostics_lines.append(
            f"Normalization: input files={normalize_result['files']}  normalized docs={normalize_result['docs']}  "
            f"failed files={len(normalize_result.get('failed_files') or [])}"
        )
    if not chunk_result.get("skipped"):
        diagnostics_lines.append(f"Chunking: input docs={chunk_result['docs_in']}  chunks generated={chunk_result['chunks_out']}")
    if not embed_result.get("skipped"):
        diagnostics_lines.append(
            f"Embedding: input chunks={embed_result['chunks_total']}  embedded={embed_result['embedded']} "
            f"(new={embed_result['newly_embedded']}, cached={embed_result['skipped_unchanged']})  "
            f"failed={embed_result['failed']}  device={embed_result['device']}"
        )
    if not upsert_result.get("skipped"):
        diagnostics_lines.append(
            f"Qdrant: chunks total={upsert_result['chunks_total']}  uploaded={upsert_result['uploaded']}  "
            f"skipped(unchanged)={upsert_result['skipped_unchanged']}  skipped(no vector)={upsert_result['skipped_no_vector']}"
        )
    diagnostics_lines.append("=============================================")
    diagnostics_block = "\n".join(diagnostics_lines)
    logger.info("\n" + diagnostics_block)

    total_seconds = round(time.perf_counter() - t_start, 2)
    manifest = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "dependency_versions": _installed_versions(),
        "config": config.to_dict(),
        "stage_timings_seconds": stage_timings,
        "total_seconds": total_seconds,
        "ingestion": ingestion_result,
        "qa": qa_result,
        "normalize": normalize_result,
        "chunk": chunk_result,
        "embed": embed_result,
        "qdrant_upsert": upsert_result,
    }
    manifest_path = config.manifests_dir / f"manifest_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (config.manifests_dir / "latest_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    logger.info(f"Pipeline run complete in {total_seconds}s -> {manifest_path}")

    if not skip_normalize and normalize_result["files"] > 0 and normalize_result["docs"] == 0:
        raise RuntimeError(
            f"Normalization produced 0 documents from {normalize_result['files']} input file(s) (see "
            f"{manifest_path}). Two likely causes: (1) every record's qa_status is still 'pending' "
            "(automated QA was skipped with --skip-qa, or scored everything pending/rejected) and "
            "--allow-pending was not passed — re-run with --allow-pending to index unreviewed content; "
            "or (2) automated QA genuinely rejected every record — check "
            f"{config.qa_reports_dir / 'latest_qa_report.jsonl'}."
        )
    if not skip_chunk and chunk_result["docs_in"] > 0 and chunk_result["chunks_out"] == 0:
        raise RuntimeError(
            f"Chunking produced 0 chunks from {chunk_result['docs_in']} normalized document(s) (see "
            f"{manifest_path}). Check chunk_min_tokens/chunk_max_tokens in configs/kb_pipeline.yaml and "
            "whether the normalized docs actually have non-empty text."
        )
    if not skip_embeddings and embed_result["chunks_total"] > 0 and embed_result["embedded"] == 0:
        raise RuntimeError(
            f"Embedding produced 0 vectors from {embed_result['chunks_total']} chunk(s) (see {manifest_path}) — "
            f"check failed_chunk_ids ({embed_result['failed']} failed) and the embedding device/model."
        )
    if (
        not skip_qdrant
        and not skip_embeddings
        and upsert_result.get("chunks_total", 0) > 0
        and upsert_result.get("uploaded", 0) == 0
        and upsert_result.get("skipped_unchanged", 0) == 0
    ):
        raise RuntimeError(
            f"Qdrant upsert uploaded 0 points and skipped 0 as already-unchanged (see {manifest_path}) — "
            "check Qdrant connectivity and qdrant_url in the config."
        )

    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the BGE-M3 + Qdrant knowledge base, end to end.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--sample", type=int, default=None, help="Only process the first N input files (Phase 10 small-scale test).")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted embedding stage.")
    parser.add_argument("--force-rebuild", action="store_true", help="Re-embed and re-upsert every chunk, ignoring content-hash matches.")
    parser.add_argument("--allow-pending", action="store_true", help="Also normalize qa_status=='pending' records (development only).")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default=None)
    parser.add_argument("--run-ingestion", action="store_true", help="Also OCR raw notes (scripts.ingest_notes) and transcribe raw videos (scripts.ingest_videos) first, writing into this config's ocr_output_dir/transcripts_dir, before building the KB.")
    parser.add_argument("--skip-ingestion", action="store_true", help="No-op, kept for CLI-shape consistency with the spec — ingestion only runs when --run-ingestion is passed.")
    parser.add_argument("--skip-qa", action="store_true", help="Skip automated Content QA (scripts.run_content_qa) — qa_status stays whatever ingestion/a previous run already set.")
    parser.add_argument("--qa-force", action="store_true", help="Re-score every record in automated QA regardless of qa_version/content_hash (e.g. after changing configs/content_qa.yaml).")
    parser.add_argument("--skip-normalize", action="store_true")
    parser.add_argument("--skip-chunk", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--skip-qdrant", action="store_true")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(
        config,
        sample=args.sample,
        resume=args.resume,
        force_rebuild=args.force_rebuild,
        allow_pending=args.allow_pending,
        run_ingestion=args.run_ingestion,
        skip_qa=args.skip_qa,
        qa_force=args.qa_force,
        skip_normalize=args.skip_normalize,
        skip_chunk=args.skip_chunk,
        skip_embeddings=args.skip_embeddings,
        skip_qdrant=args.skip_qdrant,
        device=args.device,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
