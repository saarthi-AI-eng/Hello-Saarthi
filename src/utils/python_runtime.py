"""Resolve a real Python interpreter. Never use the Windows Store stub."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_store_stub(path: str | None) -> bool:
    if not path:
        return True
    p = path.replace("/", "\\").lower()
    name = Path(p).name
    if "windowsapps" in p or "microsoft\\windowsapps" in p:
        return True
    # Store alias often looks like a 0-byte python.exe in WindowsApps
    try:
        if name in ("python.exe", "python3.exe", "python3") and Path(path).stat().st_size < 4096:
            if "windowsapps" in p or "appdata\\local\\microsoft" in p:
                return True
    except OSError:
        pass
    return False


def _ok(path: str | None) -> bool:
    if not path:
        return False
    try:
        return Path(path).is_file() and not _is_store_stub(path)
    except OSError:
        return False


def python_argv() -> list[str]:
    """Full path to the interpreter that is already running Saarthi.

    On the eval laptop that is conda ml_env. Never return the names
    python / python3 / py -- Windows App Execution Aliases intercept those.
    """
    candidates: list[str] = []

    if sys.executable:
        candidates.append(sys.executable)

    conda = os.environ.get("CONDA_PREFIX") or ""
    if conda:
        candidates.append(str(Path(conda) / "python.exe"))
        candidates.append(str(Path(conda) / "bin" / "python"))

    venv = os.environ.get("VIRTUAL_ENV") or ""
    if venv:
        candidates.append(str(Path(venv) / "python.exe"))
        candidates.append(str(Path(venv) / "Scripts" / "python.exe"))
        candidates.append(str(Path(venv) / "bin" / "python"))

    # Known path from this project's earlier logs
    candidates.append(r"E:\anaconda_conda\envs\ml_env\python.exe")

    seen: set[str] = set()
    for c in candidates:
        key = c.replace("/", "\\").lower()
        if key in seen:
            continue
        seen.add(key)
        if _ok(c):
            return [c]

    # Last resort: still prefer sys.executable even if detection failed
    if sys.executable:
        return [sys.executable]
    return [r"E:\anaconda_conda\envs\ml_env\python.exe"]


def python_display() -> str:
    return python_argv()[0]
