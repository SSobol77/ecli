# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extension_layer_config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the [extensions] configuration surface (#101).

These verify that the shipped ``config.toml`` and the ``DEFAULT_CONFIG`` fallback
expose the required data-only Extensions Layer switches, that
``ExtensionLayerConfig`` parses and validates them deterministically, that no
configuration value can enable an extension runtime, and that the legacy regex
syntax highlighter is preserved (not removed or disabled) in #101.
"""

from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

from ecli.extensions.ecli_integration import ExtensionLayerConfig
from ecli.utils.utils import DEFAULT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_EXTENSIONS_DEFAULTS = {
    "enabled": True,
    "metadata_registry": True,
    "grammar_catalog": True,
    "language_detection": True,
    "syntax_engine": "extension",
}


def _config_toml() -> dict[str, object]:
    return tomllib.loads((REPO_ROOT / "config.toml").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Shipped defaults.
# --------------------------------------------------------------------------- #


def test_config_toml_ships_extensions_defaults() -> None:
    extensions = _config_toml()["extensions"]
    assert extensions == REQUIRED_EXTENSIONS_DEFAULTS


def test_default_config_fallback_exposes_extensions() -> None:
    assert DEFAULT_CONFIG["extensions"] == REQUIRED_EXTENSIONS_DEFAULTS


def test_from_config_parses_default_config() -> None:
    config = ExtensionLayerConfig.from_config(DEFAULT_CONFIG)
    assert config.enabled
    assert config.metadata_registry
    assert config.grammar_catalog
    assert config.language_detection
    assert config.syntax_engine == "extension"
    assert config.diagnostics == ()


# --------------------------------------------------------------------------- #
# Defaults + validation.
# --------------------------------------------------------------------------- #


def test_dataclass_defaults() -> None:
    config = ExtensionLayerConfig()
    assert (config.enabled, config.metadata_registry) == (True, True)
    assert (config.grammar_catalog, config.language_detection) == (True, True)
    assert config.syntax_engine == "legacy"
    assert config.uses_legacy_syntax is True


def test_missing_section_uses_defaults() -> None:
    config = ExtensionLayerConfig.from_config({})
    assert config.enabled and config.uses_legacy_syntax
    assert config.diagnostics == ()


def test_non_mapping_section_is_diagnosed() -> None:
    config = ExtensionLayerConfig.from_section("not-a-table")
    assert any(d.level == "warning" for d in config.diagnostics)


def test_syntax_engine_legacy_is_preserved() -> None:
    config = ExtensionLayerConfig.from_section({"syntax_engine": "legacy"})
    assert config.syntax_engine == "legacy"
    assert config.diagnostics == ()


def test_syntax_engine_extension_is_accepted() -> None:
    # As of #102, "extension" is a valid selection of the extension-backed
    # syntax-service boundary. It does not enable any runtime, and rendering
    # still falls back to legacy (proven by the syntax-service tests).
    config = ExtensionLayerConfig.from_section({"syntax_engine": "extension"})
    assert config.syntax_engine == "extension"
    assert config.uses_legacy_syntax is False
    assert config.diagnostics == ()


def test_unknown_syntax_engine_falls_back_to_legacy() -> None:
    config = ExtensionLayerConfig.from_section({"syntax_engine": "tree-sitter"})
    assert config.syntax_engine == "legacy"
    assert any("unknown syntax_engine" in d.message for d in config.diagnostics)


def test_invalid_boolean_falls_back_with_diagnostic() -> None:
    config = ExtensionLayerConfig.from_section({"enabled": "yes"})
    assert config.enabled is True  # default preserved
    assert any("enabled must be a boolean" in d.message for d in config.diagnostics)


# --------------------------------------------------------------------------- #
# No runtime execution surface.
# --------------------------------------------------------------------------- #


def test_no_runtime_execution_field_exists() -> None:
    field_names = {f.name for f in dataclasses.fields(ExtensionLayerConfig)}
    forbidden = {"runtime", "execute", "execution", "host", "node", "npm", "scripts"}
    assert field_names.isdisjoint(forbidden)
    assert ExtensionLayerConfig().allows_runtime_execution is False


def test_runtime_execution_keys_are_ignored_with_diagnostic() -> None:
    config = ExtensionLayerConfig.from_section(
        {"enabled": True, "runtime": True, "node": True, "scripts": ["build"]}
    )
    assert config.allows_runtime_execution is False
    assert not hasattr(config, "runtime")
    messages = " ".join(d.message for d in config.diagnostics)
    assert "runtime execution settings are not permitted" in messages


# --------------------------------------------------------------------------- #
# Legacy highlighter remains available; obsolete tables moved out of config.toml.
# --------------------------------------------------------------------------- #


def test_global_highlighting_toggle_is_preserved() -> None:
    config = _config_toml()
    # The global visible-highlighting switch stays in both config.toml and
    # DEFAULT_CONFIG and applies to both engines.
    assert config["editor"]["syntax_highlighting"] is True
    assert DEFAULT_CONFIG["editor"]["syntax_highlighting"] is True


def test_obsolete_tables_removed_from_config_toml() -> None:
    config = _config_toml()
    # The old internal data tables no longer ship in the user-facing config.
    assert "syntax_highlighting" not in config
    assert "comments" not in config
    assert "supported_formats" not in config
    # They remain available as internal code defaults so legacy still works.
    assert "comments" in DEFAULT_CONFIG
    assert "supported_formats" in DEFAULT_CONFIG


def test_config_toml_and_default_config_agree_on_user_sections() -> None:
    config = _config_toml()
    # Every key the user-facing config.toml ships must have the same value in the
    # in-code DEFAULT_CONFIG fallback (DEFAULT_CONFIG may carry extra internal
    # keys, e.g. editor.default_new_filename).
    for section in ("editor", "fonts", "linter", "logging", "extensions", "settings"):
        for key, value in config[section].items():
            assert DEFAULT_CONFIG[section].get(key) == value, f"{section}.{key}"
