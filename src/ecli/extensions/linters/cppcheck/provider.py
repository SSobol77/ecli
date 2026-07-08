# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/cppcheck/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Cppcheck (C/C++) diagnostics provider -- secondary static analysis
alongside Clang-Tidy, useful even when compile-database context is limited.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from ecli.extensions.linters.core.command_runner import run_linter_command
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.core.provider_utils import (
    build_command_diagnostics_result,
    find_executable,
    missing_executable_result,
    status_result,
    supports_by_language_or_extension,
)
from ecli.extensions.linters.cppcheck.parser import parse_cppcheck_output


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_LANGUAGES = frozenset({"c", "cpp", "c++", "cplusplus", "objective-c"})
_EXTENSIONS = frozenset({".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".hxx"})
_DISPLAY_NAME = "Cppcheck"
_DEFAULT_TIMEOUT_SECONDS = 30.0


class CppcheckDiagnosticProvider:
    """Diagnostics provider backed by ``cppcheck --template=gcc``."""

    name = "cppcheck"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "cppcheck",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True for C/C++ files by language or extension."""
        return supports_by_language_or_extension(
            request, languages=_LANGUAGES, extensions=_EXTENSIONS
        )

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run cppcheck against the current file."""
        if request.file_path is None:
            return status_result(
                request,
                name=self.name,
                enabled=self.enabled,
                status="skipped",
                message=f"{_DISPLAY_NAME} diagnostics require a saved file.",
            )
        executable = find_executable(self.executable)
        if executable is None:
            return missing_executable_result(
                request, name=self.name, enabled=self.enabled, display_name=_DISPLAY_NAME
            )

        argv = [
            executable,
            "--enable=warning,style,performance,portability",
            "--template=gcc",
            request.file_path,
        ]
        result = run_linter_command(
            argv,
            cwd=request.project_root or ".",
            timeout_seconds=self.timeout_seconds,
            runner=self._runner,
        )
        file_path = request.file_path
        return build_command_diagnostics_result(
            request,
            result,
            name=self.name,
            enabled=self.enabled,
            display_name=_DISPLAY_NAME,
            timeout_seconds=self.timeout_seconds,
            # cppcheck reports findings on stderr by default.
            parse=lambda _stdout: parse_cppcheck_output(
                "\n".join(part for part in (result.stdout, result.stderr) if part),
                default_file=file_path,
            ),
        )
