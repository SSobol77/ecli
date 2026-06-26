"""Tests for normalized diagnostics providers and scheduler behavior."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ecli.diagnostics.models import (
    Diagnostic,
    DiagnosticRequest,
    DiagnosticResult,
    DiagnosticsSnapshot,
)
from ecli.diagnostics.ruff_provider import RuffDiagnosticProvider, parse_ruff_output
from ecli.diagnostics.service import DiagnosticsService


def request(tmp_path: Path, generation: int = 1) -> DiagnosticRequest:
    return DiagnosticRequest(
        generation=generation,
        scope="buffer",
        file_path=str(tmp_path / "sample.py"),
        text="import os\n",
        project_root=str(tmp_path),
        language="python",
    )


def test_diagnostics_sorting_is_deterministic() -> None:
    diagnostics = [
        Diagnostic("b.py", 2, 1, "warning", "B001", "b", "ruff"),
        Diagnostic("a.py", 9, 1, "hint", "H001", "h", "ruff"),
        Diagnostic("a.py", 1, 9, "error", "F821", "e2", "ruff"),
        Diagnostic("a.py", 1, 1, "error", "F401", "e1", "ruff"),
    ]

    ordered = sorted(diagnostics, key=lambda item: item.sort_key())

    assert [
        (item.severity, item.file_path, item.line, item.column) for item in ordered
    ] == [
        ("error", "a.py", 1, 1),
        ("error", "a.py", 1, 9),
        ("warning", "b.py", 2, 1),
        ("hint", "a.py", 9, 1),
    ]


def test_parse_ruff_json_output_normalizes_fix_hint_and_order() -> None:
    raw = json.dumps(
        [
            {
                "filename": "b.py",
                "location": {"row": 3, "column": 2},
                "code": "B006",
                "message": "mutable default",
            },
            {
                "filename": "a.py",
                "location": {"row": 1, "column": 5},
                "code": "F821",
                "message": "undefined name",
                "fix": {"message": "Replace with known_name"},
            },
        ]
    )

    diagnostics = parse_ruff_output(raw, default_file="fallback.py")

    assert [item.code for item in diagnostics] == ["F821", "B006"]
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].fix_hint == "Replace with known_name"
    assert diagnostics[1].severity == "warning"


def test_parse_ruff_json_preserves_syntax_null_and_invalid_codes() -> None:
    raw = json.dumps(
        [
            {
                "filename": "sample.py",
                "location": {"row": 4, "column": 1},
                "code": "invalid-syntax",
                "message": "Expected an indented block",
            },
            {
                "filename": "sample.py",
                "location": {"row": 5, "column": 1},
                "code": None,
                "message": "null code diagnostic",
            },
            {
                "filename": "sample.py",
                "location": {"row": 6, "column": 1},
                "code": {"unexpected": "shape"},
                "message": "invalid code diagnostic",
            },
        ]
    )

    diagnostics = parse_ruff_output(raw, default_file="fallback.py")

    assert len(diagnostics) == 3
    assert [item.message for item in diagnostics] == [
        "Expected an indented block",
        "null code diagnostic",
        "invalid code diagnostic",
    ]
    assert diagnostics[0].code == "invalid-syntax"
    assert diagnostics[1].code is None
    assert diagnostics[2].code == "{'unexpected': 'shape'}"


def test_parse_ruff_text_output_is_deterministic() -> None:
    diagnostics = parse_ruff_output(
        "b.py:4:2: B006 mutable default\na.py:1:5: F821 undefined name\n",
        default_file="fallback.py",
    )

    assert [
        (item.file_path, item.line, item.column, item.code) for item in diagnostics
    ] == [
        ("a.py", 1, 5, "F821"),
        ("b.py", 4, 2, "B006"),
    ]


def test_missing_ruff_produces_controlled_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ecli.diagnostics.ruff_provider.shutil.which", lambda _: None)
    provider = RuffDiagnosticProvider()

    result = provider.run(request(tmp_path))

    assert result.status == "error"
    assert result.diagnostics == ()
    assert "not found" in result.message


def test_non_python_buffer_does_not_run_ruff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr("ecli.diagnostics.ruff_provider.shutil.which", lambda _: "ruff")
    provider = RuffDiagnosticProvider(runner=lambda *args, **kwargs: calls.append(args))
    non_python = DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(tmp_path / "README.md"),
        text="# readme\n",
        project_root=str(tmp_path),
        language="markdown",
    )

    result = provider.run(non_python)

    assert result.status == "skipped"
    assert result.diagnostics == ()
    assert "only available for Python files" in result.message
    assert calls == []


def test_buffer_refresh_uses_stdin_filename_and_project_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")

    monkeypatch.setattr("ecli.diagnostics.ruff_provider.shutil.which", lambda _: "ruff")
    provider = RuffDiagnosticProvider(runner=runner)

    result = provider.run(request(tmp_path))

    assert result.status == "ready"
    assert result.message == "Diagnostics: PASS — no issues found."
    assert calls[0]["command"] == [
        "ruff",
        "check",
        "--output-format=json",
        "--stdin-filename",
        str(tmp_path / "sample.py"),
        "-",
    ]
    assert calls[0]["cwd"] == str(tmp_path)
    assert calls[0]["input"] == "import os\n"


def test_diagnostics_snapshot_result_replaces_previous_diagnostics() -> None:
    old = Diagnostic("old.py", 1, 1, "warning", "F401", "old", "ruff")
    new = Diagnostic("new.py", 2, 1, "warning", "F821", "new", "ruff")
    snapshot = DiagnosticsSnapshot(
        generation=1,
        diagnostics=(old,),
        status="ready",
        message="Diagnostics: 1 issue(s).",
    )
    result = DiagnosticResult(
        generation=2,
        diagnostics=(new,),
        status="ready",
        message="Diagnostics: 1 issue(s).",
    )

    updated = snapshot.with_result(
        result,
        running_generation=None,
        pending_generation=None,
    )

    assert updated.generation == 2
    assert updated.diagnostics == (new,)


class BlockingProvider:
    name = "blocking"
    enabled = True

    def __init__(self) -> None:
        """Initialize blocking provider state."""
        self.calls: list[int] = []
        self.release_first = threading.Event()

    def run(self, diagnostic_request: DiagnosticRequest) -> DiagnosticResult:
        self.calls.append(diagnostic_request.generation)
        if diagnostic_request.generation == 1:
            assert self.release_first.wait(3)
        return DiagnosticResult(
            generation=diagnostic_request.generation,
            diagnostics=(),
            status="ready",
            message="Diagnostics: PASS — no issues found.",
        )


def test_repeated_refresh_is_coalesced_to_latest_pending(tmp_path: Path) -> None:
    provider = BlockingProvider()
    service = DiagnosticsService()
    service.register_provider(provider)

    gen1, started1, pending1 = service.request_refresh(
        scope="buffer",
        file_path=str(tmp_path / "a.py"),
        text="",
        project_root=str(tmp_path),
        language="python",
    )
    gen2, started2, pending2 = service.request_refresh(
        scope="buffer",
        file_path=str(tmp_path / "b.py"),
        text="",
        project_root=str(tmp_path),
        language="python",
    )
    gen3, started3, pending3 = service.request_refresh(
        scope="buffer",
        file_path=str(tmp_path / "c.py"),
        text="",
        project_root=str(tmp_path),
        language="python",
    )

    assert (gen1, started1, pending1) == (1, True, None)
    assert (gen2, started2, pending2) == (2, False, 2)
    assert (gen3, started3, pending3) == (3, False, 3)

    provider.release_first.set()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and provider.calls != [1, 3]:
        time.sleep(0.01)

    assert provider.calls == [1, 3]
    assert all(result.generation != 2 for result in service.drain_results())
