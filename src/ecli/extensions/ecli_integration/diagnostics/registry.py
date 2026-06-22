# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Diagnostics provider registry (#104).

The registry knows which providers exist, which are *active* (an executing
adapter is present in this build) and which are *planned* (metadata only). It
resolves a file to a language id, exposes active/planned candidates by language
or extension, distinguishes "active provider, executable missing" from "planned
provider", and surfaces project-quality providers separately.

The provider-registry concept is ported from `fnando/vscode-linter` (MIT); see
``THIRD_PARTY_NOTICES.md``. ECLI re-implements it in Python and executes no VS
Code runtime code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import import_module
from pathlib import PurePath
from typing import Any, cast

from .provider_metadata import DiagnosticsProvider, ProviderMetadata
from .providers.ruff import RuffDiagnosticsProvider


__all__ = [
    "PlannedSummary",
    "ProviderRegistry",
    "ProviderRegistrySources",
    "build_default_registry",
]


@dataclass(frozen=True)
class PlannedSummary:
    """Panel-ready summary for a file whose language has planned providers."""

    language_id: str
    label: str
    detail: str
    hint: str


@dataclass(frozen=True)
class ProviderRegistrySources:
    """Constructor dependency group for :class:`ProviderRegistry`."""

    active_providers: Sequence[DiagnosticsProvider] = ()
    planned_metadata: Sequence[ProviderMetadata] = ()
    project_quality: Sequence[ProviderMetadata] = ()
    labels: Mapping[str, str] | None = None
    filename_language: Mapping[str, str] | None = None
    note_overrides: Mapping[str, str] | None = None
    load_default_catalog: bool = False


class ProviderRegistry:
    """Registry of active executing adapters plus planned provider metadata."""

    def __init__(
        self,
        sources: ProviderRegistrySources | Sequence[DiagnosticsProvider] | None = None,
        *legacy_args: Any,
        **legacy_sources: Any,
    ) -> None:
        """Create a registry from active providers and planned metadata."""
        resolved_sources = self._resolve_sources(sources, legacy_args, legacy_sources)
        self._active: tuple[DiagnosticsProvider, ...] = tuple(
            resolved_sources.active_providers
        )
        self._planned: tuple[ProviderMetadata, ...] = tuple(
            resolved_sources.planned_metadata
        )
        self._project_quality: tuple[ProviderMetadata, ...] = tuple(
            resolved_sources.project_quality
        )
        self._labels = dict(resolved_sources.labels or {})
        self._filename_language = {
            name.lower(): lang
            for name, lang in (resolved_sources.filename_language or {}).items()
        }
        self._note_overrides = dict(resolved_sources.note_overrides or {})
        self._load_default_catalog = resolved_sources.load_default_catalog
        self._default_catalog_loaded = not self._load_default_catalog

        self._active_metadata: tuple[ProviderMetadata, ...] = tuple(
            md
            for provider in self._active
            if (md := getattr(provider, "metadata", None)) is not None
        )
        self._extension_language = self._build_extension_index()

    # -- construction helpers --------------------------------------------- #

    @staticmethod
    def _resolve_sources(
        sources: ProviderRegistrySources | Sequence[DiagnosticsProvider] | None,
        legacy_args: tuple[Any, ...],
        legacy_sources: dict[str, Any],
    ) -> ProviderRegistrySources:
        if isinstance(sources, ProviderRegistrySources):
            if legacy_args:
                raise TypeError(
                    "ProviderRegistrySources cannot be combined with "
                    "legacy positional arguments"
                )
            resolved = sources
        else:
            field_names = tuple(ProviderRegistrySources.__dataclass_fields__)
            if len(legacy_args) >= len(field_names):
                raise TypeError("too many positional ProviderRegistry arguments")
            active_providers = sources or ()
            planned_metadata = cast(
                Sequence[ProviderMetadata],
                legacy_args[0] if len(legacy_args) > 0 else (),
            )
            project_quality = cast(
                Sequence[ProviderMetadata],
                legacy_args[1] if len(legacy_args) > 1 else (),
            )
            labels = cast(
                Mapping[str, str] | None,
                legacy_args[2] if len(legacy_args) > 2 else None,
            )
            filename_language = cast(
                Mapping[str, str] | None,
                legacy_args[3] if len(legacy_args) > 3 else None,
            )
            note_overrides = cast(
                Mapping[str, str] | None,
                legacy_args[4] if len(legacy_args) > 4 else None,
            )
            resolved = ProviderRegistrySources(
                active_providers=active_providers,
                planned_metadata=planned_metadata,
                project_quality=project_quality,
                labels=labels,
                filename_language=filename_language,
                note_overrides=note_overrides,
            )
        if not legacy_sources:
            return resolved
        valid_fields = set(ProviderRegistrySources.__dataclass_fields__)
        unknown = sorted(set(legacy_sources) - valid_fields)
        if unknown:
            joined = ", ".join(unknown)
            raise TypeError(f"unexpected ProviderRegistry source argument(s): {joined}")
        return replace(resolved, **legacy_sources)

    def _ensure_default_catalog(self) -> None:
        if self._default_catalog_loaded:
            return

        planned = import_module(
            "ecli.extensions.ecli_integration.diagnostics.providers.planned"
        )

        if not self._planned:
            self._planned = planned.PLANNED_PROVIDERS
        if not self._project_quality:
            self._project_quality = (planned.SONARQUBE_PROVIDER,)

        labels = dict(planned.LANGUAGE_LABELS)
        labels.update(self._labels)
        self._labels = labels

        filename_language = {
            name.lower(): lang for name, lang in planned.FILENAME_LANGUAGE.items()
        }
        filename_language.update(self._filename_language)
        self._filename_language = filename_language

        note_overrides = dict(planned.PLANNED_NOTE_OVERRIDES)
        note_overrides.update(self._note_overrides)
        self._note_overrides = note_overrides

        self._extension_language = self._build_extension_index()
        self._default_catalog_loaded = True

    def _build_extension_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for metadata in (*self._active_metadata, *self._planned):
            language = metadata.language_ids[0] if metadata.language_ids else None
            if language is None:
                continue
            for extension in metadata.extensions:
                index.setdefault(extension.lower(), language)
        return index

    # -- language resolution ---------------------------------------------- #

    def language_for(self, file_path: str) -> str | None:
        """Resolve *file_path* to a language id (filename first, then suffix)."""
        self._ensure_default_catalog()
        if not file_path:
            return None
        pure = PurePath(file_path)
        by_name = self._filename_language.get(pure.name.lower())
        if by_name is not None:
            return by_name
        return self._extension_language.get(pure.suffix.lower())

    def language_label(self, language_id: str) -> str:
        """Return a human-readable label for *language_id*."""
        self._ensure_default_catalog()
        return self._labels.get(language_id, language_id)

    # -- active providers -------------------------------------------------- #

    @property
    def active_providers(self) -> tuple[DiagnosticsProvider, ...]:
        """Return the executing provider instances."""
        return self._active

    def active_provider_for(self, file_path: str) -> DiagnosticsProvider | None:
        """Return the first active provider that applies to *file_path*."""
        for provider in self._active:
            if provider.applies_to(file_path):
                return provider
        return None

    def active_metadata_for_language(
        self, language_id: str
    ) -> tuple[ProviderMetadata, ...]:
        """Return active provider metadata supporting *language_id*."""
        return tuple(
            md for md in self._active_metadata if language_id in md.language_ids
        )

    def active_metadata_for_extension(
        self, extension: str
    ) -> tuple[ProviderMetadata, ...]:
        """Return active provider metadata supporting *extension*."""
        ext = extension.lower()
        return tuple(md for md in self._active_metadata if ext in md.extensions)

    # -- planned providers ------------------------------------------------- #

    def planned_for_language(self, language_id: str) -> tuple[ProviderMetadata, ...]:
        """Return planned provider metadata for *language_id* (catalog order)."""
        self._ensure_default_catalog()
        return tuple(md for md in self._planned if language_id in md.language_ids)

    def planned_for_extension(self, extension: str) -> tuple[ProviderMetadata, ...]:
        """Return planned provider metadata for *extension* (catalog order)."""
        self._ensure_default_catalog()
        ext = extension.lower()
        return tuple(md for md in self._planned if ext in md.extensions)

    def planned_summary_for(self, file_path: str) -> PlannedSummary | None:
        """Build a panel summary when *file_path* maps to planned providers."""
        language = self.language_for(file_path)
        if language is None:
            return None
        planned = self.planned_for_language(language)
        if not planned:
            return None
        label = self.language_label(language)
        detail = f"No active bundled diagnostics provider for {label} in this build."
        override = self._note_overrides.get(language)
        if override is not None:
            hint = override
        else:
            labels = _unique_labels(planned)
            word = "Planned provider" if len(labels) == 1 else "Planned providers"
            hint = f"{word}: {', '.join(labels)}."
        return PlannedSummary(
            language_id=language, label=label, detail=detail, hint=hint
        )

    # -- project quality --------------------------------------------------- #

    def project_quality_providers(self) -> tuple[ProviderMetadata, ...]:
        """Return planned project-quality providers (e.g. SonarQube)."""
        self._ensure_default_catalog()
        return self._project_quality

    # -- introspection ----------------------------------------------------- #

    def find(self, provider_id: str) -> ProviderMetadata | None:
        """Return any provider metadata by id (active, planned, or quality)."""
        for metadata in self._active_metadata:
            if metadata.id == provider_id:
                return metadata
        self._ensure_default_catalog()
        for metadata in (*self._planned, *self._project_quality):
            if metadata.id == provider_id:
                return metadata
        return None

    def all_metadata(self) -> tuple[ProviderMetadata, ...]:
        """Return every known provider metadata."""
        self._ensure_default_catalog()
        return (*self._active_metadata, *self._planned, *self._project_quality)


def _unique_labels(metadata: Sequence[ProviderMetadata]) -> list[str]:
    seen: dict[str, None] = {}
    for md in metadata:
        seen.setdefault(md.label, None)
    return list(seen.keys())


@lru_cache(maxsize=1)
def build_default_registry() -> ProviderRegistry:
    """Build the registry shipped with ECLI: active Ruff + planned catalog."""
    return ProviderRegistry(
        ProviderRegistrySources(
            active_providers=(RuffDiagnosticsProvider(),),
            load_default_catalog=True,
        )
    )
