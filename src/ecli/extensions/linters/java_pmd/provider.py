# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_pmd/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""PMD (Java) diagnostics provider.

PMD's CLI structurally requires a ``--rulesets`` argument to run at all.
Rather than run it blindly and surface PMD's own CLI usage error, this
provider looks for a conventional project ruleset file first and returns a
controlled, actionable message when none is found -- mirroring the safety
pattern used by Cargo Clippy's crate-root requirement.
"""

from __future__ import annotations

import dataclasses
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
from ecli.extensions.linters.java_pmd.parser import parse_pmd_output


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_LANGUAGES = frozenset({"java"})
_EXTENSIONS = frozenset({".java"})
_DISPLAY_NAME = "PMD"
_DEFAULT_TIMEOUT_SECONDS = 30.0

_RULESET_CANDIDATES: tuple[str, ...] = ("pmd.xml", "ruleset.xml")


def _find_ruleset(project_root: str) -> str | None:
    base = Path(project_root) if project_root else Path(".")
    for candidate in _RULESET_CANDIDATES:
        path = base / candidate
        if path.is_file():
            return str(path)
    return None


class JavaPmdDiagnosticProvider:
    """Diagnostics provider backed by ``pmd check --format xml --rulesets``."""

    name = "pmd"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "pmd",
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
        """Run PMD against the current file if a ruleset is found."""
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

        ruleset = _find_ruleset(request.project_root)
        if ruleset is None:
            return status_result(
                request,
                name=self.name,
                enabled=self.enabled,
                status="skipped",
                message=(
                    f"{_DISPLAY_NAME} diagnostics require a PMD ruleset "
                    "file (pmd.xml or ruleset.xml)."
                ),
            )

        argv = [
            executable,
            "check",
            "--format",
            "xml",
            "--dir",
            request.file_path,
            "--rulesets",
            ruleset,
        ]
        result = run_linter_command(
            argv,
            cwd=request.project_root or ".",
            timeout_seconds=self.timeout_seconds,
            runner=self._runner,
        )
        # PMD returns exit code 4 when violations are found and 0 otherwise
        # (unless a real usage/config error occurred, surfaced via stderr);
        # normalize 4 to 0 so the shared PASS/error classification below
        # does not mistake "violations found" for a tool failure.
        if result.returncode == 4:
            result = dataclasses.replace(result, returncode=0)
        file_path = request.file_path
        return build_command_diagnostics_result(
            request,
            result,
            name=self.name,
            enabled=self.enabled,
            display_name=_DISPLAY_NAME,
            timeout_seconds=self.timeout_seconds,
            parse=lambda stdout: parse_pmd_output(stdout, default_file=file_path),
        )
