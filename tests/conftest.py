from __future__ import annotations

import pytest

import scripts.env_loader as env_loader


@pytest.fixture(autouse=True)
def isolate_from_real_env_kb(tmp_path, monkeypatch):
    """Repo-wide: load_env_file() is called by src/knowledge_base/config.py's
    load_config() AND by scripts/ingest_notes.py and ingest_videos.py's own
    main(), and it mutates the real os.environ directly (not via
    monkeypatch). Any test that reaches any of those — not just tests/kb —
    would otherwise leak this machine's real .env.kb values
    (SAARTHI_KB_DATA_ROOT, QDRANT_BACKEND, the OCR flags, ...) into every
    OTHER test for the rest of the pytest process, since os.environ
    persists across tests regardless of which directory they're in.
    Confirmed: a test calling scripts.ingest_notes.main() from outside
    tests/kb leaked SAARTHI_KB_DATA_ROOT and broke an unrelated tests/kb
    test later in the same run. Pointing the loader at a nonexistent path
    makes load_env_file() a no-op during every test, everywhere."""
    monkeypatch.setattr(env_loader, "DEFAULT_ENV_KB_PATH", tmp_path / "nonexistent.env.kb")
