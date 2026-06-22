# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the [linter] configuration surface used by F4 (#104)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from ecli.extensions.ecli_integration.diagnostics import LinterLayerConfig
from ecli.utils.utils import DEFAULT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[2]


def _config_toml() -> dict[str, object]:
    return tomllib.loads((REPO_ROOT / "config.toml").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Shipped [linter] table remains accepted.
# --------------------------------------------------------------------------- #


def test_config_toml_ships_linter_table() -> None:
    linter = _config_toml()["linter"]
    assert linter["enabled"] is True
    assert linter["auto_install"] is True
    assert isinstance(linter["exclude"], list)


def test_from_config_parses_shipped_and_default_config() -> None:
    for source in (_config_toml(), DEFAULT_CONFIG):
        config = LinterLayerConfig.from_config(source)
        assert config.enabled is True
        assert config.auto_install is True
        assert config.exclude == tuple(source["linter"]["exclude"])  # type: ignore[index]
        assert config.diagnostics == ()


def test_defaults_when_section_missing() -> None:
    config = LinterLayerConfig.from_config({})
    assert config.enabled is True
    assert config.auto_install is True
    assert config.exclude  # non-empty default
    assert config.diagnostics == ()


# --------------------------------------------------------------------------- #
# Disabled / validation.
# --------------------------------------------------------------------------- #


def test_disabled_state_is_honored() -> None:
    config = LinterLayerConfig.from_section({"enabled": False})
    assert config.enabled is False


def test_invalid_enabled_falls_back_with_diagnostic() -> None:
    config = LinterLayerConfig.from_section({"enabled": "yes"})
    assert config.enabled is True
    assert any("enabled must be a boolean" in d.message for d in config.diagnostics)


def test_non_mapping_section_is_diagnosed() -> None:
    config = LinterLayerConfig.from_section("not-a-table")
    assert any(d.level == "warning" for d in config.diagnostics)


def test_invalid_exclude_type_falls_back() -> None:
    config = LinterLayerConfig.from_section({"exclude": "nope"})
    assert config.exclude == LinterLayerConfig().exclude
    assert any("exclude must be a list" in d.message for d in config.diagnostics)


def test_non_string_exclude_entries_are_dropped() -> None:
    config = LinterLayerConfig.from_section({"exclude": [".git", 5, ""]})
    assert config.exclude == (".git",)
    assert any(
        "exclude entries must be strings" in d.message for d in config.diagnostics
    )


# --------------------------------------------------------------------------- #
# auto_install is parsed but never acted upon.
# --------------------------------------------------------------------------- #


def test_auto_install_is_never_performed() -> None:
    config = LinterLayerConfig.from_section({"auto_install": True})
    assert config.auto_install is True
    assert config.performs_auto_install is False


# --------------------------------------------------------------------------- #
# exclude glob matching.
# --------------------------------------------------------------------------- #


def test_is_excluded_matches_segments_and_patterns() -> None:
    config = LinterLayerConfig.from_section(
        {"exclude": [".git", "**pycache**", ".venv"]}
    )
    assert config.is_excluded(".venv/lib/mod.py") is True
    assert config.is_excluded("pkg/__pycache__/mod.py") is True
    assert config.is_excluded("src/pkg/module.py") is False
    assert config.is_excluded(None) is False
