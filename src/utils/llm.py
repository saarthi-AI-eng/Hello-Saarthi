"""
Single place for chat + embeddings, with tiered model routing (WBS 3.2.2).

Default: OpenAI (gpt-4.1 / gpt-4o-mini / text-embedding-3-small).

OpenRouter (GLM chat + Nemotron embeddings) — set in saarthi_backend/.env:

    OPENAI_API_KEY=sk-or-v1-...
    OPENAI_BASE_URL=https://openrouter.ai/api/v1
    CHAT_MODEL=z-ai/glm-5.2:free
    ROUTER_MODEL=z-ai/glm-5.2:free
    EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free

Tiers (all optional — with none of these set, behaviour is unchanged):

    Tier 0  semantic cache hit (no model call; see src/cache)
    Tier 1  small / local model. LOCAL_BASE_URL, LOCAL_API_KEY, LOCAL_CHAT_MODEL
            (default: the OPENAI_* / CHAT_MODEL settings above)
    Tier 2  full / cloud model.  CLOUD_BASE_URL, CLOUD_API_KEY, CLOUD_CHAT_MODEL
            Used for complex questions while src.utils.budget.cloud_allowed();
            otherwise the request silently drops to Tier 1.

Router / critic / follow-up rewrite calls (fast=True) always use Tier 1 with
ROUTER_MODEL. Embeddings always use the base OPENAI_* settings so every index
stays in one vector space.
"""
from __future__ import annotations

import os
from contextvars import ContextVar

# Tier chosen for the current request (set by the chat policy; None = Tier 1).
_TIER: ContextVar[int | None] = ContextVar("saarthi_llm_tier", default=None)


def set_tier(tier: int | None):
    """Set the model tier for the current context. Returns a token for reset_tier()."""
    return _TIER.set(tier)


def reset_tier(token) -> None:
    _TIER.reset(token)


def _key() -> str:
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or ""
    )


def _base() -> str | None:
    return (os.environ.get("OPENAI_BASE_URL") or "").strip() or None


def tier2_configured() -> bool:
    return bool((os.environ.get("CLOUD_CHAT_MODEL") or "").strip())


def _tier_settings(tier: int) -> dict:
    """base_url / api_key / model for a tier (Tier 2 falls back to Tier 1 if unset)."""
    if tier == 2 and tier2_configured():
        return {
            "base_url": (os.environ.get("CLOUD_BASE_URL") or "").strip() or None,
            "api_key": os.environ.get("CLOUD_API_KEY") or _key(),
            "model": os.environ["CLOUD_CHAT_MODEL"].strip(),
        }
    return {
        "base_url": (os.environ.get("LOCAL_BASE_URL") or "").strip() or _base(),
        "api_key": os.environ.get("LOCAL_API_KEY") or _key(),
        "model": (os.environ.get("LOCAL_CHAT_MODEL") or "").strip() or os.environ.get("CHAT_MODEL") or "gpt-4.1",
    }


def effective_tier(tier: int | None = None) -> int:
    """The tier that will actually serve a non-fast call (budget-checked)."""
    t = tier if tier is not None else (_TIER.get() or 1)
    if t == 2:
        if not tier2_configured():
            return 1
        from src.utils.budget import cloud_allowed
        ok, _ = cloud_allowed()
        return 2 if ok else 1
    return 1


def chat_model_name(*, fast: bool = False, tier: int | None = None) -> str:
    if fast:
        return (
            os.environ.get("ROUTER_MODEL")
            or _tier_settings(1)["model"]
            or "gpt-4o-mini"
        )
    return _tier_settings(effective_tier(tier))["model"]


def embedding_model_name() -> str:
    return os.environ.get("EMBEDDING_MODEL") or "text-embedding-3-small"


def _openrouter_headers() -> dict:
    return {
        "HTTP-Referer": os.environ.get("APP_FRONTEND_URL", "http://localhost:5173"),
        "X-Title": "Saarthi",
    }


def _usage_callback(tier: int, model: str):
    """LangChain callback that records token usage for budget + traces."""
    from langchain_core.callbacks import BaseCallbackHandler

    class _Usage(BaseCallbackHandler):
        def on_llm_end(self, response, **kwargs):
            from src.utils import budget
            usage = (getattr(response, "llm_output", None) or {}).get("token_usage") or {}
            p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if p is None:
                text = ""
                for gens in getattr(response, "generations", []) or []:
                    for g in gens:
                        text += getattr(g, "text", "") or ""
                budget.record(tier, model, 0, budget.estimate_tokens(text), estimated=True)
            else:
                budget.record(tier, model, p, c or 0)

    return _Usage()


def chat_llm(*, temperature: float = 0, max_tokens: int | None = None, fast: bool = False, tier: int | None = None, **extra):
    from langchain_openai import ChatOpenAI

    t = 1 if fast else effective_tier(tier)
    cfg = _tier_settings(t)
    model = chat_model_name(fast=fast, tier=tier)
    kwargs: dict = {
        "model": model,
        "api_key": cfg["api_key"],
        "temperature": temperature,
        "callbacks": [_usage_callback(t, model)],
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
        kwargs["default_headers"] = _openrouter_headers()
        if max_tokens is not None and "api.openai.com" not in cfg["base_url"]:
            # langchain-openai sends `max_completion_tokens`, which Ollama's OpenAI-compatible
            # API ignores (a 1B router once generated 40,960 tokens). Send the legacy field too.
            kwargs["extra_body"] = {**(extra.pop("extra_body", None) or {}), "max_tokens": max_tokens}
    kwargs.update(extra)
    return ChatOpenAI(**kwargs)


_EMB_CACHE: dict[tuple, object] = {}


def embeddings():
    """Shared client per (model, key, base): building one per call costs connection set-up
    on every cache check / classification (the query classifier must stay < 50 ms)."""
    from langchain_openai import OpenAIEmbeddings

    cache_key = (embedding_model_name(), _key(), _base())
    client = _EMB_CACHE.get(cache_key)
    if client is not None:
        return client
    kwargs: dict = {
        "model": embedding_model_name(),
        "api_key": _key(),
        "check_embedding_ctx_length": False,
    }
    base = _base()
    if base:
        kwargs["base_url"] = base
    client = OpenAIEmbeddings(**kwargs)
    _EMB_CACHE[cache_key] = client
    return client


def async_openai(*, tier: int | None = None):
    from openai import AsyncOpenAI

    cfg = _tier_settings(effective_tier(tier))
    kwargs: dict = {"api_key": cfg["api_key"]}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
        kwargs["default_headers"] = _openrouter_headers()
    return AsyncOpenAI(**kwargs)
