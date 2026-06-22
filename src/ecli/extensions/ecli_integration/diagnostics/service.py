# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Diagnostics coordinator service for the F4 panel (#104).

:class:`DiagnosticsService` is the single entry point the TUI uses. It ties
together the :class:`~.config.LinterLayerConfig`, the
:class:`~.registry.ProviderRegistry` and the bounded
:class:`~.store.DiagnosticsStore`, and it owns every policy decision before a
provider runs:

* honour ``[linter].enabled`` and ``[linter].exclude``;
* validate the file path and classify outside-workspace / unreadable;
* pick the active executing provider via the registry, or surface a *planned*
  state listing the roadmap providers, or *unsupported* when nothing is known;
* serve cached results until the buffer revision changes or a refresh is forced.

Only ECLI-owned adapters execute subprocesses, always through a fixed argv with a
bounded timeout. The service never auto-installs a tool and never runs a project
scan (SonarQube) during F4 rendering. :meth:`collect` is synchronous and
deterministic; the panel runs it on a background thread.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .config import LinterLayerConfig
from .model import DiagnosticsState
from .provider_metadata import (
    DEFAULT_TIMEOUT_SECONDS,
    DiagnosticsProvider,
    ProviderExecutionMode,
    ProviderMetadata,
)
from .registry import ProviderRegistry, build_default_registry
from .store import DiagnosticsStore


__all__ = ["DiagnosticsService", "DiagnosticsServiceDeps"]


@dataclass(frozen=True)
class DiagnosticsServiceDeps:
    """Constructor dependency group for :class:`DiagnosticsService`."""

    config: Mapping[str, object] | LinterLayerConfig | None = None
    registry: ProviderRegistry | None = None
    providers: Sequence[DiagnosticsProvider] | None = None
    store: DiagnosticsStore | None = None
    workspace_root: str | Path | None = None
    timeout: float = DEFAULT_TIMEOUT_SECONDS


class DiagnosticsService:
    """Coordinates configuration, the provider registry and the cache."""

    def __init__(
        self,
        deps: DiagnosticsServiceDeps | None = None,
        **legacy_deps: Any,
    ) -> None:
        """Create a diagnostics service.

        Args:
            deps: Grouped service dependencies. Defaults preserve the shipped
                registry, fresh cache, and standard timeout.
            **legacy_deps: Compatibility keyword arguments matching the previous
                constructor shape:
            ``config``: A parsed :class:`LinterLayerConfig` or a full ECLI config
                mapping (its ``[linter]`` table is read).
            ``registry``: Provider registry. Defaults to the shipped registry (active
                Ruff + planned catalog + SonarQube project-quality metadata).
            ``providers``: Convenience for tests — wrap an ad-hoc list of active
                providers in a registry with no planned catalog. Ignored when
                *registry* is given.
            ``store``: Bounded result cache. A fresh one is created when omitted.
            ``workspace_root``: When set, files resolved outside this directory are
                reported as outside-workspace and are not linted.
            ``timeout``: Bounded per-collection external-process timeout, in seconds.
        """
        resolved_deps = self._resolve_deps(deps, legacy_deps)
        if isinstance(resolved_deps.config, LinterLayerConfig):
            self.config = resolved_deps.config
        else:
            self.config = LinterLayerConfig.from_config(resolved_deps.config)
        if resolved_deps.registry is not None:
            self._registry = resolved_deps.registry
        elif resolved_deps.providers is not None:
            self._registry = ProviderRegistry(active_providers=resolved_deps.providers)
        else:
            self._registry = build_default_registry()
        self._store = (
            resolved_deps.store
            if resolved_deps.store is not None
            else DiagnosticsStore()
        )
        self._workspace_root = (
            Path(resolved_deps.workspace_root).resolve()
            if resolved_deps.workspace_root is not None
            else None
        )
        self._timeout = float(resolved_deps.timeout)

    @property
    def store(self) -> DiagnosticsStore:
        """Return the bounded result cache."""
        return self._store

    @property
    def registry(self) -> ProviderRegistry:
        """Return the provider registry."""
        return self._registry

    @property
    def providers(self) -> tuple[DiagnosticsProvider, ...]:
        """Return the active executing providers."""
        return self._registry.active_providers

    @property
    def workspace_root(self) -> Path | None:
        """Return the configured workspace root, if any."""
        return self._workspace_root

    def provider_for(self, file_path: str) -> DiagnosticsProvider | None:
        """Return the first active provider that applies to *file_path*."""
        return self._registry.active_provider_for(file_path)

    def project_quality_providers(self) -> tuple[ProviderMetadata, ...]:
        """Return planned project-quality providers (e.g. SonarQube)."""
        return self._registry.project_quality_providers()

    def collect(
        self,
        file_path: str | None,
        *,
        text: str | None = None,
        force: bool = False,
    ) -> DiagnosticsState:
        """Collect diagnostics for *file_path*, returning an explicit state.

        Never raises: every condition maps to a structured
        :class:`DiagnosticsState`. Results are cached by ``(provider, path)`` and
        keyed by a content revision, so an unchanged buffer reuses the cache and
        no external process runs.
        """
        preflight = self._preflight_collect(file_path)
        if preflight is not None:
            return preflight
        kind, safe_path = self._validated_collect_path(file_path)
        external = kind == "outside"
        provider = self._registry.active_provider_for(safe_path)
        provider_state = self._provider_preflight_state(provider, safe_path, external)
        if provider_state is not None:
            return provider_state
        return self._collect_with_provider(
            provider, safe_path, text if text is not None else "", force, external
        )

    @staticmethod
    def _resolve_deps(
        deps: DiagnosticsServiceDeps | None,
        legacy_deps: dict[str, Any],
    ) -> DiagnosticsServiceDeps:
        if deps is not None and not isinstance(deps, DiagnosticsServiceDeps):
            raise TypeError(
                "DiagnosticsService positional argument must be DiagnosticsServiceDeps"
            )
        resolved = deps or DiagnosticsServiceDeps()
        if not legacy_deps:
            return resolved
        valid_fields = set(DiagnosticsServiceDeps.__dataclass_fields__)
        unknown = sorted(set(legacy_deps) - valid_fields)
        if unknown:
            joined = ", ".join(unknown)
            raise TypeError(
                f"unexpected DiagnosticsService dependency argument(s): {joined}"
            )
        return replace(resolved, **legacy_deps)

    def _preflight_collect(self, file_path: str | None) -> DiagnosticsState | None:
        if not self.config.enabled:
            return DiagnosticsState.disabled(
                "Diagnostics are disabled ([linter].enabled = false)"
            )
        if not file_path:
            return DiagnosticsState.no_active_file("Open a file to see diagnostics")
        if self.config.is_excluded(file_path):
            return DiagnosticsState.disabled(
                f"{Path(file_path).name} is excluded by [linter].exclude"
            )
        kind, safe_path = self._validate_path(file_path)
        if kind == "invalid" or safe_path is None:
            return DiagnosticsState.unreadable(
                file_path=file_path,
                detail="Current file path is invalid or cannot be read.",
            )
        return None

    def _validated_collect_path(self, file_path: str | None) -> tuple[str, str]:
        if file_path is None:
            raise AssertionError("file_path must be preflighted before validation")
        kind, safe_path = self._validate_path(file_path)
        if safe_path is None:
            raise AssertionError("safe_path must be present after collect preflight")
        return kind, safe_path

    def _provider_preflight_state(
        self,
        provider: DiagnosticsProvider | None,
        safe_path: str,
        external: bool,
    ) -> DiagnosticsState | None:
        if provider is None:
            if external:
                return DiagnosticsState.outside_workspace(
                    file_path=safe_path,
                    detail="Current file is outside ECLI workspace.",
                )
            return self._inactive_state(safe_path)
        if external and not self._is_current_file_provider(provider):
            return DiagnosticsState.outside_workspace(
                file_path=safe_path,
                detail=(
                    f"{getattr(provider, 'name', 'provider')} only runs inside "
                    "the ECLI workspace; current file is outside it."
                ),
            )
        return None

    def _collect_with_provider(
        self,
        provider: DiagnosticsProvider | None,
        safe_path: str,
        payload: str,
        force: bool,
        external: bool,
    ) -> DiagnosticsState:
        if provider is None:
            raise AssertionError("provider must be resolved before collection")
        revision = self._revision(safe_path, payload)
        cache_key = f"{provider.name}:{safe_path}"
        if not force:
            cached = self._store.get(cache_key, revision)
            if cached is not None:
                return cached

        state = self._run_provider(provider, safe_path, payload, external=external)
        self._store.put(cache_key, revision, state)
        return state

    def invalidate(self, file_path: str | None = None) -> None:
        """Drop cached diagnostics for *file_path* (or all when ``None``)."""
        if file_path is None:
            self._store.clear()
            return
        _kind, safe_path = self._validate_path(file_path)
        target = safe_path or file_path
        for provider in self._registry.active_providers:
            self._store.invalidate(f"{provider.name}:{target}")

    # -- internals --------------------------------------------------------- #

    def _inactive_state(self, file_path: str) -> DiagnosticsState:
        """No active provider applies: planned roadmap state, or unsupported."""
        summary = self._registry.planned_summary_for(file_path)
        if summary is not None:
            return DiagnosticsState.planned(
                file_path=file_path, detail=summary.detail, hint=summary.hint
            )
        suffix = Path(file_path).suffix or "(none)"
        return DiagnosticsState.unsupported(
            file_path=file_path,
            detail=f"No diagnostics provider for {suffix} files",
            hint=self._active_providers_hint(),
        )

    def _run_provider(
        self,
        provider: DiagnosticsProvider,
        file_path: str,
        text: str,
        *,
        external: bool = False,
    ) -> DiagnosticsState:
        if not provider.is_available():
            return self._unavailable_state(provider, file_path)
        try:
            result = provider.collect(file_path, text, self._timeout)
        except Exception as exc:  # defensive: keep collect() total
            return DiagnosticsState.error(
                provider=provider.name,
                detail=f"{provider.name} failed: {exc}"[:160],
                file_path=file_path,
            )
        if not result.available:
            return self._unavailable_state(provider, file_path, result.detail)
        if not result.ok:
            return DiagnosticsState.error(
                provider=provider.name,
                detail=result.detail or f"{provider.name} failed",
                file_path=file_path,
            )
        return DiagnosticsState.from_diagnostics(
            provider=provider.name,
            file_path=file_path,
            diagnostics=result.diagnostics,
            external=external,
        )

    @staticmethod
    def _is_current_file_provider(provider: DiagnosticsProvider) -> bool:
        """Return ``True`` for safe current-file (stdin) providers like Ruff.

        Determined solely from immutable provider metadata
        (``execution_mode == CURRENT_FILE``). Providers without metadata default
        to *not* current-file, so the conservative workspace boundary still
        applies to them.
        """
        metadata = getattr(provider, "metadata", None)
        return (
            getattr(metadata, "execution_mode", None)
            is ProviderExecutionMode.CURRENT_FILE
        )

    def _unavailable_state(
        self,
        provider: DiagnosticsProvider,
        file_path: str,
        detail: str | None = None,
    ) -> DiagnosticsState:
        metadata = getattr(provider, "metadata", None)
        if metadata is not None:
            language = self._registry.language_for(file_path)
            if language is not None:
                label = self._registry.language_label(language)
            elif metadata.language_ids:
                label = metadata.language_ids[0]
            else:
                label = ""
            registered_detail = (
                f"{metadata.display_name} provider is registered for {label} "
                f"but the {metadata.display_name} executable is not available."
            )
            return DiagnosticsState.provider_unavailable(
                provider=provider.name,
                detail=detail or registered_detail,
                file_path=file_path,
                hint=metadata.install_hint,
            )
        return DiagnosticsState.provider_unavailable(
            provider=provider.name,
            detail=detail
            or f"{provider.name} is not installed; install it to see diagnostics",
            file_path=file_path,
        )

    def _active_providers_hint(self) -> str | None:
        descriptions: list[str] = []
        for provider in self._registry.active_providers:
            text = getattr(provider, "description", None) or getattr(
                provider, "name", ""
            )
            if text:
                descriptions.append(str(text))
        if not descriptions:
            return None
        label = "Available provider" + ("s" if len(descriptions) > 1 else "")
        return f"{label}: {', '.join(descriptions)}."

    def _validate_path(self, file_path: str) -> tuple[str, str | None]:
        """Classify *file_path* as ``"ok"``, ``"outside"`` or ``"invalid"``.

        Returns a ``(kind, resolved_path)`` pair. ``"invalid"`` covers empty
        paths, NUL bytes, directories, and unresolvable paths (``resolved_path``
        is ``None``). ``"outside"`` means the path resolved but lives outside the
        configured workspace root (``resolved_path`` is returned so the UI can
        show it). ``"ok"`` returns the safe resolved absolute path. Path
        validation is never weakened by configuration.
        """
        candidate = file_path.strip()
        if not candidate or "\x00" in candidate:
            return ("invalid", None)
        try:
            resolved = Path(candidate).resolve()
        except (OSError, ValueError, RuntimeError):
            return ("invalid", None)
        if resolved.is_dir():
            return ("invalid", None)
        if self._workspace_root is not None:
            try:
                inside = resolved.is_relative_to(self._workspace_root)
            except ValueError:
                inside = False
            if not inside:
                return ("outside", str(resolved))
        return ("ok", str(resolved))

    @staticmethod
    def _revision(file_path: str, text: str) -> str:
        """Return a stable content revision token for cache keying.

        Hashes the buffer contents so any edit invalidates the cache. The file
        path is folded in so identical contents under different paths do not
        collide.
        """
        digest = hashlib.sha256()
        digest.update(file_path.encode("utf-8", "surrogatepass"))
        digest.update(b"\x00")
        digest.update(text.encode("utf-8", "surrogatepass"))
        return digest.hexdigest()
