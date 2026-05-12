"""Code execution service: local subprocess runner + AI error explanation.

Piston public API went whitelist-only on 2026-02-15.
We now run code locally in a temp directory with a strict timeout.
Each language must be installed on the host (python3, node, g++, gcc,
javac/java, rustc, go, bash, Rscript).  Missing runtimes return a clear
error rather than crashing.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from saarthi_backend.schema.code_schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CodeExecuteResult,
    CodeExplainRequest,
    CodeExplainResponse,
)

logger = logging.getLogger(__name__)

EXEC_TIMEOUT = 15  # seconds per run

# ── Language → (binary, compile_cmd | None, run_cmd) ─────────────────────────
# {lang_key: (check_binary, compile_template, run_template)}
# Templates use {src} for source file path and {out} for compiled binary path.

_LANG_CONFIG: dict[str, tuple[str, str | None, str]] = {
    "python":     ("python3",  None,                              "python3 {src}"),
    "javascript": ("node",     None,                              "node {src}"),
    "cpp":        ("g++",      "g++ -O2 -o {out} {src}",         "{out}"),
    "c":          ("gcc",      "gcc -O2 -o {out} {src} -lm",     "{out}"),
    "java":       ("javac",    "javac {src}",                     "java -cp {dir} Main"),
    "rust":       ("rustc",    "rustc -o {out} {src}",            "{out}"),
    "go":         ("go",       None,                              "go run {src}"),
    "bash":       ("bash",     None,                              "bash {src}"),
    "r":          ("Rscript",  None,                              "Rscript {src}"),
}

_EXT: dict[str, str] = {
    "python": "py", "javascript": "js", "cpp": "cpp", "c": "c",
    "java": "java", "rust": "rs", "go": "go", "bash": "sh", "r": "r",
}


# ── Execute ───────────────────────────────────────────────────────────────────

async def execute_code(body: CodeExecuteRequest) -> CodeExecuteResponse:
    lang = body.language.lower()
    config = _LANG_CONFIG.get(lang)

    if config is None:
        return CodeExecuteResponse(
            result=CodeExecuteResult(
                stdout="", stderr=f"Language '{lang}' is not supported.",
                exitCode=1, language=lang, runtime=lang,
            )
        )

    binary, compile_tpl, run_tpl = config

    # Check binary is installed
    if not shutil.which(binary):
        return CodeExecuteResponse(
            result=CodeExecuteResult(
                stdout="",
                stderr=(
                    f"Runtime '{binary}' is not installed on this server.\n"
                    f"Ask your administrator to install {binary}."
                ),
                exitCode=1, language=lang, runtime=binary,
            )
        )

    ext = _EXT.get(lang, "txt")
    # Java requires filename == class name "Main"
    filename = f"Main.{ext}" if lang == "java" else f"main.{ext}"

    with tempfile.TemporaryDirectory() as tmpdir:
        src = str(Path(tmpdir) / filename)
        out = str(Path(tmpdir) / "prog")

        Path(src).write_text(body.code, encoding="utf-8")

        t0 = time.monotonic()
        compile_stderr = ""

        # ── Compile step ──────────────────────────────────────────────────────
        if compile_tpl:
            cmd = compile_tpl.format(src=src, out=out, dir=tmpdir)
            ok, _, compile_stderr = await _run_cmd(cmd, stdin="", cwd=tmpdir)
            if not ok:
                elapsed = round((time.monotonic() - t0) * 1000, 1)
                return CodeExecuteResponse(
                    result=CodeExecuteResult(
                        stdout="", stderr=compile_stderr,
                        exitCode=1, language=lang, runtime=binary,
                        executionMs=elapsed,
                    )
                )

        # ── Run step ──────────────────────────────────────────────────────────
        run_cmd = run_tpl.format(src=src, out=out, dir=tmpdir)
        exit_ok, stdout, stderr = await _run_cmd(
            run_cmd, stdin=body.stdin or "", cwd=tmpdir
        )
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        exit_code = 0 if exit_ok else 1

        result = CodeExecuteResult(
            stdout=stdout,
            stderr=stderr,
            exitCode=exit_code,
            language=lang,
            runtime=binary,
            executionMs=elapsed,
        )

        ai_explanation: str | None = None
        ai_suggestions: list[str] = []

        if body.explainOnError and (exit_code != 0 or stderr):
            explain_body = CodeExplainRequest(
                code=body.code, language=lang, stderr=stderr,
                exitCode=exit_code, courseContext=body.courseContext,
            )
            explained = await explain_error(explain_body)
            ai_explanation = explained.explanation
            ai_suggestions = explained.suggestions

        return CodeExecuteResponse(
            result=result,
            aiExplanation=ai_explanation,
            aiSuggestions=ai_suggestions,
        )


async def _run_cmd(
    cmd: str, stdin: str, cwd: str, timeout: int = EXEC_TIMEOUT
) -> tuple[bool, str, str]:
    """Run a shell command, return (success, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=stdin.encode()),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return False, "", f"Execution timed out after {timeout} seconds."

        stdout = stdout_b.decode(errors="replace")
        stderr = stderr_b.decode(errors="replace")
        return proc.returncode == 0, stdout, stderr

    except Exception as e:
        return False, "", f"Execution error: {e}"


# ── AI error explanation ───────────────────────────────────────────────────────

_EXPLAIN_SYSTEM = """You are an expert programming tutor for engineering students.
A student's code has failed. Analyse the error and provide a clear explanation.

Return ONLY valid JSON:
{
  "explanation": "2-3 sentence plain-English explanation of what went wrong and why",
  "suggestions": ["specific fix 1", "specific fix 2", "specific fix 3"]
}

Rules:
- Be specific — reference the actual error message and line numbers when visible
- suggestions must be actionable one-liners the student can apply immediately
- If it's a logic error (wrong output, not a crash), explain the logical mistake
- Relate to engineering/DSP/ML context when courseContext is provided"""


async def explain_error(body: CodeExplainRequest) -> CodeExplainResponse:
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        context_line = f"\nCourse context: {body.courseContext}" if body.courseContext else ""
        user_prompt = (
            f"Language: {body.language}{context_line}\n\n"
            f"Code:\n```{body.language}\n{body.code[:3000]}\n```\n\n"
            f"Error (exit code {body.exitCode}):\n{body.stderr[:1500]}"
        )

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _EXPLAIN_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=600,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content or "{}")
        return CodeExplainResponse(
            explanation=data.get("explanation", "An error occurred in your code."),
            suggestions=data.get("suggestions", []),
        )
    except Exception as e:
        logger.exception("AI error explanation failed: %s", e)
        return CodeExplainResponse(
            explanation="Your code encountered an error. Check the stderr output above for details.",
            suggestions=["Review the error message carefully", "Check for syntax errors", "Verify variable names and types"],
        )


# ── SSE streaming explanation ─────────────────────────────────────────────────

_EXPLAIN_STREAM_SYSTEM = """You are a programming tutor. A student's code failed.
Explain what went wrong in clear, friendly plain English. Be specific about the error.
Then give 2-3 concrete fixes. Keep it under 150 words total. No code blocks."""


async def stream_explain_error(body: CodeExplainRequest) -> AsyncGenerator[str, None]:
    """Stream the AI error explanation token-by-token via SSE."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        context_line = f" (course: {body.courseContext})" if body.courseContext else ""
        user_prompt = (
            f"Language: {body.language}{context_line}\n"
            f"Exit code: {body.exitCode}\n"
            f"Error:\n{body.stderr[:800]}\n\n"
            f"Code snippet:\n{body.code[:1500]}"
        )

        stream = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _EXPLAIN_STREAM_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=300,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {delta.replace(chr(10), chr(92) + 'n')}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.exception("Stream explain failed: %s", e)
        yield "data: Unable to generate explanation.\n\n"
        yield "data: [DONE]\n\n"


# ── Runtime list (local, no external API) ─────────────────────────────────────

async def list_runtimes() -> list[dict]:
    """Return which runtimes are actually installed on this machine."""
    result = []
    for lang, (binary, _, _) in _LANG_CONFIG.items():
        if shutil.which(binary):
            result.append({"language": lang, "runtime": binary, "available": True})
        else:
            result.append({"language": lang, "runtime": binary, "available": False})
    return result
