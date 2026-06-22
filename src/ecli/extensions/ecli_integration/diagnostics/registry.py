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

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePath

from .provider_metadata import DiagnosticsProvider, ProviderMetadata
from .providers import (
    FILENAME_LANGUAGE,
    LANGUAGE_LABELS,
    PLANNED_NOTE_OVERRIDES,
    PLANNED_PROVIDERS,
    SONARQUBE_PROVIDER,
    RuffDiagnosticsProvider,
)


__all__ = ["PlannedSummary", "ProviderRegistry", "build_default_registry"]


@dataclass(frozen=True)
class PlannedSummary:
    """Panel-ready summary for a file whose language has planned providers."""

    language_id: str
    label: str
    detail: str
    hint: str


class ProviderRegistry:
    """Registry of active executing adapters plus planned provider metadata."""

    def __init__(
        self,
        active_providers: Sequence[DiagnosticsProvider] = (),
        planned_metadata: Sequence[ProviderMetadata] = (),
        project_quality: Sequence[ProviderMetadata] = (),
        labels: dict[str, str] | None = None,
        filename_language: dict[str, str] | None = None,
        note_overrides: dict[str, str] | None = None,
    ) -> None:
        """Create a registry from active providers and planned metadata."""
        self._active: tuple[DiagnosticsProvider, ...] = tuple(active_providers)
        self._planned: tuple[ProviderMetadata, ...] = tuple(planned_metadata)
        self._project_quality: tuple[ProviderMetadata, ...] = tuple(project_quality)
        self._labels = dict(labels or {})
        self._filename_language = {
            name.lower(): lang for name, lang in (filename_language or {}).items()
        }
        self._note_overrides = dict(note_overrides or {})

        self._active_metadata: tuple[ProviderMetadata, ...] = tuple(
            md
            for provider in self._active
            if (md := getattr(provider, "metadata", None)) is not None
        )
        self._extension_language = self._build_extension_index()

    # -- construction helpers --------------------------------------------- #

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
        if not file_path:
            return None
        pure = PurePath(file_path)
        by_name = self._filename_language.get(pure.name.lower())
        if by_name is not None:
            return by_name
        return self._extension_language.get(pure.suffix.lower())

    def language_label(self, language_id: str) -> str:
        """Return a human-readable label for *language_id*."""
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
        return tuple(md for md in self._planned if language_id in md.language_ids)

    def planned_for_extension(self, extension: str) -> tuple[ProviderMetadata, ...]:
        """Return planned provider metadata for *extension* (catalog order)."""
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
        return self._project_quality

    # -- introspection ----------------------------------------------------- #

    def find(self, provider_id: str) -> ProviderMetadata | None:
        """Return any provider metadata by id (active, planned, or quality)."""
        for metadata in (
            *self._active_metadata,
            *self._planned,
            *self._project_quality,
        ):
            if metadata.id == provider_id:
                return metadata
        return None

    def all_metadata(self) -> tuple[ProviderMetadata, ...]:
        """Return every known provider metadata."""
        return (*self._active_metadata, *self._planned, *self._project_quality)


def _unique_labels(metadata: Sequence[ProviderMetadata]) -> list[str]:
    seen: dict[str, None] = {}
    for md in metadata:
        seen.setdefault(md.label, None)
    return list(seen.keys())


def build_default_registry() -> ProviderRegistry:
    """Build the registry shipped with ECLI: active Ruff + planned catalog."""
    return ProviderRegistry(
        active_providers=(RuffDiagnosticsProvider(),),
        planned_metadata=PLANNED_PROVIDERS,
        project_quality=(SONARQUBE_PROVIDER,),
        labels=LANGUAGE_LABELS,
        filename_language=FILENAME_LANGUAGE,
        note_overrides=PLANNED_NOTE_OVERRIDES,
    )
