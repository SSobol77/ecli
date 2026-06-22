# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/providers/ruff.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Active Ruff diagnostics adapter (the only executing provider in #104).

Ruff is invoked once per collection with a **fixed argv** that reads the current
buffer from stdin (``--stdin-filename`` supplies the path used for output and
per-file configuration discovery), so unsaved edits are linted without touching
the file on disk. ECLI ships no Python lint rules — Ruff owns the rules; this
adapter only runs Ruff safely and normalises its JSON.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import PurePath

from ..command import DEFAULT_TIMEOUT_SECONDS, CommandResult, CommandRunner, default_runner
from ..parsers import ParseError, parse_ruff_json, short_detail
from ..provider_metadata import (
    ProviderCategory,
    ProviderExecutionMode,
    ProviderMetadata,
    ProviderResult,
    ProviderStatus,
)


__all__ = ["RUFF_METADATA", "RuffDiagnosticsProvider"]


RUFF_METADATA = ProviderMetadata(
    id="ruff",
    display_name="Ruff",
    tool_name="ruff",
    category=ProviderCategory.LINT,
    execution_mode=ProviderExecutionMode.CURRENT_FILE,
    status=ProviderStatus.SUPPORTED_EXTERNAL,
    language_ids=("python",),
    extensions=(".py", ".pyi"),
    executable="ruff",
    argv_contract=(
        "ruff",
        "check",
        "--output-format=json",
        "--no-cache",
        "--stdin-filename",
        "<path>",
        "-",
    ),
    parser="parse_ruff_json",
    config_files=("ruff.toml", ".ruff.toml", "pyproject.toml"),
    docs_url="https://docs.astral.sh/ruff/",
    install_hint="This build expects Ruff to be provided by the ECLI diagnostics toolchain.",
    short_label="Ruff",
    runnable_in_build=True,
)


class RuffDiagnosticsProvider:
    """Diagnostics provider backed by the Ruff linter (Python files only)."""

    name = "ruff"
    metadata = RUFF_METADATA

    #: Human-readable capability summary (used in some panel hints).
    description = "Ruff for Python files"

    #: File suffixes Ruff understands.
    SUPPORTED_SUFFIXES = RUFF_METADATA.extensions

    def __init__(
        self,
        executable: str = "ruff",
        runner: CommandRunner | None = None,
    ) -> None:
        """Create a Ruff provider.

        Args:
            executable: Name or path of the Ruff executable. Resolved via
                :func:`shutil.which` for the availability probe.
            runner: Optional injectable command runner (used by tests). Defaults
                to a real, bounded, ``shell=False`` subprocess runner.
        """
        self._executable = executable
        self._runner: CommandRunner = runner or default_runner

    def applies_to(self, file_path: str) -> bool:
        """Return ``True`` for Python source files (``.py`` / ``.pyi``)."""
        if not file_path:
            return False
        return PurePath(file_path).suffix.lower() in self.SUPPORTED_SUFFIXES

    def is_available(self) -> bool:
        """Return ``True`` when the Ruff executable is resolvable on ``PATH``."""
        return shutil.which(self._executable) is not None

    def build_argv(self, file_path: str) -> list[str]:
        """Return the fixed argv used to invoke Ruff for *file_path*.

        Exposed so the exact, unchanging command line is testable. The argv never
        embeds shell metacharacters and never interpolates configured command
        strings.
        """
        return [
            self._executable,
            "check",
            "--output-format=json",
            "--no-cache",
            "--stdin-filename",
            file_path,
            "-",
        ]

    def collect(
        self, file_path: str, text: str, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> ProviderResult:
        """Run Ruff against *text* and parse its JSON output into diagnostics."""
        argv = self.build_argv(file_path)
        try:
            result = self._runner(argv, text, timeout)
        except FileNotFoundError:
            return ProviderResult(
                available=False,
                ok=False,
                detail=f"{self._executable} executable not found",
            )
        except subprocess.TimeoutExpired:
            return ProviderResult(
                available=True,
                ok=False,
                detail=f"{self.name} timed out after {timeout:g}s",
            )
        except OSError as exc:
            return ProviderResult(
                available=True,
                ok=False,
                detail=f"{self.name} could not be executed: {exc.strerror or exc}",
            )
        return self._parse_result(file_path, result)

    def _parse_result(self, file_path: str, result: CommandResult) -> ProviderResult:
        # Ruff exits 0 (clean) or 1 (issues) for a successful run, and 2 on an
        # internal error. With JSON output a successful run prints a JSON array.
        if not result.stdout.strip() and result.returncode >= 2:
            detail = short_detail(result.stderr) or "ruff reported an error"
            return ProviderResult(available=True, ok=False, detail=detail)
        try:
            diagnostics = parse_ruff_json(file_path, result.stdout)
        except ParseError as exc:
            return ProviderResult(available=True, ok=False, detail=str(exc))
        return ProviderResult(available=True, ok=True, diagnostics=diagnostics)
