"""Shared fixtures for the content-management pipeline test suite.

No test in this package makes a real network call: OpenAI embeddings are
replaced with FakeEmbeddings (deterministic, hash-based), and no test
requires a GPU, a real Whisper model, or a real Tesseract/OCR call unless
explicitly mocked at the pytesseract boundary.
"""
from __future__ import annotations

import hashlib
from typing import List

import pytest
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    """Deterministic, offline stand-in for langchain_openai.OpenAIEmbeddings.

    Must subclass langchain_core.embeddings.Embeddings — langchain_community's
    FAISS does an isinstance() check (not duck typing) to decide whether to
    call .embed_query()/.embed_documents() vs. treat the object as a raw
    callable, so a plain duck-typed class fails at query time.
    """

    def __init__(self, model: str = "fake", **kwargs):
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:16]]


@pytest.fixture
def fake_embeddings_patch(monkeypatch):
    """Patch langchain_openai.OpenAIEmbeddings everywhere it's lazily imported from."""
    import langchain_openai

    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", FakeEmbeddings)
    return FakeEmbeddings


@pytest.fixture(autouse=True)
def isolated_ingestion_log(tmp_path, monkeypatch):
    """Never let any test append to the real repo-root logs/ingestion_log.json.

    scripts.content_common.log_operation() resolves its default log_path
    lazily from this module attribute, so patching it here redirects every
    caller across the pipeline (build_knowledge_base, update_knowledge_base,
    ingest_videos, ingest_notes, ...) even though none of them pass
    log_path explicitly.
    """
    import scripts.content_common as content_common

    monkeypatch.setattr(content_common, "INGESTION_LOG_PATH", tmp_path / "ingestion_log.json")
