"""Data contracts for normalized editor diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DiagnosticSeverity = Literal["error", "warning", "info", "hint"]
DiagnosticScope = Literal["buffer", "workspace"]
DiagnosticStatus = Literal["idle", "running", "ready", "skipped", "error"]

_SEVERITY_ORDER: dict[DiagnosticSeverity, int] = {
    "error": 0,
    "warning": 1,
    "info": 2,
    "hint": 3,
}


@dataclass(frozen=True, order=True)
class Diagnostic:
    """One normalized diagnostic item shown by ECLI."""

    file_path: str
    line: int
    column: int
    severity: DiagnosticSeverity
    code: str | None
    message: str
    source: str
    fix_hint: str | None = None
    suggested_code: str | None = None

    def sort_key(self) -> tuple[int, str, int, int, str, str, str]:
        """Return the deterministic ordering key for diagnostics."""
        return (
            _SEVERITY_ORDER[self.severity],
            self.file_path,
            self.line,
            self.column,
            self.source,
            self.code or "",
            self.message,
        )


@dataclass(frozen=True)
class ProviderState:
    """Visible enabled/disabled state for a diagnostics provider."""

    name: str
    enabled: bool


@dataclass(frozen=True)
class DiagnosticRequest:
    """Immutable request handed to diagnostics providers."""

    generation: int
    scope: DiagnosticScope
    file_path: str | None
    text: str | None
    project_root: str
    language: str | None = None


@dataclass(frozen=True)
class DiagnosticResult:
    """Diagnostics result produced by a background worker."""

    generation: int
    diagnostics: tuple[Diagnostic, ...]
    status: DiagnosticStatus
    message: str
    provider_states: tuple[ProviderState, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DiagnosticsSnapshot:
    """UI-side snapshot of the last accepted diagnostics state."""

    generation: int = 0
    diagnostics: tuple[Diagnostic, ...] = ()
    status: DiagnosticStatus = "idle"
    message: str = "Diagnostics not run yet."
    provider_states: tuple[ProviderState, ...] = ()
    running_generation: int | None = None
    pending_generation: int | None = None

    def with_refresh_state(
        self,
        *,
        generation: int,
        pending_generation: int | None,
        provider_states: tuple[ProviderState, ...],
        message: str,
    ) -> DiagnosticsSnapshot:
        """Return a snapshot representing an active or pending refresh."""
        return DiagnosticsSnapshot(
            generation=self.generation,
            diagnostics=(),
            status="running",
            message=message,
            provider_states=provider_states,
            running_generation=generation,
            pending_generation=pending_generation,
        )

    def with_result(
        self,
        result: DiagnosticResult,
        *,
        running_generation: int | None,
        pending_generation: int | None,
    ) -> DiagnosticsSnapshot:
        """Return a snapshot updated with an accepted worker result."""
        return DiagnosticsSnapshot(
            generation=result.generation,
            diagnostics=result.diagnostics,
            status=result.status,
            message=result.message,
            provider_states=result.provider_states,
            running_generation=running_generation,
            pending_generation=pending_generation,
        )


def sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    """Sort diagnostics according to the required deterministic contract."""
    return tuple(sorted(diagnostics, key=lambda diagnostic: diagnostic.sort_key()))
