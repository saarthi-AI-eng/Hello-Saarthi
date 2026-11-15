"""Tiny, dependency-free .env.kb loader (Part 3). No python-dotenv — this
project already avoids adding a dependency for something a dozen lines of
stdlib code does just as well.

Precedence, documented in docs/KB_PIPELINE_SETUP.md: a real environment
variable already set in your shell always wins over .env.kb — this uses
os.environ.setdefault-style logic, never overwriting an already-set value.
That is also exactly how you override a variable TEMPORARILY for one run:
set it in your shell before running (e.g. PowerShell's
`$env:SAARTHI_HANDWRITING_OCR = "trocr"`), and it takes priority over
whatever .env.kb says, for that session only.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_KB_PATH = REPO_ROOT / ".env.kb"


def load_env_file(path: Optional[Path] = None) -> int:
    """Sets os.environ from KEY=VALUE lines in .env.kb, skipping blank
    lines and '#' comments. Never overwrites a variable already set in the
    real environment. Returns how many variables it actually set — 0 if
    the file doesn't exist (missing .env.kb is not an error, same
    convention as configs/kb_pipeline.yaml's own load_config())."""
    path = path or DEFAULT_ENV_KB_PATH
    if not path.exists():
        return 0
    set_count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            set_count += 1
    return set_count
