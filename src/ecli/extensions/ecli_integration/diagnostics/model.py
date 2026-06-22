# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/model.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Deterministic, data-only diagnostics model for the F4 Diagnostics panel (#104).

This module defines the immutable types that flow from a diagnostics provider
(see :mod:`.providers`) through the store/service to the TUI panel. Everything
here is pure data: there is no curses code, no external process execution, and
no network access, so it is fully testable without a terminal.

The model intentionally mirrors the shape of an LSP/Ruff diagnostic but stays
provider-neutral:

* :class:`DiagnosticSeverity` is an :class:`enum.IntEnum` ordered from most to
  least severe so a plain sort surfaces errors first.
* :class:`Diagnostic` carries the user-facing fields required by #104: file
  path, line, optional column, severity, source/provider, message and an
  optional rule code.
* :class:`DiagnosticsState` is the single object the panel renders. It captures
  both the success case and every explicit empty state (disabled, no active
  file, unavailable provider, clean file).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum


__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "DiagnosticsState",
    "DiagnosticsStatus",
    "sort_diagnostics",
]


class DiagnosticSeverity(IntEnum):
    """Severity of a single diagnostic, ordered most-severe-first.

    The integer values double as the primary sort rank, so ``ERROR`` (0) sorts
    before ``WARNING`` (1) before ``INFO`` (2) before ``HINT`` (3).
    """

    ERROR = 0
    WARNING = 1
    INFO = 2
    HINT = 3

    @property
    def label(self) -> str:
        """Return a short, fixed-width, human-readable severity label."""
        return _SEVERITY_LABELS[self]

    @classmethod
    def normalize(cls, value: object) -> DiagnosticSeverity:
        """Coerce a provider-supplied severity into a :class:`DiagnosticSeverity`.

        Accepts existing members, the LSP integer scale (1=error … 4=hint),
        Ruff/pycodestyle code letters (``E``/``W``/``F``…) and common severity
        words. Anything unrecognised degrades to :data:`WARNING`, never raising,
        so a malformed provider record can still be displayed.
        """
        if isinstance(value, DiagnosticSeverity):
            return value
        if isinstance(value, bool):  # guard: bool is an int subclass
            return cls.WARNING
        if isinstance(value, int):
            return _LSP_SEVERITY.get(value, cls.WARNING)
        if isinstance(value, str):
            token = value.strip().lower()
            if token in _STRING_SEVERITY:
                return _STRING_SEVERITY[token]
            if token[:1] in _LETTER_SEVERITY:
                return _LETTER_SEVERITY[token[:1]]
        return cls.WARNING


_SEVERITY_LABELS: dict[DiagnosticSeverity, str] = {
    DiagnosticSeverity.ERROR: "ERROR",
    DiagnosticSeverity.WARNING: "WARN",
    DiagnosticSeverity.INFO: "INFO",
    DiagnosticSeverity.HINT: "HINT",
}

# LSP DiagnosticSeverity scale: 1=Error, 2=Warning, 3=Information, 4=Hint.
_LSP_SEVERITY: dict[int, DiagnosticSeverity] = {
    1: DiagnosticSeverity.ERROR,
    2: DiagnosticSeverity.WARNING,
    3: DiagnosticSeverity.INFO,
    4: DiagnosticSeverity.HINT,
}

_STRING_SEVERITY: dict[str, DiagnosticSeverity] = {
    "error": DiagnosticSeverity.ERROR,
    "err": DiagnosticSeverity.ERROR,
    "fatal": DiagnosticSeverity.ERROR,
    "warning": DiagnosticSeverity.WARNING,
    "warn": DiagnosticSeverity.WARNING,
    "info": DiagnosticSeverity.INFO,
    "information": DiagnosticSeverity.INFO,
    "note": DiagnosticSeverity.INFO,
    "convention": DiagnosticSeverity.INFO,
    "refactor": DiagnosticSeverity.HINT,
    "hint": DiagnosticSeverity.HINT,
}

# Ruff/pycodestyle/pyflakes code letters used when no explicit severity exists.
_LETTER_SEVERITY: dict[str, DiagnosticSeverity] = {
    "e": DiagnosticSeverity.WARNING,  # pycodestyle errors are style warnings here
    "w": DiagnosticSeverity.WARNING,
    "f": DiagnosticSeverity.WARNING,  # pyflakes
    "c": DiagnosticSeverity.INFO,  # conventions/complexity
    "n": DiagnosticSeverity.INFO,  # naming
    "i": DiagnosticSeverity.INFO,
}


class DiagnosticsStatus(StrEnum):
    """Outcome of a diagnostics collection, including every explicit empty state."""

    OK = "ok"  # provider ran and returned at least one diagnostic
    NO_DIAGNOSTICS = "no_diagnostics"  # provider ran and the file is clean
    NO_ACTIVE_FILE = "no_active_file"  # nothing to lint (no current file)
    OUTSIDE_WORKSPACE = "outside_workspace"  # current file is outside the workspace
    UNREADABLE = "unreadable"  # path is invalid / cannot be read
    UNSUPPORTED = "unsupported"  # no diagnostics provider for this file type
    PLANNED = "planned"  # a provider is planned but not bundled in this build
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # provider tool (e.g. ruff) missing
    DISABLED = "disabled"  # [linter].enabled = false, or file excluded
    COLLECTING = "collecting"  # background collection in flight
    ERROR = "error"  # provider failed (timeout, bad output, crash)


@dataclass(frozen=True)
class Diagnostic:
    """One immutable diagnostic record rendered by the F4 panel."""

    file_path: str
    line: int
    severity: DiagnosticSeverity
    source: str
    message: str
    column: int | None = None
    code: str | None = None
    end_line: int | None = None
    end_column: int | None = None
    docs_url: str | None = None
    # Inactive future metadata only: #104 is read-only and never applies fixes.
    correctable: bool = False

    @property
    def sort_key(self) -> tuple[int, str, int, int, str]:
        """Deterministic sort key: severity, file, line, column, message."""
        return (
            int(self.severity),
            self.file_path,
            self.line,
            self.column if self.column is not None else -1,
            self.message,
        )

    @property
    def location(self) -> str:
        """Return a compact ``path:line:col`` (or ``path:line``) location string."""
        if self.column is not None:
            return f"{self.file_path}:{self.line}:{self.column}"
        return f"{self.file_path}:{self.line}"


def sort_diagnostics(diagnostics: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    """Return *diagnostics* sorted by the deterministic #104 ordering."""
    return tuple(sorted(diagnostics, key=lambda diag: diag.sort_key))


@dataclass(frozen=True)
class DiagnosticsState:
    """Immutable result the panel renders: diagnostics plus an explicit status.

    ``detail`` is a short, already-redacted, user-facing note (never a raw
    traceback). It explains empty/error states (e.g. why a provider is
    unavailable) and is bounded by the producing layer. ``hint`` is an optional
    second, actionable line (e.g. which providers are available).
    """

    status: DiagnosticsStatus
    provider: str = ""
    file_path: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    detail: str | None = None
    hint: str | None = None
    #: True when the analysed file resolves outside the ECLI workspace and was
    #: linted anyway by a safe current-file (stdin) provider. The panel surfaces
    #: this as an "external file" note; path safety for project/workspace
    #: providers is never weakened by it.
    external: bool = False

    @property
    def total(self) -> int:
        """Total number of diagnostics."""
        return len(self.diagnostics)

    @property
    def error_count(self) -> int:
        """Number of error-severity diagnostics."""
        return self._count(DiagnosticSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Number of warning-severity diagnostics."""
        return self._count(DiagnosticSeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Number of info-severity diagnostics."""
        return self._count(DiagnosticSeverity.INFO)

    @property
    def hint_count(self) -> int:
        """Number of hint-severity diagnostics."""
        return self._count(DiagnosticSeverity.HINT)

    def _count(self, severity: DiagnosticSeverity) -> int:
        return sum(1 for diag in self.diagnostics if diag.severity is severity)

    @property
    def has_diagnostics(self) -> bool:
        """Return ``True`` when at least one diagnostic is present."""
        return bool(self.diagnostics)

    # -- Factories for the explicit states --------------------------------- #

    @classmethod
    def disabled(cls, detail: str | None = None) -> DiagnosticsState:
        """Diagnostics are turned off (config) or the file is excluded."""
        return cls(status=DiagnosticsStatus.DISABLED, detail=detail)

    @classmethod
    def no_active_file(cls, detail: str | None = None) -> DiagnosticsState:
        """There is no current file to analyse."""
        return cls(status=DiagnosticsStatus.NO_ACTIVE_FILE, detail=detail)

    @classmethod
    def outside_workspace(
        cls, file_path: str | None = None, detail: str | None = None
    ) -> DiagnosticsState:
        """The current file resolves outside the ECLI workspace; not linted."""
        return cls(
            status=DiagnosticsStatus.OUTSIDE_WORKSPACE,
            file_path=file_path,
            detail=detail,
        )

    @classmethod
    def unreadable(
        cls, file_path: str | None = None, detail: str | None = None
    ) -> DiagnosticsState:
        """The current file path is invalid or cannot be read."""
        return cls(
            status=DiagnosticsStatus.UNREADABLE,
            file_path=file_path,
            detail=detail,
        )

    @classmethod
    def unsupported(
        cls,
        file_path: str | None = None,
        detail: str | None = None,
        hint: str | None = None,
    ) -> DiagnosticsState:
        """No diagnostics provider handles this file type (not an error)."""
        return cls(
            status=DiagnosticsStatus.UNSUPPORTED,
            file_path=file_path,
            detail=detail,
            hint=hint,
        )

    @classmethod
    def planned(
        cls,
        file_path: str | None = None,
        detail: str | None = None,
        hint: str | None = None,
    ) -> DiagnosticsState:
        """A provider is planned for this file type but not bundled in this build."""
        return cls(
            status=DiagnosticsStatus.PLANNED,
            file_path=file_path,
            detail=detail,
            hint=hint,
        )

    @classmethod
    def provider_unavailable(
        cls,
        provider: str = "",
        detail: str | None = None,
        file_path: str | None = None,
        hint: str | None = None,
    ) -> DiagnosticsState:
        """A provider applies but its tool is missing (e.g. Ruff not installed)."""
        return cls(
            status=DiagnosticsStatus.PROVIDER_UNAVAILABLE,
            provider=provider,
            file_path=file_path,
            detail=detail,
            hint=hint,
        )

    @classmethod
    def error(
        cls, provider: str, detail: str, file_path: str | None = None
    ) -> DiagnosticsState:
        """The provider was invoked but failed (timeout, bad output, crash)."""
        return cls(
            status=DiagnosticsStatus.ERROR,
            provider=provider,
            file_path=file_path,
            detail=detail,
        )

    @classmethod
    def collecting(
        cls, provider: str = "", file_path: str | None = None
    ) -> DiagnosticsState:
        """A background collection is in flight; the panel shows a placeholder."""
        return cls(
            status=DiagnosticsStatus.COLLECTING,
            provider=provider,
            file_path=file_path,
        )

    @classmethod
    def from_diagnostics(
        cls,
        provider: str,
        file_path: str | None,
        diagnostics: Sequence[Diagnostic],
        detail: str | None = None,
        external: bool = False,
    ) -> DiagnosticsState:
        """Build an ``OK``/``NO_DIAGNOSTICS`` state from collected diagnostics."""
        ordered = sort_diagnostics(diagnostics)
        status = DiagnosticsStatus.OK if ordered else DiagnosticsStatus.NO_DIAGNOSTICS
        return cls(
            status=status,
            provider=provider,
            file_path=file_path,
            diagnostics=ordered,
            detail=detail,
            external=external,
        )
