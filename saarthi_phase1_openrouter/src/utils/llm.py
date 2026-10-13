"""
Single place for chat + embeddings.

Default: OpenAI (gpt-4.1 / gpt-4o-mini / text-embedding-3-small).

OpenRouter (GLM chat + Nemotron embeddings) — set in saarthi_backend/.env:

    OPENAI_API_KEY=sk-or-v1-...
    OPENAI_BASE_URL=https://openrouter.ai/api/v1
    CHAT_MODEL=z-ai/glm-5.2:free
    ROUTER_MODEL=z-ai/glm-5.2:free
    EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free
"""
from __future__ import annotations

import os


def _key() -> str:
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or ""
    )


def _base() -> str | None:
    return (os.environ.get("OPENAI_BASE_URL") or "").strip() or None


def chat_model_name(*, fast: bool = False) -> str:
    if fast:
        return (
            os.environ.get("ROUTER_MODEL")
            or os.environ.get("CHAT_MODEL")
            or "gpt-4o-mini"
        )
    return os.environ.get("CHAT_MODEL") or "gpt-4.1"


def embedding_model_name() -> str:
    return os.environ.get("EMBEDDING_MODEL") or "text-embedding-3-small"


def _openrouter_headers() -> dict:
    return {
        "HTTP-Referer": os.environ.get("APP_FRONTEND_URL", "http://localhost:5173"),
        "X-Title": "Saarthi",
    }


def chat_llm(*, temperature: float = 0, max_tokens: int | None = None, fast: bool = False, **extra):
    from langchain_openai import ChatOpenAI

    kwargs: dict = {
        "model": chat_model_name(fast=fast),
        "api_key": _key(),
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    base = _base()
    if base:
        kwargs["base_url"] = base
        kwargs["default_headers"] = _openrouter_headers()
    kwargs.update(extra)
    return ChatOpenAI(**kwargs)


def embeddings():
    from langchain_openai import OpenAIEmbeddings

    kwargs: dict = {
        "model": embedding_model_name(),
        "api_key": _key(),
        "check_embedding_ctx_length": False,
    }
    base = _base()
    if base:
        kwargs["base_url"] = base
    return OpenAIEmbeddings(**kwargs)


def async_openai():
    from openai import AsyncOpenAI

    kwargs: dict = {"api_key": _key()}
    base = _base()
    if base:
        kwargs["base_url"] = base
        kwargs["default_headers"] = _openrouter_headers()
    return AsyncOpenAI(**kwargs)
