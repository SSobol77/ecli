# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/actionlint/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""actionlint diagnostics provider.

Deliberately narrow applicability: only ``.github/workflows/*.yml`` and
``.github/workflows/*.yaml`` files, never arbitrary YAML (design doc
section 7.2).
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from ecli.extensions.linters.actionlint.parser import parse_actionlint_output
from ecli.extensions.linters.core.command_runner import run_linter_command
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.core.provider_utils import (
    build_command_diagnostics_result,
    find_executable,
    missing_executable_result,
    status_result,
)


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_WORKFLOW_EXTENSIONS = frozenset({".yml", ".yaml"})
_DISPLAY_NAME = "actionlint"
_DEFAULT_TIMEOUT_SECONDS = 15.0


def _is_github_workflow_file(file_path: str | None) -> bool:
    """Return True only for files under a ``.github/workflows/`` directory."""
    if not file_path:
        return False
    path = Path(file_path)
    if path.suffix.lower() not in _WORKFLOW_EXTENSIONS:
        return False
    parts = path.parts
    return any(
        parts[index] == ".github" and parts[index + 1] == "workflows"
        for index in range(len(parts) - 1)
    )


class ActionlintDiagnosticProvider:
    """Diagnostics provider backed by ``actionlint -color=never``."""

    name = "actionlint"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "actionlint",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True only for GitHub Actions workflow YAML files."""
        return _is_github_workflow_file(request.file_path)

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run actionlint against the current workflow file."""
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

        argv = [executable, "-color=never", request.file_path]
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
            parse=lambda stdout: parse_actionlint_output(stdout, default_file=file_path),
        )
