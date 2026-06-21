# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/grammar_catalog.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""TextMate grammar catalog built from the #100 manifest registry (#101).

This is a deterministic, data-only catalog of ``contributes.grammars`` metadata.
It records each grammar's TextMate scope, language binding, file location,
embedded-language metadata, and token-type metadata, and verifies that grammar
files resolve to existing locations under ``src/ecli/extensions/``.

It does **not** parse TextMate grammar internals, tokenize text, or render
syntax. Those belong to the syntax service (#102), which does not exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .manifest import RegistryDiagnostic
from .registry import ExtensionRegistry, build_registry


@dataclass(frozen=True)
class TextMateGrammar:
    """Data-only record for one ``contributes.grammars[]`` entry."""

    scope_name: str | None
    language_id: str | None
    path: str | None
    path_repo_relative: str | None
    exists: bool
    source_manifest: str
    embedded_languages: tuple[tuple[str, str], ...] = ()
    token_types: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class GrammarCatalog:
    """Immutable catalog of grammars with deterministic lookups + diagnostics."""

    grammars: tuple[TextMateGrammar, ...] = field(default_factory=tuple)
    diagnostics: tuple[RegistryDiagnostic, ...] = field(default_factory=tuple)

    def list_grammars(self) -> tuple[TextMateGrammar, ...]:
        """Return every grammar in deterministic registry order."""
        return self.grammars

    def list_diagnostics(self) -> tuple[RegistryDiagnostic, ...]:
        """Return diagnostics for missing/traversal/malformed/conflicting grammars."""
        return self.diagnostics

    def scope_names(self) -> tuple[str, ...]:
        """Return every contributed TextMate scope name, sorted and de-duplicated."""
        return tuple(sorted({g.scope_name for g in self.grammars if g.scope_name}))

    def language_ids(self) -> tuple[str, ...]:
        """Return every language id that has a grammar, sorted and de-duplicated."""
        return tuple(sorted({g.language_id for g in self.grammars if g.language_id}))

    def grammars_for_language(self, language_id: str) -> tuple[TextMateGrammar, ...]:
        """Return grammars bound to ``language_id`` in deterministic order."""
        return tuple(g for g in self.grammars if g.language_id == language_id)

    def grammar_for_language(self, language_id: str) -> TextMateGrammar | None:
        """Return the first grammar bound to ``language_id`` or ``None``."""
        matches = self.grammars_for_language(language_id)
        return matches[0] if matches else None

    def grammars_for_scope(self, scope_name: str) -> tuple[TextMateGrammar, ...]:
        """Return grammars declaring ``scope_name`` in deterministic order."""
        return tuple(g for g in self.grammars if g.scope_name == scope_name)

    def grammar_for_scope(self, scope_name: str) -> TextMateGrammar | None:
        """Return the first grammar declaring ``scope_name`` or ``None``."""
        matches = self.grammars_for_scope(scope_name)
        return matches[0] if matches else None

    def embedded_languages_for_language(
        self, language_id: str
    ) -> tuple[tuple[str, str], ...]:
        """Return the union of embedded-language pairs for ``language_id``."""
        pairs: set[tuple[str, str]] = set()
        for grammar in self.grammars_for_language(language_id):
            pairs.update(grammar.embedded_languages)
        return tuple(sorted(pairs))


def _grammar_relative(path_repo_relative: str) -> str:
    prefix = f"{paths.REPO_RELATIVE_PREFIX}/"
    if path_repo_relative.startswith(prefix):
        return path_repo_relative[len(prefix) :]
    return path_repo_relative


def _build_grammar(
    manifest_name: str,
    grammar: object,
    root: Path,
    diagnostics: list[RegistryDiagnostic],
) -> TextMateGrammar:
    # ``grammar`` is a manifest.GrammarContribution; typed loosely to avoid a
    # cyclic import while keeping this helper focused.
    scope_name = grammar.scope_name  # type: ignore[attr-defined]
    path = grammar.path  # type: ignore[attr-defined]
    path_repo_relative = grammar.path_repo_relative  # type: ignore[attr-defined]

    exists = False
    if path is not None and path_repo_relative is None:
        diagnostics.append(
            RegistryDiagnostic(
                "warning",
                manifest_name,
                f"grammar path escapes extension tree: {path!r}",
            )
        )
    elif path_repo_relative is not None:
        exists = (root / _grammar_relative(path_repo_relative)).is_file()
        if not exists:
            diagnostics.append(
                RegistryDiagnostic(
                    "warning",
                    manifest_name,
                    f"grammar file missing: {path_repo_relative}",
                )
            )

    if scope_name is None:
        diagnostics.append(
            RegistryDiagnostic(
                "warning",
                manifest_name,
                f"grammar missing scopeName: {path_repo_relative or path}",
            )
        )

    return TextMateGrammar(
        scope_name=scope_name,
        language_id=grammar.language_id,  # type: ignore[attr-defined]
        path=path,
        path_repo_relative=path_repo_relative,
        exists=exists,
        source_manifest=manifest_name,
        embedded_languages=grammar.embedded_languages,  # type: ignore[attr-defined]
        token_types=grammar.token_types,  # type: ignore[attr-defined]
    )


def _diagnose_scope_conflicts(
    grammars: list[TextMateGrammar], diagnostics: list[RegistryDiagnostic]
) -> None:
    scope_paths: dict[str, set[str]] = {}
    exact_seen: set[tuple[str | None, str | None, str | None]] = set()
    for grammar in grammars:
        key = (grammar.scope_name, grammar.path_repo_relative, grammar.language_id)
        if key in exact_seen:
            diagnostics.append(
                RegistryDiagnostic(
                    "warning",
                    grammar.source_manifest,
                    f"duplicate grammar entry: scope={grammar.scope_name} "
                    f"language={grammar.language_id}",
                )
            )
        exact_seen.add(key)
        if grammar.scope_name is not None and grammar.path_repo_relative is not None:
            scope_paths.setdefault(grammar.scope_name, set()).add(
                grammar.path_repo_relative
            )
    for scope_name, paths_for_scope in sorted(scope_paths.items()):
        if len(paths_for_scope) > 1:
            diagnostics.append(
                RegistryDiagnostic(
                    "warning",
                    scope_name,
                    f"conflicting grammar paths for scope {scope_name}: "
                    f"{sorted(paths_for_scope)}",
                )
            )


def build_grammar_catalog(
    registry: ExtensionRegistry | None = None, root: Path | None = None
) -> GrammarCatalog:
    """Build a :class:`GrammarCatalog` from the manifest registry.

    ``root`` defaults to the imported ``ecli/extensions`` asset tree. To exercise
    fixtures, pass ``root=<temp dir>`` (a registry is built from it automatically)
    so grammar file-existence checks resolve against that fixture tree.
    """
    base = (root or paths.extensions_root()).resolve()
    if registry is None:
        registry = build_registry(base)

    grammars: list[TextMateGrammar] = []
    diagnostics: list[RegistryDiagnostic] = []
    for manifest in registry.list_manifests():
        for grammar in manifest.grammars:
            grammars.append(
                _build_grammar(manifest.directory_name, grammar, base, diagnostics)
            )
    _diagnose_scope_conflicts(grammars, diagnostics)

    return GrammarCatalog(grammars=tuple(grammars), diagnostics=tuple(diagnostics))
