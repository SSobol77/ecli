# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_diagnostics_panel.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the F4 Diagnostics / Linter panel rendering and behavior (#104)."""

from __future__ import annotations

import curses
import inspect
import queue
import re
import time
from pathlib import Path
from types import MethodType
from typing import Any, Optional

import pytest

from ecli.core.Ecli import Ecli
from ecli.extensions.ecli_integration.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    DiagnosticsService,
    DiagnosticsState,
    DiagnosticsStatus,
    ProviderRegistry,
    RuffDiagnosticsProvider,
    build_default_registry,
)
from ecli.ui.panels import DiagnosticsPanel


class FakeWindow:
    def __init__(self) -> None:
        """Initialize a fake curses window that records drawn text."""
        self.drawn_text: list[str] = []
        self.draw_calls: list[tuple[int, int, str]] = []
        self.bkgd_calls: list[tuple[str, int]] = []
        self.touch_count = 0

    def getmaxyx(self) -> tuple[int, int]:
        return (32, 120)

    def keypad(self, value: bool) -> None:
        return None

    def bkgd(self, ch: str, attr: int = 0) -> None:
        self.bkgd_calls.append((ch, attr))

    def erase(self) -> None:
        self.drawn_text.clear()

    def border(self) -> None:
        return None

    def addnstr(self, _y: int, _x: int, text: str, _width: int, _attr: int = 0) -> None:
        self.drawn_text.append(text)
        self.draw_calls.append((_y, _x, text))

    def touchwin(self) -> None:
        self.touch_count += 1

    def refresh(self) -> None:
        return None

    def noutrefresh(self) -> None:
        return None


class NarrowWindow(FakeWindow):
    def getmaxyx(self) -> tuple[int, int]:
        return (6, 20)


class FakePanelManager:
    def __init__(self) -> None:
        """Count close_active_panel calls."""
        self.closed = 0

    def close_active_panel(self) -> None:
        self.closed += 1


class FakeService:
    def __init__(
        self, state: DiagnosticsState, workspace_root: Optional[Path] = None
    ) -> None:
        """Return a fixed state and record every collect call."""
        self.state = state
        self.workspace_root = workspace_root
        self.calls: list[dict[str, Any]] = []

    def collect(
        self,
        file_path: Optional[str],
        *,
        text: Optional[str] = None,
        force: bool = False,
    ) -> DiagnosticsState:
        self.calls.append({"file_path": file_path, "text": text, "force": force})
        return self.state


class FakeEditor:
    def __init__(self, service: Optional[FakeService] = None) -> None:
        """Initialize a panel-compatible editor double."""
        self.stdscr = FakeWindow()
        self.focus = "panel"
        self._force_full_redraw = False
        self.colors: dict[str, int] = {}
        self.filename = "a.py"
        self.text = ["import os"]
        self.diagnostics_service = service
        self.panel_manager = FakePanelManager()
        self.status_messages: list[str] = []

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def toggle_focus(self) -> None:
        self.focus = "editor" if self.focus == "panel" else "panel"


@pytest.fixture(autouse=True)
def fake_curses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: FakeWindow())
    monkeypatch.setattr("ecli.ui.panels.curses.curs_set", lambda value: None)


def _diag(
    severity: DiagnosticSeverity, message: str = "msg", code: str | None = None
) -> Diagnostic:
    return Diagnostic(
        file_path="a.py",
        line=10,
        severity=severity,
        source="ruff",
        message=message,
        column=5,
        code=code,
    )


def rendered(panel: DiagnosticsPanel) -> str:
    return "\n".join(panel.win.drawn_text)


# --------------------------------------------------------------------------- #
# Rendering: diagnostics list + summary.
# --------------------------------------------------------------------------- #


def test_renders_diagnostics_list_and_summary() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff",
        "a.py",
        [
            _diag(DiagnosticSeverity.ERROR, "undefined name foo", "F821"),
            _diag(DiagnosticSeverity.WARNING, "imported but unused", "F401"),
        ],
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()

    text = rendered(panel)
    assert "Diagnostics" in text
    assert "ruff" in text
    assert "E:1" in text and "W:1" in text
    assert "ERROR" in text and "F821" in text
    assert "WARN" in text and "F401" in text
    assert "a.py:10:5" in text


def test_summary_shows_all_severity_counts() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff",
        "a.py",
        [
            _diag(DiagnosticSeverity.ERROR),
            _diag(DiagnosticSeverity.INFO),
            _diag(DiagnosticSeverity.HINT),
        ],
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "Σ3" in text
    assert "I:1" in text and "H:1" in text


def test_list_row_includes_severity_path_location_code_and_message() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff",
        "a.py",
        [_diag(DiagnosticSeverity.WARNING, "imported but unused", "F401")],
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "WARN" in text  # severity label
    assert "a.py:10:5" in text  # path + line:column
    assert "[F401]" in text  # rule/code
    assert "imported but unused" in text  # message


def test_list_uses_relative_path_inside_workspace(tmp_path: Path) -> None:
    file_path = str(tmp_path / "pkg" / "mod.py")
    diag = Diagnostic(
        file_path=file_path,
        line=3,
        severity=DiagnosticSeverity.WARNING,
        source="ruff",
        message="unused",
        column=2,
        code="F401",
    )
    state = DiagnosticsState.from_diagnostics("ruff", file_path, [diag])
    service = FakeService(state, workspace_root=tmp_path)
    editor = FakeEditor(service)
    panel = DiagnosticsPanel(
        editor.stdscr, editor, state=state, background=False, service=service
    )
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "pkg/mod.py:3:2" in text
    assert str(tmp_path) not in text  # absolute workspace prefix is hidden


def test_selected_diagnostic_detail_area_shows_full_information() -> None:
    long_message = "undefined name foobar that keeps going on and on " * 3
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR, long_message, "F821")]
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    # The detail area carries the complete, structured diagnostic information.
    assert "Severity: ERROR" in text
    assert "Provider: ruff" in text
    assert "Rule: F821" in text
    assert "Line: 10  Column: 5" in text
    assert "Message:" in text
    assert "undefined name foobar" in text
    # Location is still shown compactly in the list header row.
    assert "a.py:10:5" in text


def _activity_bar_line(panel: DiagnosticsPanel) -> str:
    return next(
        line
        for line in panel.win.drawn_text
        if "[" in line and "]" in line and "===" in line
    )


def test_collecting_state_renders_bracketed_activity_bar() -> None:
    state = DiagnosticsState.collecting("ruff", "a.py")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "collecting diagnostics" in text.lower()
    bar = _activity_bar_line(panel)
    assert bar.startswith("[")
    assert bar.endswith("]")
    assert "===" in bar
    # Indeterminate indicator: no percent sign anywhere in the bar.
    assert "%" not in bar


def test_collecting_state_has_no_literal_schematic_strings() -> None:
    state = DiagnosticsState.collecting("ruff", "a.py")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "<-||----------->" not in text
    assert "<------||------>" not in text
    assert "||" not in text
    assert "<" not in text and ">" not in text


def test_activity_indicator_animates_between_frames() -> None:
    state = DiagnosticsState.collecting("ruff", "a.py")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()

    panel.draw()
    frame_one = _activity_bar_line(panel)
    panel.draw()
    frame_two = _activity_bar_line(panel)
    assert frame_one != frame_two


def test_activity_block_is_approximately_centered() -> None:
    state = DiagnosticsState.collecting("ruff", "a.py")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()

    bar_calls = [
        (x, text)
        for (_y, x, text) in panel.win.draw_calls
        if "[" in text and "]" in text and "===" in text
    ]
    assert bar_calls
    x, text = bar_calls[-1]
    left_margin = x - 1  # panel body starts at column 1
    right_margin = (panel.width - 1) - (x + len(text))
    assert abs(left_margin - right_margin) <= 2


def test_activity_bar_helper_adapts_width_and_is_indeterminate() -> None:
    narrow = DiagnosticsPanel._diagnostics_activity_bar(20, 0)
    wide = DiagnosticsPanel._diagnostics_activity_bar(120, 0)
    # Width adapts but stays bounded; never the schematic characters.
    assert len(narrow) < len(wide)
    for frame in range(0, 40):
        bar = DiagnosticsPanel._diagnostics_activity_bar(48, frame)
        assert "||" not in bar and "<" not in bar and ">" not in bar
        assert bar.count("===") == 1
        # Indeterminate: no percent sign and no numeric progress at all.
        assert "%" not in bar
        assert re.search(r"\d", bar) is None


def test_collecting_process_queues_requests_redraw_for_animation() -> None:
    # While a background collection is in flight, process_queues() returns True so
    # the main loop keeps redrawing and the indicator animates.
    state = DiagnosticsState.from_diagnostics("ruff", "a.py", [])
    service = FakeService(state)
    editor = FakeEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=True)
    panel._collecting = True
    assert panel.process_queues() is True


# --------------------------------------------------------------------------- #
# Empty states.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (DiagnosticsState.no_active_file(), "No active file"),
        (DiagnosticsState.disabled(), "disabled"),
        (
            DiagnosticsState.provider_unavailable("ruff", "not installed"),
            "not installed",
        ),
        (DiagnosticsState.from_diagnostics("ruff", "a.py", []), "No diagnostics"),
    ],
)
def test_empty_states_render_explicit_message(
    state: DiagnosticsState, expected: str
) -> None:
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    assert expected.lower() in rendered(panel).lower()


@pytest.mark.parametrize("suffix", [".css", ".tsx", ".json"])
def test_unsupported_file_type_message_is_clear_not_linter_unavailable(
    suffix: str,
) -> None:
    state = DiagnosticsState.unsupported(
        file_path=f"a{suffix}",
        detail=f"No diagnostics provider for {suffix} files",
        hint="Available provider: Ruff for Python files.",
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert f"No diagnostics provider for {suffix} files" in text
    assert "Available provider: Ruff for Python files." in text
    assert "Linter unavailable" not in text


def test_outside_workspace_message_and_clipped_path() -> None:
    state = DiagnosticsState.outside_workspace(
        file_path="/etc/some/external/file.py",
        detail="Current file is outside ECLI workspace.",
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "Current file is outside ECLI workspace." in text
    assert "file.py" in text


def test_provider_unavailable_shows_bounded_detail_not_traceback() -> None:
    state = DiagnosticsState.provider_unavailable("ruff", "ruff is not installed")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "ruff is not installed" in text
    assert "Traceback" not in text


# --------------------------------------------------------------------------- #
# Message clipping + small terminals.
# --------------------------------------------------------------------------- #


def test_long_messages_wrap_within_panel_width_without_ellipsis() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR, "x" * 400, "E001")]
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    budget = panel.width - 2
    # Nothing is written outside the panel bounds...
    assert all(len(line) <= budget for line in panel.win.drawn_text)
    # ...and the long message is wrapped (multiple all-"x" continuation lines)
    # rather than truncated with an ellipsis.
    x_lines = [line for line in panel.win.drawn_text if set(line.strip()) == {"x"}]
    assert len(x_lines) >= 2
    assert not any(line.endswith("…") for line in panel.win.drawn_text)


def test_narrow_terminal_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: NarrowWindow())
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR)]
    )
    editor = FakeEditor()
    editor.stdscr = NarrowWindow()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()  # must not raise on a tiny terminal


def test_panel_applies_opaque_background_and_touches_window() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR)]
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    assert panel.win.bkgd_calls
    assert panel.win.touch_count >= 1


# --------------------------------------------------------------------------- #
# Collection: synchronous + background.
# --------------------------------------------------------------------------- #


def test_synchronous_collection_on_open_uses_service() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.WARNING)]
    )
    service = FakeService(state)
    editor = FakeEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    assert service.calls
    assert service.calls[0]["file_path"] == "a.py"
    assert service.calls[0]["text"] == "import os"
    assert panel.state is state


def test_background_collection_delivers_via_process_queues() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR)]
    )
    service = FakeService(state)
    editor = FakeEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=True)
    panel.open()  # starts a worker thread; placeholder state is COLLECTING

    delivered = False
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if panel.process_queues():
            delivered = True
            break
        time.sleep(0.01)

    assert delivered
    assert panel.state.status is DiagnosticsStatus.OK


def test_missing_service_renders_error() -> None:
    editor = FakeEditor(service=None)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    assert panel.state is not None
    assert panel.state.status is DiagnosticsStatus.ERROR


# --------------------------------------------------------------------------- #
# Key handling: refresh + close.
# --------------------------------------------------------------------------- #


def test_r_key_forces_refresh() -> None:
    state = DiagnosticsState.from_diagnostics("ruff", "a.py", [])
    service = FakeService(state)
    editor = FakeEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    service.calls.clear()
    assert panel.handle_key(ord("r")) is True
    assert service.calls and service.calls[-1]["force"] is True


def test_f4_closes_panel() -> None:
    state = DiagnosticsState.no_active_file()
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    assert panel.handle_key(curses.KEY_F4) is True
    assert editor.panel_manager.closed == 1


def test_escape_closes_panel() -> None:
    state = DiagnosticsState.no_active_file()
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    assert panel.handle_key(27) is True
    assert editor.panel_manager.closed == 1


# --------------------------------------------------------------------------- #
# Security regression: the panel never executes anything itself.
# --------------------------------------------------------------------------- #


def test_panel_source_has_no_subprocess_or_runtime_execution() -> None:
    source = inspect.getsource(DiagnosticsPanel)
    forbidden = (
        "subprocess",
        "Popen",
        "os.system",
        "package.json",
        "activationEvents",
        "node",
        "npm",
        "copilot",
    )
    lowered = source.lower()
    for token in forbidden:
        assert token.lower() not in lowered, token


# --------------------------------------------------------------------------- #
# Provider-framework states rendered with the real registry (#104 rework).
# --------------------------------------------------------------------------- #


def _real_editor(service: DiagnosticsService, filename: str) -> FakeEditor:
    editor = FakeEditor(service=service)  # type: ignore[arg-type]
    editor.filename = filename
    editor.text = ["x"]
    return editor


def test_panel_renders_planned_state_for_java(tmp_path: Path) -> None:
    service = DiagnosticsService(
        registry=build_default_registry(), workspace_root=tmp_path
    )
    editor = _real_editor(service, str(tmp_path / "App.java"))
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "Java" in text
    assert "JDT LS" in text and "Checkstyle" in text
    assert "Planned" in text
    # Known planned languages must not show a generic "Linter unavailable".
    assert "Linter unavailable" not in text


def test_panel_planned_state_states_no_auto_install(tmp_path: Path) -> None:
    service = DiagnosticsService(
        registry=build_default_registry(), workspace_root=tmp_path
    )
    editor = _real_editor(service, str(tmp_path / "main.rs"))
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "rust-analyzer" in text or "cargo" in text
    assert "never auto-installed" in text


def test_panel_renders_sonarqube_project_quality_footer(tmp_path: Path) -> None:
    service = DiagnosticsService(
        registry=build_default_registry(), workspace_root=tmp_path
    )
    editor = _real_editor(service, str(tmp_path / "App.java"))
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "SonarQube" in text
    assert "project-quality" in text
    assert "cached/manual project scan" in text


def test_panel_renders_ruff_missing_executable_message(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        active_providers=(RuffDiagnosticsProvider(executable="ruff-not-here-xyz"),),
        labels={"python": "Python"},
    )
    service = DiagnosticsService(registry=registry, workspace_root=tmp_path)
    editor = _real_editor(service, str(tmp_path / "mod.py"))
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    assert "Ruff provider is registered for Python" in text
    assert "diagnostics toolchain" in text
    assert "Linter unavailable" not in text


# --------------------------------------------------------------------------- #
# Wrapping: detail area, docs URLs, and list-row continuation lines (#104 UX).
# --------------------------------------------------------------------------- #


def _within_bounds(panel: DiagnosticsPanel) -> bool:
    budget = panel.width - 2
    return all(len(line) <= budget for line in panel.win.drawn_text)


def test_detail_area_wraps_full_message_without_ellipsis() -> None:
    message = (
        "Local variable result is assigned to but never used and this explanation "
        "keeps going well past the available panel width so it must wrap"
    )
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.WARNING, message, "F841")]
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    # Every word of the message is present somewhere in the rendered panel and no
    # line was clipped with an ellipsis.
    for word in message.split():
        assert word in text
    assert not any(line.endswith("…") for line in panel.win.drawn_text)
    assert _within_bounds(panel)


def test_long_docs_url_wraps_safely_inside_panel() -> None:
    url = "https://docs.astral.sh/ruff/rules/missing-newline-at-end-of-file"
    diag = Diagnostic(
        file_path="a.py",
        line=458,
        severity=DiagnosticSeverity.WARNING,
        source="ruff",
        message="No newline at end of file",
        column=29,
        code="W292",
        docs_url=url,
    )
    state = DiagnosticsState.from_diagnostics("ruff", "a.py", [diag])
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()

    assert "Docs:" in rendered(panel)
    assert _within_bounds(panel)
    # The URL is hard-wrapped across at least two lines and reassembles exactly,
    # with no characters dropped and no ellipsis.
    url_fragment_lines = [
        line.strip()
        for line in panel.win.drawn_text
        if line.strip() and line.strip() in url
    ]
    assert len(url_fragment_lines) >= 2
    assert "".join(url_fragment_lines) == url
    assert not any(line.endswith("…") for line in panel.win.drawn_text)


def test_panel_marks_external_file_and_shows_absolute_path() -> None:
    abs_path = "/home/ssobol/tmp/test_file.py"
    diag = Diagnostic(
        file_path=abs_path,
        line=1,
        severity=DiagnosticSeverity.WARNING,
        source="ruff",
        message="undefined name x",
        column=1,
        code="F821",
    )
    state = DiagnosticsState.from_diagnostics("ruff", abs_path, [diag], external=True)
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    text = rendered(panel)
    # An out-of-workspace file linted via stdin is flagged and shows its absolute
    # path (there is no workspace-relative form to display).
    assert "external file" in text
    assert abs_path in text


def test_list_row_message_wraps_to_continuation_lines() -> None:
    message = "imported but unused and the rest of this message must continue onto a second visible line"
    state = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.WARNING, message, "F401")]
    )
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()

    # The compact header row carries the location/code...
    header_rows = [
        text for (_y, _x, text) in panel.win.draw_calls if "a.py:10:5" in text
    ]
    assert header_rows
    assert "[F401]" in header_rows[0]
    assert "imported but unused" not in header_rows[0]  # message is not on the header
    # ...and the message is wrapped onto indented continuation rows in the list.
    indented_continuations = [
        text
        for text in panel.win.drawn_text
        if text.startswith("  ") and "imported but unused" in text
    ]
    assert indented_continuations
    assert _within_bounds(panel)


# --------------------------------------------------------------------------- #
# Collecting animation: panel-local tick + non-fake indicator (#104 UX).
# --------------------------------------------------------------------------- #


def test_collecting_state_requests_periodic_repaint() -> None:
    editor = FakeEditor()
    panel = DiagnosticsPanel(
        editor.stdscr,
        editor,
        state=DiagnosticsState.collecting("ruff", "a.py"),
        background=False,
    )
    panel.open()
    # COLLECTING placeholder requests ticks even without an in-flight worker.
    assert panel.wants_periodic_repaint() is True

    panel._collecting = True
    assert panel.wants_periodic_repaint() is True

    panel._collecting = False
    panel.state = DiagnosticsState.from_diagnostics("ruff", "a.py", [])
    assert panel.wants_periodic_repaint() is False


def test_activity_frame_advances_across_periodic_render_ticks() -> None:
    state = DiagnosticsState.collecting("ruff", "a.py")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()

    frames: list[str] = []
    for _ in range(4):
        panel.draw()  # simulate periodic repaint ticks (no key input)
        frames.append(_activity_bar_line(panel))
    # Each tick advances the indicator: consecutive frames differ.
    assert all(a != b for a, b in zip(frames, frames[1:], strict=False))
    assert panel._activity_frame == 4


def test_activity_indicator_has_no_pipes_or_percentage() -> None:
    state = DiagnosticsState.collecting("ruff", "a.py")
    editor = FakeEditor()
    panel = DiagnosticsPanel(editor.stdscr, editor, state=state, background=False)
    panel.open()
    panel.draw()
    bar = _activity_bar_line(panel)
    # A moving segment, but no percent, no fake progress number, no schematic.
    assert "===" in bar
    assert "%" not in bar
    assert re.search(r"\d", bar) is None
    assert "||" not in bar
    assert "<" not in bar and ">" not in bar
    # The whole collecting panel must not render a percent sign anywhere.
    assert "%" not in rendered(panel)


# --------------------------------------------------------------------------- #
# Source consistency: F4 lints the current buffer through stdin (#104 UX).
# --------------------------------------------------------------------------- #


def test_refresh_relints_current_dirty_buffer_and_replaces_results() -> None:
    first = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR, "stale", "E001")]
    )
    second = DiagnosticsState.from_diagnostics("ruff", "a.py", [])
    service = FakeService(first)
    editor = FakeEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=False)
    panel.open()
    assert panel.state is first

    # The buffer is edited (dirty); refreshing must re-collect the *current*
    # buffer text and replace the previously shown results.
    editor.text = ["import os", "x = 1"]
    service.state = second
    assert panel.handle_key(ord("r")) is True
    assert service.calls[-1]["force"] is True
    assert service.calls[-1]["text"] == "import os\nx = 1"
    assert panel.state is second


# --------------------------------------------------------------------------- #
# Main-loop integration: no-key ticks must poll completion, advance the
# animation frame, and request a redraw — all without a keypress (#104 UX).
# --------------------------------------------------------------------------- #


class LoopStdscr(FakeWindow):
    def __init__(self) -> None:
        """A fake screen that also records curses input-timeout changes."""
        super().__init__()
        self.timeouts: list[int] = []

    def timeout(self, milliseconds: int) -> None:
        self.timeouts.append(milliseconds)


class LoopPanelManager:
    def __init__(self) -> None:
        """Expose a single active panel and record close requests."""
        self.active_panel: Any = None
        self.closed = 0

    def is_panel_active(self) -> bool:
        return self.active_panel is not None and self.active_panel.visible

    def close_active_panel(self) -> None:
        self.closed += 1


class LoopEditor:
    """Editor double wired with the *real* Ecli main-loop tick helpers."""

    PANEL_TICK_MS = Ecli.PANEL_TICK_MS

    def __init__(self, service: FakeService) -> None:
        """Build a double exposing exactly what _process_all_queues touches."""
        self.stdscr = LoopStdscr()
        self.focus = "panel"
        self._force_full_redraw = False
        self.is_lightweight = False
        self.colors: dict[str, int] = {}
        self.filename = "a.py"
        self.text = ["import os"]
        self.diagnostics_service = service
        self.status_messages: list[str] = []
        self.status_message = ""
        self.panel_manager = LoopPanelManager()
        # Background-queue dependencies referenced by the real _process_all_queues.
        self._shell_cmd_q: queue.Queue[Any] = queue.Queue()
        self.git = None
        self.linter_bridge = None
        self.async_engine = None
        self._async_results_q: queue.Queue[Any] = queue.Queue()
        self.lint_panel_active = False
        self.lint_panel_message = ""
        self._panel_tick_active = False
        # Bind the genuine implementations under test.
        self._process_all_queues = MethodType(Ecli._process_all_queues, self)
        self._active_panel_wants_tick = MethodType(Ecli._active_panel_wants_tick, self)
        self._sync_input_cadence = MethodType(Ecli._sync_input_cadence, self)

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def toggle_focus(self) -> None:
        self.focus = "editor" if self.focus == "panel" else "panel"


def _no_key_tick(editor: LoopEditor, panel: DiagnosticsPanel) -> bool:
    """Simulate one main-loop iteration that received no key input.

    Mirrors the render-before-read path for a no-key Diagnostics tick: drain
    background queues, include autonomous panel animation, repaint if needed,
    and only then sync the input cadence. Returns whether a redraw happened.
    """
    redraw = bool(editor._process_all_queues())
    if editor._active_panel_wants_tick():
        redraw = True
    if redraw or editor._force_full_redraw:
        panel.draw()
        editor._force_full_redraw = False
    editor._sync_input_cadence(pending_redraw=False)
    return redraw


def test_no_key_tick_advances_animation_and_requests_redraw() -> None:
    service = FakeService(DiagnosticsState.from_diagnostics("ruff", "a.py", []))
    editor = LoopEditor(service)
    panel = DiagnosticsPanel(
        editor.stdscr,
        editor,
        state=DiagnosticsState.collecting("ruff", "a.py"),
        background=False,
    )
    panel._collecting = True  # simulate an in-flight background collection
    panel.open()
    editor.panel_manager.active_panel = panel

    first_frame = panel._activity_frame
    # Two iterations with NO key input at all.
    assert _no_key_tick(editor, panel) is True
    assert _no_key_tick(editor, panel) is True

    # The collecting indicator advanced purely on the timeout/no-key path...
    assert panel._activity_frame > first_frame
    # ...and the loop applied the bounded repaint timeout.
    assert editor.stdscr.timeouts
    assert editor.stdscr.timeouts[-1] == Ecli.PANEL_TICK_MS


def test_background_completion_updates_panel_without_keypress() -> None:
    done = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.ERROR, "boom", "E001")]
    )
    service = FakeService(done)
    editor = LoopEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=True)
    panel.open()  # starts the worker; placeholder state is COLLECTING
    editor.panel_manager.active_panel = panel
    assert panel.state.status is DiagnosticsStatus.COLLECTING

    # Drive idle no-key ticks only; never feed a key. The background result must
    # be drained by _process_all_queues on a tick and replace the COLLECTING UI.
    deadline = time.time() + 2.0
    while time.time() < deadline and panel.state.status is DiagnosticsStatus.COLLECTING:
        _no_key_tick(editor, panel)
        time.sleep(0.01)

    assert panel.state.status is DiagnosticsStatus.OK
    assert panel._collecting is False
    # After completion the panel no longer requests periodic repaints, so the
    # loop is free to return to a blocking read (no busy looping).
    assert panel.wants_periodic_repaint() is False


def test_service_completion_is_polled_on_ticks_not_only_key_events() -> None:
    # The panel queue is drained by the editor's per-tick queue processing, so a
    # result delivered while idle is picked up without any key dispatch.
    service = FakeService(DiagnosticsState.from_diagnostics("ruff", "a.py", []))
    editor = LoopEditor(service)
    panel = DiagnosticsPanel(editor.stdscr, editor, background=True)
    panel.state = DiagnosticsState.collecting("ruff", "a.py")
    panel._collecting = True
    panel.open()
    editor.panel_manager.active_panel = panel

    # Inject a finished result directly into the panel's delivery queue.
    finished = DiagnosticsState.from_diagnostics(
        "ruff", "a.py", [_diag(DiagnosticSeverity.WARNING, "w", "W001")]
    )
    panel._result_q.put_nowait(finished)

    # A single no-key tick must pick it up via the editor's queue processing.
    changed = editor._process_all_queues()
    assert changed is True
    assert panel.state is finished
    assert panel._collecting is False
