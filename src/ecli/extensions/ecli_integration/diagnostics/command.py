# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/command.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Safe command-execution contract for diagnostics adapters (#104).

This is the *only* place the diagnostics layer touches :mod:`subprocess`. The
command contract is intentionally narrow:

* a **fixed argv list** built by an ECLI-owned adapter (never a shell string and
  never a user-supplied command),
* ``shell=False`` (the default),
* a **bounded timeout**,
* the current buffer fed on stdin,
* captured stdout/stderr returned as a small immutable :class:`CommandResult`.

It never runs a VS Code extension host, never runs ``package.json`` scripts,
never invokes a package manager, and never auto-installs anything. The runner is
injectable (:data:`CommandRunner`) so adapters and tests can substitute a
deterministic fake without spawning a real process.

The command model concept is ported from the multi-linter design of
`fnando/vscode-linter` (MIT); see ``THIRD_PARTY_NOTICES.md``. ECLI re-implements
it in Python and does not execute any VS Code runtime code.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "CommandResult",
    "CommandRunner",
    "default_runner",
]

#: Bounded default timeout (seconds) for any provider subprocess.
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CommandResult:
    """Minimal, captured result of an external command invocation."""

    returncode: int
    stdout: str
    stderr: str = ""


# A runner abstracts subprocess execution so adapters and tests can inject
# deterministic behavior without spawning real processes. It receives the
# fully-built argv, the stdin payload and a bounded timeout, and returns a
# CommandResult. Implementations must never use a shell.
CommandRunner = Callable[[Sequence[str], str, float], CommandResult]


def default_runner(argv: Sequence[str], text: str, timeout: float) -> CommandResult:
    """Run *argv* with *text* on stdin, capturing output with a bounded timeout.

    Uses ``shell=False`` (the default) so the fixed argv is executed directly,
    never through a shell. Raises :class:`FileNotFoundError` when the executable
    is missing and :class:`subprocess.TimeoutExpired` when the timeout elapses;
    adapters convert both into a structured result.
    """
    # Safe by construction: a fixed argv (never a shell string), shell=False
    # (the default), and a bounded timeout. The executable is the linter only.
    completed = subprocess.run(
        list(argv),
        input=text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
