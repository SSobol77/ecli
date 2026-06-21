# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Deterministic, data-only registry of imported extension contributions (#100).

The registry discovers **direct child** extension folders under
``src/ecli/extensions/`` that contain a ``package.json``, parses their
contribution metadata, and exposes read-only lookup APIs. It deliberately does
not recurse into nested ``package.json`` files (language servers, node packages,
fixtures, tests), and it never executes extension code, scripts, activation
events, npm/node, or any runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .manifest import (
    ExtensionManifest,
    GrammarContribution,
    LanguageContribution,
    RegistryDiagnostic,
    SnippetContribution,
    ThemeContribution,
    parse_manifest,
)


def _normalize_extension(extension: str) -> str:
    """Return a lowercase file extension with a single leading dot."""
    extension = extension.lower()
    return extension if extension.startswith(".") else f".{extension}"


@dataclass(frozen=True)
class ExtensionRegistry:
    """Immutable collection of parsed manifests with deterministic lookups."""

    manifests: tuple[ExtensionManifest, ...] = field(default_factory=tuple)
    diagnostics: tuple[RegistryDiagnostic, ...] = field(default_factory=tuple)

    def list_manifests(self) -> tuple[ExtensionManifest, ...]:
        """Return every discovered manifest, ordered by directory name."""
        return self.manifests

    def list_diagnostics(self) -> tuple[RegistryDiagnostic, ...]:
        """Return diagnostics for malformed or skipped manifests/targets."""
        return self.diagnostics

    def language_ids(self) -> tuple[str, ...]:
        """Return every contributed language id, sorted and de-duplicated."""
        ids = {
            language.language_id
            for manifest in self.manifests
            for language in manifest.languages
        }
        return tuple(sorted(ids))

    def find_languages_by_id(
        self, language_id: str
    ) -> tuple[LanguageContribution, ...]:
        """Return all language contributions declaring ``language_id``."""
        return tuple(
            language
            for manifest in self.manifests
            for language in manifest.languages
            if language.language_id == language_id
        )

    def find_language_by_id(self, language_id: str) -> LanguageContribution | None:
        """Return the first language contribution for ``language_id`` or ``None``."""
        matches = self.find_languages_by_id(language_id)
        return matches[0] if matches else None

    def find_languages_by_extension(
        self, extension: str
    ) -> tuple[LanguageContribution, ...]:
        """Return all language contributions claiming the given file extension."""
        wanted = _normalize_extension(extension)
        return tuple(
            language
            for manifest in self.manifests
            for language in manifest.languages
            if wanted in {_normalize_extension(item) for item in language.extensions}
        )

    def find_language_by_extension(self, extension: str) -> LanguageContribution | None:
        """Return the first language contribution for ``extension`` or ``None``."""
        matches = self.find_languages_by_extension(extension)
        return matches[0] if matches else None

    def find_grammars_by_language(
        self, language_id: str
    ) -> tuple[GrammarContribution, ...]:
        """Return grammar contributions whose ``language`` is ``language_id``."""
        return tuple(
            grammar
            for manifest in self.manifests
            for grammar in manifest.grammars
            if grammar.language_id == language_id
        )

    def find_snippets_by_language(
        self, language_id: str
    ) -> tuple[SnippetContribution, ...]:
        """Return snippet contributions whose ``language`` is ``language_id``."""
        return tuple(
            snippet
            for manifest in self.manifests
            for snippet in manifest.snippets
            if snippet.language_id == language_id
        )

    def list_themes(self) -> tuple[ThemeContribution, ...]:
        """Return all contributed colour themes in deterministic manifest order."""
        return tuple(theme for manifest in self.manifests for theme in manifest.themes)

    def find_theme_by_id(self, theme_id: str) -> ThemeContribution | None:
        """Return the first theme contribution with ``id == theme_id``."""
        for manifest in self.manifests:
            for theme in manifest.themes:
                if theme.theme_id == theme_id:
                    return theme
        return None


def discover_manifest_directories(root: Path) -> tuple[Path, ...]:
    """Return direct-child directories of ``root`` that contain a ``package.json``.

    Discovery is intentionally shallow: only immediate children of the extension
    tree root are considered, so nested ``package.json`` files (for example
    ``html-language-features/server/package.json``) are never picked up.
    """
    if not root.is_dir():
        return ()
    children = (entry for entry in root.iterdir() if entry.is_dir())
    return tuple(
        sorted(
            (child for child in children if (child / "package.json").is_file()),
            key=lambda path: path.name,
        )
    )


def build_registry(root: Path | None = None) -> ExtensionRegistry:
    """Build an :class:`ExtensionRegistry` from the imported extension tree.

    ``root`` defaults to the imported ``ecli/extensions`` asset tree but may be
    overridden (for example with a temporary directory) to exercise malformed or
    edge-case manifests in tests. Parsing never raises on bad input; problems are
    collected as deterministic diagnostics.
    """
    base = (root or paths.extensions_root()).resolve()
    manifests: list[ExtensionManifest] = []
    diagnostics: list[RegistryDiagnostic] = []

    for directory in discover_manifest_directories(base):
        manifest, manifest_diagnostics = parse_manifest(directory, base)
        diagnostics.extend(manifest_diagnostics)
        if manifest is not None:
            manifests.append(manifest)

    return ExtensionRegistry(
        manifests=tuple(manifests),
        diagnostics=tuple(diagnostics),
    )
