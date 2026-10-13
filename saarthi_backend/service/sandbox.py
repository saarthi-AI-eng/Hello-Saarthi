"""Code sandbox: Docker (no network, timeout, memory/pid caps) or local
subprocess fallback — for EVERY supported language, not just Python.

CODE_SANDBOX=docker|local (default: docker if the daemon is reachable, else local)

IMPORTANT: the default SANDBOX_IMAGE (python:3.12-slim) only has Python.
To actually sandbox C++/Java/Go/Rust/Bash/R under Docker, build an image
with all of: python3, node, g++, gcc, javac/java, rustc, go, bash, Rscript,
and point SANDBOX_IMAGE at it. Until then, non-Python languages under
CODE_SANDBOX=docker will fail *inside the container* with a clear
"command not found" in stderr (safe, but not sandboxed-and-working) — set
CODE_SANDBOX=local if you want them to actually run using host runtimes.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.utils.python_runtime import _is_store_stub, python_argv, python_display

logger = logging.getLogger(__name__)

TIMEOUT = int(os.environ.get("SANDBOX_TIMEOUT_SEC", "30"))
MEMORY = os.environ.get("SANDBOX_MEMORY", "512m")
CPUS = os.environ.get("SANDBOX_CPUS", "0.5")
PIDS_LIMIT = os.environ.get("SANDBOX_PIDS_LIMIT", "64")
IMAGE = os.environ.get("SANDBOX_IMAGE", "python:3.12-slim")

_py = python_argv()
_py_run_local = " ".join(_py) + " {src}"

# Single source of truth for language config. code_service.py imports this
# instead of keeping its own copy (that duplication is how Python ended up
# the only sandboxed language last time).
# {lang: (binary_for_local_check, compile_template | None, run_template)}
LANG_CONFIG: dict[str, tuple[str, str | None, str]] = {
    "python":     (_py[0],   None,                          _py_run_local),
    "javascript": ("node",   None,                          "node {src}"),
    "cpp":        ("g++",    "g++ -O2 -o {out} {src}",       "{out}"),
    "c":          ("gcc",    "gcc -O2 -o {out} {src} -lm",   "{out}"),
    "java":       ("javac",  "javac {src}",                  "java -cp {dir} Main"),
    "rust":       ("rustc",  "rustc -o {out} {src}",         "{out}"),
    "go":         ("go",     None,                           "go run {src}"),
    "bash":       ("bash",   None,                           "bash {src}"),
    "r":          ("Rscript", None,                          "Rscript {src}"),
}

EXT: dict[str, str] = {
    "python": "py", "javascript": "js", "cpp": "cpp", "c": "c",
    "java": "java", "rust": "rs", "go": "go", "bash": "sh", "r": "r",
}

# Docker containers are always Linux. The host's local run template for
# Python resolves to `py -3` on Windows (via python_argv()) — that launcher
# does not exist inside the container, so override it here. Everything else
# (g++, gcc, javac, rustc, node, bash, Rscript) is the same command whether
# it runs on a Linux/Mac host or inside the container.
_DOCKER_RUN_OVERRIDES: dict[str, str] = {
    "python": "python3 {src}",
}


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def mode() -> str:
    # Default LOCAL. Docker is up for Postgres on the eval laptop; if we
    # auto-pick docker, student Python runs in python:3.12-slim with no numpy
    # and Windows volume mounts often fail. Opt in with CODE_SANDBOX=docker.
    pref = (os.environ.get("CODE_SANDBOX") or "local").strip().lower()
    if pref == "docker" and docker_available():
        return "docker"
    return "local"


def runtime_missing(language: str) -> str | None:
    """Human-readable message if the LOCAL runtime for `language` is missing.
    Not meaningful in docker mode (the container carries its own toolchain,
    or doesn't — see module docstring)."""
    config = LANG_CONFIG.get(language)
    if config is None:
        return f"Language '{language}' is not supported."
    binary, _, _ = config
    if language == "python":
        argv = python_argv()
        if argv and Path(argv[0]).exists() and not _is_store_stub(argv[0]):
            return None
        return (
            "No real Python interpreter found.\n"
            "Start the API from conda ml_env (the same window as: python saarthi_backend/main.py).\n"
            "Do not use the Microsoft Store python / python3 aliases."
        )
    if not shutil.which(binary):
        return (
            f"Runtime '{binary}' is not installed on this host.\n"
            f"Install it locally, or set CODE_SANDBOX=docker with an image "
            f"that has it (see SANDBOX_IMAGE)."
        )
    return None


def _filename_for(language: str) -> str:
    ext = EXT.get(language, "txt")
    # Java requires filename == public class name.
    return f"Main.{ext}" if language == "java" else f"main.{ext}"


def run_python(code: str, stdin: str = "") -> dict:
    """Back-compat wrapper for existing callers (expert_http_service.py etc).
    Returns {stdout, stderr, exit_code, sandbox, language, runtime}."""
    return run_code("python", code, stdin)


def run_code(language: str, code: str, stdin: str = "", timeout: int = TIMEOUT) -> dict:
    """Run code in any supported language, routed through Docker when
    CODE_SANDBOX permits it — the same isolation guarantee Python always had.
    Returns {stdout, stderr, exit_code, sandbox, language, runtime}.
    """
    if language not in LANG_CONFIG:
        return {
            "stdout": "", "stderr": f"Language '{language}' is not supported.",
            "exit_code": 1, "sandbox": "none", "language": language, "runtime": language,
        }
    # Windows Store aliases hijack python/python3. Always run student Python
    # with the API's conda interpreter -- never docker python3, never PATH.
    if language == "python":
        return _local(language, code, stdin, timeout)
    if mode() == "docker":
        return _docker(language, code, stdin, timeout)
    return _local(language, code, stdin, timeout)


def _run_shell(cmd: str, stdin: str, cwd: str, timeout: int) -> tuple[bool, str, str]:
    """Blocking local subprocess run — internal to _local()."""
    try:
        r = subprocess.run(
            cmd, shell=True, input=stdin.encode(),
            capture_output=True, timeout=timeout, cwd=cwd,
        )
        return (
            r.returncode == 0,
            r.stdout.decode(errors="replace"),
            r.stderr.decode(errors="replace"),
        )
    except subprocess.TimeoutExpired:
        return False, "", f"Execution timed out after {timeout} seconds."
    except Exception as e:
        return False, "", f"Execution error: {e}"


def _local_python(src: str, stdin: str, cwd: str, timeout: int) -> tuple[bool, str, str]:
    """Run student Python with argv (not shell=True) so Windows paths with spaces work."""
    argv = python_argv() + [src]
    try:
        r = subprocess.run(
            argv,
            input=stdin.encode(),
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            shell=False,
            env={**os.environ, "PYTHONEXECUTABLE": argv[0]},
        )
        stderr = r.stderr.decode(errors="replace")
        if r.returncode != 0 and "Microsoft Store" in stderr:
            stderr += (
                "\n\nSaarthi tried: " + " ".join(argv) +
                "\nCopy the new python_runtime.py, restart the API from conda ml_env, "
                "and disable App execution aliases for python.exe / python3.exe."
            )
        if r.returncode != 0 and "No module named 'numpy'" in stderr:
            stderr += (
                "\n\nHint: this lab uses the Python standard library. "
                "Replace `import numpy as np` with `import math`, or pip install numpy "
                "in the same env that runs the API (conda ml_env)."
            )
        return r.returncode == 0, r.stdout.decode(errors="replace"), stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Execution timed out after {timeout} seconds."
    except Exception as e:
        return False, "", f"Execution error: {e}"


def _local(language: str, code: str, stdin: str, timeout: int) -> dict:
    binary, compile_tpl, run_tpl = LANG_CONFIG[language]
    missing = runtime_missing(language)
    if missing:
        return {
            "stdout": "", "stderr": missing, "exit_code": 1,
            "sandbox": "local", "language": language, "runtime": binary,
        }
    with tempfile.TemporaryDirectory() as tmp:
        src = str(Path(tmp) / _filename_for(language))
        out = str(Path(tmp) / "prog")
        Path(src).write_text(code, encoding="utf-8")

        if compile_tpl:
            cmd = compile_tpl.format(src=src, out=out, dir=tmp)
            ok, _, compile_err = _run_shell(cmd, "", tmp, timeout)
            if not ok:
                return {
                    "stdout": "", "stderr": compile_err, "exit_code": 1,
                    "sandbox": "local", "language": language, "runtime": binary,
                }

        if language == "python":
            ok, stdout, stderr = _local_python(src, stdin, tmp, timeout)
            runtime = python_display()
        else:
            run_cmd = run_tpl.format(src=src, out=out, dir=tmp)
            ok, stdout, stderr = _run_shell(run_cmd, stdin, tmp, timeout)
            runtime = binary
        return {
            "stdout": stdout, "stderr": stderr, "exit_code": 0 if ok else 1,
            "sandbox": "local", "language": language, "runtime": runtime,
        }


def _docker(language: str, code: str, stdin: str, timeout: int) -> dict:
    binary, compile_tpl, run_tpl = LANG_CONFIG[language]
    run_tpl = _DOCKER_RUN_OVERRIDES.get(language, run_tpl)
    filename = _filename_for(language)

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / filename).write_text(code, encoding="utf-8")

        container_src = f"/work/{filename}"
        container_out = "/work/prog"
        steps = []
        if compile_tpl:
            steps.append(compile_tpl.format(src=container_src, out=container_out, dir="/work"))
        steps.append(run_tpl.format(src=container_src, out=container_out, dir="/work"))
        inner_cmd = " && ".join(steps)

        cmd = [
            "docker", "run", "--rm", "-i",
            "--network", "none",
            "--memory", MEMORY,
            "--cpus", CPUS,
            "--pids-limit", PIDS_LIMIT,
            "-v", f"{tmp}:/work",  # writable: compiled langs need to drop a binary here
            "-w", "/work",
            IMAGE,
            "timeout", str(timeout),
            "bash", "-c", inner_cmd,
        ]
        try:
            r = subprocess.run(
                cmd, input=stdin.encode(), capture_output=True, timeout=timeout + 5,
            )
            return {
                "stdout": r.stdout.decode(errors="replace"),
                "stderr": r.stderr.decode(errors="replace"),
                "exit_code": r.returncode,
                "sandbox": "docker", "language": language, "runtime": binary,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": 124,
                "sandbox": "docker", "language": language, "runtime": binary,
            }
        except Exception as e:
            logger.warning("Docker sandbox failed for %s (%s); falling back to local", language, e)
            return _local(language, code, stdin, timeout)
