# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_terminal_panel_reservation.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Smoke tests for the ECLI-owned PySH Console Panel integration.

These assert that F11 now opens/focuses the PySH Console Panel while the legacy
``TerminalPanel`` class remains absent.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, cast

import pytest

import ecli.ui.panels as panels_module
from ecli.core.Ecli import Ecli
from ecli.integrations.pysh_backend import MISSING_PYSH_MESSAGE, PySHSubprocessBackend
from ecli.ui.geometry import compute_layout
from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.panels import MODAL_PANEL_KINDS, SIDE_PANEL_KINDS
from ecli.ui.pysh_console_panel import PySHConsolePanel


def test_terminal_is_a_reserved_side_panel_kind() -> None:
    assert "terminal" in SIDE_PANEL_KINDS
    assert "terminal" not in MODAL_PANEL_KINDS


def test_legacy_terminal_panel_class_is_not_active() -> None:
    assert not hasattr(panels_module, "TerminalPanel")


class _FakePanel:
    visible = False


class _FakePanelManager:
    def __init__(self) -> None:
        self.active_panel: object | None = None
        self.shown: list[object] = []

    def show_panel_instance(self, panel: object) -> None:
        self.active_panel = panel
        self.shown.append(panel)
        panel.visible = True  # type: ignore[attr-defined]


class _KeyBinderEditor:
    def __init__(self) -> None:
        self.history = type("History", (), {"undo": self._ok, "redo": self._ok})()
        self.config: dict[str, Any] = {}
        self.stdscr = _FakeWin()
        self.status_message = "Ready"
        self._state_lock = threading.RLock()
        self._force_full_redraw = False
        self.is_lightweight = True
        self.linter_bridge = None
        self._lexer = None
        self.terminal_panel_toggles = 0

    def __getattr__(self, _name: str) -> Any:
        return self._ok

    def _ok(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    def _set_status_message(self, message: str) -> None:
        self.status_message = message

    def insert_text(self, text: str) -> bool:
        self.status_message = f"inserted {text}"
        return True

    def toggle_terminal_panel(self) -> bool:
        self.terminal_panel_toggles += 1
        self.status_message = "PySH Console Panel opened."
        return True


def test_toggle_terminal_panel_opens_pysh_console_panel() -> None:
    editor = cast(Any, Ecli.__new__(Ecli))
    messages: list[str] = []
    editor._set_status_message = lambda m, *a, **k: messages.append(m)
    editor._force_full_redraw = False
    editor.focus = "editor"
    panel = _FakePanel()
    manager = _FakePanelManager()
    editor.panel_manager = manager
    editor.pysh_console_panel_instance = panel

    assert editor.toggle_terminal_panel() is True
    assert manager.shown == [panel]
    assert panel.visible is True
    assert messages == ["PySH Console Panel opened."]


def test_toggle_terminal_panel_focuses_existing_pysh_console_panel() -> None:
    editor = cast(Any, Ecli.__new__(Ecli))
    messages: list[str] = []
    editor._set_status_message = lambda m, *a, **k: messages.append(m)
    editor._force_full_redraw = False
    editor.focus = "editor"
    panel = _FakePanel()
    panel.visible = True
    manager = _FakePanelManager()
    manager.active_panel = panel
    editor.panel_manager = manager
    editor.pysh_console_panel_instance = panel

    assert editor.toggle_terminal_panel() is True
    assert manager.shown == []
    assert editor.focus == "panel"
    assert editor._force_full_redraw is True
    assert messages == ["PySH Console Panel focused."]


def test_f11_opens_pysh_console_panel_action() -> None:
    editor = _KeyBinderEditor()
    binder = KeyBinder(editor)  # type: ignore[arg-type]

    assert binder.handle_input(275) is True
    assert editor.terminal_panel_toggles == 1
    assert editor.status_message == "PySH Console Panel opened."


# --- PySH Console Panel inherits the existing side-panel split layout ----


class _FakeWin:
    def __init__(self) -> None:
        """Minimal curses-window stand-in."""
        self.bkgd_calls: list[tuple[Any, ...]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (32, 120)

    def keypad(self, _value: bool) -> None:
        return None

    def bkgd(self, *args: object) -> None:
        self.bkgd_calls.append(args)

    def touchwin(self) -> None:
        return None

    def noutrefresh(self) -> None:
        return None


class _FakeEditor:
    def __init__(self) -> None:
        """Editor double exposing only what BasePanel geometry needs."""
        self.stdscr = _FakeWin()
        self.colors: dict[str, int] = {}
        self.is_lightweight = False


def test_pysh_console_panel_gets_split_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: _FakeWin())
    editor = _FakeEditor()
    backend = PySHSubprocessBackend(executable="missing-ecli-pysh")
    panel = PySHConsolePanel(editor.stdscr, cast(Any, editor), backend=backend)

    panel._layout_window()

    geo = compute_layout(120, 32, active_panel=True)
    assert geo.panel is not None
    assert panel.win is not None
    assert panel.panel_kind == "terminal"
    assert panel._rendered_as_modal is False
    # Same 60/40 split, work-area rows only, no global-chrome overlap.
    assert panel.start_y == geo.panel.y == 1
    assert panel.start_x == geo.editor.width
    assert panel.start_x + panel.width == 120
    assert panel.start_y + panel.height <= 32 - 2
    # Opaque background applied like every other side panel.
    assert panel.win.bkgd_calls


def test_pysh_backend_missing_executable_returns_deterministic_result(
    tmp_path: Path,
) -> None:
    backend = PySHSubprocessBackend(executable="missing-ecli-pysh")

    result = backend.run("echo hello", tmp_path, {})

    assert result.returncode == 127
    assert result.stdout == ""
    assert result.stderr == MISSING_PYSH_MESSAGE
    assert result.cancelled is False
