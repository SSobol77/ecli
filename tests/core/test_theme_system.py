# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_theme_system.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the fixed built-in theme system and syntax-highlighting toggle."""

from __future__ import annotations

import pytest

from ecli.utils.themes import (
    DEFAULT_THEME_ID,
    THEME_ENV_VAR,
    ThemeId,
    get_theme,
    resolve_theme,
)


@pytest.fixture(autouse=True)
def _clear_theme_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ECLI_THEME never leaks into config-based theme tests."""
    monkeypatch.delenv(THEME_ENV_VAR, raising=False)


# Colour names the renderer / highlighter look up in ``self.colors``.
RENDERER_COLOR_KEYS = {
    "default",
    "comment",
    "keyword",
    "string",
    "number",
    "function",
    "class",
    "type",
    "constant",
    "operator",
    "decorator",
    "variable",
    "tag",
    "attribute",
    "builtin",
    "error",
    "status",
    "status_error",
    "line_number",
    "git_info",
    "git_dirty",
    "git_added",
    "git_deleted",
    "search_highlight",
}


def test_exactly_eight_themes_exist() -> None:
    ids = [int(member) for member in ThemeId]
    assert ids == [1, 2, 3, 4, 5, 6, 7, 8]


def test_four_light_and_four_dark_themes() -> None:
    light = [tid for tid in range(1, 9) if not get_theme(tid).is_dark]
    dark = [tid for tid in range(1, 9) if get_theme(tid).is_dark]
    assert light == [1, 2, 3, 4]
    assert dark == [5, 6, 7, 8]


def test_get_theme_returns_matching_id() -> None:
    for tid in range(1, 9):
        assert get_theme(tid).theme_id == tid


@pytest.mark.parametrize("tid", list(range(1, 9)))
def test_every_palette_defines_all_renderer_colors(tid: int) -> None:
    color_map = get_theme(tid).syntax_color_hex()
    assert RENDERER_COLOR_KEYS <= set(color_map)
    # Every value is a #rrggbb hex string.
    for name, value in color_map.items():
        assert isinstance(value, str) and value.startswith("#") and len(value) == 7, (
            name,
            value,
        )


@pytest.mark.parametrize("tid", list(range(1, 9)))
def test_palette_defines_required_surfaces(tid: int) -> None:
    palette = get_theme(tid)
    for field in (
        palette.background,
        palette.foreground,
        palette.cursor,
        palette.selection,
        palette.status,
        palette.line_number,
        palette.current_line,
        palette.warning,
    ):
        assert field.startswith("#") and len(field) == 7


# Chrome roles required by the professional UI (header/status/footer/...).
CHROME_ROLES = (
    "dim",
    "header_bg",
    "header_fg",
    "status_bg",
    "status_fg",
    "footer_bg",
    "footer_fg",
    "border",
    "panel_title",
    "info",
    "success",
)


@pytest.mark.parametrize("tid", list(range(1, 9)))
def test_every_theme_defines_all_chrome_roles(tid: int) -> None:
    palette = get_theme(tid)
    for role in CHROME_ROLES:
        value = getattr(palette, role)
        assert isinstance(value, str) and value.startswith("#") and len(value) == 7, (
            tid,
            role,
            value,
        )


@pytest.mark.parametrize("tid", list(range(1, 9)))
def test_chrome_color_pairs_are_complete_fg_bg_hex(tid: int) -> None:
    pairs = get_theme(tid).chrome_color_pairs()
    expected = {
        "ui_header",
        "ui_status",
        "ui_footer",
        "ui_footer_key",
        "ui_border",
        "ui_panel_title",
        "ui_current_line",
        "ui_current_line_number",
        "ui_selection",
        "ui_info",
        "ui_success",
        "ui_error",
        "ui_warning",
    }
    assert expected <= set(pairs)
    for name, (fg, bg) in pairs.items():
        assert fg.startswith("#") and len(fg) == 7, (name, fg)
        assert bg.startswith("#") and len(bg) == 7, (name, bg)


def test_resolve_theme_reads_config_value() -> None:
    assert resolve_theme({"theme": 1}).name == "Light Classic"
    assert resolve_theme({"theme": 8}).name == "Dark Neon"


def test_resolve_theme_missing_uses_default() -> None:
    assert resolve_theme({}).theme_id == DEFAULT_THEME_ID
    assert resolve_theme(None).theme_id == DEFAULT_THEME_ID


def test_resolve_theme_out_of_range_falls_back() -> None:
    assert resolve_theme({"theme": 0}).theme_id == DEFAULT_THEME_ID
    assert resolve_theme({"theme": 99}).theme_id == DEFAULT_THEME_ID
    assert resolve_theme({"theme": -3}).theme_id == DEFAULT_THEME_ID


def test_resolve_theme_integer_like_string_is_accepted() -> None:
    assert resolve_theme({"theme": "3"}).theme_id == 3


def test_resolve_theme_non_integer_string_falls_back() -> None:
    assert resolve_theme({"theme": "dark"}).theme_id == DEFAULT_THEME_ID
    assert resolve_theme({"theme": 2.5}).theme_id == DEFAULT_THEME_ID


def test_resolve_theme_boolean_is_rejected() -> None:
    # bool is an int subclass; it must not be treated as theme 1/0.
    assert resolve_theme({"theme": True}).theme_id == DEFAULT_THEME_ID
    assert resolve_theme({"theme": False}).theme_id == DEFAULT_THEME_ID


def test_env_var_overrides_config_theme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(THEME_ENV_VAR, "7")
    assert resolve_theme({"theme": 2}).theme_id == 7


def test_invalid_env_var_falls_back_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(THEME_ENV_VAR, "not-a-theme")
    assert resolve_theme({"theme": 2}).theme_id == 2


def test_blank_env_var_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(THEME_ENV_VAR, "   ")
    assert resolve_theme({"theme": 4}).theme_id == 4


def test_legacy_theme_table_name_maps_to_default_dark_or_light() -> None:
    # Stale configs ship a [theme] table; map its name without forcing theme 5.
    assert resolve_theme({"theme": {"name": "dark"}}).theme_id == int(
        ThemeId.DARK_CLASSIC
    )
    assert resolve_theme({"theme": {"name": "light"}}).theme_id == int(
        ThemeId.LIGHT_CLASSIC
    )


def test_legacy_theme_table_id_is_honoured() -> None:
    assert resolve_theme({"theme": {"id": 3}}).theme_id == 3
    # id wins over name.
    assert resolve_theme({"theme": {"id": 8, "name": "light"}}).theme_id == 8


def test_legacy_theme_table_without_id_or_name_uses_default() -> None:
    assert (
        resolve_theme({"theme": {"ui": {"background": "#fff"}}}).theme_id
        == DEFAULT_THEME_ID
    )


def test_legacy_colors_table_does_not_override_theme() -> None:
    # A [colors] table must not change the resolved built-in theme.
    cfg = {"theme": 6, "colors": {"keyword": "red", "background": "#000000"}}
    assert resolve_theme(cfg).theme_id == 6
