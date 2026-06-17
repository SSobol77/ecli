# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_design_system.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the Terminal UI Design System role layer."""

from __future__ import annotations

import curses

from ecli.ui.design import ROLE_COLOR_KEYS, TuiDesign
from ecli.utils.themes import get_theme


# Roles the design brief requires the design system to define.
REQUIRED_ROLES = {
    "app_header",
    "menu_bar",
    "editor_bg",
    "editor_text",
    "gutter_bg",
    "gutter_text",
    "current_line",
    "panel_bg",
    "panel_border",
    "panel_title",
    "panel_text",
    "panel_dim",
    "panel_selected_bg",
    "panel_selected_fg",
    "panel_focus_border",
    "table_header",
    "table_separator",
    "status_bg",
    "status_fg",
    "footer_bg",
    "footer_fg",
    "key_hint",
    "warning",
    "error",
    "success",
    "info",
    "git_dirty",
    "git_clean",
    "ai_warning",
}


def test_all_required_roles_are_defined() -> None:
    assert REQUIRED_ROLES <= set(ROLE_COLOR_KEYS)


def test_every_role_maps_to_a_color_key_present_in_chrome_or_syntax() -> None:
    # Every mapped colour key must be a key the renderer actually allocates,
    # i.e. a chrome pair name or a syntax/git colour name.
    palette = get_theme(5)
    available = set(palette.chrome_color_pairs()) | set(palette.syntax_color_hex())
    for role, key in ROLE_COLOR_KEYS.items():
        assert key in available, (role, key)


def test_design_resolves_roles_from_colors_map() -> None:
    colors = {"ui_panel_selected": 42, "ui_panel": 7, "default": 1}
    design = TuiDesign(colors)
    assert design.attr("panel_selected_bg") == 42
    assert design.attr("panel_bg") == 7
    assert design.attr("editor_text") == 1


def test_design_unknown_role_and_missing_key_use_defaults() -> None:
    design = TuiDesign({})
    assert design.attr("nonexistent-role", default=99) == 99
    # Known role but colour key absent (limited terminal) -> default.
    assert design.attr("panel_bg", default=5) == 5


def test_selected_and_border_helpers_apply_focus() -> None:
    design = TuiDesign({"ui_panel_selected": 8, "ui_panel_border": 4})
    assert design.selected(focused=True) == 8
    assert design.selected(focused=False) != 8  # dim/unfocused fallback
    assert design.border(focused=True) == (4 | curses.A_BOLD)
    assert design.border(focused=False) == 4
