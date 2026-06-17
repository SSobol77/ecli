# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/characterization/test_existing_tui_panels.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Characterization tests for existing panel classes and transitions."""

from __future__ import annotations

import curses
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from ecli.ui.PanelManager import PanelManager
from ecli.ui.panels import (
    AiResponsePanel,
    BasePanel,
    CommandPlanPanel,
    FileBrowserPanel,
    GitPanel,
    ServicesPanel,
    SystemDoctorPanel,
)


class FakeWindow:
    def __init__(self) -> None:
        """Initialize a fake curses window."""
        self.keypad_values: list[bool] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (30, 100)

    def keypad(self, value: bool) -> None:
        self.keypad_values.append(value)

    def clear(self) -> None:
        return None

    def refresh(self) -> None:
        return None


class FakeEditor:
    def __init__(self, workspace: Path | None = None) -> None:
        """Initialize a panel-compatible editor double."""
        self.stdscr = FakeWindow()
        self.focus = "editor"
        self._force_full_redraw = False
        self.colors = {
            "status": curses.A_BOLD,
            "keyword": curses.A_BOLD,
            "default": curses.A_NORMAL,
            "comment": curses.A_DIM,
            "function": curses.A_BOLD,
        }
        self.config: dict[str, Any] = {}
        self.status_messages: list[str] = []
        self.opened_files: list[str] = []
        self.filename = None
        self.git = None
        self.panel_manager: Any = None
        self.workspace = workspace

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def open_file(self, path: str) -> None:
        self.opened_files.append(path)

    def toggle_file_browser(self) -> None:
        self.status_messages.append("toggle_file_browser")

    def toggle_focus(self) -> None:
        self.focus = "editor" if self.focus == "panel" else "panel"

    def exit_editor(self) -> None:
        self.status_messages.append("exit_editor")


class DummyPanel(BasePanel):
    def draw(self) -> None:
        return None

    def handle_key(self, key: Any) -> bool:
        return key == "handled"


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-existing-tui-panels"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


@pytest.fixture(autouse=True)
def fake_curses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: FakeWindow())
    monkeypatch.setattr("ecli.ui.panels.curses.curs_set", lambda value: None)
    monkeypatch.setattr("ecli.ui.PanelManager.curses.curs_set", lambda value: None)
    monkeypatch.setattr("ecli.ui.panels.curses.init_pair", lambda *args: None)
    monkeypatch.setattr("ecli.ui.panels.curses.color_pair", lambda pair: pair)


def test_panel_manager_default_registry_preserves_existing_panel_names() -> None:
    editor = FakeEditor()

    manager = PanelManager(editor)  # type: ignore[arg-type]

    assert manager.registered_panels["ai_response"] is AiResponsePanel
    assert manager.registered_panels["file_browser"] is FileBrowserPanel
    assert manager.registered_panels["system_doctor"] is SystemDoctorPanel
    assert manager.registered_panels["command_plan"] is CommandPlanPanel
    assert manager.registered_panels["services_status"] is ServicesPanel
    assert "git" not in manager.registered_panels


def test_panel_manager_show_close_and_toggle_transitions_are_stable() -> None:
    editor = FakeEditor()
    manager = PanelManager(editor)  # type: ignore[arg-type]
    manager.registered_panels = {"dummy": DummyPanel}

    manager.show_panel("dummy")

    assert isinstance(manager.active_panel, DummyPanel)
    assert manager.active_panel.visible is True
    assert editor.focus == "panel"
    assert editor._force_full_redraw is True
    assert manager.is_panel_active() is True

    manager.show_panel("dummy")

    assert manager.active_panel is None
    assert editor.focus == "editor"
    assert manager.is_panel_active() is False


def test_panel_manager_delegates_keys_to_active_panel() -> None:
    editor = FakeEditor()
    manager = PanelManager(editor)  # type: ignore[arg-type]
    manager.registered_panels = {"dummy": DummyPanel}
    manager.show_panel("dummy")

    assert manager.handle_key("handled") is True
    assert manager.handle_key("ignored") is False


def test_panel_labels_and_titles_remain_stable() -> None:
    assert "AI responses" in AiResponsePanel.__doc__
    assert "FileBrowserPanel" in FileBrowserPanel.__doc__
    assert "GitPanel" in GitPanel.__doc__

    source = Path("src/ecli/ui/panels.py").read_text(encoding="utf-8")
    assert 'self.title: str = kwargs.get("title", "AI Response")' in source
    assert 'title = " Git Control "' in source
    # File Manager now uses an MC-style action bar (F2/F3/F5/F6/Del/Enter/F10).
    assert '("F10", "Close")' in source
    assert '("Enter", "Open")' in source
    assert "^C:Copy | Shift+arr:Select | F7:Close | F12:Focus" in source


def test_file_browser_right_arrow_enters_directory(workspace: Path) -> None:
    child_dir = workspace / "child"
    child_dir.mkdir()
    editor = FakeEditor(workspace)

    panel = FileBrowserPanel(
        editor.stdscr,
        editor,
        start_path=str(workspace),  # type: ignore[arg-type]
    )
    panel.idx = next(
        index
        for index, entry in enumerate(panel.entries)
        if entry and entry.name == "child"
    )

    assert panel.handle_key(curses.KEY_RIGHT) is True
    assert panel.cwd == child_dir.resolve()


def test_file_browser_right_arrow_opens_selected_file(workspace: Path) -> None:
    target = workspace / "target.txt"
    target.write_text("content\n", encoding="utf-8")
    editor = FakeEditor(workspace)

    panel = FileBrowserPanel(
        editor.stdscr,
        editor,
        start_path=str(workspace),  # type: ignore[arg-type]
    )
    panel.idx = next(
        index
        for index, entry in enumerate(panel.entries)
        if entry and entry.name == "target.txt"
    )

    assert panel.handle_key(curses.KEY_RIGHT) is True
    assert editor.opened_files == [str(target.resolve())]
    assert editor.status_messages[-1] == "Opened file: target.txt"


def test_test_workspaces_remain_under_logs(workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_root)
