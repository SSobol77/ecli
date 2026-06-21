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

"""ECLI-owned deterministic adapter layer over the imported extension tree (#100).

This package reads VS Code-style ``package.json`` contribution metadata from the
read-only imported extension tree under ``src/ecli/extensions/`` and exposes it
as typed, immutable Python data. It is data-only: it never starts a VS Code
extension host, never activates a Node/TypeScript or Copilot runtime, never runs
``activationEvents`` or ``package.json`` scripts, and never executes any command.
"""

from __future__ import annotations

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
    "ExtensionManifest",
    "ExtensionRegistry",
    "GrammarContribution",
    "LanguageContribution",
    "RegistryDiagnostic",
    "SnippetContribution",
    "build_registry",
    "discover_manifest_directories",
    "extensions_root",
    "parse_manifest",
]
