# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_diagnostics_keybinding.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""F4 keybinding tests for the Diagnostics panel; F11 PySH stays independent."""

from __future__ import annotations

import curses
import types
from typing import Any

from ecli.core.Ecli import Ecli
from ecli.ui.KeyBinder import KeyBinder


class FakeWindow:
    def getmaxyx(self) -> tuple[int, int]:
        return (30, 100)


class BinderEditor:
    def __init__(self) -> None:
        """Initialize a minimal editor double for KeyBinder construction."""
        self.history = type("History", (), {"undo": self._ok, "redo": self._ok})()
        self.config: dict[str, Any] = {}
        self.stdscr = FakeWindow()
        self._lexer = None

    def __getattr__(self, _name: str) -> Any:
        """Return a no-op callable for any unmapped editor attribute."""
        return self._ok

    def _ok(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    def toggle_diagnostics_panel(self) -> bool:
        return True

    def toggle_terminal_panel(self) -> bool:
        return True

    def toggle_focus(self) -> bool:
        return True


class FakePanelManager:
    def __init__(self) -> None:
        """Record panels requested via show_panel."""
        self.shown: list[tuple[str, dict[str, Any]]] = []

    def show_panel(self, name: str, **kwargs: Any) -> None:
        self.shown.append((name, kwargs))


class FakeEditor:
    def __init__(self) -> None:
        """Initialize an editor double exposing the diagnostics wiring."""
        self.panel_manager = FakePanelManager()
        self.diagnostics_service = object()
        self.status_messages: list[str] = []

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)


# --------------------------------------------------------------------------- #
# F4 is bound to the Diagnostics panel.
# --------------------------------------------------------------------------- #


def test_f4_is_bound_to_toggle_diagnostics_panel() -> None:
    binder = KeyBinder(BinderEditor())  # type: ignore[arg-type]

    assert curses.KEY_F4 in binder.keybindings["toggle_diagnostics_panel"]
    assert binder.action_map[curses.KEY_F4].__name__ == "toggle_diagnostics_panel"
    assert 268 in binder.keybindings["toggle_diagnostics_panel"]


def test_toggle_diagnostics_panel_opens_diagnostics_view() -> None:
    editor = FakeEditor()

    assert Ecli.toggle_diagnostics_panel(editor) is True  # type: ignore[arg-type]

    name, kwargs = editor.panel_manager.shown[-1]
    assert name == "diagnostics"
    assert kwargs["service"] is editor.diagnostics_service


# --------------------------------------------------------------------------- #
# F4 does not disturb the F11 PySH Console panel or F12 focus toggle.
# --------------------------------------------------------------------------- #


def test_f4_does_not_affect_f11_pysh_or_f12_focus() -> None:
    binder = KeyBinder(BinderEditor())  # type: ignore[arg-type]

    assert curses.KEY_F11 in binder.keybindings["toggle_terminal_panel"]
    assert curses.KEY_F12 in binder.keybindings["toggle_focus"]
    assert binder.action_map[curses.KEY_F11].__name__ == "toggle_terminal_panel"
    assert binder.action_map[curses.KEY_F12].__name__ == "toggle_focus"
    # F4 and F11 are distinct keys mapped to distinct actions.
    assert curses.KEY_F4 not in binder.keybindings["toggle_terminal_panel"]
    assert curses.KEY_F11 not in binder.keybindings["toggle_diagnostics_panel"]


def test_lint_action_no_longer_owns_f4() -> None:
    binder = KeyBinder(BinderEditor())  # type: ignore[arg-type]
    assert "lint" not in binder.keybindings


# --------------------------------------------------------------------------- #
# Main-loop input cadence: a collecting panel drives a bounded repaint tick
# without user input, then the loop returns to a blocking read (#104 UX).
# --------------------------------------------------------------------------- #


class TickStdscr:
    def __init__(self) -> None:
        """Record every curses input-timeout change."""
        self.timeouts: list[int] = []

    def timeout(self, milliseconds: int) -> None:
        self.timeouts.append(milliseconds)


class TickPanel:
    def __init__(self, wants: bool) -> None:
        """Panel double that opts into periodic repaint via the public hook."""
        self._wants = wants

    def wants_periodic_repaint(self) -> bool:
        return self._wants


class PlainPanel:
    """Panel double without the repaint hook (e.g. F11 PySH console)."""


class TickPanelManager:
    def __init__(self, panel: Any) -> None:
        """Expose a single active panel to the cadence helpers."""
        self.active_panel = panel

    def is_panel_active(self) -> bool:
        return self.active_panel is not None


class TickEditor:
    PANEL_TICK_MS = Ecli.PANEL_TICK_MS

    class _KeyBinderStub:
        def __init__(self) -> None:
            self.active_input_timeout = -1

    def __init__(self, panel: Any) -> None:
        """Minimal editor double exposing the real cadence wiring under test."""
        self.stdscr = TickStdscr()
        self.panel_manager = TickPanelManager(panel)
        self._panel_tick_active = False
        self.keybinder = TickEditor._KeyBinderStub()
        # Exercise the genuine Ecli implementations against this double.
        self._active_panel_wants_tick = types.MethodType(
            Ecli._active_panel_wants_tick, self
        )
        self._sync_input_cadence = types.MethodType(Ecli._sync_input_cadence, self)


def test_collecting_panel_drives_tick_then_idle_block() -> None:
    panel = TickPanel(wants=True)
    editor = TickEditor(panel)
    tick_active_attr = "_panel_tick_active"

    # While collecting: bounded tick timeout, shared with the KeyBinder so its
    # read helpers cannot clobber it back to blocking.
    editor._sync_input_cadence()
    assert editor.stdscr.timeouts[-1] == Ecli.PANEL_TICK_MS
    assert 100 <= Ecli.PANEL_TICK_MS <= 250
    assert getattr(editor, tick_active_attr) is True
    assert editor.keybinder.active_input_timeout == Ecli.PANEL_TICK_MS

    # Re-asserted every iteration so a key read mid-collection cannot freeze it.
    editor._sync_input_cadence()
    assert editor.stdscr.timeouts[-1] == Ecli.PANEL_TICK_MS

    # Collection finishes and nothing else pending: idle blocking read.
    panel._wants = False
    editor._sync_input_cadence(pending_redraw=False)
    assert editor.stdscr.timeouts[-1] == -1
    assert getattr(editor, tick_active_attr) is False
    assert editor.keybinder.active_input_timeout == -1


def test_pending_redraw_does_not_arm_poll_cadence() -> None:
    # The render-before-read loop flushes pending draw work before selecting the
    # input cadence. A stale pending_redraw=True call is therefore a defensive
    # no-op and must not reintroduce timeout(0) polling.
    editor = TickEditor(PlainPanel())
    editor._sync_input_cadence(pending_redraw=True)
    assert editor.stdscr.timeouts[-1] == -1
    assert editor.keybinder.active_input_timeout == -1
    assert 0 not in editor.stdscr.timeouts


def test_panel_without_repaint_hook_idles_blocking() -> None:
    editor = TickEditor(PlainPanel())
    assert editor._active_panel_wants_tick() is False
    editor._sync_input_cadence(pending_redraw=False)
    # A panel that does not opt in falls back to a blocking idle read.
    assert editor.stdscr.timeouts[-1] == -1


def test_pysh_console_panel_does_not_opt_into_periodic_repaint() -> None:
    # F11 PySH stays untouched: it must not request the diagnostics repaint tick.
    from ecli.ui.pysh_console_panel import PySHConsolePanel

    assert not hasattr(PySHConsolePanel, "wants_periodic_repaint")


# --------------------------------------------------------------------------- #
# KeyBinder must not clobber the editor-chosen input cadence while reading.
# --------------------------------------------------------------------------- #


class ScriptedWindow:
    def __init__(self, keys: list[int]) -> None:
        """A window double that replays a key script and records timeouts."""
        self._keys = list(keys)
        self.timeout_calls: list[int] = []

    def getch(self) -> int:
        return self._keys.pop(0) if self._keys else curses.ERR

    def nodelay(self, _flag: bool) -> None:
        return None

    def timeout(self, milliseconds: int) -> None:
        self.timeout_calls.append(milliseconds)

    def keypad(self, _flag: bool) -> None:
        return None


def test_get_key_input_restores_editor_cadence_not_blocking() -> None:
    # Regression: reading an ESC/arrow/function-key sequence while the F4
    # Diagnostics panel is collecting must NOT reset the read to blocking mode.
    # The escape-branch finally restores the editor-chosen cadence instead.
    binder = KeyBinder(BinderEditor())  # type: ignore[arg-type]
    binder.active_input_timeout = 120  # editor is in the diagnostics tick cadence

    win = ScriptedWindow([27, ord("O"), ord("S")])  # ESC O S == F4 (SS3)
    code = binder.get_key_input(window=win)  # type: ignore[arg-type]

    assert code == curses.KEY_F4
    # The last input-mode change restored the periodic-repaint timeout, never a
    # hardcoded blocking (-1) or 35ms read.
    assert win.timeout_calls, "ESC read must restore the input cadence"
    assert win.timeout_calls[-1] == 120
