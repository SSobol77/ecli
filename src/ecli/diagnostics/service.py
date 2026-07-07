"""Provider registry and bounded async diagnostics execution."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Protocol

from ecli.diagnostics.models import (
    Diagnostic,
    DiagnosticRequest,
    DiagnosticResult,
    DiagnosticsSnapshot,
    DiagnosticStatus,
    ProviderState,
    sort_diagnostics,
)


logger = logging.getLogger(__name__)


class DiagnosticProvider(Protocol):
    """Protocol implemented by diagnostics providers."""

    name: str
    enabled: bool

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run diagnostics for the given request."""


class DiagnosticsService:
    """Registry plus one-in-flight diagnostics worker scheduler."""

    def __init__(self) -> None:
        """Initialize an empty provider registry and worker state."""
        self._providers: dict[str, DiagnosticProvider] = {}
        self._lock = threading.RLock()
        self._generation = 0
        self._in_flight = False
        self._running_generation: int | None = None
        self._pending_request: DiagnosticRequest | None = None
        self._results: queue.Queue[DiagnosticResult] = queue.Queue()

    def register_provider(self, provider: DiagnosticProvider) -> None:
        """Register or replace a provider by name."""
        with self._lock:
            self._providers[provider.name] = provider

    def set_provider_enabled(self, provider_name: str, enabled: bool) -> bool:
        """Set a provider enabled flag; return False if it is unknown."""
        with self._lock:
            provider = self._providers.get(provider_name)
            if provider is None:
                return False
            provider.enabled = enabled
            return True

    def provider_states(self) -> tuple[ProviderState, ...]:
        """Return deterministic provider enabled/disabled state."""
        with self._lock:
            return tuple(
                ProviderState(name=name, enabled=provider.enabled)
                for name, provider in sorted(self._providers.items())
            )

    def request_refresh(
        self,
        *,
        scope: str,
        file_path: str | None,
        text: str | None,
        project_root: str,
        language: str | None,
    ) -> tuple[int, bool, int | None]:
        """Schedule diagnostics refresh and return generation/coalescing state.

        Returns:
            A tuple ``(generation, started_now, pending_generation)``. At most
            one worker runs at a time. While a worker is active, the newest
            request replaces any older pending request.
        """
        if scope not in ("buffer", "workspace"):
            raise ValueError(f"unsupported diagnostics scope: {scope}")

        with self._lock:
            self._generation += 1
            request = DiagnosticRequest(
                generation=self._generation,
                scope=scope,  # type: ignore[arg-type]
                file_path=file_path,
                text=text,
                project_root=project_root,
                language=language,
            )
            if self._in_flight:
                self._pending_request = request
                return request.generation, False, request.generation

            self._start_worker_locked(request)
            return request.generation, True, None

    def drain_results(self) -> list[DiagnosticResult]:
        """Drain completed worker results without blocking the caller."""
        results: list[DiagnosticResult] = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                return results

    def worker_state(self) -> tuple[int | None, int | None]:
        """Return running and pending generations."""
        with self._lock:
            pending = (
                self._pending_request.generation
                if self._pending_request is not None
                else None
            )
            return self._running_generation, pending

    def _start_worker_locked(self, request: DiagnosticRequest) -> None:
        self._in_flight = True
        self._running_generation = request.generation
        worker = threading.Thread(
            target=self._run_worker,
            args=(request,),
            name=f"DiagnosticsWorker-{request.generation}",
            daemon=True,
        )
        worker.start()

    def _run_worker(self, request: DiagnosticRequest) -> None:
        try:
            result = self._run_providers(request)
        except Exception as exc:
            logger.exception(
                "Diagnostics worker crashed for generation %s",
                request.generation,
            )
            result = DiagnosticResult(
                generation=request.generation,
                diagnostics=(
                    Diagnostic(
                        file_path=request.file_path or request.project_root,
                        line=1,
                        column=1,
                        severity="error",
                        code="DIAGNOSTICS-WORKER",
                        message=f"Diagnostics worker failed: {exc}",
                        source="ecli",
                    ),
                ),
                status="error",
                message="Diagnostics worker failed. See logs/editor.log.",
                provider_states=self.provider_states(),
            )
        self._results.put(result)
        with self._lock:
            next_request = self._pending_request
            self._pending_request = None
            if next_request is not None:
                self._start_worker_locked(next_request)
            else:
                self._in_flight = False
                self._running_generation = None

    def _run_providers(self, request: DiagnosticRequest) -> DiagnosticResult:
        enabled = self._enabled_providers()
        if not enabled:
            return DiagnosticResult(
                generation=request.generation,
                diagnostics=(),
                status="skipped",
                message="Diagnostics providers are disabled.",
                provider_states=self.provider_states(),
            )

        diagnostics: list[Diagnostic] = []
        messages: list[str] = []
        status: DiagnosticStatus = "ready"
        saw_skipped = False
        for provider in enabled:
            status, saw_skipped = self._merge_provider_result(
                provider.run(request),
                diagnostics,
                messages,
                status,
                saw_skipped,
            )

        sorted_diagnostics = sort_diagnostics(diagnostics)
        status = self._final_result_status(
            status,
            has_diagnostics=bool(sorted_diagnostics),
            saw_skipped=saw_skipped,
        )
        message = self._final_result_message(
            status,
            diagnostic_count=len(sorted_diagnostics),
            messages=messages,
        )
        return DiagnosticResult(
            generation=request.generation,
            diagnostics=sorted_diagnostics,
            status=status,
            message=message,
            provider_states=self.provider_states(),
        )

    def _merge_provider_result(
        self,
        result: DiagnosticResult,
        diagnostics: list[Diagnostic],
        messages: list[str],
        status: DiagnosticStatus,
        saw_skipped: bool,
    ) -> tuple[DiagnosticStatus, bool]:
        """Merge one provider result into aggregate diagnostics state."""
        diagnostics.extend(result.diagnostics)
        if result.status == "error":
            status = "error"
        elif result.status == "skipped" and status != "error":
            saw_skipped = True
        if result.message:
            messages.append(result.message)
        return status, saw_skipped

    def _final_result_status(
        self,
        status: DiagnosticStatus,
        *,
        has_diagnostics: bool,
        saw_skipped: bool,
    ) -> DiagnosticStatus:
        """Return aggregate status after all providers have run."""
        if status == "error":
            return "error"
        if has_diagnostics:
            return "ready"
        if saw_skipped:
            return "skipped"
        return status

    def _final_result_message(
        self,
        status: DiagnosticStatus,
        *,
        diagnostic_count: int,
        messages: list[str],
    ) -> str:
        """Return aggregate message for the final diagnostics status."""
        if status == "error":
            return messages[-1] if messages else "Diagnostics failed."
        if diagnostic_count:
            return f"Diagnostics: {diagnostic_count} issue(s)."
        if status == "skipped":
            return messages[-1] if messages else "Diagnostics skipped."
        return "Diagnostics: PASS — no issues found."

    def _enabled_providers(self) -> tuple[DiagnosticProvider, ...]:
        with self._lock:
            return tuple(
                provider
                for _name, provider in sorted(self._providers.items())
                if provider.enabled
            )


def initial_snapshot(provider_states: tuple[ProviderState, ...]) -> DiagnosticsSnapshot:
    """Return the initial diagnostics UI snapshot."""
    return DiagnosticsSnapshot(provider_states=provider_states)
