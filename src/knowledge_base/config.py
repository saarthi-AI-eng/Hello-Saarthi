"""Central configuration for the BGE-M3 + Qdrant KB pipeline.

Load order (later wins): configs/kb_pipeline.yaml defaults -> --config
<path> override -> environment variables -> explicit CLI flags (applied
by the calling script, not here). This keeps one source of truth
(the YAML) while still letting every value be overridden without
editing a file, per the "configuration-driven, reproducible on another
machine" requirement.

All paths are resolved relative to SAARTHI_KB_DATA_ROOT, which must live
outside the Git repository (see docs/KB_PIPELINE_SETUP.md Phase 7) — no
path here defaults to a location the user hasn't actually chosen; there
is no bundled real default like D:\\SaarthiData baked into the code,
only into the shipped configs/kb_pipeline.yaml template (which itself
reads the env var first).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "kb_pipeline.yaml"


def _env_path(name: str, default: Optional[str] = None) -> Optional[Path]:
    value = os.environ.get(name, default)
    return Path(value) if value else None


@dataclass
class KBConfig:
    # --- Data root and derived directories ---
    data_root: Path = field(default_factory=lambda: Path(os.environ.get("SAARTHI_KB_DATA_ROOT", "")))

    # --- Chunking ---
    chunk_target_tokens: int = 500
    chunk_min_tokens: int = 100
    chunk_max_tokens: int = 900
    chunk_overlap_tokens: int = 75
    semantic_similarity_threshold: float = 0.6
    semantic_boundary_detection: bool = True  # requires the embedding model; disable for a cheap structural-only pass
    video_segment_merge_gap_seconds: float = 2.0  # consecutive transcript segments closer than this merge into one unit

    # --- Embedding ---
    embedding_model: str = "BAAI/bge-m3"
    embedding_revision: str = "main"  # pin an exact commit hash once you've validated a specific one
    embedding_dim: int = 1024
    embedding_device: str = "auto"  # auto | cuda | cpu
    embedding_batch_size: int = 16  # conservative default for an 8GB GPU; raise if VRAM allows
    embedding_checkpoint_interval: int = 100  # chunks between checkpoint writes

    # --- Qdrant ---
    # local/cloud selection (new): qdrant_url/qdrant_api_key are the LOCAL
    # backend's address (kept for backward compat with existing QDRANT_URL/
    # QDRANT_API_KEY env vars and docker-compose.kb.yml); qdrant_cloud_url/
    # qdrant_cloud_api_key are entirely separate fields for Qdrant Cloud.
    # QdrantKBStore._ensure_client() resolves which pair to actually use
    # based on qdrant_backend — see that method for the one place this
    # matters. Local remains the default; nothing changes for existing
    # local-only setups that never set QDRANT_BACKEND/QDRANT_CLOUD_*.
    qdrant_backend: str = "local"  # "local" | "cloud"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_cloud_url: str = ""
    qdrant_cloud_api_key: Optional[str] = None
    qdrant_collection: str = "saarthi_knowledge_base_v1"
    qdrant_upsert_batch_size: int = 64

    # --- Chunk schema version — bump when the chunk shape changes so old
    # and new chunks are never silently mixed in Qdrant without a rebuild. ---
    chunk_schema_version: str = "1.1"

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def source_content_dir(self) -> Path:
        return self.data_root / "source_content"

    @property
    def ocr_output_dir(self) -> Path:
        return self.source_content_dir / "ocr"

    @property
    def transcripts_dir(self) -> Path:
        return self.source_content_dir / "transcripts"

    @property
    def qa_reports_dir(self) -> Path:
        return self.data_root / "qa_reports"

    @property
    def kb_dir(self) -> Path:
        return self.data_root / "knowledge_base"

    @property
    def normalized_dir(self) -> Path:
        return self.kb_dir / "normalized"

    @property
    def chunks_dir(self) -> Path:
        return self.kb_dir / "chunks"

    @property
    def embeddings_dir(self) -> Path:
        return self.kb_dir / "embeddings"

    @property
    def manifests_dir(self) -> Path:
        return self.kb_dir / "manifests"

    @property
    def exports_dir(self) -> Path:
        return self.kb_dir / "exports"

    @property
    def reports_dir(self) -> Path:
        return self.kb_dir / "reports"

    @property
    def models_cache_dir(self) -> Path:
        return self.data_root / "models"

    @property
    def logs_dir(self) -> Path:
        return self.data_root / "logs"

    @property
    def effective_qdrant_url(self) -> str:
        return self.qdrant_cloud_url if self.qdrant_backend == "cloud" else self.qdrant_url

    @property
    def effective_qdrant_api_key(self) -> Optional[str]:
        return self.qdrant_cloud_api_key if self.qdrant_backend == "cloud" else self.qdrant_api_key

    def ensure_directories(self) -> None:
        """Creates every directory this config references, if missing.
        Never destructive — only creates, never clears or overwrites."""
        for prop in (
            self.source_content_dir, self.ocr_output_dir, self.transcripts_dir,
            self.qa_reports_dir, self.normalized_dir, self.chunks_dir, self.embeddings_dir,
            self.manifests_dir, self.exports_dir, self.reports_dir,
            self.models_cache_dir, self.logs_dir,
        ):
            prop.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        """Never includes real API key VALUES — this dict is written to
        manifest.json/config_snapshot.json on disk (not committed, but
        still shouldn't hold a plaintext secret). Presence is shown as a
        boolean so a manifest can still confirm 'a cloud key was configured'
        without ever containing the key itself."""
        d = {}
        for f in fields(self):
            if f.name in ("qdrant_api_key", "qdrant_cloud_api_key"):
                d[f.name] = "<redacted>" if getattr(self, f.name) else None
                continue
            value = getattr(self, f.name)
            d[f.name] = str(value) if isinstance(value, Path) else value
        return d


# Environment variables that override a YAML value, keyed by KBConfig field name.
_ENV_OVERRIDES = {
    "data_root": "SAARTHI_KB_DATA_ROOT",
    "embedding_device": "SAARTHI_KB_EMBED_DEVICE",
    "embedding_batch_size": "SAARTHI_KB_EMBED_BATCH_SIZE",
    "qdrant_url": "QDRANT_URL",
    "qdrant_api_key": "QDRANT_API_KEY",
    "qdrant_collection": "QDRANT_COLLECTION",
    "qdrant_backend": "QDRANT_BACKEND",
    "qdrant_cloud_url": "QDRANT_CLOUD_URL",
    "qdrant_cloud_api_key": "QDRANT_CLOUD_API_KEY",
}
_INT_FIELDS = {"embedding_batch_size", "chunk_target_tokens", "chunk_min_tokens", "chunk_max_tokens", "chunk_overlap_tokens", "embedding_checkpoint_interval", "qdrant_upsert_batch_size", "embedding_dim"}
_FLOAT_FIELDS = {"semantic_similarity_threshold", "video_segment_merge_gap_seconds"}
_BOOL_FIELDS = {"semantic_boundary_detection"}
_PATH_FIELDS = {"data_root"}


def load_config(config_path: Optional[Path] = None) -> KBConfig:
    """Loads configs/kb_pipeline.yaml (or config_path), then applies
    environment-variable overrides. Missing YAML file is not an error —
    falls back to KBConfig's own dataclass defaults, so a bare `import
    load_config; load_config()` always works for tests."""
    from scripts.env_loader import load_env_file

    load_env_file()  # .env.kb, if present — never overwrites an already-set real env var (Part 3)

    path = config_path or DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    valid_fields = {f.name for f in fields(KBConfig)}
    kwargs = {k: v for k, v in raw.items() if k in valid_fields}
    if "data_root" in kwargs:
        kwargs["data_root"] = Path(kwargs["data_root"])

    config = KBConfig(**kwargs)

    for field_name, env_name in _ENV_OVERRIDES.items():
        env_value = os.environ.get(env_name)
        if env_value is None or env_value == "":
            continue
        if field_name in _INT_FIELDS:
            setattr(config, field_name, int(env_value))
        elif field_name in _FLOAT_FIELDS:
            setattr(config, field_name, float(env_value))
        elif field_name in _BOOL_FIELDS:
            setattr(config, field_name, env_value.strip().lower() in ("1", "true", "yes"))
        elif field_name in _PATH_FIELDS:
            setattr(config, field_name, Path(env_value))
        else:
            setattr(config, field_name, env_value)

    # QDRANT_LOCAL_URL is the new, explicit name for the same field QDRANT_URL
    # already maps above — applied after the loop so it wins if both happen
    # to be set, without disturbing QDRANT_URL's existing back-compat mapping.
    if os.environ.get("QDRANT_LOCAL_URL"):
        config.qdrant_url = os.environ["QDRANT_LOCAL_URL"]

    config.qdrant_backend = (config.qdrant_backend or "local").strip().lower()
    if config.qdrant_backend not in ("local", "cloud"):
        raise ValueError(
            f"Invalid QDRANT_BACKEND {config.qdrant_backend!r} — must be 'local' or 'cloud'. "
            "See .env.kb.example."
        )

    if not config.data_root or str(config.data_root) == ".":
        raise ValueError(
            "No KB data root configured. Set SAARTHI_KB_DATA_ROOT (e.g. "
            "E:\\SaarthiData) or set data_root in configs/kb_pipeline.yaml — "
            "see docs/KB_PIPELINE_SETUP.md."
        )
    return config
