# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_file_browser_panel.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""File Browser panel responsiveness tests.

These guard the F10 File Browser against the release-blocking freeze where
opening the panel ran ``git status --porcelain`` synchronously on the curses
UI thread. Opening must be instant and Git refresh must happen off-thread.
"""

from __future__ import annotations

import curses
import logging
import queue
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Optional

import pytest

from ecli.integrations.GitBridge import GitBridge
from ecli.ui.panels import FileBrowserPanel, GitPanel


class FakeWindow:
    def __init__(self) -> None:
        """Initialize a fake curses window."""
        self.drawn: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (30, 120)

    def keypad(self, value: bool) -> None:
        return None

    def bkgd(self, ch: str, attr: int = 0) -> None:
        return None

    def touchwin(self) -> None:
        return None

    def erase(self) -> None:
        return None

    def border(self) -> None:
        return None

    def attron(self, attr: int) -> None:
        return None

    def attroff(self, attr: int) -> None:
        return None

    def addstr(self, *_args: Any) -> None:
        return None

    def addnstr(self, *_args: Any) -> None:
        if len(_args) >= 3:
            self.drawn.append(str(_args[2]))

    def noutrefresh(self) -> None:
        return None

    def refresh(self) -> None:
        return None


class FakeEditor:
    """Minimal editor double compatible with FileBrowserPanel and GitPanel."""

    def __init__(self, filename: Path | None = None) -> None:
        """Initialize the editor double."""
        self.stdscr = FakeWindow()
        self.focus = "panel"
        self._force_full_redraw = False
        self.colors: dict[str, Any] = {
            "status": curses.A_BOLD,
            "keyword": curses.A_BOLD,
            "default": curses.A_NORMAL,
            "comment": curses.A_DIM,
            "function": curses.A_BOLD,
            "error": curses.A_BOLD,
            "git_dirty": curses.A_BOLD,
            "git_added": curses.A_NORMAL,
            "git_deleted": curses.A_NORMAL,
            "number": curses.A_NORMAL,
        }
        self.config: dict[str, Any] = {"git": {"enabled": True}}
        self.filename = str(filename) if filename is not None else None
        self.status_messages: list[str] = []
        self.toggle_calls = 0
        self.exit_calls = 0
        self.focus_calls = 0
        self.opened_files: list[str] = []
        self._state_lock = threading.RLock()
        self._git_q: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._git_cmd_q: queue.Queue[str] = queue.Queue()
        self.panel_manager: Any = None
        self.git = GitBridge(self)  # type: ignore[arg-type]

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def toggle_file_browser(self) -> bool:
        self.toggle_calls += 1
        return True

    def exit_editor(self) -> None:
        self.exit_calls += 1

    def toggle_focus(self) -> None:
        self.focus_calls += 1
        self.focus = "editor" if self.focus == "panel" else "panel"

    def open_file(self, path: str) -> None:
        self.opened_files.append(path)


class FakeGitPanel:
    """Records how the File Browser interacts with the Git bridge."""

    def __init__(self) -> None:
        """Initialize the recording double."""
        self.async_calls = 0
        self.sync_calls = 0
        self.statuses: dict[str, str] = {}
        self._pending: Optional[dict[str, str]] = None

    def request_file_status_refresh(self) -> None:
        self.async_calls += 1

    def force_update_file_status_cache(self) -> None:  # must never be called on open
        self.sync_calls += 1

    def get_file_git_status(self, path: str) -> Optional[str]:
        return self.statuses.get(path)

    def queue_result(self, statuses: dict[str, str]) -> None:
        self._pending = statuses

    def drain_file_status_results(self) -> bool:
        if self._pending is None:
            return False
        self.statuses = self._pending
        self._pending = None
        return True


@pytest.fixture(autouse=True)
def fake_curses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: FakeWindow())
    monkeypatch.setattr("ecli.ui.panels.curses.curs_set", lambda value: None)
    monkeypatch.setattr("ecli.ui.panels.curses.init_pair", lambda *args: None)
    monkeypatch.setattr("ecli.ui.panels.curses.color_pair", lambda pair: pair)


def make_browser(
    tmp_path: Path, git_panel: Any = None
) -> tuple[FakeEditor, FileBrowserPanel]:
    editor = FakeEditor(filename=tmp_path / "file.txt")
    panel = FileBrowserPanel(editor.stdscr, editor, start_path=str(tmp_path))  # type: ignore[arg-type]
    if git_panel is not None:
        panel.set_git_panel(git_panel)
    return editor, panel


# ---------------------------------------------------------------------------
# 1. open() schedules an async refresh and never runs Git synchronously.
# ---------------------------------------------------------------------------
def test_open_schedules_async_refresh_not_sync(tmp_path: Path) -> None:
    git_panel = FakeGitPanel()
    _editor, panel = make_browser(tmp_path, git_panel)

    panel.open()

    assert panel.visible is True
    assert git_panel.async_calls == 1
    assert git_panel.sync_calls == 0  # no blocking git status on the UI thread


def test_open_without_git_panel_still_opens(tmp_path: Path) -> None:
    _editor, panel = make_browser(tmp_path, git_panel=None)

    panel.open()  # must not raise even when no Git bridge is wired

    assert panel.visible is True


# ---------------------------------------------------------------------------
# 2 + 6. open() does not wait for the Git subprocess even when it is slow.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_open_does_not_block_on_slow_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    editor = FakeEditor(filename=repo / "file.txt")
    git_panel = GitPanel(editor.stdscr, editor)  # type: ignore[arg-type]
    panel = FileBrowserPanel(editor.stdscr, editor, start_path=str(repo))  # type: ignore[arg-type]
    panel.set_git_panel(git_panel)

    started = threading.Event()
    release = threading.Event()

    def slow_compute() -> dict[str, str]:
        started.set()
        release.wait(5.0)
        return {"slow.txt": "M"}

    monkeypatch.setattr(git_panel, "_compute_file_status_cache", slow_compute)

    t0 = time.monotonic()
    panel.open()
    elapsed = time.monotonic() - t0

    try:
        # open() returned without waiting for the (still-blocked) Git worker.
        assert elapsed < 1.0
        assert started.wait(2.0)  # the worker really did run in the background
        # Nothing applied yet, so no redraw is requested.
        assert panel.process_queues() is False
    finally:
        release.set()

    deadline = time.monotonic() + 3.0
    applied = False
    while time.monotonic() < deadline:
        if panel.process_queues():
            applied = True
            break
        time.sleep(0.02)

    assert applied is True
    assert git_panel.get_file_git_status("slow.txt") == "M"


def test_request_refresh_is_coalesced_while_in_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    editor = FakeEditor(filename=repo / "file.txt")
    git_panel = GitPanel(editor.stdscr, editor)  # type: ignore[arg-type]

    release = threading.Event()
    calls = {"n": 0}

    def slow_compute() -> dict[str, str]:
        calls["n"] += 1
        release.wait(5.0)
        return {}

    monkeypatch.setattr(git_panel, "_compute_file_status_cache", slow_compute)

    try:
        for _ in range(5):
            git_panel.request_file_status_refresh()
        time.sleep(0.1)
        # Only one worker should be in flight despite five requests.
        assert calls["n"] == 1
    finally:
        release.set()

    # Drain so the in-flight flag is cleared for the next request.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        git_panel.drain_file_status_results()
        if not git_panel._file_status_refresh_in_flight:
            break
        time.sleep(0.02)
    assert git_panel._file_status_refresh_in_flight is False


# ---------------------------------------------------------------------------
# 3. Esc / F10 close the panel after it is opened.
# ---------------------------------------------------------------------------
def test_esc_and_f10_close_panel(tmp_path: Path) -> None:
    editor, panel = make_browser(tmp_path, FakeGitPanel())
    panel.open()

    assert panel.handle_key(27) is True  # Esc
    assert editor.toggle_calls == 1

    assert panel.handle_key(curses.KEY_F10) is True
    assert editor.toggle_calls == 2

    assert panel.handle_key(ord("q")) is True
    assert editor.toggle_calls == 3


# ---------------------------------------------------------------------------
# 4. Ctrl+Q quits even while the panel is active.
# ---------------------------------------------------------------------------
def test_ctrl_q_exits_while_panel_active(tmp_path: Path) -> None:
    editor, panel = make_browser(tmp_path, FakeGitPanel())
    panel.open()

    assert panel.handle_key(17) is True  # Ctrl+Q
    assert editor.exit_calls == 1


# ---------------------------------------------------------------------------
# 5. Repeated redraws do not emit per-file DEBUG spam.
# ---------------------------------------------------------------------------
def test_repeated_draw_emits_no_per_file_debug_spam(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    git_panel = FakeGitPanel()
    git_panel.statuses = {str(tmp_path / "a.txt"): "M"}
    _editor, panel = make_browser(tmp_path, git_panel)
    panel.open()

    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = _Capture()
    ecli_logger = logging.getLogger("ecli")
    previous_level = ecli_logger.level
    ecli_logger.addHandler(handler)
    ecli_logger.setLevel(logging.DEBUG)
    try:
        for _ in range(5):
            panel.draw()
    finally:
        ecli_logger.removeHandler(handler)
        ecli_logger.setLevel(previous_level)

    spam = [msg for msg in records if "Git status:" in msg]
    assert spam == []


# ---------------------------------------------------------------------------
# process_queues only requests a redraw when status data actually changed.
# ---------------------------------------------------------------------------
def test_process_queues_is_quiet_without_new_data(tmp_path: Path) -> None:
    git_panel = FakeGitPanel()
    _editor, panel = make_browser(tmp_path, git_panel)
    panel.open()

    # No async result pending -> no redraw requested (avoids a tight redraw loop).
    assert panel.process_queues() is False

    git_panel.queue_result({str(tmp_path / "a.txt"): "M"})
    assert panel.process_queues() is True
    assert panel.process_queues() is False


# ---------------------------------------------------------------------------
# 'r' triggers a bounded async refresh without blocking.
# ---------------------------------------------------------------------------
def test_r_key_triggers_async_refresh(tmp_path: Path) -> None:
    git_panel = FakeGitPanel()
    _editor, panel = make_browser(tmp_path, git_panel)
    panel.open()
    assert git_panel.async_calls == 1

    assert panel.handle_key(ord("r")) is True
    assert git_panel.async_calls == 2
    assert git_panel.sync_calls == 0
