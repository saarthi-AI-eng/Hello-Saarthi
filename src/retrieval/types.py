from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Hit:
    source_id: str          # docstore id — unique inside one index folder
    text: str
    content_type: str       # notes | books | video | course_material
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    via: str = ""           # which legs found it, e.g. "dense+bm25"
