# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/integrations/test_pysh_backend.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from ecli.integrations import pysh_backend
from ecli.integrations.pysh_backend import MISSING_PYSH_MESSAGE, PySHSubprocessBackend


class _CompletedProcess:
    def __init__(
        self,
        stdout: str = "out\n",
        stderr: str = "err\n",
        returncode: int | None = 5,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.terminate_calls = 0
        self.kill_calls = 0

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        if self.returncode is None:
            self.returncode = 5
        return (self.stdout, self.stderr)

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = -15

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9


class _TimeoutThenCancelledProcess:
    def __init__(self, backend: PySHSubprocessBackend) -> None:
        self.backend = backend
        self.returncode: int | None = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self._first_communicate = True

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        if self._first_communicate:
            self._first_communicate = False
            self.backend.cancel()
            raise subprocess.TimeoutExpired(cmd=["pysh"], timeout=timeout or 0.0)
        self.returncode = -15
        return ("partial stdout\n", "partial stderr\n")

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = -15

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9


def test_pysh_backend_missing_executable_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("ecli.integrations.pysh_backend.shutil.which", lambda _name: None)
    backend = PySHSubprocessBackend()

    result = backend.run("echo hello", tmp_path, {"ECLI_TEST": "1"})

    assert backend.is_available() is False
    assert result.command == "echo hello"
    assert result.cwd == tmp_path
    assert result.returncode == 127
    assert result.stdout == ""
    assert result.stderr == MISSING_PYSH_MESSAGE
    assert result.cancelled is False


def test_pysh_backend_invokes_pysh_with_argv_and_captures_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_popen(args: list[str], **kwargs: Any) -> _CompletedProcess:
        calls.append({"args": args, **kwargs})
        return _CompletedProcess(stdout="stdout text\n", stderr="stderr text\n")

    env = {"ORIGINAL": "value"}
    monkeypatch.setattr("ecli.integrations.pysh_backend.shutil.which", lambda _name: "pysh")
    monkeypatch.setattr("ecli.integrations.pysh_backend.subprocess.Popen", fake_popen)

    result = PySHSubprocessBackend().run("echo $HOME && false", tmp_path, env)

    assert result.returncode == 5
    assert result.stdout == "stdout text\n"
    assert result.stderr == "stderr text\n"
    assert result.cancelled is False
    assert calls == [
        {
            "args": ["pysh", "-c", "echo $HOME && false"],
            "cwd": str(tmp_path),
            "env": {"ORIGINAL": "value"},
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }
    ]
    assert "shell" not in calls[0]
    assert calls[0]["env"] is not env
    assert env == {"ORIGINAL": "value"}


def test_pysh_backend_cancel_without_process_is_idempotent() -> None:
    backend = PySHSubprocessBackend()

    backend.cancel()
    backend.cancel()

    assert backend._process is None


def test_pysh_backend_cancel_terminates_only_tracked_process_once() -> None:
    backend = PySHSubprocessBackend()
    tracked = _CompletedProcess(returncode=None)
    unrelated = _CompletedProcess()
    backend._process = cast(Any, tracked)  # regression target: owned process only.

    backend.cancel()
    backend.cancel()

    assert tracked.terminate_calls == 1
    assert unrelated.terminate_calls == 0


def test_pysh_backend_cancelled_run_returns_cancelled_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backend = PySHSubprocessBackend()
    processes: list[_TimeoutThenCancelledProcess] = []

    def fake_popen(_args: list[str], **_kwargs: Any) -> _TimeoutThenCancelledProcess:
        process = _TimeoutThenCancelledProcess(backend)
        processes.append(process)
        return process

    monkeypatch.setattr("ecli.integrations.pysh_backend.shutil.which", lambda _name: "pysh")
    monkeypatch.setattr("ecli.integrations.pysh_backend.subprocess.Popen", fake_popen)

    result = backend.run("long command", tmp_path, {})

    assert result.cancelled is True
    assert result.returncode == -15
    assert result.stdout == "partial stdout\n"
    assert result.stderr == "partial stderr\n"
    assert processes[0].terminate_calls == 1
