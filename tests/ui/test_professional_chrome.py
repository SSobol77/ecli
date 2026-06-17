# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_professional_chrome.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the professional chrome (header/status/footer) layout and the
guarantee that chrome rendering never mutates the editor buffer.
"""

from __future__ import annotations

import curses

import pytest
from wcwidth import wcswidth

from ecli.ui.DrawScreen import DrawScreen
from ecli.utils.themes import get_theme


# --- Pure geometry -------------------------------------------------------


@pytest.mark.parametrize("height", [5, 6, 7, 8, 10, 24, 40, 120])
def test_content_plus_chrome_equals_height(height: int) -> None:
    header_h, status_h, footer_h = DrawScreen.chrome_heights(height)
    content = DrawScreen.content_height(height)
    assert content >= 1
    assert content + header_h + status_h + footer_h == height


def test_full_chrome_on_tall_terminal() -> None:
    assert DrawScreen.chrome_heights(24) == (1, 1, 1)
    # 24 - header - status - footer
    assert DrawScreen.content_height(24) == 21


def test_chrome_degrades_on_small_terminal() -> None:
    # Below the threshold the header and footer are dropped (status only),
    # maximising editable rows on tiny terminals.
    header_h, status_h, footer_h = DrawScreen.chrome_heights(6)
    assert (header_h, status_h, footer_h) == (0, 1, 0)
    assert DrawScreen.content_height(6) == 5


def test_content_height_never_zero() -> None:
    for height in range(1, 200):
        assert DrawScreen.content_height(height) >= 1


# --- Vertical-border geometry --------------------------------------------


def test_borders_present_on_full_size_terminal() -> None:
    assert DrawScreen.border_cols(24, 84) == (1, 1)
    assert DrawScreen.border_cols(40, 120) == (1, 1)


def test_borders_dropped_on_narrow_terminal() -> None:
    assert DrawScreen.border_cols(24, 30) == (0, 0)


def test_borders_dropped_on_short_terminal() -> None:
    # Below the full-chrome height threshold there is no top/bottom frame, so
    # the verticals are dropped too.
    assert DrawScreen.border_cols(6, 120) == (0, 0)


@pytest.mark.parametrize("width", [40, 84, 120, 200])
def test_content_width_inside_borders_is_positive(width: int) -> None:
    left, right = DrawScreen.border_cols(24, width)
    content_width = width - left - right
    assert content_width > 0
    assert content_width == width - 2  # both borders present at these widths


# --- Chrome rendering does not mutate the buffer -------------------------


class FakeWin:
    """Minimal curses-window stand-in that records written cells."""

    def __init__(self, rows: int, cols: int) -> None:
        """Create a blank fake window of the given size."""
        self.rows = rows
        self.cols = cols
        self.cells: dict[tuple[int, int], str] = {}

    def getmaxyx(self) -> tuple[int, int]:
        return (self.rows, self.cols)

    def addstr(self, y: int, x: int, text: str, _attr: int = 0) -> None:
        if y < 0 or y >= self.rows or x < 0:
            raise curses.error("out of bounds")
        if x + len(text) > self.cols:
            raise curses.error("would write past EOL")
        for i, ch in enumerate(text):
            self.cells[(y, x + i)] = ch

    def insch(self, y: int, x: int, ch: int | str, _attr: int = 0) -> None:
        if y < 0 or y >= self.rows or x < 0 or x >= self.cols:
            raise curses.error("out of bounds")
        self.cells[(y, x)] = chr(ch) if isinstance(ch, int) else ch

    def chgat(self, *_a: object, **_k: object) -> None:
        return None


class FakeEditor:
    def __init__(self) -> None:
        """Create a fake editor with a small multi-line buffer."""
        self.text = ["import os", "", "def main():", "    return 1"]
        self.filename = "/home/user/projects/ecli/src/sample.py"
        self.modified = True
        self.is_lightweight = False
        self.active_theme = get_theme(5)
        self.cursor_y = 0

    def get_string_width(self, text: str) -> int:
        width = wcswidth(text)
        return len(text) if width < 0 else width


def _make_drawscreen(win: FakeWin) -> DrawScreen:
    ds = DrawScreen.__new__(DrawScreen)
    ds.editor = FakeEditor()  # type: ignore[assignment]
    ds.stdscr = win  # type: ignore[assignment]
    ds.colors = {}  # exercise the .get(...) defaults path
    ds.config = {}
    ds.content_area_y_offset = 1
    ds._text_start_x = 0
    return ds


def _row_text(win: FakeWin, y: int) -> str:
    xs = [x for (yy, x) in win.cells if yy == y]
    if not xs:
        return ""
    return "".join(win.cells.get((y, x), " ") for x in range(max(xs) + 1))


def test_header_renders_app_file_and_theme_within_bounds() -> None:
    win = FakeWin(24, 90)
    ds = _make_drawscreen(win)
    before = list(ds.editor.text)

    ds._draw_header(90)

    row0 = _row_text(win, 0)
    assert "ECLI" in row0
    assert "sample.py" in row0
    assert "theme 5" in row0 or "Dark Classic" in row0
    # Every write stays within the terminal width.
    assert all(0 <= x < 90 for (_y, x) in win.cells)
    # Buffer is untouched by chrome rendering.
    assert ds.editor.text == before


def test_footer_renders_shortcuts_within_bounds() -> None:
    win = FakeWin(24, 90)
    ds = _make_drawscreen(win)
    before = list(ds.editor.text)

    ds._draw_footer(90)

    last = _row_text(win, 23)
    assert "Ctrl+S" in last and "Save" in last
    assert "Quit" in last
    assert all(0 <= x < 90 for (_y, x) in win.cells)
    assert ds.editor.text == before


def test_footer_truncates_on_narrow_terminal_without_error() -> None:
    win = FakeWin(24, 24)
    ds = _make_drawscreen(win)
    ds._draw_footer(24)
    # Nothing was written past the (narrow) width.
    assert all(0 <= x < 24 for (_y, x) in win.cells)


def test_shorten_path_keeps_basename() -> None:
    win = FakeWin(24, 90)
    ds = _make_drawscreen(win)
    long_path = "/very/deeply/nested/directory/structure/module_name.py"
    out = ds._shorten_path(long_path, 25)
    assert ds.editor.get_string_width(out) <= 25
    assert "module_name.py" in out


def test_header_and_footer_do_not_write_into_buffer_lines() -> None:
    win = FakeWin(24, 90)
    ds = _make_drawscreen(win)
    sentinel = list(ds.editor.text)
    ds._draw_header(90)
    ds._draw_footer(90)
    # No file content leaked into chrome, no chrome leaked into the buffer.
    assert ds.editor.text == sentinel
    assert "ECLI" not in "".join(ds.editor.text)
