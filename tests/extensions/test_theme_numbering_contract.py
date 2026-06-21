# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_theme_numbering_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Theme numbering policy + config.toml cleanliness contract (#102).

The policy: 1-8 are deprecated aliases only, 100-199 light, 200-299 dark,
300-399 high contrast, 800-899 reserved. These gates pin the policy against the
**real** theme registry built from imported extension metadata, and assert the
shipped, user-facing ``config.toml`` stays clean (no internal/declarative tables).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ecli.extensions.ecli_integration.theme_registry import (
    THEME_NUMBERING_POLICY,
    cached_theme_registry,
)
from ecli.utils.themes import DEFAULT_THEME_ID, resolve_theme


REPO_ROOT = Path(__file__).resolve().parents[2]


def _band(number: int) -> str:
    if 100 <= number < 200:
        return "light"
    if 200 <= number < 300:
        return "dark"
    if 300 <= number < 400:
        return "high-contrast"
    if 800 <= number < 900:
        return "reserved"
    if 1 <= number < 9:
        return "deprecated"
    return "out-of-policy"


# --------------------------------------------------------------------------- #
# Numbering policy is documented and enforced against real loaded themes.
# --------------------------------------------------------------------------- #


def test_numbering_policy_bands_are_documented() -> None:
    assert THEME_NUMBERING_POLICY["deprecated_aliases"] == "1-8"
    assert THEME_NUMBERING_POLICY["light"] == "100-199"
    assert THEME_NUMBERING_POLICY["dark"] == "200-299"
    assert THEME_NUMBERING_POLICY["high_contrast"] == "300-399"
    assert THEME_NUMBERING_POLICY["reserved_custom_imported"] == "800-899"


def test_loaded_extension_theme_numbers_match_their_band() -> None:
    registry = cached_theme_registry()
    numbered = [t for t in registry.list_available_extension_themes() if t.number]
    assert numbered, "expected real numbered themes from imported metadata"
    for theme in numbered:
        band = _band(theme.number)
        assert band in {"light", "dark", "high-contrast"}, (theme.number, theme.name)
        if band in {"light", "dark"}:
            assert theme.theme_type == band, (
                theme.number,
                theme.name,
                theme.theme_type,
            )
        else:
            assert theme.theme_type == "high-contrast", (theme.number, theme.name)


def test_no_theme_is_assigned_in_reserved_band() -> None:
    registry = cached_theme_registry()
    reserved = [
        t
        for t in registry.list_available_extension_themes()
        if t.number and 800 <= t.number < 900
    ]
    assert reserved == [], reserved
    # And resolving a reserved-band number is not a real theme.
    assert resolve_theme({"theme": 850}).theme_id == DEFAULT_THEME_ID


def test_resolved_theme_band_matches_darkness() -> None:
    # Light band is light; dark band is dark (builtin compatibility ids are always
    # present, so this is deterministic regardless of which files are imported).
    assert resolve_theme({"theme": 181}).is_dark is False  # PySH Light (light band)
    assert resolve_theme({"theme": 281}).is_dark is True  # PySH Dark (dark band)


def test_deprecated_1_8_are_aliases_only_not_primary_numbers() -> None:
    # 1-8 as a *primary* theme number is not a real theme: it falls back.
    for primary in range(1, 9):
        assert resolve_theme({"theme": primary}).theme_id == DEFAULT_THEME_ID
    # But a legacy ``[theme]`` table id (the deprecated alias form) still migrates.
    assert resolve_theme({"theme": {"id": 3}}).theme_id == 381
    assert resolve_theme({"theme": {"id": 8}}).theme_id == 283


# --------------------------------------------------------------------------- #
# Shipped config.toml stays user-facing and clean.
# --------------------------------------------------------------------------- #


def _config_text_and_parsed() -> tuple[str, dict[str, object]]:
    path = REPO_ROOT / "config.toml"
    raw = path.read_text(encoding="utf-8")
    return raw, tomllib.loads(raw)


def test_config_toml_has_no_internal_declarative_tables() -> None:
    raw, parsed = _config_text_and_parsed()
    # Internal/declarative defaults live in code, not the user config.
    assert "comments" not in parsed, "[comments.*] must not be in user config"
    assert "supported_formats" not in parsed, "[supported_formats] must not be present"
    syntax = parsed.get("syntax_highlighting")
    if isinstance(syntax, dict):
        for language, table in syntax.items():
            assert not (isinstance(table, dict) and "patterns" in table), (
                f"[[syntax_highlighting.{language}.patterns]] must not ship in config"
            )
    # The obsolete empty placeholder is gone.
    assert "keybindings = {}" not in raw


def test_config_toml_theme_is_in_a_real_policy_band() -> None:
    _raw, parsed = _config_text_and_parsed()
    theme = parsed.get("theme")
    assert isinstance(theme, int) and not isinstance(theme, bool)
    assert _band(theme) in {"light", "dark", "high-contrast"}, theme
    # It resolves to exactly that theme (a real, present theme).
    assert resolve_theme({"theme": theme}).theme_id == theme
