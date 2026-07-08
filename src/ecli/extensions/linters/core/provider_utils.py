# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/provider_utils.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Shared, linter-agnostic provider helpers.

Small building blocks reused by every F4 linter microservice provider:
language/path applicability matching, common ``DiagnosticResult``
constructors, and the canonical missing-executable/timeout/error messages.
This module must never grow into a dispatcher -- it has no knowledge of
which linter is calling it and never executes anything itself (see
``command_runner.py`` for that).
"""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Callable
from pathlib import Path

from ecli.extensions.linters.core.command_runner import CommandResult
from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticRequest,
    DiagnosticResult,
    DiagnosticStatus,
    ProviderState,
)


def has_extension(file_path: str | None, extensions: frozenset[str]) -> bool:
    """Return True if ``file_path``'s lowercased suffix is in ``extensions``."""
    if not file_path:
        return False
    return Path(file_path).suffix.lower() in extensions


def has_basename(file_path: str | None, basenames: frozenset[str]) -> bool:
    """Return True if ``file_path``'s exact basename is in ``basenames``."""
    if not file_path:
        return False
    return Path(file_path).name in basenames


def matches_language(language: str | None, languages: frozenset[str]) -> bool:
    """Return True if ``language`` (case-insensitive) is a member of ``languages``."""
    if not language:
        return False
    return language.lower() in languages


def supports_by_language_or_extension(
    request: DiagnosticRequest,
    *,
    languages: frozenset[str],
    extensions: frozenset[str],
    basenames: frozenset[str] = frozenset(),
) -> bool:
    """Standard applicability check shared by most single-file providers.

    File extension/basename is authoritative (deterministic regardless of
    how ``request.language`` was derived); ``language`` is an additional,
    non-exclusive signal so callers that set it directly (tests, or a
    future non-Pygments detector) still match.
    """
    if has_extension(request.file_path, extensions):
        return True
    if basenames and has_basename(request.file_path, basenames):
        return True
    return matches_language(request.language, languages)


def find_executable(executable: str) -> str | None:
    """Resolve ``executable`` on ``$PATH``, or None if it is not installed."""
    return shutil.which(executable)


def status_result(  # noqa: PLR0913
    request: DiagnosticRequest,
    *,
    name: str,
    enabled: bool,
    status: DiagnosticStatus,
    message: str,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> DiagnosticResult:
    """Build a ``DiagnosticResult`` carrying this provider's own state only."""
    return DiagnosticResult(
        generation=request.generation,
        diagnostics=diagnostics,
        status=status,
        message=message,
        provider_states=(ProviderState(name=name, enabled=enabled),),
    )


def missing_executable_result(
    request: DiagnosticRequest,
    *,
    name: str,
    enabled: bool,
    display_name: str,
) -> DiagnosticResult:
    """Controlled result for a missing tool: an installation defect, not normal UX.

    See ``docs/architecture/ecli-f4-linter-microservices-design.md`` section
    17.1: a missing executable in a full installation is an installation
    defect, not something the user is expected to fix as routine workflow.
    It is a controlled ``skipped`` outcome, not a provider/runtime error --
    the provider exists and applies to this file, but the underlying tool
    is absent. Reserve ``status="error"`` for actual crashes, timeouts, and
    execution failures. The message is kept short so it fits the F4 panel's
    one-line summary without truncation; detailed install guidance belongs
    in a details action or System Doctor, not here.
    """
    message = f"{display_name} unavailable: ECLI Full installation is incomplete."
    return status_result(
        request, name=name, enabled=enabled, status="skipped", message=message
    )


def timeout_result(
    request: DiagnosticRequest,
    *,
    name: str,
    enabled: bool,
    display_name: str,
    timeout_seconds: float,
) -> DiagnosticResult:
    """Controlled result for a tool that exceeded its bounded timeout."""
    message = f"{display_name} timed out after {timeout_seconds:.1f}s."
    return status_result(
        request, name=name, enabled=enabled, status="error", message=message
    )


def execution_error_result(
    request: DiagnosticRequest,
    *,
    name: str,
    enabled: bool,
    display_name: str,
    error: str,
) -> DiagnosticResult:
    """Controlled result for an OS-level failure launching the tool."""
    message = f"{display_name} execution failed: {error}"
    return status_result(
        request, name=name, enabled=enabled, status="error", message=message
    )


def pass_result(
    request: DiagnosticRequest, *, name: str, enabled: bool
) -> DiagnosticResult:
    """Controlled PASS result: the existing F4 PASS message, unchanged."""
    return status_result(
        request,
        name=name,
        enabled=enabled,
        status="ready",
        message="Diagnostics: PASS — no issues found.",
    )


def diagnostics_result(
    request: DiagnosticRequest,
    *,
    name: str,
    enabled: bool,
    diagnostics: tuple[Diagnostic, ...],
    display_name: str,
) -> DiagnosticResult:
    """Controlled result carrying one or more parsed diagnostics."""
    return DiagnosticResult(
        generation=request.generation,
        diagnostics=diagnostics,
        status="ready",
        message=f"{display_name}: {len(diagnostics)} diagnostic(s).",
        provider_states=(ProviderState(name=name, enabled=enabled),),
    )


def first_non_empty_line(text: str) -> str | None:
    """Return the first non-blank line of ``text``, or None."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _resolve_existing_diagnostic_path(
    candidate: Path, request_file_path: Path, cwd: Path | None
) -> Path | None:
    """Return an existing (or known-equal) path for ``candidate``, if any."""
    if candidate.is_absolute():
        if candidate == request_file_path or candidate.exists():
            return candidate
        return None
    if cwd is not None and (cwd / candidate).exists():
        return cwd / candidate
    via_parent = request_file_path.parent / candidate
    if via_parent.exists():
        return via_parent
    return None


def normalize_diagnostic_file_path(
    reported_path: str | Path | None,
    request_file_path: Path,
    cwd: Path | None,
) -> Path:
    """Resolve a linter-reported file path to a stable, jumpable path.

    Linter output commonly reports the target file as a bare basename or a
    path relative to the tool's own working directory (which does not
    always match ``cwd``), instead of echoing back the exact path ECLI
    invoked it with. ``Ecli.goto_diagnostic`` resolves a relative
    ``Diagnostic.file_path`` against the *editor process's* cwd, not the
    file's own directory, so an unresolved relative/basename value from
    the tool silently breaks Enter-jump ("file not available: <name>")
    even though the diagnostic is for the file currently open in ECLI.

    Never returns a bare, unresolved basename for a diagnostic that
    belongs to the current request file.
    """
    if not reported_path:
        return request_file_path

    candidate = Path(reported_path)
    resolved = _resolve_existing_diagnostic_path(candidate, request_file_path, cwd)
    if resolved is not None:
        return resolved

    if candidate.name == request_file_path.name:
        return request_file_path

    # Doesn't exist anywhere we tried and isn't the current request file
    # either (a different file, e.g. a workspace-scope diagnostic): still
    # never hand back a bare basename.
    if candidate.is_absolute():
        return candidate
    if cwd is not None:
        return cwd / candidate
    return request_file_path.parent / candidate


def _normalize_diagnostics_file_paths(
    request: DiagnosticRequest, diagnostics: tuple[Diagnostic, ...]
) -> tuple[Diagnostic, ...]:
    """Apply :func:`normalize_diagnostic_file_path` to every diagnostic.

    No-op for workspace-scope requests (no single current file to resolve
    relative paths against) and for diagnostics that already carry the
    exact request file path.
    """
    if not diagnostics or not request.file_path:
        return diagnostics
    request_file_path = Path(request.file_path)
    cwd = Path(request.project_root) if request.project_root else None
    normalized: list[Diagnostic] = []
    for diagnostic in diagnostics:
        resolved = str(
            normalize_diagnostic_file_path(diagnostic.file_path, request_file_path, cwd)
        )
        if resolved == diagnostic.file_path:
            normalized.append(diagnostic)
        else:
            normalized.append(dataclasses.replace(diagnostic, file_path=resolved))
    return tuple(normalized)


def build_command_diagnostics_result(  # noqa: PLR0913
    request: DiagnosticRequest,
    result: CommandResult,
    *,
    name: str,
    enabled: bool,
    display_name: str,
    timeout_seconds: float,
    parse: Callable[[str], tuple[Diagnostic, ...]],
    parse_input: str | None = None,
) -> DiagnosticResult:
    """Classify one ``CommandResult`` into a ``DiagnosticResult``.

    Centralizes the timeout / execution-error / diagnostics / PASS / error
    decision tree shared by every single-command provider, so each
    provider's own ``run()`` only needs its own pre-flight applicability
    checks (missing executable, crate root, config file, ...) before
    delegating here. Also centralizes diagnostic file-path normalization
    (see :func:`normalize_diagnostic_file_path`) so every provider's
    parser can report whatever path shape its underlying tool emits
    without individually guarding against unresolved relative paths.
    """
    if result.timed_out:
        return timeout_result(
            request,
            name=name,
            enabled=enabled,
            display_name=display_name,
            timeout_seconds=timeout_seconds,
        )
    if result.execution_error:
        return execution_error_result(
            request,
            name=name,
            enabled=enabled,
            display_name=display_name,
            error=result.execution_error,
        )

    diagnostics = parse(result.stdout if parse_input is None else parse_input)
    diagnostics = _normalize_diagnostics_file_paths(request, diagnostics)
    if diagnostics:
        return diagnostics_result(
            request,
            name=name,
            enabled=enabled,
            diagnostics=diagnostics,
            display_name=display_name,
        )
    if result.returncode == 0:
        return pass_result(request, name=name, enabled=enabled)

    message = first_non_empty_line(result.stderr) or f"{display_name} failed."
    return status_result(
        request, name=name, enabled=enabled, status="error", message=message
    )
