# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/command_runner.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Shared safe command runner for F4 linter microservice providers.

See ``docs/architecture/ecli-f4-linter-microservices-design.md`` section 8
("Common Command Runner"). This module knows nothing about any specific
linter -- it only provides safe subprocess primitives every provider's
``provider.py`` builds its own argv for and calls into.

Rules enforced here:

* the runner always calls subprocess with an argv list, never a shell string;
* no ``shell=True``, ever;
* output is bounded (``max_stdout_bytes``/``max_stderr_bytes``);
* timeouts are explicit and required;
* errors (timeout, missing executable, OS-level failure) are converted into
  a structured ``CommandResult`` instead of raising.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_STDOUT_BYTES = 2_000_000
DEFAULT_MAX_STDERR_BYTES = 200_000

_TRUNCATION_MARKER = "\n... [output truncated]"


@dataclass(frozen=True)
class CommandResult:
    """Structured, safe outcome of one bounded subprocess invocation."""

    argv: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    execution_error: str | None = None

    @property
    def ok(self) -> bool:
        """Return True when the process ran to completion without a runner-level failure."""
        return not self.timed_out and self.execution_error is None


def run_linter_command(  # noqa: PLR0913 -- signature mandated verbatim by the
    # design contract, docs/architecture/ecli-f4-linter-microservices-design.md
    # section 8 ("Common Command Runner").
    argv: Sequence[str],
    *,
    cwd: str,
    input_text: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_stdout_bytes: int = DEFAULT_MAX_STDOUT_BYTES,
    max_stderr_bytes: int = DEFAULT_MAX_STDERR_BYTES,
    runner: Runner = subprocess.run,
) -> CommandResult:
    """Run ``argv`` as a bounded, non-shell subprocess.

    Never raises for expected failure modes (timeout, missing executable,
    other OS-level errors); each is converted into a ``CommandResult`` the
    caller can turn into a controlled ``DiagnosticResult``.
    """
    argv_tuple = tuple(argv)
    try:
        completed = runner(
            list(argv_tuple),
            input=input_text,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            argv=argv_tuple,
            cwd=cwd,
            returncode=-1,
            stdout="",
            stderr="",
            timed_out=True,
        )
    except OSError as exc:
        logger.warning("Command execution failed for %r: %s", argv_tuple, exc)
        return CommandResult(
            argv=argv_tuple,
            cwd=cwd,
            returncode=-1,
            stdout="",
            stderr="",
            execution_error=str(exc),
        )

    return CommandResult(
        argv=argv_tuple,
        cwd=cwd,
        returncode=completed.returncode,
        stdout=_bounded(completed.stdout, max_stdout_bytes),
        stderr=_bounded(completed.stderr, max_stderr_bytes),
    )


def _bounded(text: str, max_bytes: int) -> str:
    """Truncate ``text`` to at most ``max_bytes`` UTF-8 bytes."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + _TRUNCATION_MARKER
