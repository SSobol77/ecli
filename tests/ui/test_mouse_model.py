# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_mouse_model.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the mouse model and hit-testing (no real terminal needed)."""

from __future__ import annotations

import curses

import pytest

from ecli.ui.geometry import Rect, compute_layout
from ecli.ui.mouse import (
    FocusRegion,
    MouseAction,
    MouseButton,
    MouseEvent,
    decode_curses_mouse,
    hit_test,
)
from ecli.ui.panels import FileBrowserPanel, SystemDoctorPanel


# --- hit testing ---------------------------------------------------------


def test_hit_test_editor_and_gutter() -> None:
    geo = compute_layout(120, 40, active_panel=False)
    editor = hit_test(geo, 10, 5)
    assert editor.region is FocusRegion.EDITOR
    assert editor.local_x == 10
    assert editor.local_y == 5 - geo.editor.y
    gutter = hit_test(geo, 2, 5, gutter_width=5)
    assert gutter.region is FocusRegion.GUTTER


def test_hit_test_split_panel_and_editor() -> None:
    geo = compute_layout(120, 40, active_panel=True)
    assert hit_test(geo, 90, 5).region is FocusRegion.PANEL  # right 40%
    assert hit_test(geo, 10, 5).region is FocusRegion.EDITOR  # left 60%
    # Panel-local coordinates are relative to the panel rect.
    target = hit_test(geo, 90, 5)
    assert target.local_x == 90 - geo.panel.x
    assert target.local_y == 5 - geo.panel.y


def test_hit_test_global_header_status_footer() -> None:
    geo = compute_layout(120, 40, active_panel=False)
    assert hit_test(geo, 5, 0).region is FocusRegion.HEADER
    assert hit_test(geo, 5, 38).region is FocusRegion.STATUS  # H-2
    assert hit_test(geo, 5, 39).region is FocusRegion.FOOTER  # H-1


def test_hit_test_modal_inside_and_outside() -> None:
    geo = compute_layout(120, 40, active_panel=False)
    modal = Rect(40, 10, 40, 15)
    assert hit_test(geo, 50, 15, modal_rect=modal).region is FocusRegion.MODAL
    assert hit_test(geo, 5, 5, modal_rect=modal).region is FocusRegion.OUTSIDE


# --- curses decode (constants probed: present on this ncurses) ------------


def test_decode_left_click_double_and_press() -> None:
    assert decode_curses_mouse(curses.BUTTON1_CLICKED) == (
        MouseButton.LEFT,
        MouseAction.CLICK,
    )
    assert decode_curses_mouse(curses.BUTTON1_DOUBLE_CLICKED) == (
        MouseButton.LEFT,
        MouseAction.DOUBLE_CLICK,
    )
    assert decode_curses_mouse(curses.BUTTON1_PRESSED) == (
        MouseButton.LEFT,
        MouseAction.PRESS,
    )


def test_decode_wheel_up_down() -> None:
    assert decode_curses_mouse(curses.BUTTON4_PRESSED) == (
        MouseButton.WHEEL_UP,
        MouseAction.WHEEL,
    )
    assert decode_curses_mouse(curses.BUTTON5_PRESSED) == (
        MouseButton.WHEEL_DOWN,
        MouseAction.WHEEL,
    )


def test_decode_unknown_state_is_safe() -> None:
    assert decode_curses_mouse(0) == (MouseButton.NONE, MouseAction.UNKNOWN)


def test_mouse_event_wheel_delta() -> None:
    up = MouseEvent(0, 0, MouseButton.WHEEL_UP, MouseAction.WHEEL)
    down = MouseEvent(0, 0, MouseButton.WHEEL_DOWN, MouseAction.WHEEL)
    click = MouseEvent(0, 0, MouseButton.LEFT, MouseAction.CLICK)
    assert up.is_wheel and up.wheel_delta == 1
    assert down.wheel_delta == -1
    assert not click.is_wheel and click.wheel_delta == 0


# --- File Manager row hit-testing & wheel scroll -------------------------


def _make_file_browser(
    entry_count: int, height: int = 24, top: int = 0
) -> FileBrowserPanel:
    fb = FileBrowserPanel.__new__(FileBrowserPanel)
    fb.entries = list(range(entry_count))  # type: ignore[assignment]
    fb.height = height
    fb._list_first_row = 2
    fb._list_last_row = height - 3
    fb._visible_top = top
    return fb


def test_file_manager_click_maps_to_entry_index() -> None:
    fb = _make_file_browser(10, height=24, top=0)
    assert fb.hit_entry_index(2) == 0  # first list row
    assert fb.hit_entry_index(5) == 3
    assert fb.hit_entry_index(11) == 9  # last entry
    # Title/header rows and beyond-list clicks select nothing.
    assert fb.hit_entry_index(0) is None
    assert fb.hit_entry_index(1) is None
    assert fb.hit_entry_index(12) is None  # past the entries
    assert fb.hit_entry_index(21) is None  # the list-bottom boundary


def test_file_manager_click_respects_scroll() -> None:
    fb = _make_file_browser(50, height=24, top=20)
    assert fb.hit_entry_index(2) == 20
    assert fb.hit_entry_index(4) == 22


def test_wheel_scroll_moves_list_selection() -> None:
    fb = _make_file_browser(10)
    fb.idx = 5
    assert fb.scroll_by(-1) is True  # wheel down -> next
    assert fb.idx == 6
    assert fb.scroll_by(1) is True  # wheel up -> previous
    assert fb.idx == 5


def test_wheel_scroll_adjusts_scroll_offset_panel() -> None:
    panel = SystemDoctorPanel.__new__(SystemDoctorPanel)
    panel.scroll = 5
    assert panel.scroll_by(1) is True  # wheel up
    assert panel.scroll == 4
    panel.scroll = 0
    assert panel.scroll_by(1) is False  # clamped at top


def test_scroll_by_noop_without_scroll_or_idx() -> None:
    bare = FileBrowserPanel.__new__(FileBrowserPanel)
    # No 'scroll', no 'idx'/'entries' attributes -> safe no-op.
    assert bare.scroll_by(1) is False


def test_mouse_dispatch_is_noop_when_disabled() -> None:
    # With mouse support off/unavailable the handler must not touch curses or crash.
    from ecli.core.Ecli import Ecli

    editor = Ecli.__new__(Ecli)
    editor.mouse_active = False
    assert editor._handle_mouse_event() is False


def test_focus_helper_is_deterministic() -> None:
    from ecli.core.Ecli import Ecli

    editor = Ecli.__new__(Ecli)
    editor.focus = "editor"
    assert editor._focus_to("editor") is False  # no change
    assert editor._focus_to("panel") is True
    assert editor.focus == "panel"
