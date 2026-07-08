# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/hadolint/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Hadolint (Dockerfile) diagnostics provider."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from ecli.extensions.linters.core.command_runner import run_linter_command
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.core.provider_utils import (
    build_command_diagnostics_result,
    find_executable,
    has_basename,
    missing_executable_result,
    status_result,
    supports_by_language_or_extension,
)
from ecli.extensions.linters.hadolint.parser import parse_hadolint_output


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_LANGUAGES = frozenset({"dockerfile", "docker"})
_EXTENSIONS = frozenset({".dockerfile"})
_BASENAMES = frozenset({"Dockerfile"})
_DISPLAY_NAME = "Hadolint"
_DEFAULT_TIMEOUT_SECONDS = 15.0


class HadolintDiagnosticProvider:
    """Diagnostics provider backed by ``hadolint --format json``."""

    name = "hadolint"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "hadolint",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True for Dockerfiles by language, extension, or basename."""
        if has_basename(request.file_path, _BASENAMES):
            return True
        return supports_by_language_or_extension(
            request, languages=_LANGUAGES, extensions=_EXTENSIONS
        )

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run Hadolint against the current file."""
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

        argv = [executable, "--format", "json", request.file_path]
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
            parse=lambda stdout: parse_hadolint_output(stdout, default_file=file_path),
        )
