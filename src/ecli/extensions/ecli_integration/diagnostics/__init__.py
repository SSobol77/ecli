# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""ECLI-owned diagnostics framework for the F4 Diagnostics / Linter panel (#104).

ECLI does **not** implement linters or lint rules. It integrates existing
professional diagnostics tools (Ruff, mypy, clippy, ShellCheck, SonarQube, …)
through safe, ECLI-owned **provider adapters**. The framework exposes:

* a provider-neutral data model (:class:`Diagnostic`, :class:`DiagnosticsState`,
  :class:`DiagnosticSeverity`);
* a typed view of the ``[linter]`` config table (:class:`LinterLayerConfig`);
* a provider-metadata model (:class:`ProviderMetadata` with category/execution
  mode/status enums) and the executing-adapter protocol
  (:class:`DiagnosticsProvider`);
* a provider :class:`ProviderRegistry` (active vs planned, by language/extension,
  plus project-quality providers);
* the only active adapter in this build, :class:`RuffDiagnosticsProvider`, which
  runs Ruff through a fixed argv with a bounded timeout;
* a safe command contract (:func:`default_runner`, :class:`CommandResult`) and
  output parsers (:func:`parse_ruff_json`);
* a bounded result cache (:class:`DiagnosticsStore`);
* a coordinator (:class:`DiagnosticsService`) that the TUI panel drives.

The provider-framework concept is ported from `fnando/vscode-linter` (MIT); see
``THIRD_PARTY_NOTICES.md``. ECLI re-implements it in Python and executes no VS
Code runtime code, runs no extension manifest scripts, installs nothing, and
runs no project scan (SonarQube) during F4 rendering.
"""

from __future__ import annotations

from .command import (
    DEFAULT_TIMEOUT_SECONDS,
    CommandResult,
    CommandRunner,
    default_runner,
)
from .config import LinterLayerConfig
from .model import (
    Diagnostic,
    DiagnosticSeverity,
    DiagnosticsState,
    DiagnosticsStatus,
    sort_diagnostics,
)
from .parsers import ParseError, parse_ruff_json, short_detail
from .provider_metadata import (
    DiagnosticsProvider,
    ProviderCategory,
    ProviderExecutionMode,
    ProviderMetadata,
    ProviderResult,
    ProviderStatus,
)
from .providers import (
    PLANNED_PROVIDERS,
    RUFF_METADATA,
    SONARQUBE_PROVIDER,
    RuffDiagnosticsProvider,
)
from .registry import PlannedSummary, ProviderRegistry, build_default_registry
from .service import DiagnosticsService
from .store import DiagnosticsStore


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "PLANNED_PROVIDERS",
    "RUFF_METADATA",
    "SONARQUBE_PROVIDER",
    "CommandResult",
    "CommandRunner",
    "Diagnostic",
    "DiagnosticSeverity",
    "DiagnosticsProvider",
    "DiagnosticsService",
    "DiagnosticsState",
    "DiagnosticsStatus",
    "DiagnosticsStore",
    "LinterLayerConfig",
    "ParseError",
    "PlannedSummary",
    "ProviderCategory",
    "ProviderExecutionMode",
    "ProviderMetadata",
    "ProviderRegistry",
    "ProviderResult",
    "ProviderStatus",
    "RuffDiagnosticsProvider",
    "build_default_registry",
    "default_runner",
    "parse_ruff_json",
    "short_detail",
    "sort_diagnostics",
]
