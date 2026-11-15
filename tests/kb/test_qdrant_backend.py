"""Backend selection (local vs Qdrant Cloud) — Part 2 of the Cloud
extension. Mocks QdrantClient entirely; no real Cloud cluster is used or
required by this suite."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.knowledge_base.qdrant_store import QdrantKBStore


def test_local_is_the_default_backend(kb_config):
    assert kb_config.qdrant_backend == "local"


def test_local_client_creation_needs_no_cloud_credentials(kb_config):
    kb_config.qdrant_cloud_url = ""
    kb_config.qdrant_cloud_api_key = None
    store = QdrantKBStore(kb_config)
    with patch("qdrant_client.QdrantClient") as mock_client:
        store._ensure_client()
    mock_client.assert_called_once_with(url=kb_config.qdrant_url, api_key=None)


def test_cloud_client_creation_uses_cloud_fields(kb_config):
    kb_config.qdrant_backend = "cloud"
    kb_config.qdrant_cloud_url = "https://example.cloud.qdrant.io"
    kb_config.qdrant_cloud_api_key = "fake-test-key"
    store = QdrantKBStore(kb_config)
    with patch("qdrant_client.QdrantClient") as mock_client:
        store._ensure_client()
    mock_client.assert_called_once_with(url="https://example.cloud.qdrant.io", api_key="fake-test-key")


def test_cloud_backend_missing_url_raises_clear_error(kb_config):
    kb_config.qdrant_backend = "cloud"
    kb_config.qdrant_cloud_url = ""
    kb_config.qdrant_cloud_api_key = "fake-test-key"
    store = QdrantKBStore(kb_config)
    with pytest.raises(ValueError, match="QDRANT_CLOUD_URL"):
        store._ensure_client()


def test_cloud_backend_missing_api_key_raises_clear_error(kb_config):
    kb_config.qdrant_backend = "cloud"
    kb_config.qdrant_cloud_url = "https://example.cloud.qdrant.io"
    kb_config.qdrant_cloud_api_key = None
    store = QdrantKBStore(kb_config)
    with pytest.raises(ValueError, match="QDRANT_CLOUD_API_KEY"):
        store._ensure_client()


def test_cloud_backend_rejects_non_https_url(kb_config):
    kb_config.qdrant_backend = "cloud"
    kb_config.qdrant_cloud_url = "http://example.cloud.qdrant.io"  # not https
    kb_config.qdrant_cloud_api_key = "fake-test-key"
    store = QdrantKBStore(kb_config)
    with pytest.raises(ValueError, match="https"):
        store._ensure_client()


def test_invalid_backend_value_raises_clear_error(kb_config):
    kb_config.qdrant_backend = "not_a_real_backend"
    store = QdrantKBStore(kb_config)
    with pytest.raises(ValueError, match="Invalid qdrant_backend"):
        store._ensure_client()


def test_local_mode_never_touches_cloud_fields_even_if_set(kb_config):
    """Backend isolation: cloud credentials being present must not leak
    into a local-mode connection."""
    kb_config.qdrant_cloud_url = "https://example.cloud.qdrant.io"
    kb_config.qdrant_cloud_api_key = "fake-test-key"
    store = QdrantKBStore(kb_config)
    with patch("qdrant_client.QdrantClient") as mock_client:
        store._ensure_client()
    _, kwargs = mock_client.call_args
    assert kwargs["url"] == kb_config.qdrant_url
    assert kwargs["api_key"] != "fake-test-key"


def test_error_messages_never_contain_the_api_key_value(kb_config):
    kb_config.qdrant_backend = "cloud"
    kb_config.qdrant_cloud_url = "https://example.cloud.qdrant.io"
    kb_config.qdrant_cloud_api_key = "super-secret-value-12345"
    store = QdrantKBStore(kb_config)

    with patch("qdrant_client.QdrantClient", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError) as excinfo:
            store.verify_connection()
    assert "super-secret-value-12345" not in str(excinfo.value)


def test_verify_connection_returns_true_on_success(kb_config):
    store = QdrantKBStore(kb_config)
    fake_client = type("Fake", (), {"get_collections": lambda self: []})()
    store._client = fake_client
    assert store.verify_connection() is True


def test_to_dict_never_includes_real_api_key_values(kb_config):
    kb_config.qdrant_api_key = "local-secret"
    kb_config.qdrant_cloud_api_key = "cloud-secret"
    d = kb_config.to_dict()
    assert "local-secret" not in str(d)
    assert "cloud-secret" not in str(d)
    assert d["qdrant_api_key"] == "<redacted>"
    assert d["qdrant_cloud_api_key"] == "<redacted>"
