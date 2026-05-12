"""Code execution service: Piston API runner + AI error explanation."""

import json
import logging
import os
import time
from collections.abc import AsyncGenerator

import httpx

from saarthi_backend.schema.code_schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CodeExecuteResult,
    CodeExplainRequest,
    CodeExplainResponse,
    PISTON_LANGUAGE_MAP,
    LANGUAGE_VERSIONS,
)

logger = logging.getLogger(__name__)

PISTON_URL = "https://emkc.org/api/v2/piston/execute"
PISTON_TIMEOUT = 30.0   # seconds


# ─── Piston execution ─────────────────────────────────────────────────────────

async def execute_code(body: CodeExecuteRequest) -> CodeExecuteResponse:
    lang_key = body.language.lower()
    piston_lang = PISTON_LANGUAGE_MAP.get(lang_key, lang_key)
    version = LANGUAGE_VERSIONS.get(lang_key, "*")

    payload = {
        "language": piston_lang,
        "version": version,
        "files": [{"name": f"main.{_ext(lang_key)}", "content": body.code}],
        "stdin": body.stdin or "",
        "args": [],
        "compile_timeout": 10000,
        "run_timeout": 10000,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=PISTON_TIMEOUT) as client:
            resp = await client.post(PISTON_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return CodeExecuteResponse(
            result=CodeExecuteResult(
                stdout="", stderr="Execution timed out after 30 seconds.",
                exitCode=1, language=lang_key,
                runtime=f"{piston_lang} {version}",
            ),
            aiExplanation="The code timed out. Check for infinite loops or excessive computation.",
            aiSuggestions=["Add a termination condition to any loops", "Reduce input size for testing"],
        )
    except Exception as e:
        logger.exception("Piston request failed: %s", e)
        return CodeExecuteResponse(
            result=CodeExecuteResult(
                stdout="", stderr=f"Execution service unavailable: {e}",
                exitCode=1, language=lang_key, runtime=f"{piston_lang} {version}",
            ),
        )

    elapsed_ms = (time.monotonic() - t0) * 1000

    # Piston returns run.stdout / run.stderr / run.code
    run = data.get("run", {})
    compile_out = data.get("compile", {})

    stdout = run.get("stdout", "")
    stderr = (compile_out.get("stderr", "") + run.get("stderr", "")).strip()
    exit_code = run.get("code", 0) if run.get("code") is not None else 0

    result = CodeExecuteResult(
        stdout=stdout,
        stderr=stderr,
        exitCode=exit_code,
        language=lang_key,
        runtime=f"{piston_lang} {data.get('version', version)}",
        executionMs=round(elapsed_ms, 1),
    )

    # AI error explanation
    ai_explanation: str | None = None
    ai_suggestions: list[str] = []

    if body.explainOnError and (exit_code != 0 or stderr):
        explain_body = CodeExplainRequest(
            code=body.code,
            language=lang_key,
            stderr=stderr,
            exitCode=exit_code,
            courseContext=body.courseContext,
        )
        explained = await explain_error(explain_body)
        ai_explanation = explained.explanation
        ai_suggestions = explained.suggestions

    return CodeExecuteResponse(
        result=result,
        aiExplanation=ai_explanation,
        aiSuggestions=ai_suggestions,
    )


# ─── AI error explanation (sync, JSON mode) ───────────────────────────────────

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


# ─── SSE streaming error explanation ──────────────────────────────────────────

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
                yield f"data: {delta.replace(chr(10), '\\n')}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.exception("Stream explain failed: %s", e)
        yield "data: Unable to generate explanation.\n\n"
        yield "data: [DONE]\n\n"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ext(lang: str) -> str:
    return {
        "python": "py", "javascript": "js", "typescript": "ts",
        "cpp": "cpp", "c": "c", "java": "java", "rust": "rs",
        "go": "go", "bash": "sh", "r": "r", "matlab_octave": "m",
    }.get(lang, "txt")


async def list_runtimes() -> list[dict]:
    """Fetch available runtimes from Piston (for language picker)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://emkc.org/api/v2/piston/runtimes")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Failed to fetch Piston runtimes: %s", e)
        return []
