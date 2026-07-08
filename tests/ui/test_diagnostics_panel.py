"""Tests for the F4 Diagnostics panel integration."""

from __future__ import annotations

import curses
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest

from ecli.core.Ecli import Ecli
from ecli.extensions.linters.biome.provider import BiomeDiagnosticProvider
from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticRequest,
    DiagnosticsSnapshot,
)
from ecli.extensions.linters.core.service import DiagnosticsService
from ecli.extensions.linters.ruff.provider import RuffDiagnosticProvider
from ecli.ui.DrawScreen import DrawScreen
from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.panels import DiagnosticsPanel


FAKE_WINDOWS: list[FakeWindow] = []


class FakeWindow:
    def __init__(self) -> None:
        """Initialize captured fake window state."""
        self.drawn: list[str] = []
        self.drawn_attrs: list[tuple[str, int | None]] = []
        self.addstr_calls: list[tuple[int, int, str, int | None]] = []
        self.chgat_calls: list[tuple[int, int, int, int]] = []
        self.keypad_values: list[bool] = []
        FAKE_WINDOWS.append(self)

    def getmaxyx(self) -> tuple[int, int]:
        return (30, 120)

    def keypad(self, value: bool) -> None:
        self.keypad_values.append(value)

    def bkgd(self, *_args: object) -> None:
        return None

    def erase(self) -> None:
        self.drawn.clear()
        self.drawn_attrs.clear()

    def border(self) -> None:
        return None

    def addstr(self, *_args: Any) -> None:
        if len(_args) >= 3:
            y = int(_args[0])
            x = int(_args[1])
            text = str(_args[2])
            attr = (
                int(_args[3]) if len(_args) >= 4 and isinstance(_args[3], int) else None
            )
            self.addstr_calls.append((y, x, text, attr))

    def addnstr(self, *_args: Any) -> None:
        if len(_args) >= 4:
            text = str(_args[2])[: int(_args[3])]
            attr = (
                int(_args[4]) if len(_args) >= 5 and isinstance(_args[4], int) else None
            )
            self.drawn.append(text)
            self.drawn_attrs.append((text, attr))

    def chgat(self, *_args: Any) -> None:
        if len(_args) >= 4:
            self.chgat_calls.append(
                (int(_args[0]), int(_args[1]), int(_args[2]), int(_args[3]))
            )

    def touchwin(self) -> None:
        return None

    def noutrefresh(self) -> None:
        return None

    def refresh(self) -> None:
        return None


class FakePanelManager:
    def __init__(self) -> None:
        """Initialize panel lifecycle call capture."""
        self.active_panel: object | None = None
        self.close_calls = 0
        self.show_calls: list[object] = []

    def is_panel_active(self) -> bool:
        return bool(getattr(self.active_panel, "visible", False))

    def show_panel_instance(self, panel: object) -> None:
        self.show_calls.append(panel)
        if self.active_panel is panel and getattr(panel, "visible", False):
            self.close_active_panel()
            return
        self.active_panel = panel
        panel.visible = True  # type: ignore[attr-defined]

    def close_active_panel(self) -> None:
        self.close_calls += 1
        if self.active_panel is not None:
            self.active_panel.visible = False  # type: ignore[attr-defined]


class FakeBridge:
    def __init__(self, snapshot: DiagnosticsSnapshot | None = None) -> None:
        """Initialize diagnostics bridge call capture."""
        self.requests: list[str] = []
        self.diagnostics_snapshot = snapshot or DiagnosticsSnapshot()

    def request_diagnostics_refresh(self, scope: str = "buffer") -> bool:
        self.requests.append(scope)
        return True


class FakeEditor:
    def __init__(self, snapshot: DiagnosticsSnapshot | None = None) -> None:
        """Initialize a diagnostics-panel-compatible editor double."""
        self.stdscr = FakeWindow()
        self.colors: dict[str, int] = {
            "ui_success": 101,
            "ui_panel_success": 105,
            "ui_status_success": 106,
            "ui_panel_warning": 102,
            "ui_panel_error": 103,
            "ui_info": 104,
        }
        self.focus = "panel"
        self._force_full_redraw = False
        self.status_message = "Ready"
        self.status_messages: list[str] = []
        self.filename: str | None = None
        self.modified = False
        self._lexer = type("Lexer", (), {"name": "Python"})()
        self.encoding = "utf-8"
        self.cursor_y = 0
        self.cursor_x = 0
        self.text = [""]
        self.insert_mode = True
        self.git = None
        self.config: dict[str, Any] = {}
        self.is_lightweight = False
        self.service_registry = None
        self.panel_manager = FakePanelManager()
        self.linter_bridge = FakeBridge(snapshot)
        self.navigated: list[Diagnostic] = []
        self.lint_panel_active = False
        self.lint_panel_message = ""
        self.drawer = type("Drawer", (), {"_next_lint_panel_hide_ts": 0})()
        self.diagnostic_line_highlight: dict[str, Any] | None = None

    def _set_status_message(self, message: str) -> None:
        self.status_message = message
        self.status_messages.append(message)

    def toggle_focus(self) -> bool:
        self.focus = "editor" if self.focus == "panel" else "panel"
        return True

    def goto_diagnostic(self, diagnostic: Diagnostic) -> bool:
        self.navigated.append(diagnostic)
        path = Path(diagnostic.file_path).name
        self._set_status_message(
            f"Jumped to {path}:{diagnostic.line}:{diagnostic.column}"
        )
        return True

    def set_diagnostic_line_highlight(
        self,
        diagnostic: Diagnostic,
        *,
        generation: int | None = None,
    ) -> None:
        self.diagnostic_line_highlight = {
            "file_path": os.path.abspath(diagnostic.file_path),
            "line": diagnostic.line,
            "severity": diagnostic.severity,
            "generation": generation,
        }

    def clear_diagnostic_line_highlight(self) -> None:
        self.diagnostic_line_highlight = None

    def get_string_width(self, text: str) -> int:
        return len(text)


class BinderEditor:
    def __init__(self) -> None:
        """Initialize a KeyBinder-compatible editor double."""
        self.history = type("History", (), {"undo": self._ok, "redo": self._ok})()
        self.config: dict[str, Any] = {}
        self.stdscr = FakeWindow()
        self.is_lightweight = False
        self.linter_bridge = object()
        self.async_engine = None
        self.status_message = "Ready"
        self._lexer = None
        self._state_lock = threading.RLock()
        self.toggle_calls = 0

    def __getattr__(self, _name: str) -> Any:
        """Return a truthy no-op for unrelated editor actions."""
        return self._ok

    def _ok(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    def _set_status_message(self, message: str) -> None:
        self.status_message = message

    def insert_text(self, text: str) -> bool:
        self.status_message = text
        return True

    def toggle_diagnostics_panel(self) -> bool:
        self.toggle_calls += 1
        return True


@pytest.fixture(autouse=True)
def fake_curses(monkeypatch: pytest.MonkeyPatch) -> None:
    FAKE_WINDOWS.clear()
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: FakeWindow())
    monkeypatch.setattr("ecli.ui.panels.curses.curs_set", lambda value: None)


def make_panel(
    snapshot: DiagnosticsSnapshot | None = None,
) -> tuple[DiagnosticsPanel, FakeEditor]:
    editor = FakeEditor(snapshot)
    panel = DiagnosticsPanel(editor.stdscr, editor)  # type: ignore[arg-type]
    editor.panel_manager.active_panel = panel
    return panel, editor


def rendered(panel: DiagnosticsPanel) -> str:
    return "\n".join(cast(FakeWindow, panel.win).drawn)


def rendered_popup() -> str:
    return "\n".join(FAKE_WINDOWS[-1].drawn)


def diagnostics_rows(panel: DiagnosticsPanel) -> list[str]:
    return [
        line
        for line in cast(FakeWindow, panel.win).drawn
        if line.startswith(("E ", "W ", "I ", "H "))
    ]


def drawn_attr(panel: DiagnosticsPanel, text: str) -> int | None:
    for line, attr in cast(FakeWindow, panel.win).drawn_attrs:
        if line == text:
            return attr
    return None


def test_f4_key_opens_diagnostics_panel() -> None:
    editor = BinderEditor()
    binder = KeyBinder(editor)  # type: ignore[arg-type]

    assert binder.handle_input(curses.KEY_F4) is True

    assert editor.toggle_calls == 1


def test_f4_and_escape_close_diagnostics_panel() -> None:
    editor = cast(Any, Ecli.__new__(Ecli))
    manager = FakePanelManager()
    panel = type("Panel", (), {"visible": False})()
    editor.panel_manager = manager
    editor.diagnostics_panel_instance = panel
    editor._set_status_message = lambda _message: None

    assert editor.toggle_diagnostics_panel() is True
    assert panel.visible is True
    assert editor.toggle_diagnostics_panel() is True
    assert panel.visible is False

    diagnostics_panel, diagnostics_editor = make_panel()
    diagnostics_panel.visible = True
    assert diagnostics_panel.handle_key(27) is True
    assert diagnostics_editor.panel_manager.close_calls == 1


def test_ctrl_q_exits_while_diagnostics_panel_is_active() -> None:
    class FakeKeyBinder:
        def is_key_for_action(self, key: int | str, action_name: str) -> bool:
            return action_name == "quit" and key == 17

    editor = cast(Any, Ecli.__new__(Ecli))
    editor.focus = "panel"
    editor.keybinder = FakeKeyBinder()
    editor.panel_manager = FakePanelManager()
    editor.panel_manager.active_panel = type("Panel", (), {"visible": True})()
    editor.handled: list[int | str] = []
    editor.handle_input = lambda key: editor.handled.append(key) or True

    assert editor._handle_input_dispatch(17) is True

    assert editor.handled == [17]


def test_event_queues_are_drained_after_waiting_for_key_before_dispatch() -> None:
    class FakeKeyReader:
        PASTE_EVENT = KeyBinder.PASTE_EVENT
        last_paste = ""

        def get_key_input(self) -> int:
            return curses.KEY_ENTER

    editor = cast(Any, Ecli.__new__(Ecli))
    editor.keybinder = FakeKeyReader()
    editor.events: list[str] = []
    editor.queue_drains = 0
    editor.diagnostics_ready = False

    def drain_queues() -> bool:
        editor.queue_drains += 1
        editor.events.append(f"drain-{editor.queue_drains}")
        if editor.queue_drains == 2:
            editor.diagnostics_ready = True
            return True
        return False

    def dispatch(key: int) -> bool:
        assert key == curses.KEY_ENTER
        editor.events.append(f"dispatch-ready-{editor.diagnostics_ready}")
        return True

    editor._process_all_queues = drain_queues
    editor._handle_input_dispatch = dispatch

    assert editor._process_events_and_input() is True

    assert editor.events == ["drain-1", "drain-2", "dispatch-ready-True"]


def test_panel_open_does_not_schedule_ruff() -> None:
    panel, editor = make_panel()

    panel.open()

    assert editor.linter_bridge.requests == []


def test_initial_panel_state_and_action_bar_are_explicit() -> None:
    panel, _editor = make_panel()
    panel.width = 90
    panel.visible = True
    panel.draw()

    text = rendered(panel)
    assert "Diagnostics not run yet." in text
    assert "Press r to run diagnostics for this file." in text
    assert "r:Run file" in text
    assert "d:Details" in text


def test_refresh_keys_schedule_background_diagnostics() -> None:
    panel, editor = make_panel()
    panel.visible = True

    assert panel.handle_key(ord("r")) is True
    assert panel.handle_key(ord("R")) is True

    assert editor.linter_bridge.requests == ["buffer", "workspace"]


def test_clean_skipped_and_error_states_are_rendered() -> None:
    running_panel, _editor = make_panel(DiagnosticsSnapshot(status="running"))
    running_panel.visible = True
    running_panel.draw()

    assert "Running diagnostics..." in rendered(running_panel)

    empty_panel, _editor = make_panel(DiagnosticsSnapshot(status="ready"))
    empty_panel.visible = True
    empty_panel.draw()

    text = rendered(empty_panel)
    assert "Diagnostics: PASS" in text
    assert "No issues found." in text
    assert "No diagnostics" not in text
    assert drawn_attr(empty_panel, "Diagnostics: PASS") == 105

    skipped_panel, _editor = make_panel(
        DiagnosticsSnapshot(status="skipped", message="not a Python file")
    )
    skipped_panel.visible = True
    skipped_panel.draw()

    assert "Diagnostics skipped: not a Python file" in rendered(skipped_panel)

    error_panel, _editor = make_panel(
        DiagnosticsSnapshot(status="error", message="Ruff executable not found")
    )
    error_panel.visible = True
    error_panel.draw()

    assert "Diagnostics failed: Ruff executable not found" in rendered(error_panel)


def test_pass_status_message_uses_success_style_hook(tmp_path: Path) -> None:
    editor = FakeEditor()
    editor.status_message = "Diagnostics: PASS — no issues found."
    editor.filename = str(tmp_path / "f4_bad.py")
    window = FakeWindow()
    drawer = cast(Any, DrawScreen.__new__(DrawScreen))
    drawer.editor = editor
    drawer.stdscr = window
    drawer.colors = editor.colors
    drawer.config = {}

    drawer._draw_status_bar()

    assert any(call[3] == 106 for call in window.chgat_calls)


def test_enter_navigation_uses_editor_diagnostic_path(tmp_path: Path) -> None:
    diagnostic_path = tmp_path / "example.py"
    diagnostic_path.write_text("print('example')\n", encoding="utf-8")
    diagnostic = Diagnostic(
        file_path=str(diagnostic_path),
        line=7,
        column=3,
        severity="warning",
        code="F401",
        message="unused import",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(diagnostic,),
            status="ready",
            message="Diagnostics: 1 issue(s).",
        )
    )
    panel.visible = True
    panel.draw()
    cursor_before = getattr(editor, "cursor_y", None)

    assert panel.handle_key(curses.KEY_ENTER) is True

    assert editor.navigated == [diagnostic]
    assert editor.diagnostic_line_highlight == {
        "file_path": os.path.abspath(str(diagnostic_path)),
        "line": 7,
        "severity": "warning",
        "generation": 1,
    }
    assert getattr(editor, "cursor_y", None) == cursor_before
    assert editor.lint_panel_active is False
    assert panel._details_is_open() is False


def test_selected_diagnostic_sets_and_updates_editor_highlight(tmp_path: Path) -> None:
    first = Diagnostic(
        file_path=str(tmp_path / "first.py"),
        line=4,
        column=2,
        severity="error",
        code="E999",
        message="first issue",
        source="ruff",
    )
    second = Diagnostic(
        file_path=str(tmp_path / "second.py"),
        line=9,
        column=1,
        severity="warning",
        code="F821",
        message="second issue",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=7,
            diagnostics=(first, second),
            status="ready",
            message="Diagnostics: 2 issue(s).",
        )
    )
    panel.visible = True
    panel.draw()

    assert editor.diagnostic_line_highlight == {
        "file_path": os.path.abspath(str(tmp_path / "first.py")),
        "line": 4,
        "severity": "error",
        "generation": 7,
    }

    assert panel.handle_key(curses.KEY_DOWN) is True

    assert editor.diagnostic_line_highlight == {
        "file_path": os.path.abspath(str(tmp_path / "second.py")),
        "line": 9,
        "severity": "warning",
        "generation": 7,
    }


def test_selected_diagnostic_highlight_clears_on_close_refresh_and_clean_result(
    tmp_path: Path,
) -> None:
    diagnostic = Diagnostic(
        file_path=str(tmp_path / "bad.py"),
        line=3,
        column=1,
        severity="warning",
        code="F401",
        message="issue",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(diagnostic,),
            status="ready",
            message="Diagnostics: 1 issue(s).",
        )
    )
    panel.visible = True
    panel.draw()
    assert editor.diagnostic_line_highlight is not None

    assert panel.handle_key(ord("r")) is True
    assert editor.diagnostic_line_highlight is None

    editor.linter_bridge.diagnostics_snapshot = DiagnosticsSnapshot(
        generation=2,
        diagnostics=(diagnostic,),
        status="ready",
        message="Diagnostics: 1 issue(s).",
    )
    panel.draw()
    assert editor.diagnostic_line_highlight is not None

    editor.linter_bridge.diagnostics_snapshot = DiagnosticsSnapshot(
        generation=3,
        diagnostics=(),
        status="ready",
        message="Diagnostics: PASS — no issues found.",
    )
    panel.draw()
    assert editor.diagnostic_line_highlight is None

    editor.linter_bridge.diagnostics_snapshot = DiagnosticsSnapshot(
        generation=4,
        diagnostics=(diagnostic,),
        status="ready",
        message="Diagnostics: 1 issue(s).",
    )
    panel.draw()
    assert editor.diagnostic_line_highlight is not None

    assert panel.handle_key(27) is True
    assert editor.diagnostic_line_highlight is None


def test_drawscreen_maps_selected_diagnostic_highlight_to_current_file(
    tmp_path: Path,
) -> None:
    editor = type("Editor", (), {})()
    current_file = tmp_path / "current.py"
    other_file = tmp_path / "other.py"
    editor.filename = str(current_file)
    editor.diagnostic_line_highlight = {
        "file_path": os.path.abspath(str(current_file)),
        "line": 5,
        "severity": "warning",
        "generation": 3,
    }
    drawer = cast(Any, DrawScreen.__new__(DrawScreen))
    drawer.editor = editor
    drawer.colors = {"ui_warning": 700}

    assert drawer._active_diagnostic_highlight_line() == 4
    assert drawer._diagnostic_line_number_attr(9) == 700

    editor.filename = str(other_file)

    assert drawer._active_diagnostic_highlight_line() is None


def test_editor_diagnostic_highlight_file_mismatch_clear_is_safe_when_absent(
    tmp_path: Path,
) -> None:
    editor = cast(Any, Ecli.__new__(Ecli))
    editor.filename = str(tmp_path / "current.py")

    editor._clear_diagnostic_line_highlight_if_file_mismatch()

    assert editor.diagnostic_line_highlight is None


def test_editor_clears_selected_diagnostic_highlight_when_file_switches(
    tmp_path: Path,
) -> None:
    current_file = tmp_path / "current.py"
    other_file = tmp_path / "other.py"
    editor = cast(Any, Ecli.__new__(Ecli))
    editor.filename = str(current_file)
    editor._force_full_redraw = False
    editor.diagnostic_line_highlight = {
        "file_path": os.path.abspath(str(current_file)),
        "line": 2,
        "severity": "warning",
        "generation": 1,
    }

    editor._clear_diagnostic_line_highlight_if_file_mismatch()
    assert editor.diagnostic_line_highlight is not None

    editor.filename = str(other_file)
    editor._clear_diagnostic_line_highlight_if_file_mismatch()

    assert editor.diagnostic_line_highlight is None
    assert editor._force_full_redraw is True


def test_details_key_opens_selected_diagnostic_popup_only(tmp_path: Path) -> None:
    selected = Diagnostic(
        file_path=str(tmp_path / "f4_bad.py"),
        line=1,
        column=11,
        severity="warning",
        code="invalid-syntax",
        message="Expected `:`, found newline",
        source="ruff",
        fix_hint="Insert a colon",
        suggested_code="class Askold:\n    pass\n",
    )
    other = Diagnostic(
        file_path=str(tmp_path / "other.py"),
        line=3,
        column=1,
        severity="warning",
        code="F401",
        message="Unused import os",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(selected, other),
            status="ready",
            message="Diagnostics: 2 issue(s).",
        )
    )
    editor.filename = str(tmp_path / "f4_bad.py")
    panel.visible = True

    assert panel.handle_key(ord("d")) is True
    panel.draw()

    text = rendered_popup()
    assert "Diagnostic details" in text
    assert "File: f4_bad.py" in text
    assert "Location: 1:11" in text
    assert "Source: ruff" in text
    assert "Code: invalid-syntax" in text
    assert "Message: Expected `:`, found newline" in text
    assert "Fix hint: Insert a colon" in text
    assert "Suggested: class Askold: pass" in text
    assert "Preview only. No changes were applied." in text
    assert "Unused import os" not in text

    assert panel.handle_key(27) is True
    assert panel._details_is_open() is False


def test_space_opens_details_popup(tmp_path: Path) -> None:
    diagnostic = Diagnostic(
        file_path=str(tmp_path / "f4_bad.py"),
        line=2,
        column=4,
        severity="warning",
        code=None,
        message="Syntax detail",
        source="ruff",
    )
    panel, _editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(diagnostic,),
            status="ready",
            message="Diagnostics: 1 issue(s).",
        )
    )
    panel.visible = True

    assert panel.handle_key(ord(" ")) is True
    panel.draw()

    text = rendered_popup()
    assert "Diagnostic details" in text
    assert "Code:" not in text


def test_refresh_and_selection_movement_close_details_popup(tmp_path: Path) -> None:
    first = Diagnostic(
        file_path=str(tmp_path / "first.py"),
        line=1,
        column=1,
        severity="warning",
        code="F401",
        message="first issue",
        source="ruff",
    )
    second = Diagnostic(
        file_path=str(tmp_path / "second.py"),
        line=2,
        column=1,
        severity="warning",
        code="F821",
        message="second issue",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(first, second),
            status="ready",
            message="Diagnostics: 2 issue(s).",
        )
    )
    panel.visible = True

    assert panel.handle_key(ord("d")) is True
    assert panel._details_is_open() is True

    assert panel.handle_key(curses.KEY_DOWN) is True
    assert panel._details_is_open() is False

    assert panel.handle_key(ord("d")) is True
    assert panel._details_is_open() is True

    assert panel.handle_key(ord("r")) is True
    assert panel._details_is_open() is False
    assert editor.linter_bridge.requests == ["buffer"]


def test_generation_change_invalidates_existing_details_popup(tmp_path: Path) -> None:
    old = Diagnostic(
        file_path=str(tmp_path / "old.py"),
        line=1,
        column=1,
        severity="warning",
        code="F401",
        message="old issue",
        source="ruff",
    )
    new = Diagnostic(
        file_path=str(tmp_path / "new.py"),
        line=1,
        column=1,
        severity="warning",
        code="F821",
        message="new issue",
        source="ruff",
    )
    snapshot = DiagnosticsSnapshot(
        generation=1,
        diagnostics=(old,),
        status="ready",
        message="Diagnostics: 1 issue(s).",
    )
    panel, editor = make_panel(snapshot)
    panel.visible = True

    assert panel.handle_key(ord("d")) is True
    editor.linter_bridge.diagnostics_snapshot = DiagnosticsSnapshot(
        generation=2,
        diagnostics=(new,),
        status="ready",
        message="Diagnostics: 1 issue(s).",
    )
    panel.draw()

    assert panel._details_is_open() is False


def test_diagnostics_row_uses_relative_path_not_absolute_path(tmp_path: Path) -> None:
    diagnostic_path = tmp_path / "pkg" / "module" / "bad.py"
    diagnostic = Diagnostic(
        file_path=str(diagnostic_path),
        line=12,
        column=4,
        severity="warning",
        code="F401",
        message="Unused import os",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(diagnostic,),
            status="ready",
            message="Diagnostics: 1 issue(s).",
        )
    )
    editor.filename = str(tmp_path / "open.py")
    panel.visible = True
    panel.draw()

    row = diagnostics_rows(panel)[0]
    assert str(tmp_path) not in row
    assert "pkg/module/bad.py:12:4" in row
    assert row.startswith("W ruff ")


def test_panel_renders_diagnostics_count_and_visible_count(tmp_path: Path) -> None:
    diagnostics = tuple(
        Diagnostic(
            file_path=str(tmp_path / f"bad_{index}.py"),
            line=index + 1,
            column=1,
            severity="warning",
            code="F401",
            message=f"issue {index}",
            source="ruff",
        )
        for index in range(10)
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=diagnostics,
            status="ready",
            message="Diagnostics: 10 issue(s).",
        )
    )
    editor.filename = str(tmp_path / "open.py")
    panel.height = 8
    panel.visible = True
    panel.draw()

    text = rendered(panel)
    assert "Diagnostics: 10 issue(s)." in text
    assert "Showing 4/10 diagnostics" in text
    assert len(diagnostics_rows(panel)) == 4


def test_diagnostic_message_remains_visible_when_width_is_constrained(
    tmp_path: Path,
) -> None:
    diagnostic = Diagnostic(
        file_path=str(tmp_path / "a" / "very" / "deep" / "package" / "bad.py"),
        line=1,
        column=1,
        severity="error",
        code="E999",
        message="Expected `:`, found newline",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(diagnostic,),
            status="ready",
            message="Diagnostics: 1 issue(s).",
        )
    )
    editor.filename = str(tmp_path / "open.py")
    panel.width = 42
    panel.visible = True
    panel.draw()

    row = diagnostics_rows(panel)[0]
    assert ":1:1" in row
    assert "Expected" in row
    assert str(tmp_path) not in row


def test_long_path_truncation_preserves_location_and_message(tmp_path: Path) -> None:
    diagnostic = Diagnostic(
        file_path=str(
            tmp_path / "alpha" / "beta" / "gamma" / "delta" / "epsilon" / "bad.py"
        ),
        line=123,
        column=45,
        severity="warning",
        code="F821",
        message="Undefined name target_value",
        source="ruff",
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=(diagnostic,),
            status="ready",
            message="Diagnostics: 1 issue(s).",
        )
    )
    editor.filename = str(tmp_path / "open.py")
    panel.width = 38
    panel.visible = True
    panel.draw()

    row = diagnostics_rows(panel)[0]
    assert ":123:45" in row
    assert "Undefined" in row
    assert str(tmp_path) not in row
    assert len(row) <= panel.width - 2


def test_selected_diagnostic_row_stays_readable_not_corrupted_composite(
    tmp_path: Path,
) -> None:
    """Regression: selected-row attr must not OR two color_pair() values.

    Reproduces the markdownlint audit-report.md bug: with a large,
    mixed-severity diagnostics list, the previously-selected row combined
    its severity attr and ``attr_selected`` via ``attr |= attr_selected``.
    Both are independent ``curses.color_pair()`` encodings, so ORing them
    corrupts the pair-number bits and can render as an unreadable black
    bar. The row must instead substitute ``attr_selected`` outright, and
    the drawn text for that row must stay non-empty.
    """
    diagnostics = tuple(
        Diagnostic(
            file_path=str(tmp_path / "audit-report.md"),
            line=index + 1,
            column=1,
            severity="warning" if index % 2 == 0 else "error",
            code="MD013",
            message=(
                f"Line length {80 + index} exceeds 80 characters "
                f"[Expected: 80; Actual: {80 + index}] issue number {index}"
            ),
            source="markdownlint-cli2",
        )
        for index in range(6)
    )
    panel, editor = make_panel(
        DiagnosticsSnapshot(
            generation=1,
            diagnostics=diagnostics,
            status="ready",
            message="Diagnostics: 6 issue(s).",
        )
    )
    editor.filename = str(tmp_path / "audit-report.md")
    panel.selected_idx = 2
    panel.visible = True
    panel.draw()

    rows = diagnostics_rows(panel)
    assert len(rows) == len(diagnostics)
    selected_row = rows[2]

    # The selected row's text must survive rendering: non-blank, and still
    # carries recognizable source/location/message fragments.
    assert selected_row.strip() != ""
    assert "markdownl" in selected_row or "MD013" in selected_row
    assert ":3:1" in selected_row

    selected_attr = drawn_attr(panel, selected_row)
    assert selected_attr == panel.attr_selected

    # Non-selected rows keep their own severity attr, not attr_selected.
    other_row = rows[0]
    other_attr = drawn_attr(panel, other_row)
    assert other_attr != panel.attr_selected
    assert other_attr == panel.attr_warning


def make_goto_editor(file_path: Path, lines: list[str]) -> Any:
    editor = cast(Any, Ecli.__new__(Ecli))
    editor.filename = str(file_path)
    editor.text = list(lines)
    editor.status_message = "Ready"
    editor.status_messages = []
    editor.cursor_y = 0
    editor.cursor_x = 0
    editor.scroll_top = 0
    editor.scroll_left = 0
    editor.stdscr = FakeWindow()
    editor.drawer = type("Drawer", (), {"_text_start_x": 0})()
    editor.panel_manager = FakePanelManager()
    editor.focus = "panel"
    editor._force_full_redraw = False
    editor.service_registry = None
    editor.visible_lines = DrawScreen.content_height(30)
    editor.diagnostic_line_highlight = None

    def set_status(message: str, *_args: Any, **_kwargs: Any) -> None:
        editor.status_message = message
        editor.status_messages.append(message)

    editor._set_status_message = set_status
    return editor


def test_goto_diagnostic_reports_jump_status_with_relative_location(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "f4_bad.py"
    file_path.write_text("def ok():\n    return 1\n", encoding="utf-8")
    editor = make_goto_editor(file_path, ["def ok():", "    return 1"])
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=2,
        column=5,
        severity="warning",
        code="F401",
        message="Unused import os",
        source="ruff",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == 1
    assert editor.cursor_x == 4
    assert editor.status_messages[-1] == "Jumped to f4_bad.py:2:5"


def test_goto_diagnostic_jump_centers_target_line_with_context(
    tmp_path: Path,
) -> None:
    """Regression: a diagnostic jump must not pin the target to the last row.

    ``_clamp_scroll()`` alone only nudges the viewport by the minimum
    amount needed to keep the cursor on-screen, which for a downward jump
    places the target line exactly on the final visible row -- the
    "pinned to the bottom edge" bug reported for markdownlint diagnostics
    on a large file. A deliberate jump (like a search jump via
    ``_goto_match``) should instead land with margin on both sides.
    """
    total_lines = 200
    lines = [f"line {index}" for index in range(total_lines)]
    file_path = tmp_path / "audit-report.md"
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    editor = make_goto_editor(file_path, lines)
    target_line = 150  # 1-indexed; far below the initial viewport.
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=target_line,
        column=1,
        severity="warning",
        code="MD013",
        message="Line length exceeds 80 characters",
        source="markdownlint-cli2",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == target_line - 1
    viewport_height = editor.visible_lines
    last_visible_row = editor.scroll_top + viewport_height - 1

    # Target must be on-screen at all.
    assert editor.scroll_top <= editor.cursor_y <= last_visible_row
    # Not pinned to the very last visible row: enough lines exist below
    # the target (200 - 150 = 50, far more than the viewport height) to
    # leave a safety margin instead of jamming it against the edge.
    assert editor.cursor_y < last_visible_row - 1
    # Not pinned to the very top either -- there is context above it too.
    assert editor.scroll_top < editor.cursor_y


def test_goto_diagnostic_jump_near_end_of_file_stays_valid(tmp_path: Path) -> None:
    """A jump near the end of a short file must still clamp to a valid scroll."""
    lines = [f"line {index}" for index in range(10)]
    file_path = tmp_path / "short.md"
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    editor = make_goto_editor(file_path, lines)
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=9,
        column=1,
        severity="warning",
        code="MD013",
        message="Line length exceeds 80 characters",
        source="markdownlint-cli2",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == 8
    assert editor.scroll_top >= 0
    assert (
        editor.scroll_top
        <= editor.cursor_y
        <= editor.scroll_top + editor.visible_lines - 1
    )


def test_goto_diagnostic_jumps_for_biome_diagnostic_reporting_bare_basename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full-pipeline regression: Biome reporting only "layout.tsx" must
    still let Enter jump and set the editor line highlight.

    Reproduces the reported bug: Biome's JSON reporter often echoes back
    a bare basename (or a path relative to its own detected project
    root) instead of the exact path ECLI invoked it with. Before path
    normalization, this Diagnostic's ``file_path`` was the literal string
    "layout.tsx", and ``goto_diagnostic`` resolves a relative path against
    the *editor process's* cwd -- not the file's own directory -- so the
    jump failed with "Diagnostics: file not available: layout.tsx" and
    the source-line highlight silently never matched the open file either
    (``set_diagnostic_line_highlight`` also calls ``os.path.abspath`` on
    the same unresolved value).
    """
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    file_path = app_dir / "layout.tsx"
    lines = [f"line {index}" for index in range(60)]
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "ecli.extensions.linters.biome.provider.find_executable", lambda _: "biome"
    )
    stdout = json.dumps(
        {
            "diagnostics": [
                {
                    "category": "lint/style/useConst",
                    "severity": "warning",
                    "description": "Use const instead of let.",
                    "location": {
                        "path": {"file": "layout.tsx"},
                        "start": {"line": 52, "column": 1},
                    },
                }
            ]
        }
    )
    provider = BiomeDiagnosticProvider(
        runner=lambda command, **_kw: subprocess.CompletedProcess(
            command, 1, stdout=stdout, stderr=""
        )
    )
    request = DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(file_path),
        text=file_path.read_text(),
        project_root=str(tmp_path),
        language="typescriptreact",
    )
    result = provider.run(request)
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.file_path == str(file_path)

    editor = make_goto_editor(file_path, lines)

    assert editor.goto_diagnostic(diagnostic) is True
    assert "file not available" not in editor.status_messages[-1]
    assert editor.cursor_y == 51

    editor.set_diagnostic_line_highlight(diagnostic, generation=1)
    assert editor.diagnostic_line_highlight is not None
    assert editor.diagnostic_line_highlight["file_path"] == os.path.abspath(file_path)
    assert editor.diagnostic_line_highlight["line"] == 52


def test_goto_diagnostic_in_range_line_still_jumps_exactly(tmp_path: Path) -> None:
    """An ordinary in-range diagnostic must jump to the exact reported line."""
    lines = [f"line {index}" for index in range(67)]
    file_path = tmp_path / "layout.tsx"
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    editor = make_goto_editor(file_path, lines)
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=52,
        column=1,
        severity="error",
        code="parse",
        message="expected `,` but instead found `export`",
        source="biome",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == 51
    assert editor.cursor_x == 0
    assert editor.status_messages[-1] == "Jumped to layout.tsx:52:1"


def test_goto_diagnostic_jumps_for_biome_eof_diagnostic_past_end_of_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full-pipeline regression: Biome reporting an EOF diagnostic one line
    past the last physical line must clamp and jump, not fail with
    "line out of range".

    Reproduces the reported bug exactly: a 67-line ``layout.tsx`` with a
    Biome parse diagnostic at ``68:1`` ("expected `}` but instead the file
    ends").
    """
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    file_path = app_dir / "layout.tsx"
    lines = [f"line {index}" for index in range(67)]
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "ecli.extensions.linters.biome.provider.find_executable", lambda _: "biome"
    )
    stdout = json.dumps(
        {
            "diagnostics": [
                {
                    "category": "parse",
                    "severity": "error",
                    "description": "expected `}` but instead the file ends",
                    "location": {
                        "path": {"file": "layout.tsx"},
                        "start": {"line": 68, "column": 1},
                    },
                }
            ]
        }
    )
    provider = BiomeDiagnosticProvider(
        runner=lambda command, **_kw: subprocess.CompletedProcess(
            command, 1, stdout=stdout, stderr=""
        )
    )
    request = DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(file_path),
        text=file_path.read_text(),
        project_root=str(tmp_path),
        language="typescriptreact",
    )
    result = provider.run(request)
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.line == 68  # original, unclamped -- preserved for details popup

    editor = make_goto_editor(file_path, lines)

    assert editor.goto_diagnostic(diagnostic) is True
    assert "line out of range" not in editor.status_messages[-1]
    assert editor.cursor_y == 66  # clamped to line 67 (last real line)

    editor.set_diagnostic_line_highlight(diagnostic, generation=1)
    assert editor.diagnostic_line_highlight is not None
    assert editor.diagnostic_line_highlight["file_path"] == os.path.abspath(file_path)
    # Highlight is clamped to the same line the cursor jumped to (67), not
    # the diagnostic's raw reported line (68): DrawScreen's gutter loop
    # only iterates real buffer rows, so an unclamped line one past the
    # buffer end would never match any row and silently paint nothing.
    assert editor.diagnostic_line_highlight["line"] == 67


def test_goto_diagnostic_missing_file_reports_controlled_status(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    current_file = tmp_path / "current.py"
    current_file.write_text("x = 1\n", encoding="utf-8")
    missing_file = tmp_path / "missing.py"
    editor = make_goto_editor(current_file, ["x = 1"])
    diagnostic = Diagnostic(
        file_path=str(missing_file),
        line=1,
        column=1,
        severity="warning",
        code="F401",
        message="Unused import os",
        source="ruff",
    )

    with caplog.at_level(logging.WARNING):
        assert editor.goto_diagnostic(diagnostic) is False

    assert editor.status_messages[-1] == "Diagnostics: file not available: missing.py"
    assert "file not available" in caplog.text


def test_goto_diagnostic_clamps_column_past_line_length(
    tmp_path: Path,
) -> None:
    """Regression: a column past the end of an existing line must clamp,
    not fail.

    Reported column is clamped to ``len(line) + 1`` (one past the last
    character, a valid cursor position) instead of refusing the jump.
    """
    file_path = tmp_path / "current.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    editor = make_goto_editor(file_path, ["x = 1"])
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=1,
        column=80,
        severity="warning",
        code="F401",
        message="Unused import os",
        source="ruff",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == 0
    assert editor.cursor_x == 5  # len("x = 1") == 5, clamped column is 6 (1-indexed)
    assert editor.status_messages[-1] == (
        "Jumped to current.py:1:6 (diagnostic reported 1:80)"
    )


def test_goto_diagnostic_clamps_line_past_end_of_file(tmp_path: Path) -> None:
    """Regression: an EOF/past-end-of-buffer diagnostic line must clamp
    to the last real line, not fail with "line out of range".

    Reproduces the reported Biome bug: a parser "unexpected end of file"
    diagnostic on a 67-line file reported at line 68.
    """
    lines = [f"line {index}" for index in range(67)]
    file_path = tmp_path / "layout.tsx"
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    editor = make_goto_editor(file_path, lines)
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=68,
        column=1,
        severity="error",
        code="parse",
        message="expected `}` but instead the file ends",
        source="biome",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == 66  # line 67, 0-indexed
    assert editor.cursor_x == 0
    assert editor.status_messages[-1] == (
        "Jumped to layout.tsx:67:1 (diagnostic reported 68:1)"
    )
    assert "line out of range" not in editor.status_messages[-1]


def test_goto_diagnostic_clamps_to_line_one_for_empty_buffer(tmp_path: Path) -> None:
    """Regression: an empty buffer must clamp to line 1 / column 1, not crash."""
    file_path = tmp_path / "empty.py"
    file_path.write_text("", encoding="utf-8")
    editor = make_goto_editor(file_path, [])
    diagnostic = Diagnostic(
        file_path=str(file_path),
        line=5,
        column=5,
        severity="warning",
        code="E999",
        message="Empty file",
        source="ruff",
    )

    assert editor.goto_diagnostic(diagnostic) is True

    assert editor.cursor_y == 0
    assert editor.cursor_x == 0


def test_ruff_diagnostic_via_full_service_pipeline_is_visible_and_actionable(
    tmp_path: Path,
) -> None:
    """Full-pipeline regression: DiagnosticsService -> snapshot -> panel row.

    The reference Ruff behavior is not just "a hand-built DiagnosticsSnapshot
    renders a row" (already covered above) -- it is "a real DiagnosticsService
    run, through a registered RuffDiagnosticProvider, produces a
    DiagnosticResult whose row is visible, whose selection survives Enter
    jump, and whose details popup opens for the correct diagnostic." This
    closes the gap between provider-level and panel-level tests so a future
    regression in how the two are wired together (result merging, snapshot
    replacement, selection sync) is caught here rather than only in a manual
    smoke test.
    """
    target_file = tmp_path / "bad.py"
    target_file.write_text("import os\n", encoding="utf-8")

    def fake_runner(
        _command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        stdout = (
            '[{"filename": "'
            + str(target_file)
            + '", "location": {"row": 1, "column": 8}, '
            + '"code": "F401", "message": "`os` imported but unused"}]'
        )
        return subprocess.CompletedProcess(_command, 1, stdout=stdout, stderr="")

    service = DiagnosticsService()
    service.register_provider(RuffDiagnosticProvider(runner=fake_runner))
    generation, started, _pending = service.request_refresh(
        scope="buffer",
        file_path=str(target_file),
        text="import os\n",
        project_root=str(tmp_path),
        language="python",
    )
    assert started

    deadline = time.monotonic() + 3
    results = []
    while time.monotonic() < deadline and not results:
        results = service.drain_results()
        if not results:
            time.sleep(0.01)
    assert len(results) == 1
    result = results[0]
    assert result.generation == generation
    assert result.status == "ready"
    assert len(result.diagnostics) == 1

    snapshot = DiagnosticsSnapshot().with_result(
        result, running_generation=None, pending_generation=None
    )
    panel, editor = make_panel(snapshot)
    editor.filename = str(target_file)
    panel.visible = True
    panel.draw()

    text = rendered(panel)
    assert "Diagnostics: 1 issue(s)." in text
    rows = diagnostics_rows(panel)
    assert len(rows) == 1
    assert rows[0].strip() != ""
    assert "bad.py:1:8" in rows[0]
    assert "imported but unused" in rows[0]

    assert panel.handle_key(curses.KEY_ENTER) is True
    assert editor.status_messages[-1] == "Jumped to bad.py:1:8"
    assert len(editor.navigated) == 1

    assert panel.handle_key(ord("d")) is True
    panel.draw()
    popup_text = rendered_popup()
    assert "F401" in popup_text
    assert "imported but unused" in popup_text
