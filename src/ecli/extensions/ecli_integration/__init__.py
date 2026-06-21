# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""ECLI-owned deterministic adapter layer over the imported extension tree.

This package reads VS Code-style extension metadata from the read-only imported
extension tree under ``src/ecli/extensions/`` and exposes it as typed, immutable
Python data:

* #100 — ``package.json`` contribution registry (manifests, languages, grammars,
  snippets, configuration).
* #101 — TextMate grammar catalog, language detection, and the typed
  ``[extensions]`` configuration surface.

It is data-only: it never starts a VS Code extension host, never activates a
Node/TypeScript or Copilot runtime, never runs ``activationEvents`` or
``package.json`` scripts, never tokenizes or renders syntax, and never executes
any command.
"""

from __future__ import annotations

from .config import ExtensionLayerConfig, SyntaxEngine
from .grammar_catalog import (
    GrammarCatalog,
    TextMateGrammar,
    build_grammar_catalog,
)
from .language_detection import (
    LanguageDetectionResult,
    LanguageDetector,
    build_language_detector,
)
from .manifest import (
    ConfigurationContribution,
    ExtensionManifest,
    GrammarContribution,
    LanguageContribution,
    RegistryDiagnostic,
    SnippetContribution,
    parse_manifest,
)
from .paths import extensions_root
from .registry import (
    ExtensionRegistry,
    build_registry,
    discover_manifest_directories,
)


__all__ = [
    "ConfigurationContribution",
    "ExtensionLayerConfig",
    "ExtensionManifest",
    "ExtensionRegistry",
    "GrammarCatalog",
    "GrammarContribution",
    "LanguageContribution",
    "LanguageDetectionResult",
    "LanguageDetector",
    "RegistryDiagnostic",
    "SnippetContribution",
    "SyntaxEngine",
    "TextMateGrammar",
    "build_grammar_catalog",
    "build_language_detector",
    "build_registry",
    "discover_manifest_directories",
    "extensions_root",
    "parse_manifest",
]
