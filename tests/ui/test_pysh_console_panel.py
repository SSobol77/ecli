# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_pysh_console_panel.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Mapping

import pytest

from ecli.integrations.pysh_backend import PySHCommandResult
from ecli.ui.pysh_console_panel import PySHConsolePanel


class _FakeWindow:
    def __init__(self) -> None:
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


class _FakePanelManager:
    def __init__(self) -> None:
        self.active_panel: object | None = None
        self.close_calls = 0

    def close_active_panel(self) -> None:
        self.close_calls += 1


class _FakeEditor:
    def __init__(self) -> None:
        self.stdscr = _FakeWindow()
        self.colors: dict[str, int] = {}
        self.config: dict[str, Any] = {}
        self.filename = None
        self.focus = "panel"
        self.status_messages: list[str] = []
        self.panel_manager = _FakePanelManager()
        self.toggle_focus_calls = 0

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def toggle_focus(self) -> bool:
        self.toggle_focus_calls += 1
        self.focus = "editor" if self.focus == "panel" else "panel"
        return True


class _FakeBackend:
    def __init__(self, result: PySHCommandResult | None = None) -> None:
        self.result = result
        self.run_calls: list[tuple[str, Path, dict[str, str]]] = []
        self.cancel_calls = 0

    def run(
        self, command: str, cwd: Path, env: Mapping[str, str]
    ) -> PySHCommandResult:
        env_copy = dict(env)
        self.run_calls.append((command, cwd, env_copy))
        if self.result is not None:
            return self.result
        return PySHCommandResult(
            command=command,
            cwd=cwd,
            returncode=0,
            stdout="",
            stderr="",
        )

    def cancel(self) -> None:
        self.cancel_calls += 1


class _ImmediateThread:
    def __init__(
        self,
        target: Any,
        args: tuple[Any, ...],
        daemon: bool,
    ) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False

    def start(self) -> None:
        self.started = True
        self.target(*self.args)


@pytest.fixture
def panel_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., tuple[PySHConsolePanel, _FakeEditor, _FakeBackend]]:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: _FakeWindow())

    def build(
        *,
        backend: _FakeBackend | None = None,
        cwd: Path | None = None,
    ) -> tuple[PySHConsolePanel, _FakeEditor, _FakeBackend]:
        editor = _FakeEditor()
        fake_backend = backend or _FakeBackend()
        panel = PySHConsolePanel(
            editor.stdscr,
            editor,
            backend=fake_backend,  # type: ignore[arg-type]
        )
        editor.panel_manager.active_panel = panel
        panel.visible = True
        if cwd is not None:
            panel.cwd = cwd
        return panel, editor, fake_backend

    return build


def _submit(panel: PySHConsolePanel, command: str) -> None:
    panel.input_line = command
    panel.cursor_col = len(command)
    assert panel.handle_key(10) is True


def test_pysh_console_builtins_do_not_call_backend(
    panel_factory: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cwd = tmp_path / "cwd"
    child = cwd / "child"
    home = tmp_path / "home"
    child.mkdir(parents=True)
    home.mkdir()
    panel, editor, backend = panel_factory(cwd=cwd)

    _submit(panel, "pwd")
    assert str(cwd) in "\n".join(panel.transcript)
    _submit(panel, "cd child")
    old_cwd = panel.cwd
    _submit(panel, "cd missing")
    assert "cd: no such directory:" in "\n".join(panel.transcript)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    _submit(panel, "cd")
    panel.transcript = ["old output"]
    _submit(panel, "clear")
    assert panel.transcript == []
    _submit(panel, "exit")

    assert panel.history[0] == "pwd"
    assert old_cwd == child.resolve()
    assert panel.cwd == home.resolve()
    assert editor.panel_manager.close_calls == 1
    assert backend.run_calls == []
    assert backend.cancel_calls == 0


def test_pysh_console_invalid_cd_preserves_cwd(
    panel_factory: Any,
    tmp_path: Path,
) -> None:
    panel, _editor, backend = panel_factory(cwd=tmp_path)

    _submit(panel, "cd does-not-exist")

    assert panel.cwd == tmp_path
    assert panel.transcript[-1].startswith("cd: no such directory:")
    assert backend.run_calls == []


def test_pysh_console_external_command_flow(
    panel_factory: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = PySHCommandResult(
        command="run tool",
        cwd=tmp_path,
        returncode=7,
        stdout="stdout line\n",
        stderr="stderr line\n",
    )
    backend = _FakeBackend(result)
    panel, _editor, fake_backend = panel_factory(backend=backend, cwd=tmp_path)
    monkeypatch.setattr("ecli.ui.pysh_console_panel.threading.Thread", _ImmediateThread)

    _submit(panel, "run tool")

    assert panel._running_command == "run tool"
    assert panel.process_queues() is True
    assert panel._running_command is None
    assert fake_backend.run_calls[0][0] == "run tool"
    assert fake_backend.run_calls[0][1] == tmp_path
    transcript = "\n".join(panel.transcript)
    assert "run tool" in transcript
    assert "stdout line" in transcript
    assert "stderr line" in transcript
    assert "[exit 7]" in transcript


def test_pysh_console_cancel_running_command(
    panel_factory: Any,
    tmp_path: Path,
) -> None:
    panel, editor, backend = panel_factory(cwd=tmp_path)
    panel._running_command = "long command"

    assert panel.handle_key(3) is True

    assert backend.cancel_calls == 1
    assert "Command cancelled." in panel.transcript
    assert panel.visible is True
    assert editor.panel_manager.close_calls == 0

    panel._result_queue.put(
        PySHCommandResult(
            command="long command",
            cwd=tmp_path,
            returncode=-15,
            stdout="",
            stderr="",
            cancelled=True,
        )
    )
    assert panel.process_queues() is True
    assert panel._running_command is None
    assert panel.transcript.count("Command cancelled.") == 1


def test_pysh_console_cancel_without_running_command_does_not_crash(
    panel_factory: Any,
) -> None:
    panel, editor, backend = panel_factory()

    assert panel.handle_key(3) is True

    assert backend.cancel_calls == 0
    assert panel.transcript == []
    assert editor.status_messages[-1] == "No PySH command is running."
