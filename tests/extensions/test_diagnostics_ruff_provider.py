# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_ruff_provider.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the Ruff diagnostics provider (#104).

These cover the deterministic, offline behavior with an injected command runner
(fixed argv, JSON parsing, no-diagnostics, invalid JSON, timeout, missing
executable) and one real end-to-end run against the installed Ruff binary.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration.diagnostics import (
    CommandResult,
    DiagnosticSeverity,
    RuffDiagnosticsProvider,
)


class RecordingRunner:
    def __init__(self, result: CommandResult) -> None:
        """Record argv/text/timeout and return a fixed result."""
        self.result = result
        self.argv: list[str] = []
        self.text: str = ""
        self.timeout: float = 0.0

    def __call__(self, argv: Sequence[str], text: str, timeout: float) -> CommandResult:
        self.argv = list(argv)
        self.text = text
        self.timeout = timeout
        return self.result


def _runner(result: CommandResult) -> RecordingRunner:
    return RecordingRunner(result)


# --------------------------------------------------------------------------- #
# Applicability and availability.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("path", "applies"),
    [("a.py", True), ("a.pyi", True), ("A.PY", True), ("a.js", False), ("", False)],
)
def test_applies_to_python_files_only(path: str, applies: bool) -> None:
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(0, "[]")))
    assert provider.applies_to(path) is applies


def test_is_available_false_for_missing_executable() -> None:
    provider = RuffDiagnosticsProvider(executable="ruff-does-not-exist-xyz")
    assert provider.is_available() is False


# --------------------------------------------------------------------------- #
# Fixed argv (no shell, no configured command strings).
# --------------------------------------------------------------------------- #


def test_build_argv_is_fixed_and_uses_stdin_filename() -> None:
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(0, "[]")))
    assert provider.build_argv("pkg/mod.py") == [
        "ruff",
        "check",
        "--output-format=json",
        "--no-cache",
        "--stdin-filename",
        "pkg/mod.py",
        "-",
    ]


def test_collect_invokes_runner_with_fixed_argv_and_buffer_text() -> None:
    runner = _runner(CommandResult(0, "[]"))
    provider = RuffDiagnosticsProvider(runner=runner)
    provider.collect("a.py", "import os\n", timeout=3.0)
    assert runner.argv == provider.build_argv("a.py")
    assert runner.text == "import os\n"
    assert runner.timeout == 3.0


# --------------------------------------------------------------------------- #
# JSON parsing.
# --------------------------------------------------------------------------- #


def test_parses_ruff_json_into_diagnostics() -> None:
    payload = json.dumps(
        [
            {
                "code": "F401",
                "message": "`os` imported but unused",
                "filename": "a.py",
                "location": {"row": 1, "column": 8},
            },
            {
                "code": "E999",
                "message": "SyntaxError: bad",
                "filename": "a.py",
                "location": {"row": 3, "column": 1},
            },
        ]
    )
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(1, payload)))
    result = provider.collect("a.py", "import os\n")

    assert result.available is True
    assert result.ok is True
    assert len(result.diagnostics) == 2
    first, second = result.diagnostics
    assert first.code == "F401"
    assert first.column == 8
    assert first.severity is DiagnosticSeverity.WARNING
    assert second.code == "E999"
    assert second.severity is DiagnosticSeverity.ERROR


def test_no_diagnostics_empty_array() -> None:
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(0, "[]")))
    result = provider.collect("a.py", "x = 1\n")
    assert result.ok is True
    assert result.available is True
    assert result.diagnostics == ()


def test_no_diagnostics_empty_stdout() -> None:
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(0, "")))
    result = provider.collect("a.py", "x = 1\n")
    assert result.ok is True
    assert result.diagnostics == ()


def test_invalid_json_is_reported_as_failure() -> None:
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(1, "not json{")))
    result = provider.collect("a.py", "x = 1\n")
    assert result.available is True
    assert result.ok is False
    assert result.detail is not None
    assert "unparseable" in result.detail


def test_internal_error_returncode_is_reported() -> None:
    provider = RuffDiagnosticsProvider(
        runner=_runner(CommandResult(2, "", "panic: boom"))
    )
    result = provider.collect("a.py", "x = 1\n")
    assert result.ok is False
    assert result.detail is not None
    assert "boom" in result.detail


# --------------------------------------------------------------------------- #
# Failure modes: timeout, missing executable.
# --------------------------------------------------------------------------- #


def test_timeout_is_reported_without_raising() -> None:
    def runner(argv: Sequence[str], text: str, timeout: float) -> CommandResult:
        raise subprocess.TimeoutExpired(cmd=list(argv), timeout=timeout)

    provider = RuffDiagnosticsProvider(runner=runner)
    result = provider.collect("a.py", "x = 1\n", timeout=2.0)
    assert result.available is True
    assert result.ok is False
    assert result.detail is not None
    assert "timed out" in result.detail


def test_missing_executable_is_reported_without_raising() -> None:
    def runner(argv: Sequence[str], text: str, timeout: float) -> CommandResult:
        raise FileNotFoundError(2, "No such file", "ruff")

    provider = RuffDiagnosticsProvider(runner=runner)
    result = provider.collect("a.py", "x = 1\n")
    assert result.available is False
    assert result.ok is False


def test_os_error_is_reported_without_raising() -> None:
    def runner(argv: Sequence[str], text: str, timeout: float) -> CommandResult:
        raise OSError("denied")

    provider = RuffDiagnosticsProvider(runner=runner)
    result = provider.collect("a.py", "x = 1\n")
    assert result.ok is False


def test_malformed_diagnostic_items_are_skipped() -> None:
    payload = json.dumps([{"code": "F401", "message": "m", "location": {"row": 1}}, 5])
    provider = RuffDiagnosticsProvider(runner=_runner(CommandResult(1, payload)))
    result = provider.collect("a.py", "import os\n")
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].column is None


# --------------------------------------------------------------------------- #
# Real Ruff end-to-end (parses actual Ruff JSON output).
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_real_ruff_reports_unused_import(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("import os\n", encoding="utf-8")

    provider = RuffDiagnosticsProvider()
    result = provider.collect(str(target), "import os\n", timeout=10.0)

    assert result.available is True
    assert result.ok is True
    codes = {diag.code for diag in result.diagnostics}
    assert "F401" in codes
