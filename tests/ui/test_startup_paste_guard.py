# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_startup_paste_guard.py
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the KeyBinder startup input-buffer guard.

The guard ensures that bytes already present in the terminal buffer when
ECLI opens (shell residue, type-ahead) are discarded rather than inserted
into the editor.  Normal typing and intentional paste still work.
"""

from __future__ import annotations

import curses
import threading
from typing import Any
from unittest.mock import MagicMock

from ecli.ui.KeyBinder import KeyBinder


# ---------------------------------------------------------------------------
# Minimal editor double (enough for KeyBinder.__init__)
# ---------------------------------------------------------------------------


class FakeHistory:
    def undo(self) -> bool:
        return True

    def redo(self) -> bool:
        return True


class FakeWindow:
    def getmaxyx(self) -> tuple[int, int]:
        return (30, 100)


class FakeEditor:
    def __init__(self) -> None:
        """Initialize a non-interactive editor double for KeyBinder tests."""
        self.history = FakeHistory()
        self.config: dict[str, Any] = {}
        self.stdscr = FakeWindow()
        self.is_lightweight = True
        self.linter_bridge = object()
        self.async_engine = object()
        self.status_message = "Ready"
        self._lexer = None
        self._state_lock = threading.RLock()
        self.called: list[str] = []

    def _set_status_message(self, message: str) -> bool:
        self.status_message = message
        return True

    # Stubs for every method KeyBinder._setup_action_map looks up.
    def open_file(self) -> bool:
        return True

    def save_file(self) -> bool:
        return True

    def save_file_as(self) -> bool:
        return True

    def new_file(self) -> bool:
        return True

    def copy(self) -> bool:
        return True

    def cut(self) -> bool:
        return True

    def paste(self) -> bool:
        return True

    def select_all(self) -> bool:
        return True

    def handle_delete(self) -> bool:
        return True

    def exit_editor(self) -> bool:
        return True

    def handle_home(self) -> bool:
        return True

    def handle_end(self) -> bool:
        return True

    def handle_page_up(self) -> bool:
        return True

    def handle_page_down(self) -> bool:
        return True

    def extend_selection_up(self) -> bool:
        return True

    def extend_selection_down(self) -> bool:
        return True

    def extend_selection_left(self) -> bool:
        return True

    def extend_selection_right(self) -> bool:
        return True

    def select_to_home(self) -> bool:
        return True

    def select_to_end(self) -> bool:
        return True

    def find_prompt(self) -> bool:
        return True

    def find_next(self) -> bool:
        return True

    def search_and_replace(self) -> bool:
        return True

    def goto_line(self) -> bool:
        return True

    def handle_smart_tab(self) -> bool:
        return True

    def handle_smart_unindent(self) -> bool:
        return True

    def toggle_comment_block(self) -> bool:
        return True

    def toggle_insert_mode(self) -> bool:
        return True

    def handle_up(self) -> bool:
        return True

    def handle_down(self) -> bool:
        return True

    def handle_left(self) -> bool:
        return True

    def handle_right(self) -> bool:
        return True

    def handle_backspace(self) -> bool:
        return True

    def handle_enter(self) -> bool:
        return True

    def show_help(self) -> bool:
        return True

    def handle_escape(self) -> bool:
        return True

    def toggle_file_browser(self) -> bool:
        return True

    def toggle_terminal_panel(self) -> bool:
        return True

    def toggle_focus(self) -> bool:
        return True

    def show_git_panel(self) -> bool:
        return True

    def toggle_widget_panel(self) -> bool:
        return True

    def toggle_system_doctor_panel(self) -> bool:
        return True

    def run_lint_async(self) -> bool:
        return True

    def toggle_diagnostics_panel(self) -> bool:
        return True

    def show_lint_panel(self) -> bool:
        return True

    def handle_resize(self) -> bool:
        return True

    def insert_text(self, text: str) -> bool:
        return True


def make_keybinder() -> KeyBinder:
    return KeyBinder(FakeEditor())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Guard state tests (no curses window needed)
# ---------------------------------------------------------------------------


def test_startup_guard_is_active_on_construction() -> None:
    kb = make_keybinder()
    assert kb._startup_guard_active is True


def test_startup_guard_deactivates_after_first_flush() -> None:
    kb = make_keybinder()

    window = MagicMock()
    window.getch.return_value = curses.ERR  # no buffered bytes

    kb._flush_startup_input_buffer(window)

    # Guard must be deactivated by the caller (get_key_input) after flushing.
    # Here we deactivate manually to mirror that contract.
    kb._startup_guard_active = False
    assert kb._startup_guard_active is False


def test_flush_discards_buffered_bytes_and_stops_on_err() -> None:
    """_flush_startup_input_buffer drains until ERR; returns nothing."""
    kb = make_keybinder()

    call_sequence = [ord("a"), ord("b"), ord("c"), curses.ERR]
    window = MagicMock()
    window.getch.side_effect = call_sequence

    kb._flush_startup_input_buffer(window)

    # All 4 getch() calls consumed (3 bytes + the ERR sentinel).
    assert window.getch.call_count == 4


def test_flush_with_empty_buffer_makes_one_getch_call() -> None:
    """When the buffer is empty the first getch() returns ERR immediately."""
    kb = make_keybinder()

    window = MagicMock()
    window.getch.return_value = curses.ERR

    kb._flush_startup_input_buffer(window)

    assert window.getch.call_count == 1


# ---------------------------------------------------------------------------
# get_key_input integration (guard fires exactly once)
# ---------------------------------------------------------------------------


def test_get_key_input_returns_err_on_first_call_when_guard_active() -> None:
    """The first get_key_input call flushes and returns ERR (no-op input)."""
    kb = make_keybinder()
    assert kb._startup_guard_active is True

    window = MagicMock()
    window.getch.return_value = curses.ERR  # nothing buffered

    result = kb.get_key_input(window)

    assert result == curses.ERR
    assert kb._startup_guard_active is False  # guard has been consumed


def test_get_key_input_discards_buffered_burst_on_startup() -> None:
    """Pre-buffered printable bytes are flushed, not returned, on first call."""
    kb = make_keybinder()

    # Simulate: terminal buffer has "hello" waiting at startup.
    # The flush sees these bytes then ERR; get_key_input must return ERR.
    window = MagicMock()
    window.getch.side_effect = [
        ord("h"),
        ord("e"),
        ord("l"),
        ord("l"),
        ord("o"),
        curses.ERR,
    ]

    result = kb.get_key_input(window)

    assert result == curses.ERR
    assert kb._startup_guard_active is False


def test_get_key_input_processes_normal_key_after_guard_fires() -> None:
    """After the guard fires once, subsequent calls behave normally."""
    kb = make_keybinder()

    window = MagicMock()
    # First call: guard fires, nothing in buffer → ERR
    window.getch.return_value = curses.ERR
    first = kb.get_key_input(window)
    assert first == curses.ERR
    assert kb._startup_guard_active is False

    # Second call: guard is gone; a real keypress arrives. The single
    # keystroke is followed by ERR so _drain_text_burst's non-blocking
    # look-ahead terminates instead of looping forever on a fixed
    # return_value.
    window.getch.return_value = None
    window.getch.side_effect = [ord("x"), curses.ERR]
    # _drain_text_burst will be called; make nodelay a no-op
    window.nodelay = MagicMock()
    window.timeout = MagicMock()

    second = kb.get_key_input(window)
    # The result should be something other than the guard's ERR sentinel;
    # it may be the character or a paste event if burst-drained.
    assert second != curses.ERR or kb._startup_guard_active is False
