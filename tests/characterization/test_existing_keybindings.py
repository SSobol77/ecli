# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/characterization/test_existing_keybindings.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Characterization tests for existing TUI keybinding behavior."""

from __future__ import annotations

import curses
import threading
from typing import Any

from ecli.core.Ecli import Ecli
from ecli.ui.KeyBinder import KeyBinder


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
        self.is_lightweight = False
        self.linter_bridge = object()
        self.async_engine = object()
        self.status_message = "Ready"
        self._lexer = None
        self._state_lock = threading.RLock()
        self.called: list[str] = []

    def _record(self, name: str) -> bool:
        self.called.append(name)
        return True

    def _set_status_message(self, message: str) -> bool:
        self.status_message = message
        return True

    def open_file(self) -> bool:
        return self._record("open_file")

    def save_file(self) -> bool:
        return self._record("save_file")

    def save_file_as(self) -> bool:
        return self._record("save_file_as")

    def new_file(self) -> bool:
        return self._record("new_file")

    def copy(self) -> bool:
        return self._record("copy")

    def cut(self) -> bool:
        return self._record("cut")

    def paste(self) -> bool:
        return self._record("paste")

    def select_all(self) -> bool:
        return self._record("select_all")

    def handle_delete(self) -> bool:
        return self._record("handle_delete")

    def exit_editor(self) -> bool:
        return self._record("exit_editor")

    def handle_home(self) -> bool:
        return self._record("handle_home")

    def handle_end(self) -> bool:
        return self._record("handle_end")

    def handle_page_up(self) -> bool:
        return self._record("handle_page_up")

    def handle_page_down(self) -> bool:
        return self._record("handle_page_down")

    def extend_selection_up(self) -> bool:
        return self._record("extend_selection_up")

    def extend_selection_down(self) -> bool:
        return self._record("extend_selection_down")

    def extend_selection_left(self) -> bool:
        return self._record("extend_selection_left")

    def extend_selection_right(self) -> bool:
        return self._record("extend_selection_right")

    def select_to_home(self) -> bool:
        return self._record("select_to_home")

    def select_to_end(self) -> bool:
        return self._record("select_to_end")

    def find_prompt(self) -> bool:
        return self._record("find_prompt")

    def find_next(self) -> bool:
        return self._record("find_next")

    def search_and_replace(self) -> bool:
        return self._record("search_and_replace")

    def goto_line(self) -> bool:
        return self._record("goto_line")

    def handle_smart_tab(self) -> bool:
        return self._record("handle_smart_tab")

    def handle_smart_unindent(self) -> bool:
        return self._record("handle_smart_unindent")

    def toggle_comment_block(self) -> bool:
        return self._record("toggle_comment_block")

    def toggle_insert_mode(self) -> bool:
        return self._record("toggle_insert_mode")

    def handle_up(self) -> bool:
        return self._record("handle_up")

    def handle_down(self) -> bool:
        return self._record("handle_down")

    def handle_left(self) -> bool:
        return self._record("handle_left")

    def handle_right(self) -> bool:
        return self._record("handle_right")

    def handle_backspace(self) -> bool:
        return self._record("handle_backspace")

    def handle_enter(self) -> bool:
        return self._record("handle_enter")

    def show_help(self) -> bool:
        return self._record("show_help")

    def handle_escape(self) -> bool:
        return self._record("handle_escape")

    def toggle_file_browser(self) -> bool:
        return self._record("toggle_file_browser")

    def toggle_terminal_panel(self) -> bool:
        return self._record("toggle_terminal_panel")

    def toggle_focus(self) -> bool:
        return self._record("toggle_focus")

    def show_git_panel(self) -> bool:
        return self._record("show_git_panel")

    def toggle_widget_panel(self) -> bool:
        return self._record("toggle_widget_panel")

    def toggle_system_doctor_panel(self) -> bool:
        return self._record("toggle_system_doctor_panel")

    def run_lint_async(self) -> bool:
        return self._record("run_lint_async")

    def toggle_diagnostics_panel(self) -> bool:
        return self._record("toggle_diagnostics_panel")

    def show_lint_panel(self) -> bool:
        return self._record("show_lint_panel")

    def handle_resize(self) -> bool:
        return self._record("handle_resize")

    def insert_text(self, text: str) -> bool:
        return self._record(f"insert_text:{text}")


def make_keybinder() -> KeyBinder:
    return KeyBinder(FakeEditor())  # type: ignore[arg-type]


def method_name_for_key(binder: KeyBinder, key: int | str) -> str:
    return binder.action_map[key].__name__


def test_default_keybinding_definitions_preserve_known_help_and_panel_bindings() -> (
    None
):
    binder = make_keybinder()

    assert curses.KEY_F1 in binder.keybindings["help"]
    assert curses.KEY_F7 in binder.keybindings["toggle_widget_panel"]
    assert curses.KEY_F10 in binder.keybindings["toggle_file_browser"]
    assert curses.KEY_F9 in binder.keybindings["git_menu"]
    assert curses.KEY_F4 in binder.keybindings["lint"]
    assert curses.KEY_F8 in binder.keybindings["toggle_system_doctor_panel"]


def test_action_map_keeps_existing_help_ai_file_manager_and_git_entrypoints() -> None:
    binder = make_keybinder()

    assert method_name_for_key(binder, curses.KEY_F1) == "show_help"
    assert method_name_for_key(binder, curses.KEY_F7) == "toggle_widget_panel"
    assert method_name_for_key(binder, curses.KEY_F10) == "toggle_file_browser"
    assert method_name_for_key(binder, curses.KEY_F9) == "show_git_panel"
    assert method_name_for_key(binder, curses.KEY_F8) == "toggle_system_doctor_panel"


def test_current_f4_behavior_remains_diagnostics_not_git_panel() -> None:
    binder = make_keybinder()

    assert method_name_for_key(binder, curses.KEY_F4) == "toggle_diagnostics_panel"
    assert method_name_for_key(binder, curses.KEY_F4) != "show_git_panel"


def test_help_text_keeps_existing_panel_and_tool_labels_discoverable() -> None:
    fake_editor = type("HelpEditor", (), {"config": {}})()

    lines = Ecli._build_help_lines(fake_editor)  # type: ignore[arg-type]
    rendered = "\n".join(lines)

    assert "F1" in rendered
    assert "This help screen" in rendered
    assert "F7" in rendered
    assert "AI Code Assistant" in rendered
    assert "F10" in rendered
    assert "File Manager" in rendered
    assert "F9" in rendered
    assert "Git menu" in rendered
    assert "F8" in rendered
    assert "System Doctor" in rendered
    assert "F11" in rendered
    assert "Open/focus PySH Console Panel" in rendered
    assert "F12" in rendered
    assert "Switch focus between editor and panels" in rendered
