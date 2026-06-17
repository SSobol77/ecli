# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/design.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""ECLI Terminal UI Design System.

A single, theme-driven layer that maps **semantic UI roles** (app header,
panel surfaces, selection/focus states, table headers, footer key hints, ...)
to concrete curses attributes resolved from the active theme palette.

Panels and chrome should ask for a *role* (``design.attr("panel_selected")``)
instead of reaching for raw colour keys, so the whole UI shares one design
language and a theme change re-styles everything consistently.

The underlying colour pairs are allocated by ``Ecli.init_colors`` from
``ThemePalette.chrome_color_pairs`` / ``syntax_color_hex`` (see
``ecli.utils.themes``); this module is the stable indirection between those
``self.colors`` keys and the role vocabulary used by the renderers.
"""

from __future__ import annotations

import curses
from typing import Mapping


#: Semantic role -> ``Ecli.colors`` key. Roles are the public vocabulary; the
#: colour keys are the allocated curses pairs. A role with no key (or a missing
#: key at runtime) falls back to a sensible default at lookup time.
ROLE_COLOR_KEYS: dict[str, str] = {
    # Application chrome
    "app_header": "ui_header",
    "app_header_accent": "ui_header_accent",
    "app_header_dim": "ui_header_dim",
    "menu_bar": "ui_header",
    # Editor surface
    "editor_bg": "default",
    "editor_text": "default",
    "gutter_bg": "line_number",
    "gutter_text": "line_number",
    "current_line": "ui_current_line",
    "current_line_number": "ui_current_line_number",
    # Panels / modals
    "panel_bg": "ui_panel",
    "panel_text": "ui_panel",
    "panel_dim": "ui_panel_dim",
    "panel_border": "ui_panel_border",
    "panel_title": "ui_panel_title",
    "panel_selected_bg": "ui_panel_selected",
    "panel_selected_fg": "ui_panel_selected",
    "panel_focus_border": "ui_panel_border",
    "panel_accent": "ui_panel_title",
    "panel_warning": "ui_panel_warning",
    "panel_error": "ui_panel_error",
    # Tables / lists
    "table_header": "ui_panel_title",
    "table_separator": "ui_panel_border",
    # Status / footer
    "status_bg": "ui_status",
    "status_fg": "ui_status",
    "status_accent": "ui_status_accent",
    "footer_bg": "ui_footer",
    "footer_fg": "ui_footer",
    "key_hint": "ui_footer_key",
    # Diagnostics / semantic
    "warning": "ui_warning",
    "error": "ui_error",
    "success": "ui_success",
    "info": "ui_info",
    "git_dirty": "git_dirty",
    "git_clean": "git_info",
    "ai_warning": "ui_panel_warning",
}

#: Stable, documented role vocabulary (sorted for tests / discoverability).
SEMANTIC_ROLES: tuple[str, ...] = tuple(sorted(ROLE_COLOR_KEYS))


class TuiDesign:
    """Resolves semantic UI roles to curses attributes from a colour map.

    ``colors`` is the live ``Ecli.colors`` dict (role-agnostic curses pairs).
    Lookups never raise: an unknown role or a colour key missing from a limited
    terminal degrades to ``curses.A_NORMAL`` (or the caller's default).
    """

    def __init__(self, colors: Mapping[str, int]) -> None:
        """Wrap a live ``Ecli.colors`` map for role-based attribute lookups."""
        self._colors = colors

    def attr(self, role: str, default: int = curses.A_NORMAL) -> int:
        """Return the curses attribute for ``role`` (or ``default``)."""
        key = ROLE_COLOR_KEYS.get(role)
        if key is None:
            return default
        return self._colors.get(key, default)

    def selected(self, focused: bool = True) -> int:
        """Full-row selection attribute; reverse-video fallback when unfocused."""
        if focused:
            return self.attr("panel_selected_bg", curses.A_REVERSE | curses.A_BOLD)
        return self.attr("panel_dim", curses.A_DIM)

    def border(self, focused: bool = False) -> int:
        """Panel border attribute, bolded when the panel is focused."""
        base = self.attr("panel_border", curses.A_NORMAL)
        return base | curses.A_BOLD if focused else base
