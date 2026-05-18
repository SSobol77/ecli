# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/ui/test_input_routing.py
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Focused tests for global shortcut routing and input error containment."""

from __future__ import annotations

import curses
import io
import logging
import threading
from pathlib import Path
from typing import Any

from ecli.core.Ecli import Ecli
from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.PanelManager import PanelManager
from ecli.utils.logging_config import setup_logging


class FakeKeyBinder:
    def __init__(self) -> None:
        """Initialize action bindings used by dispatch tests."""
        self.bindings = {
            "help": {curses.KEY_F1, 265, "f1"},
            "toggle_widget_panel": {curses.KEY_F7, 271, "f7"},
        }

    def is_key_for_action(self, key: int | str, action_name: str) -> bool:
        return key in self.bindings.get(action_name, set())


class FakePanelManager:
    def __init__(self, panel_name: str) -> None:
        """Initialize an active panel manager double."""
        self.active_panel = type(panel_name, (), {"visible": True})()
        self.panel_key_calls: list[int | str] = []
        self.close_calls = 0

    def is_panel_active(self) -> bool:
        return bool(getattr(self.active_panel, "visible", False))

    def handle_key(self, key: int | str) -> bool:
        self.panel_key_calls.append(key)
        return True

    def close_active_panel(self) -> None:
        self.close_calls += 1
        self.active_panel.visible = False


class DispatchEditor:
    _handle_input_dispatch = Ecli._handle_input_dispatch
    _is_active_panel_type = Ecli._is_active_panel_type
    _is_file_browser_active = Ecli._is_file_browser_active
    _close_file_browser_for_ai = Ecli._close_file_browser_for_ai
    toggle_widget_panel = Ecli.toggle_widget_panel

    def __init__(self, panel_name: str) -> None:
        """Create a minimal editor object for dispatch routing."""
        self.focus = "panel"
        self.keybinder = FakeKeyBinder()
        self.panel_manager = FakePanelManager(panel_name)
        self.status_message = "Ready"
        self._force_full_redraw = False
        self.editor_key_calls: list[int | str] = []
        self.ai_flow_calls = 0

    def handle_input(self, key: int | str) -> bool:
        if self.keybinder.is_key_for_action(key, "toggle_widget_panel"):
            return self.toggle_widget_panel()
        self.editor_key_calls.append(key)
        return True

    def _set_status_message(self, message: str) -> None:
        self.status_message = message

    def select_ai_provider_and_ask(self) -> bool:
        self.ai_flow_calls += 1
        return True


class SelectionEditor:
    get_selected_text = Ecli.get_selected_text
    _get_normalized_selection_range = Ecli._get_normalized_selection_range

    def __init__(
        self,
        *,
        text: list[str],
        start: tuple[int, int] | None,
        end: tuple[int, int] | None,
        selecting: bool = True,
        cursor_y: int = 0,
    ) -> None:
        """Create a minimal editor selection state."""
        self.text = text
        self.selection_start = start
        self.selection_end = end
        self.is_selecting = selecting
        self.cursor_y = cursor_y


class BinderEditor:
    def __init__(self) -> None:
        """Create a minimal editor for KeyBinder.handle_input tests."""
        self.status_message = "Ready"
        self._state_lock = threading.RLock()
        self._force_full_redraw = False
        self.inserted: list[str] = []

    def _set_status_message(self, message: str) -> None:
        self.status_message = message

    def insert_text(self, text: str) -> bool:
        self.inserted.append(text)
        return True


def _replace_root_handlers(
    log_path: Path,
    *,
    stream_level: int = logging.ERROR,
) -> tuple[list[logging.Handler], int, io.StringIO]:
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    stream = io.StringIO()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(stream)
    stream_handler.setLevel(stream_level)
    root.handlers = [file_handler, stream_handler]
    root.setLevel(logging.DEBUG)
    return old_handlers, old_level, stream


def _restore_root_handlers(
    old_handlers: list[logging.Handler],
    old_level: int,
) -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        handler.close()
    root.handlers = old_handlers
    root.setLevel(old_level)


def test_f1_routes_to_help_before_git_panel() -> None:
    editor = DispatchEditor("GitPanel")

    assert editor._handle_input_dispatch(curses.KEY_F1) is True

    assert editor.editor_key_calls == [curses.KEY_F1]
    assert editor.panel_manager.panel_key_calls == []


def test_f1_routes_to_help_before_file_manager() -> None:
    editor = DispatchEditor("FileBrowserPanel")

    assert editor._handle_input_dispatch(curses.KEY_F1) is True

    assert editor.editor_key_calls == [curses.KEY_F1]
    assert editor.panel_manager.panel_key_calls == []


def test_f1_routes_to_help_before_ai_panel() -> None:
    editor = DispatchEditor("AiResponsePanel")

    assert editor._handle_input_dispatch(curses.KEY_F1) is True

    assert editor.editor_key_calls == [curses.KEY_F1]
    assert editor.panel_manager.panel_key_calls == []


def test_f7_while_file_manager_active_closes_file_manager_and_starts_ai() -> None:
    editor = DispatchEditor("FileBrowserPanel")

    assert editor._handle_input_dispatch(curses.KEY_F7) is True

    assert editor.ai_flow_calls == 1
    assert editor.panel_manager.close_calls == 1
    assert editor.panel_manager.is_panel_active() is False
    assert editor.focus == "editor"
    assert editor.editor_key_calls == []
    assert editor.panel_manager.panel_key_calls == []


def test_f7_while_file_manager_open_with_editor_focus_closes_and_starts_ai() -> None:
    editor = DispatchEditor("FileBrowserPanel")
    editor.focus = "editor"

    assert editor._handle_input_dispatch(curses.KEY_F7) is True

    assert editor.ai_flow_calls == 1
    assert editor.panel_manager.close_calls == 1
    assert editor.panel_manager.is_panel_active() is False
    assert editor.focus == "editor"


def test_f7_while_non_file_panel_active_is_global_but_conservative() -> None:
    editor = DispatchEditor("GitPanel")

    assert editor._handle_input_dispatch(curses.KEY_F7) is True

    assert editor.ai_flow_calls == 0
    assert editor.panel_manager.close_calls == 0
    assert editor.panel_manager.is_panel_active() is True
    assert editor.panel_manager.panel_key_calls == []
    assert (
        editor.status_message
        == "AI Code Assistant is available from the editor. Close active panel first."
    )


def test_get_selected_text_empty_buffer_returns_empty_string() -> None:
    editor = SelectionEditor(text=[], start=(0, 0), end=(0, 1))

    assert editor.get_selected_text() == ""


def test_get_selected_text_cursor_row_out_of_range_does_not_raise() -> None:
    editor = SelectionEditor(
        text=["alpha"],
        start=None,
        end=None,
        selecting=False,
        cursor_y=99,
    )

    assert editor.get_selected_text() == ""


def test_get_selected_text_selection_row_out_of_range_returns_empty() -> None:
    editor = SelectionEditor(text=["alpha"], start=(0, 0), end=(9, 1))

    assert editor.get_selected_text() == ""


def test_get_selected_text_invalid_bounds_do_not_emit_console_warning(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "editor.log"
    old_handlers, old_level, stream = _replace_root_handlers(
        log_path,
        stream_level=logging.WARNING,
    )
    try:
        editor = SelectionEditor(text=["alpha"], start=(0, 0), end=(1, 1))

        assert editor.get_selected_text() == ""

        for handler in logging.getLogger().handlers:
            handler.flush()
        assert stream.getvalue() == ""
        assert "get_selected_text: selection rows out of bounds" in log_path.read_text(
            encoding="utf-8"
        )
    finally:
        _restore_root_handlers(old_handlers, old_level)


def test_get_selected_text_reversed_selection_returns_text() -> None:
    editor = SelectionEditor(text=["abcdef"], start=(0, 4), end=(0, 1))

    assert editor.get_selected_text() == "bcd"


def test_get_selected_text_single_line_selection_returns_text() -> None:
    editor = SelectionEditor(text=["abcdef"], start=(0, 1), end=(0, 4))

    assert editor.get_selected_text() == "bcd"


def test_get_selected_text_multi_line_selection_returns_text() -> None:
    editor = SelectionEditor(
        text=["alpha", "bravo", "charlie"],
        start=(0, 2),
        end=(2, 3),
    )

    assert editor.get_selected_text() == "pha\nbravo\ncha"


def test_keybinder_action_exception_is_file_logged_without_console_traceback(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "editor.log"
    old_handlers, old_level, stream = _replace_root_handlers(log_path)
    try:
        editor = BinderEditor()
        binder = KeyBinder.__new__(KeyBinder)
        binder.editor = editor
        binder.action_map = {"boom": _raise_input_error}
        binder.keybindings = {}

        assert binder.handle_input("boom") is True

        for handler in logging.getLogger().handlers:
            handler.flush()
        log_text = log_path.read_text(encoding="utf-8")
        assert "Input handler critical error" in log_text
        assert "RuntimeError: synthetic input failure" in log_text
        assert stream.getvalue() == ""
        assert editor.status_message == "Input handler error. See logs."
        assert editor._force_full_redraw is True
    finally:
        _restore_root_handlers(old_handlers, old_level)


def test_panel_key_exception_is_file_logged_without_console_traceback(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "editor.log"
    old_handlers, old_level, stream = _replace_root_handlers(log_path)
    try:
        editor = BinderEditor()
        manager = PanelManager.__new__(PanelManager)
        manager.editor = editor
        manager.active_panel = CrashPanel()

        assert manager.handle_key("x") is True

        for handler in logging.getLogger().handlers:
            handler.flush()
        log_text = log_path.read_text(encoding="utf-8")
        assert "Panel key-handler crashed" in log_text
        assert "RuntimeError: synthetic panel failure" in log_text
        assert stream.getvalue() == ""
        assert editor.status_message == "Input handler error. See logs."
        assert editor._force_full_redraw is True
    finally:
        _restore_root_handlers(old_handlers, old_level)


def test_setup_logging_uses_file_handlers_only_for_runtime_logging(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        setup_logging({"logging": {"log_to_console": True, "file_level": "DEBUG"}})

        assert any(
            isinstance(handler, logging.FileHandler) for handler in root.handlers
        )
        assert all(
            isinstance(handler, logging.FileHandler) for handler in root.handlers
        )
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = old_handlers
        root.setLevel(old_level)


def _raise_input_error() -> bool:
    raise RuntimeError("synthetic input failure")


class CrashPanel:
    visible = True

    def handle_key(self, _key: Any) -> bool:
        raise RuntimeError("synthetic panel failure")
