# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_config_loading.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Effective-config / theme-precedence tests using an isolated HOME."""

from __future__ import annotations

from pathlib import Path

import pytest

from ecli.utils.themes import THEME_ENV_VAR, resolve_theme
from ecli.utils.utils import load_config


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv(THEME_ENV_VAR, raising=False)
    cfg_dir = tmp_path / ".config" / "ecli"
    cfg_dir.mkdir(parents=True)
    return cfg_dir


def test_user_config_theme_overrides_default(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 4\n", encoding="utf-8")

    config = load_config()

    assert config["theme"] == 4  # user value beats DEFAULT_CONFIG (5)
    assert resolve_theme(config).theme_id == 4
    assert config["_loaded_config_path"] == str(isolated_home / "config.toml")


def test_effective_config_theme_1_resolves_theme_1(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 1\n", encoding="utf-8")
    assert resolve_theme(load_config()).theme_id == 1


def test_effective_config_theme_8_resolves_theme_8(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 8\n", encoding="utf-8")
    assert resolve_theme(load_config()).theme_id == 8


def test_legacy_theme_table_config_is_migrated_to_root_theme(
    isolated_home: Path,
) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text(
        '[theme]\nname = "dark"\n[theme.ui]\nbackground = "#252526"\n[editor]\ntab_size = 4\n',
        encoding="utf-8",
    )
    config = load_config()
    # load_config migrates the file: 'theme' is now a root int, resolving to dark.
    assert config["theme"] == 5
    assert resolve_theme(config).theme_id == 5
    # The on-disk file gained an editable root 'theme = N' and kept other sections.
    text = cfg.read_text(encoding="utf-8")
    assert "theme = 5" in text
    assert "[editor]" in text
    assert cfg.with_name("config.toml.bak").exists()
    # The user can now switch by editing that single line.
    cfg.write_text(text.replace("theme = 5", "theme = 2"), encoding="utf-8")
    assert resolve_theme(load_config()).theme_id == 2


def test_light_legacy_theme_migrates_to_theme_one(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text(
        '[theme]\nname = "light"\n', encoding="utf-8"
    )
    assert resolve_theme(load_config()).theme_id == 1


def test_migration_is_noop_for_root_theme_config(isolated_home: Path) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text("theme = 7\n[editor]\ntab_size = 4\n", encoding="utf-8")
    load_config()
    # No legacy table -> no migration, no backup.
    assert not cfg.with_name("config.toml.bak").exists()
    assert "theme = 7" in cfg.read_text(encoding="utf-8")


def test_env_overrides_user_config_via_load(isolated_home: Path, monkeypatch) -> None:
    (isolated_home / "config.toml").write_text("theme = 2\n", encoding="utf-8")
    monkeypatch.setenv(THEME_ENV_VAR, "6")
    assert resolve_theme(load_config()).theme_id == 6


def test_loaded_config_path_recorded_when_present(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 3\n", encoding="utf-8")
    config = load_config()
    assert "_loaded_config_path" in config
    assert config["_loaded_config_path"].endswith("config.toml")
