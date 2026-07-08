# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/biome/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Biome diagnostics provider -- the ECLI default web (JS/TS/JSON/CSS/GraphQL)
linter. ESLint is not registered as a default provider; see
``docs/extensions/diagnostics-linter-layer.md``.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from ecli.extensions.linters.biome.parser import parse_biome_output
from ecli.extensions.linters.core.command_runner import run_linter_command
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.core.provider_utils import (
    build_command_diagnostics_result,
    find_executable,
    missing_executable_result,
    status_result,
    supports_by_language_or_extension,
)


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_LANGUAGES = frozenset(
    {
        "javascript",
        "javascriptreact",
        "typescript",
        "typescriptreact",
        "json",
        "jsonc",
        "css",
        "graphql",
        # Common Pygments-derived aliases for the same file types.
        "jsx",
        "tsx",
    }
)
_EXTENSIONS = frozenset(
    {
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".json",
        ".jsonc",
        ".css",
        ".graphql",
        ".gql",
    }
)
_DISPLAY_NAME = "Biome"
_DEFAULT_TIMEOUT_SECONDS = 20.0


class BiomeDiagnosticProvider:
    """Diagnostics provider backed by ``biome lint --reporter=json``."""

    name = "biome"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "biome",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True for JS/TS/JSON/CSS/GraphQL files by language or extension."""
        return supports_by_language_or_extension(
            request, languages=_LANGUAGES, extensions=_EXTENSIONS
        )

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run Biome against the current file."""
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

        argv = [executable, "lint", "--reporter=json", request.file_path]
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
            parse=lambda stdout: parse_biome_output(stdout, default_file=file_path),
        )
