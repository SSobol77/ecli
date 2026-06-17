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

"""Architecture-readiness tests for the future Terminal Panel (not implemented).

These assert that the generic split-layout/panel system explicitly *reserves*
the ``terminal`` panel kind and the F11 keybinding, and that a future terminal
side panel would inherit the existing split layout unchanged — without any PTY,
subprocess or terminal UI being present yet.
"""

from __future__ import annotations

import inspect

import pytest

import ecli.ui.panels as panels_module
from ecli.core.Ecli import Ecli
from ecli.ui.geometry import compute_layout
from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.panels import MODAL_PANEL_KINDS, SIDE_PANEL_KINDS, BasePanel


def test_terminal_is_a_reserved_side_panel_kind() -> None:
    assert "terminal" in SIDE_PANEL_KINDS
    assert "terminal" not in MODAL_PANEL_KINDS


def test_terminal_panel_is_not_implemented_yet() -> None:
    # Reserved vocabulary only: no TerminalPanel class, no PTY/subprocess wiring.
    assert not hasattr(panels_module, "TerminalPanel")


def test_toggle_terminal_panel_is_a_safe_noop() -> None:
    editor = Ecli.__new__(Ecli)
    messages: list[str] = []
    editor._set_status_message = lambda m, *a, **k: messages.append(m)  # type: ignore[method-assign]
    # Must not crash, must not open a panel or start anything; just reports back.
    assert editor.toggle_terminal_panel() is True
    assert messages and "Terminal" in messages[0]


def test_f11_is_reserved_for_terminal_panel() -> None:
    source = inspect.getsource(KeyBinder)
    assert '"toggle_terminal_panel"' in source
    assert "f11" in source
    assert "self.editor.toggle_terminal_panel" in source


# --- A representative future terminal side panel inherits the split layout ----


class _FakeWin:
    def __init__(self) -> None:
        """Minimal curses-window stand-in."""
        self.bkgd_calls: list[tuple] = []

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


class _TerminalLikePanel(BasePanel):
    """Stand-in for the FUTURE Terminal Panel; no PTY/subprocess here."""

    panel_kind = "terminal"
    is_modal_panel = False


def test_future_terminal_side_panel_gets_split_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: _FakeWin())
    editor = _FakeEditor()
    panel = _TerminalLikePanel(editor.stdscr, editor)  # type: ignore[arg-type]

    panel._layout_window()

    geo = compute_layout(120, 32, active_panel=True)
    assert panel.panel_kind == "terminal"
    assert panel._rendered_as_modal is False
    # Same 60/40 split, work-area rows only, no global-chrome overlap.
    assert panel.start_y == geo.panel.y == 1
    assert panel.start_x == geo.editor.width
    assert panel.start_x + panel.width == 120
    assert panel.start_y + panel.height <= 32 - 2
    # Opaque background applied like every other side panel.
    assert panel.win.bkgd_calls
