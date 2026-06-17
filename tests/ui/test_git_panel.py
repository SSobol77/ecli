# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_git_panel.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Git panel command execution and repository-state tests."""

from __future__ import annotations

import curses
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ecli.integrations.GitBridge import GitBridge, GitCommandResult
from ecli.ui.panels import GitPanel


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


class FakeWindow:
    def __init__(self) -> None:
        """Initialize a fake curses window."""
        self.keypad_values: list[bool] = []
        self.drawn: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (30, 120)

    def keypad(self, value: bool) -> None:
        self.keypad_values.append(value)

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

    def hline(self, *_args: Any) -> None:
        return None

    def vline(self, *_args: Any) -> None:
        return None

    def noutrefresh(self) -> None:
        return None

    def refresh(self) -> None:
        return None


class FakePanelManager:
    active_panel: Any = None

    def close_active_panel(self) -> None:
        return None


class FakeEditor:
    def __init__(self, filename: Path | None = None) -> None:
        """Initialize a Git panel compatible editor double."""
        self.stdscr = FakeWindow()
        self.focus = "panel"
        self._force_full_redraw = False
        self.colors = {
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
        self.status_messages: list[str] = []
        self.filename = str(filename) if filename is not None else None
        self._state_lock = threading.RLock()
        self._git_q: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._git_cmd_q: queue.Queue[str] = queue.Queue()
        self.panel_manager = FakePanelManager()
        self.git = GitBridge(self)  # type: ignore[arg-type]

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def prompt(self, *_args: Any, **_kwargs: Any) -> str:
        return ""

    def toggle_focus(self) -> None:
        self.focus = "editor" if self.focus == "panel" else "panel"


@pytest.fixture(autouse=True)
def fake_curses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: FakeWindow())
    monkeypatch.setattr("ecli.ui.panels.curses.curs_set", lambda value: None)
    monkeypatch.setattr("ecli.ui.panels.curses.init_pair", lambda *args: None)
    monkeypatch.setattr("ecli.ui.panels.curses.color_pair", lambda pair: pair)


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def init_repo(path: Path, *, commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init")
    git(path, "config", "user.name", "ECLI Tests")
    git(path, "config", "user.email", "ecli-tests@example.invalid")
    tracked = path / "tracked.txt"
    tracked.write_text("hello\n", encoding="utf-8")
    if commit:
        git(path, "add", "tracked.txt")
        git(path, "commit", "-m", "initial")
    return tracked


def make_panel(filename: Path | None = None) -> tuple[FakeEditor, GitPanel]:
    editor = FakeEditor(filename)
    panel = GitPanel(editor.stdscr, editor)  # type: ignore[arg-type]
    editor.panel_manager.active_panel = panel
    panel.visible = True
    return editor, panel


def wait_for_panel(panel: GitPanel, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        panel.process_queues()
        if not panel.is_busy:
            return
        time.sleep(0.02)
    pytest.fail(f"Git panel remained busy with output: {panel.output_lines!r}")


def test_status_command_returns_output_and_clears_busy(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    (tracked.parent / "new.txt").write_text("new\n", encoding="utf-8")
    _editor, panel = make_panel(tracked)

    panel._handle_status()
    assert panel.output_lines == ["Running: git status --short --branch..."]
    wait_for_panel(panel)

    output = "\n".join(panel.output_lines)
    assert "Running:" not in output
    assert "##" in output
    assert "new.txt" in output
    assert panel.is_busy is False


def test_status_command_clean_repo_does_not_stay_running(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    _editor, panel = make_panel(tracked)

    panel._handle_status()
    wait_for_panel(panel)

    output = "\n".join(panel.output_lines)
    assert "Running:" not in output
    assert output == "Clean working tree." or "##" in output
    assert panel.is_busy is False


def test_status_command_non_git_directory_reports_not_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "not-repo" / "file.txt"
    target.parent.mkdir()
    target.write_text("hello\n", encoding="utf-8")
    monkeypatch.chdir(target.parent)
    _editor, panel = make_panel(target)

    panel._handle_status()
    wait_for_panel(panel)

    assert panel.output_lines == ["Not a Git repository."]
    assert panel.is_busy is False
    assert panel.git_bridge.repo_state == "not repo"


def test_failing_cwd_renders_error_and_clears_busy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked = init_repo(tmp_path / "repo")
    _editor, panel = make_panel(tracked)
    missing = tmp_path / "missing"
    monkeypatch.setattr(
        panel.git_bridge, "resolve_repo_root", lambda _ctx=None: str(missing)
    )

    panel._run_command_sync(["git", "status", "--short", "--branch"])

    output = "\n".join(panel.output_lines)
    assert "Command failed: git status --short --branch" in output
    assert "Return code: 127" in output
    assert panel.is_busy is False


def test_timeout_renders_message_and_clears_busy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked = init_repo(tmp_path / "repo")
    _editor, panel = make_panel(tracked)

    def timed_out(*_args: Any, **_kwargs: Any) -> GitCommandResult:
        return GitCommandResult(
            command_label="git status --short --branch",
            cwd=str(tracked.parent),
            returncode=-15,
            stdout="",
            stderr="",
            timed_out=True,
            error="Command timed out after 15s.",
        )

    monkeypatch.setattr(panel.git_bridge, "run_git_command", timed_out)
    panel._run_command_sync(["git", "status", "--short", "--branch"])

    output = "\n".join(panel.output_lines)
    assert "Command timed out: git status --short --branch" in output
    assert panel.is_busy is False


def test_async_worker_only_enqueues_result_until_ui_thread_consumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked = init_repo(tmp_path / "repo")
    editor, panel = make_panel(tracked)

    def completed(*_args: Any, **_kwargs: Any) -> GitCommandResult:
        return GitCommandResult(
            command_label="git status --short --branch",
            cwd=str(tracked.parent),
            returncode=0,
            stdout="## main\n",
            stderr="",
        )

    monkeypatch.setattr(panel, "_run_git_command", completed)

    panel._handle_status()
    editor._force_full_redraw = False

    deadline = time.monotonic() + 5.0
    while panel.command_results.empty() and time.monotonic() < deadline:
        time.sleep(0.02)

    assert not panel.command_results.empty()
    assert panel.output_lines == ["Running: git status --short --branch..."]
    assert panel.is_busy is True
    assert editor._force_full_redraw is False

    assert panel.process_queues() is True
    assert panel.output_lines == ["## main"]
    assert panel.is_busy is False
    assert editor._force_full_redraw is True


def test_stale_worker_result_after_cancel_is_ignored(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    _editor, panel = make_panel(tracked)
    stale_generation = panel._command_generation + 1
    panel._command_generation = stale_generation
    panel.is_busy = True
    panel.output_lines = ["Running: git status --short --branch..."]

    assert panel.handle_key(27) is True
    assert panel.output_lines == ["Operation cancelled."]

    panel.command_results.put(
        (
            stale_generation,
            GitCommandResult(
                command_label="git status --short --branch",
                cwd=str(tracked.parent),
                returncode=0,
                stdout="## stale\n",
                stderr="",
            ),
        )
    )

    assert panel.process_queues() is True
    assert panel.output_lines == ["Operation cancelled."]
    assert panel.is_busy is False


def test_nonzero_exit_renders_stderr_and_clears_busy(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    _editor, panel = make_panel(tracked)

    panel._run_command_sync(["git", "rev-parse", "--verify", "missing-ref"])

    output = "\n".join(panel.output_lines)
    assert "Command failed: git rev-parse --verify missing-ref" in output
    assert "Return code: 128" in output
    assert "stderr:" in output
    assert panel.is_busy is False


def test_operation_cancelled_is_panel_local(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    editor, panel = make_panel(tracked)
    editor.status_messages.clear()
    panel.is_busy = True

    assert panel.handle_key(27) is True

    assert panel.output_lines == ["Operation cancelled."]
    assert panel.is_busy is False
    assert editor.status_messages
    assert all(message != "Operation cancelled." for message in editor.status_messages)


def test_header_fields_are_populated_for_repo(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    editor, _panel = make_panel(tracked)

    branch, user, commits = editor.git.get_info(str(tracked))

    assert branch.strip("*")
    assert user == "ECLI Tests"
    assert commits == "1"
    assert editor.git.repo_state in {"clean", "dirty"}


def test_empty_repo_has_zero_commits_and_no_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global-gitconfig"))
    repo = tmp_path / "empty"
    repo.mkdir()
    git(repo, "init")
    editor, _panel = make_panel(repo / "new.txt")

    branch, user, commits = editor.git.get_info(str(repo / "new.txt"))

    assert branch.strip("*")
    assert user == "not configured"
    assert commits == "0"


def test_commands_use_repo_root_when_root_opened_directly(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    editor, _panel = make_panel(tracked.parent)

    result = editor.git.run_git_command(
        ["git", "rev-parse", "--show-toplevel"],
        file_path_context=str(tracked.parent),
    )

    assert result.returncode == 0
    assert Path(result.cwd).resolve() == tracked.parent.resolve()
    assert Path(result.stdout.strip()).resolve() == tracked.parent.resolve()


def test_commands_use_repo_root_for_file_in_subdirectory(tmp_path: Path) -> None:
    tracked = init_repo(tmp_path / "repo")
    nested = tracked.parent / "subdir" / "nested.txt"
    nested.parent.mkdir()
    nested.write_text("nested\n", encoding="utf-8")
    editor, _panel = make_panel(nested)

    result = editor.git.run_git_command(
        ["git", "rev-parse", "--show-toplevel"],
        file_path_context=str(nested),
    )

    assert result.returncode == 0
    assert Path(result.cwd).resolve() == tracked.parent.resolve()
    assert Path(result.stdout.strip()).resolve() == tracked.parent.resolve()


def test_commands_use_repo_root_when_launched_outside_repo_with_relative_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracked = init_repo(tmp_path / "repo")
    nested = tracked.parent / "subdir" / "nested.txt"
    nested.parent.mkdir()
    nested.write_text("nested\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(tmp_path)
    relative_file = Path("repo") / "subdir" / "nested.txt"
    editor, _panel = make_panel(relative_file)

    result = editor.git.run_git_command(
        ["git", "rev-parse", "--show-toplevel"],
        file_path_context=str(relative_file),
    )

    assert result.returncode == 0
    assert Path(result.cwd).resolve() == tracked.parent.resolve()
    assert Path(result.stdout.strip()).resolve() == tracked.parent.resolve()
    assert Path.cwd() != Path(result.cwd)


def test_empty_repo_status_uses_repo_root_and_clears_busy(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    git(repo, "init")
    editor, panel = make_panel(repo)

    result = editor.git.run_git_command(
        ["git", "status", "--short", "--branch"],
        file_path_context=str(repo),
    )

    assert result.returncode == 0
    assert Path(result.cwd).resolve() == repo.resolve()

    panel._run_command_sync(["git", "status", "--short", "--branch"])
    assert "Running:" not in "\n".join(panel.output_lines)
    assert panel.is_busy is False
