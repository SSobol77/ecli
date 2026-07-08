# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_checkstyle/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Checkstyle (Java) diagnostics provider.

Checkstyle's CLI structurally requires a ``-c <config>`` ruleset argument
to run at all. Rather than run it blindly and surface Checkstyle's own CLI
usage error, this provider looks for a conventional project configuration
file first and returns a controlled, actionable message when none is
found -- mirroring the safety pattern used by Cargo Clippy's crate-root
requirement.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from ecli.extensions.linters.core.command_runner import run_linter_command
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.core.provider_utils import (
    build_command_diagnostics_result,
    find_executable,
    missing_executable_result,
    status_result,
    supports_by_language_or_extension,
)
from ecli.extensions.linters.java_checkstyle.parser import parse_checkstyle_output


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_LANGUAGES = frozenset({"java"})
_EXTENSIONS = frozenset({".java"})
_DISPLAY_NAME = "Checkstyle"
_DEFAULT_TIMEOUT_SECONDS = 30.0

_CONFIG_CANDIDATES: tuple[str, ...] = (
    "checkstyle.xml",
    "config/checkstyle/checkstyle.xml",
)


def _find_config(project_root: str) -> str | None:
    base = Path(project_root) if project_root else Path(".")
    for candidate in _CONFIG_CANDIDATES:
        path = base / candidate
        if path.is_file():
            return str(path)
    return None


class JavaCheckstyleDiagnosticProvider:
    """Diagnostics provider backed by ``checkstyle -f xml -c <config>``."""

    name = "checkstyle"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "checkstyle",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True for Java files by language or extension."""
        return supports_by_language_or_extension(
            request, languages=_LANGUAGES, extensions=_EXTENSIONS
        )

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run Checkstyle against the current file if a config is found."""
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

        config = _find_config(request.project_root)
        if config is None:
            return status_result(
                request,
                name=self.name,
                enabled=self.enabled,
                status="skipped",
                message=(
                    f"{_DISPLAY_NAME} diagnostics require a Checkstyle "
                    "configuration file (checkstyle.xml)."
                ),
            )

        argv = [executable, "-f", "xml", "-c", config, request.file_path]
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
            parse=lambda stdout: parse_checkstyle_output(stdout, default_file=file_path),
        )
