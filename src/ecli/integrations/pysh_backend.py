# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/integrations/pysh_backend.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""PySH subprocess integration for the ECLI Console Panel.

PySH is used here as a command execution backend only. This module does not
open a terminal device, parse terminal control sequences, or embed an
interactive shell inside curses.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


MISSING_PYSH_MESSAGE = (
    "PySH backend is not available. Install pysh or configure the PySH backend path."
)


@dataclass(frozen=True)
class PySHCommandResult:
    """Completed PySH command result."""

    command: str
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    cancelled: bool = False
    backend: str = "pysh-subprocess"


class PySHBackendUnavailable(RuntimeError):  # noqa: N818
    """Raised when the PySH backend executable is not available."""


class PySHSubprocessBackend:
    """Subprocess adapter for executing commands through PySH."""

    def __init__(self, executable: str = "pysh") -> None:
        """Initialize the backend with the executable name or absolute path."""
        self.executable = executable
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = False

    def is_available(self) -> bool:
        """Return True when the configured PySH executable is discoverable."""
        return self._resolve_executable() is not None

    def run(self, command: str, cwd: Path, env: Mapping[str, str]) -> PySHCommandResult:
        """Execute *command* as ``pysh -c <command>`` without host shell parsing."""
        executable = self._resolve_executable()
        if executable is None:
            return PySHCommandResult(
                command=command,
                cwd=cwd,
                returncode=127,
                stdout="",
                stderr=MISSING_PYSH_MESSAGE,
            )

        with self._lock:
            if self._process is not None:
                return PySHCommandResult(
                    command=command,
                    cwd=cwd,
                    returncode=126,
                    stdout="",
                    stderr="PySH backend is already running a command.",
                )
            self._cancel_requested = False

        try:
            process = subprocess.Popen(
                [executable, "-c", command],
                cwd=str(cwd),
                env=dict(env),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            return PySHCommandResult(
                command=command,
                cwd=cwd,
                returncode=127,
                stdout="",
                stderr=MISSING_PYSH_MESSAGE,
            )
        except OSError as exc:
            return PySHCommandResult(
                command=command,
                cwd=cwd,
                returncode=126,
                stdout="",
                stderr=f"PySH backend execution failed: {exc}",
            )

        with self._lock:
            self._process = process
            cancel_requested = self._cancel_requested

        if cancel_requested:
            self._terminate_process(process)

        stdout = ""
        stderr = ""
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                with self._lock:
                    cancel_requested = self._cancel_requested
                if cancel_requested:
                    self._terminate_process(process)
                    stdout, stderr = self._collect_cancelled_process(process)
                    break

        with self._lock:
            cancelled = self._cancel_requested
            self._process = None

        return PySHCommandResult(
            command=command,
            cwd=cwd,
            returncode=int(process.returncode),
            stdout=stdout,
            stderr=stderr,
            cancelled=cancelled,
        )

    def cancel(self) -> None:
        """Request cancellation of the current PySH subprocess, if any."""
        with self._lock:
            self._cancel_requested = True
            process = self._process
        if process is not None:
            self._terminate_process(process)

    def _resolve_executable(self) -> str | None:
        return shutil.which(self.executable)

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
        except ProcessLookupError:
            return
        except OSError:
            return

    def _collect_cancelled_process(
        self, process: subprocess.Popen[str]
    ) -> tuple[str, str]:
        try:
            return process.communicate(timeout=1.0)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                except OSError:
                    pass
            return process.communicate()
