"""Features for the learned Tier 1 / Tier 2 classifier — shared by training and inference."""
from __future__ import annotations

import re

import numpy as np

from src.orchestrator.classifier import _COMPLEX, _DEFINITION, _MATHY, _PROBLEM, _SMALLTALK

_CODE = re.compile(r"\b(matlab|python|numpy|scipy|np\.|code|error|debug|bug|nan|index exceeds|traceback)\b", re.I)
_STEPS = re.compile(r"\b(step by step|steps|justify|show that|sketch|verify|prove)\b", re.I)

CUE_NAMES = ["words", "math", "problem_verb", "complex_cue", "definition_start", "code_debug", "steps", "smalltalk"]


def cues(query: str) -> np.ndarray:
    q = query or ""
    return np.array([
        min(len(q.split()), 40) / 40.0,
        1.0 if _MATHY.search(q) else 0.0,
        1.0 if _PROBLEM.search(q) else 0.0,
        1.0 if _COMPLEX.search(q) else 0.0,
        1.0 if _DEFINITION.match(q) else 0.0,
        1.0 if _CODE.search(q) else 0.0,
        1.0 if _STEPS.search(q) else 0.0,
        1.0 if _SMALLTALK.match(q) else 0.0,
    ], dtype="float32")


def feature_vector(query: str, embedding) -> np.ndarray:
    e = np.asarray(embedding, dtype="float32")
    e = e / (float(np.linalg.norm(e)) or 1.0)
    return np.concatenate([e, cues(query)])
