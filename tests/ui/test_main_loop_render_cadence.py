# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_main_loop_render_cadence.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Regression tests for ECLI's render-before-read main-loop cadence."""

from __future__ import annotations

import curses
import importlib
from types import MethodType
from typing import Any

import pytest

from ecli.core.Ecli import Ecli


ECLI_MODULE = importlib.import_module("ecli.core.Ecli")


class LoopStdscr:
    def __init__(self, events: list[str]) -> None:
        """Initialize a fake curses screen that records input timeout changes."""
        self.events = events
        self.timeouts: list[int] = []
        self.current_timeout: int | None = None

    def timeout(self, milliseconds: int) -> None:
        self.current_timeout = milliseconds
        self.timeouts.append(milliseconds)
        self.events.append(f"timeout:{milliseconds}")


class LoopKeyBinder:
    def __init__(
        self, events: list[str], stdscr: LoopStdscr, key_input: int = curses.ERR
    ) -> None:
        """Initialize a key reader double that records the active timeout."""
        self.events = events
        self.stdscr = stdscr
        self.key_input = key_input
        self.active_input_timeout = -1
        self.last_paste = ""

    def get_key_input(self) -> int:
        self.events.append(f"get_key:{self.stdscr.current_timeout}")
        return self.key_input

    def is_key_for_action(self, _key_input: Any, _action: str) -> bool:
        return False


class LoopDrawer:
    def __init__(self, events: list[str]) -> None:
        """Initialize a drawer double that records render phases."""
        self.events = events

    def draw(self) -> None:
        self.events.append("draw")

    def _position_cursor(self) -> None:
        self.events.append("position_cursor")


class TickPanel:
    def __init__(self, wants_tick: bool) -> None:
        """Initialize a panel double with a fixed periodic-repaint state."""
        self.wants_tick = wants_tick

    def wants_periodic_repaint(self) -> bool:
        return self.wants_tick


class LoopPanelManager:
    def __init__(self, events: list[str], wants_tick: bool) -> None:
        """Initialize a panel manager double exposing one active panel."""
        self.events = events
        self.active_panel = TickPanel(wants_tick)

    def is_panel_active(self) -> bool:
        return self.active_panel is not None

    def draw_active_panel(self) -> None:
        self.events.append("draw_panel")

    def handle_key(self, _key: Any) -> bool:
        return False


class LoopEditor:
    PANEL_TICK_MS = Ecli.PANEL_TICK_MS

    def __init__(
        self,
        *,
        force_redraw: bool,
        queue_changed: bool,
        wants_tick: bool,
        key_input: int = curses.ERR,
        key_opens_tick: bool = False,
    ) -> None:
        """Initialize an editor double wired to the real loop helpers."""
        self.events: list[str] = []
        self._force_full_redraw = force_redraw
        self._queue_changed = queue_changed
        self._key_opens_tick = key_opens_tick
        self._panel_tick_active = False
        self.focus = "editor"
        self.stdscr = LoopStdscr(self.events)
        self.keybinder = LoopKeyBinder(self.events, self.stdscr, key_input)
        self.drawer = LoopDrawer(self.events)
        self.panel_manager = LoopPanelManager(self.events, wants_tick)

        self._active_panel_wants_tick = MethodType(Ecli._active_panel_wants_tick, self)
        self._sync_input_cadence = MethodType(Ecli._sync_input_cadence, self)
        self._pre_input_redraw_needed = MethodType(Ecli._pre_input_redraw_needed, self)
        self._read_and_dispatch_input = MethodType(Ecli._read_and_dispatch_input, self)
        self._render_screen = MethodType(Ecli._render_screen, self)
        self._run_loop_iteration = MethodType(Ecli._run_loop_iteration, self)

    def _process_all_queues(self) -> bool:
        self.events.append("process_queues")
        return self._queue_changed

    def _handle_paste_event(self, _text: str) -> bool:
        return False

    def _handle_mouse_event(self) -> bool:
        return False

    def handle_resize(self) -> bool:
        return False

    def _handle_input_dispatch(self, _key_input: Any) -> bool:
        if self._key_opens_tick:
            self.panel_manager.active_panel.wants_tick = True
            return True
        return False


def _patch_core_curses(monkeypatch: pytest.MonkeyPatch, editor: LoopEditor) -> None:
    monkeypatch.setattr(
        ECLI_MODULE.curses,
        "curs_set",
        lambda value: editor.events.append(f"curs_set:{value}"),
    )
    monkeypatch.setattr(
        ECLI_MODULE.curses,
        "doupdate",
        lambda: editor.events.append("doupdate"),
    )


def test_initial_forced_redraw_flushes_before_first_input_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor = LoopEditor(force_redraw=True, queue_changed=False, wants_tick=False)
    _patch_core_curses(monkeypatch, editor)

    editor._run_loop_iteration()

    assert editor.events.index("draw") < editor.events.index("doupdate")
    assert editor.events.index("doupdate") < editor.events.index("get_key:-1")
    assert editor.stdscr.timeouts == [-1]
    assert 0 not in editor.stdscr.timeouts


def test_queue_redraw_flushes_before_blocking_idle_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor = LoopEditor(force_redraw=False, queue_changed=True, wants_tick=False)
    _patch_core_curses(monkeypatch, editor)

    editor._run_loop_iteration()

    assert editor.events.index("process_queues") < editor.events.index("draw")
    assert editor.events.index("doupdate") < editor.events.index("get_key:-1")
    assert editor.stdscr.timeouts == [-1]
    assert 0 not in editor.stdscr.timeouts


def test_idle_without_animation_blocks_after_no_pending_render() -> None:
    editor = LoopEditor(force_redraw=False, queue_changed=False, wants_tick=False)

    editor._run_loop_iteration()

    assert "draw" not in editor.events
    assert editor.events[-2:] == ["timeout:-1", "get_key:-1"]
    assert editor.keybinder.active_input_timeout == -1


def test_collecting_diagnostics_uses_finite_tick_after_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor = LoopEditor(force_redraw=False, queue_changed=False, wants_tick=True)
    _patch_core_curses(monkeypatch, editor)

    editor._run_loop_iteration()

    assert editor.events.index("doupdate") < editor.events.index(
        f"timeout:{Ecli.PANEL_TICK_MS}"
    )
    assert editor.events[-1] == f"get_key:{Ecli.PANEL_TICK_MS}"
    assert 100 <= Ecli.PANEL_TICK_MS <= 250
    assert editor.keybinder.active_input_timeout == Ecli.PANEL_TICK_MS
    assert 0 not in editor.stdscr.timeouts


def test_key_opening_collecting_panel_arms_tick_after_panel_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor = LoopEditor(
        force_redraw=False,
        queue_changed=False,
        wants_tick=False,
        key_input=ord("x"),
        key_opens_tick=True,
    )
    _patch_core_curses(monkeypatch, editor)

    editor._run_loop_iteration()

    assert editor.stdscr.timeouts == [-1, Ecli.PANEL_TICK_MS]
    assert editor.events.index("get_key:-1") < editor.events.index("draw")
    assert editor.events.index("doupdate") < editor.events.index(
        f"timeout:{Ecli.PANEL_TICK_MS}"
    )
    assert editor.keybinder.active_input_timeout == Ecli.PANEL_TICK_MS
    assert 0 not in editor.stdscr.timeouts
