# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/utils/test_path_resolution.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Development-checkout vs installed-user config/log path resolution.

These tests pin the dev-mode contract: when ECLI runs from a source checkout it
must use ``<repo>/config.toml`` and ``<repo>/logs/editor.log`` and must never
create, read, migrate, or write ``~/.config/ecli``. Explicit ``ECLI_CONFIG_PATH``
/ ``ECLI_LOG_DIR`` overrides win over everything, and ``ECLI_FORCE_USER_CONFIG``
restores installed-user XDG behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ecli.utils.utils import (
    CONFIG_FILENAME,
    find_dev_project_root,
    load_config,
    resolve_config_path,
    resolve_env_file,
    resolve_log_dir,
)


def _make_fake_repo(root: Path) -> Path:
    """Create a minimal ECLI development-checkout layout under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname='ecli'\n", encoding="utf-8")
    (root / CONFIG_FILENAME).write_text("theme = 208\n", encoding="utf-8")
    (root / "src" / "ecli").mkdir(parents=True)
    return root


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME and clear ECLI path overrides; return the fake HOME dir."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for name in (
        "ECLI_CONFIG_PATH",
        "ECLI_LOG_DIR",
        "ECLI_FORCE_USER_CONFIG",
        "ECLI_THEME",
    ):
        monkeypatch.delenv(name, raising=False)
    return home


@pytest.fixture
def fake_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_env: Path
) -> Path:
    """Create a fake checkout and chdir into it so dev detection triggers."""
    repo = _make_fake_repo(tmp_path / "checkout")
    monkeypatch.chdir(repo)
    return repo


def _user_config_dir(home: Path) -> Path:
    return home / ".config" / "ecli"


# --------------------------------------------------------------------------- #
# 1. Development checkout: repo-local config + logs, no ~/.config/ecli.
# --------------------------------------------------------------------------- #


def test_dev_root_detected_from_repo_root(fake_repo: Path) -> None:
    assert find_dev_project_root() == fake_repo.resolve()


def test_dev_root_detected_from_nested_subdir(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = fake_repo / "src" / "ecli" / "deeper"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert find_dev_project_root() == fake_repo.resolve()


def test_dev_config_path_resolves_to_repo(fake_repo: Path) -> None:
    path, mode = resolve_config_path()
    assert mode == "development"
    assert path == fake_repo.resolve() / CONFIG_FILENAME


def test_dev_log_dir_resolves_to_repo_logs(fake_repo: Path) -> None:
    assert resolve_log_dir() == fake_repo.resolve() / "logs"


def test_dev_env_file_resolves_to_repo(fake_repo: Path) -> None:
    assert resolve_env_file() == fake_repo.resolve() / ".env"


def test_dev_load_config_reads_repo_and_skips_user_dir(
    fake_repo: Path, isolated_env: Path
) -> None:
    config = load_config()

    assert config["theme"] == 208
    assert config["_config_mode"] == "development"
    assert config["_loaded_config_path"] == str(fake_repo.resolve() / CONFIG_FILENAME)
    # No XDG path is referenced or created in development mode.
    assert "/.config/ecli" not in config["_loaded_config_path"]


# --------------------------------------------------------------------------- #
# 5. The development resolver must not mutate or copy into ~/.config/ecli.
# --------------------------------------------------------------------------- #


def test_dev_mode_does_not_create_or_mutate_user_config_dir(
    fake_repo: Path, isolated_env: Path
) -> None:
    user_dir = _user_config_dir(isolated_env)
    assert not user_dir.exists()

    load_config()

    # No ~/.config/ecli directory, config, .env, or migration backup appears.
    assert not user_dir.exists()
    assert not (user_dir / CONFIG_FILENAME).exists()
    assert not (user_dir / ".env").exists()


# --------------------------------------------------------------------------- #
# 2. ECLI_FORCE_USER_CONFIG disables dev detection -> installed-user XDG.
# --------------------------------------------------------------------------- #


def test_force_user_config_ignores_dev_detection(
    fake_repo: Path, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECLI_FORCE_USER_CONFIG", "1")

    assert find_dev_project_root() is None

    path, mode = resolve_config_path()
    assert mode == "user"
    assert path == _user_config_dir(isolated_env) / CONFIG_FILENAME
    assert resolve_log_dir() == _user_config_dir(isolated_env) / "logs"
    assert resolve_env_file() == _user_config_dir(isolated_env) / ".env"


# --------------------------------------------------------------------------- #
# 3. ECLI_CONFIG_PATH explicit override wins (even inside a dev checkout).
# --------------------------------------------------------------------------- #


def test_explicit_config_path_override_wins(
    fake_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "custom" / "my-config.toml"
    explicit.parent.mkdir(parents=True)
    explicit.write_text("theme = 201\n", encoding="utf-8")
    monkeypatch.setenv("ECLI_CONFIG_PATH", str(explicit))

    path, mode = resolve_config_path()
    assert mode == "override"
    assert path == explicit

    config = load_config()
    assert config["_config_mode"] == "override"
    assert config["theme"] == 201
    assert config["_loaded_config_path"] == str(explicit)


# --------------------------------------------------------------------------- #
# 4. ECLI_LOG_DIR explicit override wins (even inside a dev checkout).
# --------------------------------------------------------------------------- #


def test_explicit_log_dir_override_wins(
    fake_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit_logs = tmp_path / "custom-logs"
    monkeypatch.setenv("ECLI_LOG_DIR", str(explicit_logs))
    assert resolve_log_dir() == explicit_logs


# --------------------------------------------------------------------------- #
# Installed-user fallback (no checkout, no overrides).
# --------------------------------------------------------------------------- #


def test_user_mode_when_no_checkout(
    tmp_path: Path, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A directory with no ECLI markers: resolution falls back to user XDG.
    elsewhere = tmp_path / "not-a-checkout"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert find_dev_project_root() is None
    path, mode = resolve_config_path()
    assert mode == "user"
    assert path == _user_config_dir(isolated_env) / CONFIG_FILENAME
