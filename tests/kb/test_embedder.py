from __future__ import annotations

import sys
import types

import pytest

from src.knowledge_base.embedder import BGEEmbedder, append_checkpoint, detect_embedding_device, load_checkpoint


def test_detect_embedding_device_honors_explicit_choice():
    assert detect_embedding_device("cpu") == "cpu"
    assert detect_embedding_device("cuda") == "cuda"


def test_detect_embedding_device_auto_falls_back_to_cpu_when_torch_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # import torch -> ImportError-like failure path
    assert detect_embedding_device("auto") == "cpu"


class _FakeDenseOnly:
    """Mimics numpy array .tolist() without importing numpy — keeps this test's own dependencies minimal."""

    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeBGEM3Model:
    calls = []

    def __init__(self, *a, **k):
        pass

    def encode(self, texts, batch_size, max_length, return_dense, return_sparse, return_colbert_vecs):
        _FakeBGEM3Model.calls.append(len(texts))
        return {"dense_vecs": [_FakeDenseOnly([0.1] * 1024) for _ in texts]}


@pytest.fixture
def fake_flagembedding(monkeypatch):
    _FakeBGEM3Model.calls = []
    module = types.ModuleType("FlagEmbedding")
    module.BGEM3FlagModel = _FakeBGEM3Model
    monkeypatch.setitem(sys.modules, "FlagEmbedding", module)
    yield _FakeBGEM3Model


def test_embed_texts_returns_one_vector_per_text(kb_config, fake_flagembedding):
    embedder = BGEEmbedder(kb_config)
    embedder.device = "cpu"

    vectors = embedder.embed_texts(["a", "b", "c"], show_progress=False)

    assert len(vectors) == 3
    assert len(vectors[0]) == 1024


def test_embed_texts_batches_at_configured_size(kb_config, fake_flagembedding):
    kb_config.embedding_batch_size = 2
    embedder = BGEEmbedder(kb_config)
    embedder.device = "cpu"

    embedder.embed_texts(["a", "b", "c", "d", "e"], show_progress=False)

    assert fake_flagembedding.calls == [2, 2, 1]


def test_embed_texts_raises_clear_error_without_flagembedding_installed(kb_config, monkeypatch):
    monkeypatch.setitem(sys.modules, "FlagEmbedding", None)
    embedder = BGEEmbedder(kb_config)

    with pytest.raises(RuntimeError, match="FlagEmbedding is not installed"):
        embedder.embed_texts(["a"])


def test_checkpoint_round_trip(tmp_path):
    path = tmp_path / "checkpoint.jsonl"
    assert load_checkpoint(path) == {}

    append_checkpoint(path, "chunk_a", [0.1, 0.2], content_hash="h1")
    append_checkpoint(path, "chunk_b", [0.3, 0.4], content_hash="h2")

    done = load_checkpoint(path)
    assert done == {
        "chunk_a": {"vector": [0.1, 0.2], "content_hash": "h1"},
        "chunk_b": {"vector": [0.3, 0.4], "content_hash": "h2"},
    }
