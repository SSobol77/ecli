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
* #102 — extension-backed syntax-service boundary that resolves language/grammar
  metadata for editor rendering while keeping the legacy highlighter
  authoritative.
* #103 — extension-backed theme registry from ``contributes.themes`` and VS Code
  theme JSON, including tokenColor scope resolution.

It is data-only: it never starts a VS Code extension host, never activates a
Node/TypeScript or Copilot runtime, never runs ``activationEvents`` or
``package.json`` scripts, and never executes any command. Tokenization is limited
to reading imported TextMate grammar JSON through the optional Python tokenizer
and degrades to the legacy highlighter when unavailable.
"""

from __future__ import annotations

from .config import ExtensionLayerConfig, SyntaxEngine
from .diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    DiagnosticsProvider,
    DiagnosticsService,
    DiagnosticsState,
    DiagnosticsStatus,
    DiagnosticsStore,
    LinterLayerConfig,
    ProviderCategory,
    ProviderExecutionMode,
    ProviderMetadata,
    ProviderRegistry,
    ProviderResult,
    ProviderStatus,
    RuffDiagnosticsProvider,
    build_default_registry,
    sort_diagnostics,
)
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
    ThemeContribution,
    parse_manifest,
)
from .paths import extensions_root
from .registry import (
    ExtensionRegistry,
    build_registry,
    discover_manifest_directories,
)
from .syntax_service import (
    EXTENSION_TOKENIZATION_AVAILABLE,
    SYNTAX_ENGINE_EXTENSION,
    SYNTAX_ENGINE_LEGACY,
    LineHighlighter,
    SyntaxResolution,
    SyntaxService,
    build_syntax_service,
)
from .textmate_tokenizer import TEXTMATE_AVAILABLE, TextMateTokenizer, load_tokenizer
from .theme_bridge import scope_to_category, tokens_to_spans
from .theme_registry import (
    TARGET_THEME_NAMES,
    TARGET_THEME_NUMBERS,
    THEME_NUMBERING_POLICY,
    ExtensionTheme,
    TextMateResolvedStyle,
    TextMateTokenColor,
    ThemeRegistry,
    build_theme_registry,
    cached_theme_registry,
)


__all__ = [
    "EXTENSION_TOKENIZATION_AVAILABLE",
    "SYNTAX_ENGINE_EXTENSION",
    "SYNTAX_ENGINE_LEGACY",
    "TEXTMATE_AVAILABLE",
    "ConfigurationContribution",
    "Diagnostic",
    "DiagnosticSeverity",
    "DiagnosticsProvider",
    "DiagnosticsService",
    "DiagnosticsState",
    "DiagnosticsStatus",
    "DiagnosticsStore",
    "ExtensionLayerConfig",
    "ExtensionManifest",
    "ExtensionRegistry",
    "ExtensionTheme",
    "GrammarCatalog",
    "GrammarContribution",
    "LanguageContribution",
    "LanguageDetectionResult",
    "LanguageDetector",
    "LineHighlighter",
    "LinterLayerConfig",
    "ProviderCategory",
    "ProviderExecutionMode",
    "ProviderMetadata",
    "ProviderRegistry",
    "ProviderResult",
    "ProviderStatus",
    "RegistryDiagnostic",
    "RuffDiagnosticsProvider",
    "SnippetContribution",
    "SyntaxEngine",
    "SyntaxResolution",
    "SyntaxService",
    "TextMateGrammar",
    "TextMateResolvedStyle",
    "TextMateTokenColor",
    "TextMateTokenizer",
    "ThemeContribution",
    "ThemeRegistry",
    "TARGET_THEME_NAMES",
    "TARGET_THEME_NUMBERS",
    "THEME_NUMBERING_POLICY",
    "build_default_registry",
    "build_grammar_catalog",
    "build_language_detector",
    "build_registry",
    "build_syntax_service",
    "build_theme_registry",
    "cached_theme_registry",
    "discover_manifest_directories",
    "extensions_root",
    "load_tokenizer",
    "parse_manifest",
    "scope_to_category",
    "sort_diagnostics",
    "tokens_to_spans",
]
