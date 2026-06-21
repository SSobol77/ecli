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

import tomllib
from pathlib import Path

import pytest

from ecli.utils.themes import THEME_ENV_VAR, resolve_theme
from ecli.utils.utils import (
    CONFIG_FILENAME,
    DEFAULT_CONFIG,
    load_config,
    migrate_legacy_theme_config,
)


REPO_CONFIG = Path(__file__).resolve().parents[2] / "config.toml"


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv(THEME_ENV_VAR, raising=False)
    cfg_dir = tmp_path / ".config" / "ecli"
    cfg_dir.mkdir(parents=True)
    return cfg_dir


def test_user_config_theme_overrides_default(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 207\n", encoding="utf-8")

    config = load_config()

    assert config["theme"] == 207  # user value beats DEFAULT_CONFIG
    assert resolve_theme(config).theme_id == 207
    assert config["_loaded_config_path"] == str(isolated_home / "config.toml")


def test_effective_config_theme_207_resolves_dark_plus(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 207\n", encoding="utf-8")
    assert resolve_theme(load_config()).theme_id == 207


def test_effective_config_theme_181_resolves_compatibility_theme(
    isolated_home: Path,
) -> None:
    (isolated_home / "config.toml").write_text("theme = 181\n", encoding="utf-8")
    assert resolve_theme(load_config()).theme_id == 181


def test_legacy_theme_table_config_is_migrated_to_root_theme(
    isolated_home: Path,
) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text(
        '[theme]\nname = "dark"\n[theme.ui]\nbackground = "#252526"\n[editor]\ntab_size = 4\n',
        encoding="utf-8",
    )
    config = load_config()
    # load_config migrates the file: 'theme' is now a root compatibility id.
    assert config["theme"] == 281
    assert resolve_theme(config).theme_id == 281
    # The on-disk file gained an editable root 'theme = N' and kept other sections.
    text = cfg.read_text(encoding="utf-8")
    assert "theme = 281" in text
    assert "[editor]" in text
    assert cfg.with_name("config.toml.pre-extension-theme-numbering.bak").exists()
    assert config["_migration_warnings"]
    # The user can now switch by editing that single line.
    cfg.write_text(text.replace("theme = 281", "theme = 181"), encoding="utf-8")
    assert resolve_theme(load_config()).theme_id == 181


def test_config_filename_constant_names_user_config() -> None:
    assert CONFIG_FILENAME == "config.toml"


def test_light_legacy_theme_migrates_to_theme_one(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text(
        '[theme]\nname = "light"\n', encoding="utf-8"
    )
    assert resolve_theme(load_config()).theme_id == 181


def test_migration_is_noop_for_root_theme_config(isolated_home: Path) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text("theme = 208\n[editor]\ntab_size = 4\n", encoding="utf-8")
    load_config()
    # No legacy table -> no migration, no backup.
    assert not cfg.with_name("config.toml.pre-extension-theme-numbering.bak").exists()
    assert "theme = 208" in cfg.read_text(encoding="utf-8")


def test_theme_migration_refuses_backup_outside_trusted_config_dir(
    isolated_home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "attacker-controlled-name.toml"
    original = '[theme]\nname = "dark"\n'
    outside.write_text(original, encoding="utf-8")

    assert migrate_legacy_theme_config(outside) is False
    assert outside.read_text(encoding="utf-8") == original
    assert not (
        tmp_path / "attacker-controlled-name.toml.pre-extension-theme-numbering.bak"
    ).exists()
    assert not (
        isolated_home / "config.toml.pre-extension-theme-numbering.bak"
    ).exists()


def test_theme_migration_writes_fixed_backup_inside_trusted_config_dir(
    isolated_home: Path,
) -> None:
    cfg = isolated_home / CONFIG_FILENAME
    original = '[theme]\nname = "dark"\n'
    cfg.write_text(original, encoding="utf-8")

    assert migrate_legacy_theme_config(cfg) is True

    backup = isolated_home / "config.toml.pre-extension-theme-numbering.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original


def test_env_overrides_user_config_via_load(isolated_home: Path, monkeypatch) -> None:
    (isolated_home / "config.toml").write_text("theme = 181\n", encoding="utf-8")
    monkeypatch.setenv(THEME_ENV_VAR, "208")
    assert resolve_theme(load_config()).theme_id == 208


def test_loaded_config_path_recorded_when_present(isolated_home: Path) -> None:
    (isolated_home / "config.toml").write_text("theme = 207\n", encoding="utf-8")
    config = load_config()
    assert "_loaded_config_path" in config
    assert config["_loaded_config_path"].endswith("config.toml")


def test_obsolete_tables_are_migrated_out_of_user_config(isolated_home: Path) -> None:
    # A stale pre-#102 user config (old data tables + transitional legacy engine)
    # must be migrated on load so the upgraded user gets the TextMate engine.
    cfg = isolated_home / "config.toml"
    cfg.write_text(
        "theme = 17\n"
        '[extensions]\nsyntax_engine = "legacy"\n'
        '[comments.python]\nline_prefix = "# "\n'
        '[[syntax_highlighting.python.patterns]]\npattern = "x"\ncolor = "keyword"\n'
        "[settings]\nauto_save_interval = 9\n",
        encoding="utf-8",
    )
    config = load_config()
    text = cfg.read_text(encoding="utf-8")

    assert "[comments.python]" not in text
    assert "[[syntax_highlighting" not in text
    assert 'syntax_engine = "extension"' in text  # transitional default flipped
    assert "auto_save_interval = 9" in text  # unrelated settings preserved
    assert cfg.with_name("config.toml.pre-textmate.bak").exists()
    assert config["extensions"]["syntax_engine"] == "extension"
    assert config["settings"]["auto_save_interval"] == 9


def test_pre_extension_root_theme_alias_migrates_to_legacy_compatibility(
    isolated_home: Path,
) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text("theme = 5\n[editor]\ntab_size = 4\n", encoding="utf-8")
    config = load_config()
    assert config["theme"] == 281
    assert resolve_theme(config).theme_id == 281
    assert "theme = 281" in cfg.read_text(encoding="utf-8")
    assert cfg.with_name("config.toml.pre-extension-theme-numbering.bak").exists()
    assert config["_migration_warnings"]


def test_transitional_theme_23_migrates_to_kimbie_dark(
    isolated_home: Path,
) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text(
        "# Professional themes are discovered from extensions.\n"
        "theme = 23\n[editor]\ntab_size = 4\n",
        encoding="utf-8",
    )
    config = load_config()
    assert config["theme"] == 213
    assert resolve_theme(config).name == "Kimbie Dark"
    assert "theme = 213" in cfg.read_text(encoding="utf-8")
    assert cfg.with_name("config.toml.pre-extension-theme-numbering.bak").exists()


def test_previous_compatibility_theme_102_migrates_to_pysh_dark(
    isolated_home: Path,
) -> None:
    cfg = isolated_home / "config.toml"
    cfg.write_text("theme = 102\n[editor]\ntab_size = 4\n", encoding="utf-8")
    config = load_config()
    assert config["theme"] == 281
    assert resolve_theme(config).name == "PySH Dark"


def test_extensions_layer_switches_default_through_loader(isolated_home: Path) -> None:
    # The Extensions Layer switches are exposed by the existing config loader via
    # DEFAULT_CONFIG. As of #102 the default syntax engine is "extension"
    # (TextMate tokenization, with automatic legacy fallback).
    extensions = load_config()["extensions"]
    assert extensions["enabled"] is True
    assert extensions["metadata_registry"] is True
    assert extensions["grammar_catalog"] is True
    assert extensions["language_detection"] is True
    assert extensions["syntax_engine"] == "extension"


def test_repository_config_is_small_user_facing_template() -> None:
    text = REPO_CONFIG.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert "keybindings" not in parsed
    assert "comments" not in parsed
    assert "syntax_highlighting" not in parsed
    assert "supported_formats" not in parsed
    assert "theme" in parsed
    for section in (
        "logging",
        "ai",
        "fonts",
        "editor",
        "extensions",
        "settings",
        "linter",
        "file_icons",
    ):
        assert section in parsed
    assert "models" in parsed["ai"]
    assert parsed["theme"] == 207


def test_default_config_matches_user_facing_template_keys() -> None:
    parsed = tomllib.loads(REPO_CONFIG.read_text(encoding="utf-8"))
    assert DEFAULT_CONFIG["theme"] == parsed["theme"]
    for key in ("logging", "fonts", "extensions", "settings", "linter", "file_icons"):
        assert DEFAULT_CONFIG[key] == parsed[key]
    for key, value in parsed["editor"].items():
        assert DEFAULT_CONFIG["editor"][key] == value


def test_theme_numbering_comment_is_public_contract() -> None:
    text = REPO_CONFIG.read_text(encoding="utf-8")
    assert "100-199 = light themes" in text
    assert "200-299 = dark themes" in text
    assert "300-399 = high-contrast themes" in text
    assert "1-8     = deprecated aliases" in text
    assert "800-899 = reserved" in text
