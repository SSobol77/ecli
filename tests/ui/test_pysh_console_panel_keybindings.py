# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_pysh_console_panel_keybindings.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import curses
from pathlib import Path
from typing import Any

import pytest

from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.pysh_console_panel import PySHConsolePanel


class _FakeWindow:
    def getmaxyx(self) -> tuple[int, int]:
        return (28, 100)

    def keypad(self, _value: bool) -> None:
        return None

    def bkgd(self, *_args: object) -> None:
        return None


class _FakePanelManager:
    def __init__(self) -> None:
        self.active_panel: object | None = None
        self.close_calls = 0

    def close_active_panel(self) -> None:
        self.close_calls += 1


class _FakeEditor:
    def __init__(self) -> None:
        self.stdscr = _FakeWindow()
        self.colors: dict[str, int] = {}
        self.config: dict[str, Any] = {}
        self.filename = None
        self.focus = "panel"
        self.panel_manager = _FakePanelManager()
        self.toggled_focus = 0

    def _set_status_message(self, _message: str) -> None:
        return None

    def toggle_focus(self) -> bool:
        self.toggled_focus += 1
        return True


class _BinderEditor:
    def __init__(self) -> None:
        self.history = type("History", (), {"undo": self._ok, "redo": self._ok})()
        self.config: dict[str, Any] = {}
        self.stdscr = _FakeWindow()
        self._lexer = None

    def __getattr__(self, _name: str) -> Any:
        return self._ok

    def _ok(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    def toggle_terminal_panel(self) -> bool:
        return True

    def toggle_focus(self) -> bool:
        return True


def _make_panel(monkeypatch: pytest.MonkeyPatch) -> tuple[PySHConsolePanel, _FakeEditor]:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: _FakeWindow())
    editor = _FakeEditor()
    panel = PySHConsolePanel(editor.stdscr, editor)
    panel.visible = True
    editor.panel_manager.active_panel = panel
    return panel, editor


def test_f11_and_f12_keybindings_remain_wired() -> None:
    binder = KeyBinder(_BinderEditor())  # type: ignore[arg-type]

    assert curses.KEY_F11 in binder.keybindings["toggle_terminal_panel"]
    assert curses.KEY_F12 in binder.keybindings["toggle_focus"]
    assert binder.action_map[curses.KEY_F11].__name__ == "toggle_terminal_panel"
    assert binder.action_map[curses.KEY_F12].__name__ == "toggle_focus"


def test_pysh_console_f12_delegates_focus_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel, editor = _make_panel(monkeypatch)

    assert panel.handle_key(curses.KEY_F12) is True

    assert editor.toggled_focus == 1
    assert editor.panel_manager.close_calls == 0


def test_pysh_console_escape_uses_panel_close_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel, editor = _make_panel(monkeypatch)

    assert panel.handle_key(27) is True

    assert editor.panel_manager.close_calls == 1


def test_forbidden_terminal_emulator_paths_are_absent() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    assert not (repo_root / "src/ecli/ui/terminal_screen.py").exists()
    assert not (repo_root / "src/ecli/ui/terminal_session.py").exists()
    assert not (repo_root / "src/ecli/command_backends").exists()
