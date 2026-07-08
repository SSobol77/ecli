# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/cargo_clippy/provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Cargo Clippy (Rust) diagnostics provider.

Clippy always lints a whole crate, never a single file. This provider
never runs blindly for an isolated ``.rs`` file: it first walks upward
from the current file (or the project root) looking for a ``Cargo.toml``
crate root, and returns a controlled skip message when none is found.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from ecli.extensions.linters.cargo_clippy.parser import parse_cargo_clippy_output
from ecli.extensions.linters.core.command_runner import run_linter_command
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.core.provider_utils import (
    build_command_diagnostics_result,
    missing_executable_result,
    status_result,
    supports_by_language_or_extension,
)


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_LANGUAGES = frozenset({"rust"})
_EXTENSIONS = frozenset({".rs"})
_DISPLAY_NAME = "Cargo Clippy"
_DEFAULT_TIMEOUT_SECONDS = 60.0

_NO_CRATE_ROOT_MESSAGE = "Cargo Clippy requires a Cargo.toml crate root."


def _find_crate_root(*, file_path: str | None, project_root: str) -> Path | None:
    """Walk upward from the current file (or project root) for Cargo.toml."""
    if file_path:
        start = Path(file_path).expanduser().parent
    else:
        start = Path(project_root or ".")
    if not start.is_absolute():
        start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "Cargo.toml").is_file():
            return candidate
    return None


class CargoClippyDiagnosticProvider:
    """Diagnostics provider backed by ``cargo clippy --message-format=json``."""

    name = "cargo-clippy"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "cargo",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True for Rust files by language or extension.

        Crate-root discovery happens in ``run``, not here, so a missing
        ``Cargo.toml`` produces the specific, actionable skip message
        rather than a generic "no provider available" result.
        """
        return supports_by_language_or_extension(
            request, languages=_LANGUAGES, extensions=_EXTENSIONS
        )

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run Cargo Clippy for the crate containing the current file."""
        executable = shutil.which(self.executable)
        if executable is None:
            return missing_executable_result(
                request,
                name=self.name,
                enabled=self.enabled,
                display_name=_DISPLAY_NAME,
            )

        crate_root = _find_crate_root(
            file_path=request.file_path, project_root=request.project_root
        )
        if crate_root is None:
            return status_result(
                request,
                name=self.name,
                enabled=self.enabled,
                status="skipped",
                message=_NO_CRATE_ROOT_MESSAGE,
            )

        argv = [executable, "clippy", "--message-format=json"]
        result = run_linter_command(
            argv,
            cwd=str(crate_root),
            timeout_seconds=self.timeout_seconds,
            max_stdout_bytes=8_000_000,
            runner=self._runner,
        )
        default_file = request.file_path or str(crate_root)
        return build_command_diagnostics_result(
            request,
            result,
            name=self.name,
            enabled=self.enabled,
            display_name=_DISPLAY_NAME,
            timeout_seconds=self.timeout_seconds,
            parse=lambda stdout: parse_cargo_clippy_output(
                stdout, default_file=default_file
            ),
        )
