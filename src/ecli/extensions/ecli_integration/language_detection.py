# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/language_detection.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Deterministic language detection from imported extension metadata (#101).

Detection maps a file name (or path) to a language id using only the
``contributes.languages`` metadata exposed by the #100 registry: exact
filenames, filename glob patterns, and file extensions. It is pure metadata
lookup — it never reads file contents, tokenizes text, or renders syntax, and it
is not wired into editor rendering in this issue.

Precedence is deterministic: an exact filename match wins over a filename-pattern
match, which wins over a file-extension match. Within the winning tier, all
candidate language ids are returned in deterministic order; more than one marks
the result ambiguous.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

from .registry import ExtensionRegistry, build_registry


MATCH_FILENAME = "filename"
MATCH_FILENAME_PATTERN = "filename_pattern"
MATCH_EXTENSION = "extension"

_REQUIRED_FALLBACK_EXTENSIONS: tuple[tuple[str, str], ...] = (
    (".toml", "toml"),
    (".asm", "asm"),
    (".s", "asm"),
    (".adb", "ada"),
    (".ads", "ada"),
    (".ada", "ada"),
    (".spark", "ada"),
    (".f", "fortran"),
    (".for", "fortran"),
    (".f90", "fortran"),
    (".f95", "fortran"),
    (".f03", "fortran"),
    (".f08", "fortran"),
)


@dataclass(frozen=True)
class LanguageDetectionResult:
    """Immutable result of a single detection lookup."""

    language_id: str | None
    matched_by: str | None
    matched_value: str | None
    candidates: tuple[str, ...] = ()
    is_ambiguous: bool = False

    @property
    def matched(self) -> bool:
        """Return ``True`` if a language id was detected."""
        return self.language_id is not None

    @classmethod
    def no_match(cls) -> LanguageDetectionResult:
        """Return the canonical 'no language detected' result."""
        return cls(language_id=None, matched_by=None, matched_value=None)


@dataclass(frozen=True)
class LanguageDetector:
    """Immutable detector built from deterministic registry metadata indexes."""

    extensions: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    filenames: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    filename_patterns: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def detect(self, name: str) -> LanguageDetectionResult:
        """Detect the language id for a file name or path, deterministically."""
        base = name.replace("\\", "/").rsplit("/", 1)[-1]

        by_filename = _match_tier(
            self.filenames, lambda token: token == base, MATCH_FILENAME
        )
        if by_filename is not None:
            return by_filename

        # VS Code metadata represents some leading-dot files (notably
        # ``.gitignore``) as extension tokens. For those names, exact basename
        # matching must still win before filename patterns and ordinary suffix
        # detection, otherwise a dotfile has no suffix and falls through to
        # content/legacy guessing.
        base_lower = base.lower()
        by_dotfile_extension = _match_tier(
            self.extensions, lambda token: token == base_lower, MATCH_FILENAME
        )
        if by_dotfile_extension is not None:
            return by_dotfile_extension

        by_pattern = _match_tier(
            self.filename_patterns,
            lambda token: _pattern_matches(token, base, name),
            MATCH_FILENAME_PATTERN,
        )
        if by_pattern is not None:
            return by_pattern

        suffix = _suffix(base)
        if suffix is None:
            return LanguageDetectionResult.no_match()
        by_extension = _match_tier(
            self.extensions, lambda token: token == suffix, MATCH_EXTENSION
        )
        if by_extension is not None:
            return by_extension
        by_required_fallback = _match_tier(
            _REQUIRED_FALLBACK_EXTENSIONS,
            lambda token: token == suffix,
            MATCH_EXTENSION,
        )
        return (
            by_required_fallback
            if by_required_fallback is not None
            else LanguageDetectionResult.no_match()
        )

    def detect_by_extension(self, extension: str) -> LanguageDetectionResult:
        """Detect using a bare file extension such as ``.py`` or ``py``."""
        suffix = _normalize_extension(extension)
        result = _match_tier(
            self.extensions, lambda token: token == suffix, MATCH_EXTENSION
        )
        if result is not None:
            return result
        fallback = _match_tier(
            _REQUIRED_FALLBACK_EXTENSIONS,
            lambda token: token == suffix,
            MATCH_EXTENSION,
        )
        return fallback if fallback is not None else LanguageDetectionResult.no_match()


def _suffix(base: str) -> str | None:
    dot = base.rfind(".")
    if dot <= 0:
        return None
    return base[dot:].lower()


def _normalize_extension(extension: str) -> str:
    extension = extension.lower()
    return extension if extension.startswith(".") else f".{extension}"


def _pattern_matches(pattern: str, base: str, full_name: str) -> bool:
    normalized = full_name.replace("\\", "/")
    return fnmatchcase(base, pattern) or fnmatchcase(normalized, pattern)


def _match_tier(
    index: Iterable[tuple[str, str]],
    predicate: Callable[[str], bool],
    matched_by: str,
) -> LanguageDetectionResult | None:
    language_ids: list[str] = []
    matched_value: str | None = None
    for token, language_id in index:
        if predicate(token):
            if matched_value is None:
                matched_value = token
            if language_id not in language_ids:
                language_ids.append(language_id)
    if not language_ids:
        return None
    return LanguageDetectionResult(
        language_id=language_ids[0],
        matched_by=matched_by,
        matched_value=matched_value,
        candidates=tuple(language_ids),
        is_ambiguous=len(language_ids) > 1,
    )


def build_language_detector(
    registry: ExtensionRegistry | None = None, root: Path | None = None
) -> LanguageDetector:
    """Build a :class:`LanguageDetector` from the manifest registry.

    ``registry`` defaults to the registry for the imported extension tree; pass a
    fixture registry (or ``root=<temp dir>``) to exercise edge cases. Index order
    follows the registry's deterministic manifest/language ordering.
    """
    if registry is None:
        registry = build_registry(root) if root is not None else build_registry()

    extensions: list[tuple[str, str]] = []
    filenames: list[tuple[str, str]] = []
    filename_patterns: list[tuple[str, str]] = []
    for manifest in registry.list_manifests():
        for language in manifest.languages:
            for extension in language.extensions:
                extensions.append(
                    (_normalize_extension(extension), language.language_id)
                )
            for filename in language.filenames:
                filenames.append((filename, language.language_id))
            for pattern in language.filename_patterns:
                filename_patterns.append((pattern, language.language_id))

    return LanguageDetector(
        extensions=tuple(extensions),
        filenames=tuple(filenames),
        filename_patterns=tuple(filename_patterns),
    )
