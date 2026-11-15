from __future__ import annotations

import os

import scripts.env_loader as env_loader


def test_missing_file_is_a_noop(tmp_path):
    assert env_loader.load_env_file(tmp_path / "does_not_exist.env") == 0


def test_sets_vars_from_file(tmp_path, monkeypatch):
    path = tmp_path / ".env.kb"
    path.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)

    count = env_loader.load_env_file(path)

    assert count == 2
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_skips_blank_lines_and_comments(tmp_path, monkeypatch):
    path = tmp_path / ".env.kb"
    path.write_text("# a comment\n\nFOO=bar\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)

    assert env_loader.load_env_file(path) == 1
    assert os.environ["FOO"] == "bar"


def test_strips_quotes(tmp_path, monkeypatch):
    path = tmp_path / ".env.kb"
    path.write_text('FOO="bar"\n', encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)

    env_loader.load_env_file(path)
    assert os.environ["FOO"] == "bar"


def test_never_overwrites_an_already_set_real_env_var(tmp_path, monkeypatch):
    """The documented override mechanism: a shell-set value always wins."""
    path = tmp_path / ".env.kb"
    path.write_text("FOO=from_file\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "from_shell")

    count = env_loader.load_env_file(path)

    assert count == 0
    assert os.environ["FOO"] == "from_shell"
