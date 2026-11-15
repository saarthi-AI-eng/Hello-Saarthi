from __future__ import annotations

import pytest

from src.knowledge_base.config import KBConfig

# isolate_from_real_env_kb (autouse) now lives in tests/conftest.py,
# applied repo-wide — see that file for why.


@pytest.fixture
def kb_config(tmp_path):
    config = KBConfig(data_root=tmp_path / "SaarthiDataTest")
    config.ensure_directories()
    return config
