"""Ruff diagnostics provider."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ecli.diagnostics.models import (
    Diagnostic,
    DiagnosticRequest,
    DiagnosticResult,
    DiagnosticSeverity,
    DiagnosticStatus,
    ProviderState,
    sort_diagnostics,
)


logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_TEXT_DIAGNOSTIC_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+):\s+"
    r"(?P<code>[A-Z]+[0-9]+[A-Z0-9]*)\s+(?P<message>.+)$"
)
_PYTHON_SUFFIXES = frozenset({".py", ".pyi"})
_ERROR_CODES = frozenset({"E999", "F821", "F822", "F823", "F831", "F901"})


class RuffDiagnosticProvider:
    """Diagnostics provider backed by ``ruff check``."""

    name = "ruff"

    def __init__(
        self,
        *,
        enabled: bool = True,
        executable: str = "ruff",
        timeout_seconds: float = 15.0,
        runner: Runner = subprocess.run,
    ) -> None:
        """Initialize the provider with explicit subprocess dependencies."""
        self.enabled = enabled
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run Ruff for a buffer or workspace request."""
        if request.scope == "buffer":
            return self._run_buffer(request)
        return self._run_workspace(request)

    def _run_buffer(self, request: DiagnosticRequest) -> DiagnosticResult:
        if not _is_python_file(request.file_path, request.language):
            return self._status_result(
                request,
                status="skipped",
                message="Ruff diagnostics are only available for Python files.",
            )
        if request.file_path is None:
            return self._status_result(
                request,
                status="skipped",
                message="Ruff diagnostics require a saved Python file.",
            )
        executable = shutil.which(self.executable)
        if executable is None:
            return self._missing_ruff(request)

        command = [
            executable,
            "check",
            "--output-format=json",
            "--stdin-filename",
            request.file_path,
            "-",
        ]
        text = request.text if request.text is not None else ""
        return self._run_command(request, command, input_text=text)

    def _run_workspace(self, request: DiagnosticRequest) -> DiagnosticResult:
        executable = shutil.which(self.executable)
        if executable is None:
            return self._missing_ruff(request)
        command = [executable, "check", "--output-format=json", "."]
        return self._run_command(request, command, input_text=None)

    def _run_command(
        self,
        request: DiagnosticRequest,
        command: Sequence[str],
        *,
        input_text: str | None,
    ) -> DiagnosticResult:
        cwd = request.project_root or "."
        try:
            completed = self._runner(
                list(command),
                input=input_text,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._status_result(
                request,
                status="error",
                message=f"Ruff timed out after {self.timeout_seconds:.1f}s.",
            )
        except OSError as exc:
            logger.warning("Ruff execution failed: %s", exc)
            return self._status_result(
                request,
                status="error",
                message=f"Ruff execution failed: {exc}",
            )

        diagnostics = parse_ruff_output(
            completed.stdout,
            fallback_text=completed.stderr,
            default_file=request.file_path or request.project_root,
        )
        if diagnostics:
            return DiagnosticResult(
                generation=request.generation,
                diagnostics=diagnostics,
                status="ready" if completed.returncode in (0, 1) else "error",
                message=f"Ruff: {len(diagnostics)} diagnostic(s).",
                provider_states=(ProviderState(name=self.name, enabled=self.enabled),),
            )

        if completed.returncode in (0, 1):
            return DiagnosticResult(
                generation=request.generation,
                diagnostics=(),
                status="ready",
                message="Diagnostics: PASS — no issues found.",
                provider_states=(ProviderState(name=self.name, enabled=self.enabled),),
            )

        message = _first_non_empty_line(completed.stderr) or "Ruff failed."
        return self._status_result(
            request,
            status="error",
            message=message,
        )

    def _missing_ruff(self, request: DiagnosticRequest) -> DiagnosticResult:
        return self._status_result(
            request,
            status="error",
            message="Ruff executable not found in PATH.",
        )

    def _status_result(
        self,
        request: DiagnosticRequest,
        *,
        status: DiagnosticStatus,
        message: str,
    ) -> DiagnosticResult:
        return DiagnosticResult(
            generation=request.generation,
            diagnostics=(),
            status=status,
            message=message,
            provider_states=(ProviderState(name=self.name, enabled=self.enabled),),
        )


def parse_ruff_output(
    stdout: str,
    *,
    fallback_text: str = "",
    default_file: str = "",
) -> tuple[Diagnostic, ...]:
    """Parse Ruff JSON output, with deterministic text-output fallback."""
    stripped = stdout.strip()
    if stripped:
        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError:
            logger.debug("Ruff JSON parse failed; falling back to text parser.")
        else:
            if isinstance(raw, list):
                return _parse_json_items(raw, default_file=default_file)

    return _parse_text_output(
        "\n".join(part for part in (stdout, fallback_text) if part),
        default_file=default_file,
    )


def _parse_json_items(raw: list[Any], *, default_file: str) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("Dropping malformed Ruff diagnostic item: %r", item)
            continue
        try:
            code = _optional_code(item.get("code"))
            location = item.get("location")
            if not isinstance(location, dict):
                location = {}
            file_path = str(item.get("filename") or default_file)
            fix_hint = _fix_hint(item.get("fix"))
            suggested_code = _suggested_code(item.get("fix"))
            diagnostics.append(
                Diagnostic(
                    file_path=file_path,
                    line=_positive_int(location.get("row")),
                    column=_positive_int(location.get("column")),
                    severity=_severity_for_code(code),
                    code=code,
                    message=str(item.get("message") or "Ruff diagnostic"),
                    source="ruff",
                    fix_hint=fix_hint,
                    suggested_code=suggested_code,
                )
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Dropping malformed Ruff diagnostic: %s", exc)
    return sort_diagnostics(diagnostics)


def _parse_text_output(text: str, *, default_file: str) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for line in text.splitlines():
        match = _TEXT_DIAGNOSTIC_RE.match(line.strip())
        if not match:
            continue
        code = match.group("code")
        diagnostics.append(
            Diagnostic(
                file_path=match.group("file") or default_file,
                line=int(match.group("line")),
                column=int(match.group("column")),
                severity=_severity_for_code(code),
                code=code,
                message=match.group("message").strip(),
                source="ruff",
            )
        )
    return sort_diagnostics(diagnostics)


def _is_python_file(file_path: str | None, language: str | None) -> bool:
    if language == "python":
        return True
    if file_path is None:
        return False
    return Path(file_path).suffix.lower() in _PYTHON_SUFFIXES


def _severity_for_code(code: str | None) -> DiagnosticSeverity:
    if code and (code in _ERROR_CODES or code.startswith("E9")):
        return "error"
    return "warning"


def _optional_code(raw_code: Any) -> str | None:
    if raw_code is None:
        return None
    if isinstance(raw_code, str):
        stripped = raw_code.strip()
        return stripped or None
    text = str(raw_code).strip()
    return text or None


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def _fix_hint(raw_fix: Any) -> str | None:
    if not isinstance(raw_fix, dict):
        return None
    message = raw_fix.get("message")
    if isinstance(message, str) and message:
        return message
    return "Fix available"


def _suggested_code(raw_fix: Any) -> str | None:
    if not isinstance(raw_fix, dict):
        return None
    edits = raw_fix.get("edits")
    if not isinstance(edits, list):
        return None
    snippets: list[str] = []
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        content = edit.get("content")
        if isinstance(content, str) and content:
            snippets.append(content)
    if not snippets:
        return None
    return "\n".join(snippets)


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
