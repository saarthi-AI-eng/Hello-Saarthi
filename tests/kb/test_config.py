from __future__ import annotations

import pytest

from src.knowledge_base.config import KBConfig, load_config


def test_load_config_raises_clear_error_without_data_root(tmp_path, monkeypatch):
    monkeypatch.delenv("SAARTHI_KB_DATA_ROOT", raising=False)
    missing_yaml = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ValueError, match="SAARTHI_KB_DATA_ROOT"):
        load_config(missing_yaml)


def test_env_var_overrides_yaml_value(tmp_path, monkeypatch):
    yaml_path = tmp_path / "kb.yaml"
    yaml_path.write_text(f"data_root: '{(tmp_path / 'from_yaml').as_posix()}'\nembedding_batch_size: 8\n", encoding="utf-8")
    monkeypatch.setenv("SAARTHI_KB_EMBED_BATCH_SIZE", "32")

    config = load_config(yaml_path)

    assert config.embedding_batch_size == 32  # env var wins over YAML
    assert str(config.data_root) == str(tmp_path / "from_yaml")  # YAML value kept when no env override


def test_data_root_env_var_overrides_yaml_path(tmp_path, monkeypatch):
    yaml_path = tmp_path / "kb.yaml"
    yaml_path.write_text(f"data_root: '{(tmp_path / 'from_yaml').as_posix()}'\n", encoding="utf-8")
    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(tmp_path / "from_env"))

    config = load_config(yaml_path)

    assert str(config.data_root) == str(tmp_path / "from_env")


def test_ensure_directories_creates_every_subdirectory(tmp_path):
    config = KBConfig(data_root=tmp_path / "root")
    config.ensure_directories()

    assert config.normalized_dir.exists()
    assert config.chunks_dir.exists()
    assert config.embeddings_dir.exists()
    assert config.manifests_dir.exists()
    assert config.reports_dir.exists()


def test_backend_defaults_to_local_with_no_cloud_env(tmp_path, monkeypatch):
    for var in ("QDRANT_BACKEND", "QDRANT_CLOUD_URL", "QDRANT_CLOUD_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(tmp_path))

    config = load_config(tmp_path / "does_not_exist.yaml")

    assert config.qdrant_backend == "local"
    assert config.effective_qdrant_url == config.qdrant_url
    assert config.effective_qdrant_api_key == config.qdrant_api_key


def test_qdrant_backend_env_var_switches_to_cloud(tmp_path, monkeypatch):
    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("QDRANT_BACKEND", "cloud")
    monkeypatch.setenv("QDRANT_CLOUD_URL", "https://example.cloud.qdrant.io")
    monkeypatch.setenv("QDRANT_CLOUD_API_KEY", "fake-test-key")

    config = load_config(tmp_path / "does_not_exist.yaml")

    assert config.qdrant_backend == "cloud"
    assert config.effective_qdrant_url == "https://example.cloud.qdrant.io"
    assert config.effective_qdrant_api_key == "fake-test-key"


def test_invalid_qdrant_backend_value_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("QDRANT_BACKEND", "nonsense")

    with pytest.raises(ValueError, match="Invalid QDRANT_BACKEND"):
        load_config(tmp_path / "does_not_exist.yaml")


def test_qdrant_local_url_overrides_qdrant_url(tmp_path, monkeypatch):
    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.setenv("QDRANT_LOCAL_URL", "http://custom-local:6333")

    config = load_config(tmp_path / "does_not_exist.yaml")

    assert config.qdrant_url == "http://custom-local:6333"


def test_local_mode_does_not_require_cloud_env_vars(tmp_path, monkeypatch):
    for var in ("QDRANT_BACKEND", "QDRANT_CLOUD_URL", "QDRANT_CLOUD_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(tmp_path))

    config = load_config(tmp_path / "does_not_exist.yaml")  # must not raise

    assert config.qdrant_backend == "local"
