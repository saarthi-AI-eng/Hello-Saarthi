"""Loads configs/content_qa.yaml. Mirrors src/knowledge_base/config.py's
load-order convention (YAML defaults, no silent fallback to made-up
numbers) but is intentionally its own small loader — this config shape
(nested weights/thresholds) doesn't fit KBConfig's flat dataclass fields,
and QA scoring must stay decoupled from the KB pipeline's config entirely
(a QA-only re-run must not need a Qdrant URL)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QA_CONFIG_PATH = REPO_ROOT / "configs" / "content_qa.yaml"

_REQUIRED_WEIGHT_KEYS = (
    "recognition_confidence",
    "text_completeness",
    "character_quality",
    "structural_integrity",
    "content_consistency",
    "metadata_validity",
)


@dataclass
class QAConfig:
    qa_version: str = "qa-v1"
    weights: dict[str, float] = field(default_factory=dict)
    approved_min: int = 85
    pending_min: int = 60
    max_repeated_char_run: int = 12
    max_control_char_ratio: float = 0.02
    min_word_count: int = 3
    min_char_count: int = 8
    max_video_segment_seconds: float = 120.0
    duplicate_penalty_score: float = 40.0
    max_control_char_ratio_for_rejection: float = 0.5


def load_qa_config(config_path: Optional[Path] = None) -> QAConfig:
    path = config_path or DEFAULT_QA_CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    weights = dict(raw.get("weights") or {})
    missing = [k for k in _REQUIRED_WEIGHT_KEYS if k not in weights]
    if missing:
        raise ValueError(f"{path}: weights missing required key(s): {missing}")
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{path}: weights must sum to 1.0, got {total}")

    thresholds = raw.get("thresholds") or {}
    char_quality = raw.get("character_quality") or {}
    completeness = raw.get("text_completeness") or {}
    structural = raw.get("structural_integrity") or {}
    consistency = raw.get("content_consistency") or {}
    critical = raw.get("critical_failures") or {}

    return QAConfig(
        qa_version=raw.get("qa_version", "qa-v1"),
        weights=weights,
        approved_min=int(thresholds.get("approved_min", 85)),
        pending_min=int(thresholds.get("pending_min", 60)),
        max_repeated_char_run=int(char_quality.get("max_repeated_char_run", 12)),
        max_control_char_ratio=float(char_quality.get("max_control_char_ratio", 0.02)),
        min_word_count=int(completeness.get("min_word_count", 3)),
        min_char_count=int(completeness.get("min_char_count", 8)),
        max_video_segment_seconds=float(structural.get("max_video_segment_seconds", 120.0)),
        duplicate_penalty_score=float(consistency.get("duplicate_penalty_score", 40.0)),
        max_control_char_ratio_for_rejection=float(critical.get("max_control_char_ratio_for_rejection", 0.5)),
    )
