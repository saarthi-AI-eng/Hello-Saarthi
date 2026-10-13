"""Code execution service: every language now routes through
saarthi_backend.service.sandbox.run_code(), so the Docker isolation
guarantees (--network none, memory/pid caps) apply consistently instead of
only to Python. Falls back to local subprocess execution when
CODE_SANDBOX=local or the Docker daemon is unavailable.
"""
import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from saarthi_backend.schema.code_schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CodeExecuteResult,
    CodeExplainRequest,
    CodeExplainResponse,
)
from saarthi_backend.service.sandbox import LANG_CONFIG, mode as sandbox_mode, run_code, runtime_missing

logger = logging.getLogger(__name__)
from src.utils.llm import async_openai, chat_model_name
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_with_api_python(code: str, stdin: str = "") -> dict:
    """Last resort: the exact interpreter running FastAPI (conda ml_env)."""
    exe = sys.executable
    conda = os.environ.get("CONDA_PREFIX") or ""
    for cand in (
        exe,
        str(Path(conda) / "python.exe") if conda else "",
        r"E:\anaconda_conda\envs\ml_env\python.exe",
    ):
        if cand and Path(cand).is_file() and "windowsapps" not in cand.lower():
            exe = cand
            break
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "main.py"
        src.write_text(code, encoding="utf-8")
        r = subprocess.run(
            [exe, str(src)],
            input=(stdin or "").encode(),
            capture_output=True,
            timeout=30,
            cwd=tmp,
            shell=False,
        )
        return {
            "stdout": r.stdout.decode(errors="replace"),
            "stderr": r.stderr.decode(errors="replace"),
            "exit_code": r.returncode,
            "sandbox": "api-python",
            "language": "python",
            "runtime": exe,
        }


# ── Execute ─────────────────────────────────────────────────────────────────
async def execute_code(body: CodeExecuteRequest) -> CodeExecuteResponse:
    lang = body.language.lower()
    if lang not in LANG_CONFIG:
        return CodeExecuteResponse(
            result=CodeExecuteResult(
                stdout="", stderr=f"Language '{lang}' is not supported.",
                exitCode=1, language=lang, runtime=lang,
            )
        )

    loop = asyncio.get_running_loop()
    t0 = time.monotonic()
    # run_code() shells out (or calls `docker run`) synchronously — keep it
    # off the event loop.
    boxed = await loop.run_in_executor(None, run_code, lang, body.code, body.stdin or "")
    err = (boxed.get("stderr") or "")
    if lang == "python" and ("Microsoft Store" in err or "WindowsApps" in err or "execution aliases" in err):
        boxed = await loop.run_in_executor(None, _run_with_api_python, body.code, body.stdin or "")
    elapsed = round((time.monotonic() - t0) * 1000, 1)

    runtime_label = f"{boxed.get('runtime') or lang} ({boxed.get('sandbox') or 'unknown'})"
    result = CodeExecuteResult(
        stdout=boxed.get("stdout") or "",
        stderr=boxed.get("stderr") or "",
        exitCode=int(boxed.get("exit_code") or 0),
        language=lang,
        runtime=runtime_label,
        executionMs=elapsed,
    )

    ai_explanation = None
    ai_suggestions: list[str] = []
    if body.explainOnError and (result.exitCode != 0 or result.stderr):
        explained = await explain_error(CodeExplainRequest(
            code=body.code, language=lang, stderr=result.stderr,
            exitCode=result.exitCode, courseContext=body.courseContext,
        ))
        ai_explanation = explained.explanation
        ai_suggestions = explained.suggestions

    return CodeExecuteResponse(result=result, aiExplanation=ai_explanation, aiSuggestions=ai_suggestions)


# ── AI error explanation ─────────────────────────────────────────────────────
_EXPLAIN_SYSTEM = """You are a programming tutor for engineering students (spec 7.2: Socratic debugging).
A student's code failed. Explain the error in plain language, then guide — do not fix it for them.

Return ONLY valid JSON:
{
  "explanation": "2-3 sentences: what the error message means and where it comes from",
  "suggestions": ["hint 1", "hint 2", "hint 3"]
}

Rules:
- Reference the actual error message and line number when visible.
- suggestions are Socratic hints: point to what to check or ask a guiding question.
  Never give the corrected line or corrected code.
- If it is a logic error (wrong output, no crash), hint at the mistaken assumption.
- Relate to the DSP/engineering context when courseContext is provided."""


async def explain_error(body: CodeExplainRequest) -> CodeExplainResponse:
    try:
        client = async_openai()
        context_line = f"\nCourse context: {body.courseContext}" if body.courseContext else ""
        user_prompt = (
            f"Language: {body.language}{context_line}\n\n"
            f"Code:\n```{body.language}\n{body.code[:3000]}\n```\n\n"
            f"Error (exit code {body.exitCode}):\n{body.stderr[:1500]}"
        )
        response = await client.chat.completions.create(
            model=chat_model_name(),
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
_EXPLAIN_STREAM_SYSTEM = """You are a programming tutor for engineering students.

If the code FAILED (exit code != 0 or stderr present):
- Explain what the error message means in friendly plain English, naming the line if visible.
- Then give 1-2 Socratic hints (what to check, or a guiding question). Do NOT write the fix.
- Under 150 words. No code blocks.

If the code SUCCEEDED (exit code 0, no errors):
- Briefly explain what the output means and one thing worth improving.
- Under 120 words. Encouraging but precise. No code blocks."""


async def stream_explain_error(body: CodeExplainRequest) -> AsyncGenerator[str, None]:
    """Stream the AI explanation/insight token-by-token via SSE."""
    try:
        client = async_openai()
        context_line = f" (course: {body.courseContext})" if body.courseContext else ""
        is_success = body.exitCode == 0 and not body.stderr

        if is_success:
            user_prompt = (
                f"Language: {body.language}{context_line}\n"
                f"The code ran successfully.\n\n"
                f"Output:\n{(body.stdout or '')[:600]}\n\n"
                f"Code:\n{body.code[:1500]}"
            )
        else:
            user_prompt = (
                f"Language: {body.language}{context_line}\n"
                f"Exit code: {body.exitCode}\n"
                f"Error:\n{body.stderr[:800]}\n\n"
                f"Code snippet:\n{body.code[:1500]}"
            )

        stream = await client.chat.completions.create(
            model=chat_model_name(),
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


# ── Runtime list ──────────────────────────────────────────────────────────────
async def list_runtimes() -> list[dict]:
    """Which runtimes are actually usable right now: local binary present,
    or the Docker sandbox is active (in which case availability depends on
    SANDBOX_IMAGE — see sandbox.py docstring)."""
    m = sandbox_mode()
    result = []
    for lang, (binary, _, _) in LANG_CONFIG.items():
        if m == "docker":
            result.append({"language": lang, "runtime": f"{binary} (docker, image={None})", "available": True})
        else:
            result.append({"language": lang, "runtime": binary, "available": runtime_missing(lang) is None})
    return result
