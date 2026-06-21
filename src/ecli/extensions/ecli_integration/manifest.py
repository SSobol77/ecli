# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Data-only model + safe parser for VS Code ``package.json`` contributions (#100).

This module turns an imported ``package.json`` contribution block into typed,
immutable Python data. It is a deterministic adapter over the read-only imported
extension tree (issue #98). It reads JSON metadata only and **never**:

* executes ``activationEvents`` or ``scripts``,
* runs npm/node/esbuild/tsc or any extension build tool,
* activates a VS Code extension host or Copilot runtime,
* performs network, auth, or any side effect.

Fields that could describe executable behavior (``scripts``,
``activationEvents``, ``main``, ``browser`` …) are intentionally **not** modeled,
so they can never be exposed or invoked through this layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import paths


@dataclass(frozen=True)
class RegistryDiagnostic:
    """A deterministic, non-fatal problem found while reading a manifest."""

    level: str
    manifest: str
    message: str


@dataclass(frozen=True)
class LanguageContribution:
    """A single ``contributes.languages[]`` entry (metadata only)."""

    language_id: str
    aliases: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    filename_patterns: tuple[str, ...] = ()
    configuration_path: str | None = None
    configuration_repo_path: str | None = None


@dataclass(frozen=True)
class GrammarContribution:
    """A single ``contributes.grammars[]`` entry (metadata only)."""

    language_id: str | None
    scope_name: str | None
    path: str | None
    path_repo_relative: str | None = None
    embedded_languages: tuple[tuple[str, str], ...] = ()
    token_types: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SnippetContribution:
    """A single ``contributes.snippets[]`` entry (metadata only)."""

    language_id: str | None
    path: str | None
    path_repo_relative: str | None = None


@dataclass(frozen=True)
class ConfigurationContribution:
    """A ``contributes.configuration`` block, reduced to declarative metadata.

    Only the title, ordering hint, and the *names* of contributed settings are
    preserved. Setting values, defaults, and schemas are never interpreted or
    applied; this is pure metadata exposure.
    """

    title: str | None
    order: int | None
    property_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionManifest:
    """Parsed, data-only view of one extension's ``package.json``."""

    name: str
    directory_name: str
    manifest_repo_path: str
    display_name: str | None = None
    version: str | None = None
    publisher: str | None = None
    languages: tuple[LanguageContribution, ...] = field(default_factory=tuple)
    grammars: tuple[GrammarContribution, ...] = field(default_factory=tuple)
    snippets: tuple[SnippetContribution, ...] = field(default_factory=tuple)
    configuration: tuple[ConfigurationContribution, ...] = field(default_factory=tuple)


@dataclass
class _ParseContext:
    """Mutable per-manifest parsing context shared by the section parsers."""

    base_dir: Path
    root: Path
    label: str
    diagnostics: list[RegistryDiagnostic]

    def warn(self, message: str) -> None:
        """Record a non-fatal warning diagnostic for this manifest."""
        self.diagnostics.append(RegistryDiagnostic("warning", self.label, message))

    def error(self, message: str) -> None:
        """Record a fatal error diagnostic for this manifest."""
        self.diagnostics.append(RegistryDiagnostic("error", self.label, message))

    def resolve_target(self, relative: str | None, kind: str) -> str | None:
        """Resolve a contribution target path; diagnose problems, never raise."""
        if relative is None:
            return None
        resolved = paths.resolve_contribution_path(self.base_dir, relative, self.root)
        if resolved is None:
            self.warn(f"{kind} path escapes extension tree: {relative!r}")
            return None
        repo_relative = paths.to_repo_relative(resolved, self.root)
        if not resolved.exists():
            self.warn(f"{kind} target file missing: {repo_relative}")
        return repo_relative


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _str_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        return ()
    pairs = [
        (key, val)
        for key, val in value.items()
        if isinstance(key, str) and isinstance(val, str)
    ]
    return tuple(sorted(pairs))


def _parse_languages(
    raw: object, context: _ParseContext
) -> tuple[LanguageContribution, ...]:
    if not isinstance(raw, list):
        return ()
    result: list[LanguageContribution] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        language_id = _as_str(entry.get("id"))
        if language_id is None:
            continue
        configuration_path = _as_str(entry.get("configuration"))
        result.append(
            LanguageContribution(
                language_id=language_id,
                aliases=_str_tuple(entry.get("aliases")),
                extensions=_str_tuple(entry.get("extensions")),
                filenames=_str_tuple(entry.get("filenames")),
                filename_patterns=_str_tuple(entry.get("filenamePatterns")),
                configuration_path=configuration_path,
                configuration_repo_path=context.resolve_target(
                    configuration_path, "language-configuration"
                ),
            )
        )
    return tuple(result)


def _parse_grammars(
    raw: object, context: _ParseContext
) -> tuple[GrammarContribution, ...]:
    if not isinstance(raw, list):
        return ()
    result: list[GrammarContribution] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        grammar_path = _as_str(entry.get("path"))
        result.append(
            GrammarContribution(
                language_id=_as_str(entry.get("language")),
                scope_name=_as_str(entry.get("scopeName")),
                path=grammar_path,
                path_repo_relative=context.resolve_target(grammar_path, "grammar"),
                embedded_languages=_str_pairs(entry.get("embeddedLanguages")),
                token_types=_str_pairs(entry.get("tokenTypes")),
            )
        )
    return tuple(result)


def _parse_snippets(
    raw: object, context: _ParseContext
) -> tuple[SnippetContribution, ...]:
    if not isinstance(raw, list):
        return ()
    result: list[SnippetContribution] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        snippet_path = _as_str(entry.get("path"))
        result.append(
            SnippetContribution(
                language_id=_as_str(entry.get("language")),
                path=snippet_path,
                path_repo_relative=context.resolve_target(snippet_path, "snippet"),
            )
        )
    return tuple(result)


def _parse_configuration(raw: object) -> tuple[ConfigurationContribution, ...]:
    blocks = raw if isinstance(raw, list) else [raw]
    result: list[ConfigurationContribution] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        properties = block.get("properties")
        property_keys = (
            tuple(sorted(k for k in properties if isinstance(k, str)))
            if isinstance(properties, dict)
            else ()
        )
        order = block.get("order")
        result.append(
            ConfigurationContribution(
                title=_as_str(block.get("title")),
                order=order if isinstance(order, int) else None,
                property_keys=property_keys,
            )
        )
    return tuple(result)


def parse_manifest(
    directory: Path, root: Path
) -> tuple[ExtensionManifest | None, list[RegistryDiagnostic]]:
    """Parse ``directory/package.json`` into an :class:`ExtensionManifest`.

    Returns ``(manifest, diagnostics)``. On unrecoverable problems (unreadable or
    invalid JSON, or a non-object document) ``manifest`` is ``None`` and a
    diagnostic explains why. Malformed ``contributes`` sub-sections degrade to
    empty contributions with warnings rather than raising.
    """
    manifest_path = directory / "package.json"
    label = paths.to_repo_relative(manifest_path, root)
    context = _ParseContext(directory, root, label, [])

    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as error:
        context.error(f"cannot read package.json: {error}")
        return None, context.diagnostics

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        context.error(f"invalid JSON: {error}")
        return None, context.diagnostics

    if not isinstance(data, dict):
        context.error("package.json is not a JSON object")
        return None, context.diagnostics

    contributes = data.get("contributes")
    if contributes is not None and not isinstance(contributes, dict):
        context.warn("contributes is not an object")
        contributes = {}
    contributes = contributes or {}

    manifest = ExtensionManifest(
        name=_as_str(data.get("name")) or directory.name,
        directory_name=directory.name,
        manifest_repo_path=label,
        display_name=_as_str(data.get("displayName")),
        version=_as_str(data.get("version")),
        publisher=_as_str(data.get("publisher")),
        languages=_parse_languages(contributes.get("languages"), context),
        grammars=_parse_grammars(contributes.get("grammars"), context),
        snippets=_parse_snippets(contributes.get("snippets"), context),
        configuration=_parse_configuration(contributes.get("configuration")),
    )
    return manifest, context.diagnostics
