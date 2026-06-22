# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/provider_metadata.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Provider metadata model for the diagnostics framework (#104).

A *provider* describes how ECLI integrates one existing, professional diagnostics
tool (Ruff, mypy, clippy, ShellCheck, SonarQube, …) through a safe, ECLI-owned
adapter. This module defines the metadata shape and the small executing-provider
protocol. ECLI never ships custom lint rules — providers only wrap external
tools.

The provider/linter metadata shape and capability concept are ported from the
multi-linter design of `fnando/vscode-linter` (MIT); see
``THIRD_PARTY_NOTICES.md``. ECLI re-implements them in Python and executes no VS
Code runtime code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .command import DEFAULT_TIMEOUT_SECONDS
from .model import Diagnostic


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "DiagnosticsProvider",
    "ProviderCategory",
    "ProviderExecutionMode",
    "ProviderMetadata",
    "ProviderResult",
    "ProviderStatus",
]


class ProviderCategory(StrEnum):
    """What kind of diagnostics a provider produces."""

    LINT = "lint"
    TYPECHECK = "typecheck"
    FORMAT_CHECK = "format_check"
    SCHEMA = "schema"
    SHELL = "shell"
    COMPILER = "compiler"
    LANGUAGE_SERVER = "language_server"
    STATIC_ANALYSIS = "static_analysis"
    BUILD_DIAGNOSTICS = "build_diagnostics"
    PROJECT_QUALITY = "project_quality"


class ProviderExecutionMode(StrEnum):
    """How/where a provider would run."""

    CURRENT_FILE = "current_file"
    WORKSPACE = "workspace"
    PROJECT_AWARE = "project_aware"
    PROJECT_SCAN = "project_scan"
    CACHED_EXTERNAL = "cached_external"


class ProviderStatus(StrEnum):
    """Lifecycle status of a provider in the current build."""

    BUNDLED = "bundled"  # active and expected to be present in this build
    SUPPORTED_EXTERNAL = "supported_external"  # active if the tool is installed
    PLANNED = "planned"  # roadmap target; metadata only, never executes
    UNAVAILABLE = "unavailable"  # registered but not usable in this build


@dataclass(frozen=True)
class ProviderResult:
    """Outcome of a single executing-provider collection.

    ``available`` is ``False`` only when the tool itself is missing. ``ok`` is
    ``True`` when collection completed (even with findings); ``ok`` is ``False``
    for runtime failures such as a timeout or unparseable output, in which case
    ``detail`` explains the failure briefly.
    """

    available: bool
    ok: bool
    diagnostics: tuple[Diagnostic, ...] = ()
    detail: str | None = None


@dataclass(frozen=True)
class ProviderMetadata:
    """Immutable, data-only description of a diagnostics provider."""

    id: str
    display_name: str
    tool_name: str
    category: ProviderCategory
    execution_mode: ProviderExecutionMode
    status: ProviderStatus
    language_ids: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    executable: str | None = None
    #: Documentation-only fixed argv template (``<path>`` is a placeholder).
    argv_contract: tuple[str, ...] | None = None
    #: Name of the output parser an adapter would use (documentation only here).
    parser: str | None = None
    config_files: tuple[str, ...] = ()
    docs_url: str | None = None
    install_hint: str | None = None
    #: Short label used when summarising planned providers in the panel.
    short_label: str = ""
    #: Whether an executing adapter for this provider exists in this build.
    runnable_in_build: bool = False
    #: Optional fixed panel lines (used by project-quality metadata).
    summary_lines: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_active(self) -> bool:
        """Return ``True`` for providers that can execute in this build."""
        return self.status in (
            ProviderStatus.BUNDLED,
            ProviderStatus.SUPPORTED_EXTERNAL,
        ) and self.runnable_in_build

    @property
    def is_planned(self) -> bool:
        """Return ``True`` for roadmap providers (metadata only, no execution)."""
        return self.status is ProviderStatus.PLANNED

    @property
    def label(self) -> str:
        """Return the short label, defaulting to the display name."""
        return self.short_label or self.display_name


@runtime_checkable
class DiagnosticsProvider(Protocol):
    """Protocol implemented by every executing diagnostics adapter."""

    name: str
    metadata: ProviderMetadata

    def applies_to(self, file_path: str) -> bool:
        """Return ``True`` when this provider can analyse *file_path*."""
        ...

    def is_available(self) -> bool:
        """Return ``True`` when the backing tool can be invoked (no execution)."""
        ...

    def collect(
        self, file_path: str, text: str, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> ProviderResult:
        """Collect diagnostics for *file_path* whose current contents are *text*."""
        ...
