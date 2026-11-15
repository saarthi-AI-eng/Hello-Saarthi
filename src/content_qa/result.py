"""QAResult: the one shape both pdf_qa.py and video_qa.py produce, and the
one shape scripts/run_content_qa.py writes back into ContentRecord.metadata
and into QA reports — explainable (checks + issues, not just a number) and
reproducible (same input always scores identically; see content_hash)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class QAResult:
    status: str                    # "approved" | "pending" | "rejected" — ContentRecord.qa_status value
    score: float                   # 0-100 weighted score (0 when a critical failure fired)
    qa_version: str
    qa_method: str                 # e.g. "pdf_heuristic_v1" / "video_heuristic_v1"
    checks: dict[str, float] = field(default_factory=dict)      # per-dimension 0-100 sub-scores
    issues: list[str] = field(default_factory=list)             # human-readable reasons, explains the score
    critical_failure: Optional[str] = None                       # set when a critical rule fired, else None
    content_hash: str = ""         # hash of exactly what was scored — see checks.qa_content_hash()
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_metadata(self) -> dict:
        """Exactly what gets stored at ContentRecord.metadata['qa']."""
        return {
            "score": round(self.score, 2),
            "version": self.qa_version,
            "method": self.qa_method,
            "checks": {k: round(v, 2) for k, v in self.checks.items()},
            "issues": self.issues,
            "critical_failure": self.critical_failure,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp,
        }
