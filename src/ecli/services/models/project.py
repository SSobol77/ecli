# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/models/project.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Typed project discovery models for the Phase 1 ProjectService."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ProjectDiagnosticLevel(StrEnum):
    """Severity for project service diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ProjectDiagnostic:
    """Structured, user-readable project service diagnostic."""

    level: ProjectDiagnosticLevel
    message: str
    path: str | None = None
    code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable diagnostic dictionary."""
        return {
            "level": self.level.value,
            "message": self.message,
            "path": self.path,
            "code": self.code,
        }


@dataclass(frozen=True)
class ProjectMarker:
    """Project root marker found during upward discovery."""

    name: str
    path: Path
    priority: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable marker dictionary."""
        return {"name": self.name, "path": str(self.path), "priority": self.priority}


@dataclass(frozen=True)
class ProjectMetadata:
    """Typed metadata extracted from a discovered project root."""

    name: str
    root: Path
    vcs: str | None
    markers: tuple[str, ...]
    primary_language_hints: tuple[str, ...]
    project_config_path: Path | None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable project metadata dictionary."""
        return {
            "name": self.name,
            "root": str(self.root),
            "vcs": self.vcs,
            "markers": list(self.markers),
            "primary_language_hints": list(self.primary_language_hints),
            "project_config_path": (
                None
                if self.project_config_path is None
                else str(self.project_config_path)
            ),
        }


@dataclass(frozen=True)
class ProjectDiscoveryResult:
    """Result of deterministic project root discovery."""

    root: Path
    metadata: ProjectMetadata
    diagnostics: tuple[ProjectDiagnostic, ...] = field(default_factory=tuple)
    discovered: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable discovery result dictionary."""
        return {
            "root": str(self.root),
            "metadata": self.metadata.as_dict(),
            "diagnostics": [diagnostic.as_dict() for diagnostic in self.diagnostics],
            "discovered": self.discovered,
        }


@dataclass(frozen=True)
class ProjectPathResolutionResult:
    """Structured result for project-aware path resolution."""

    path: Path
    inside_root: bool
    diagnostics: tuple[ProjectDiagnostic, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable path resolution result dictionary."""
        return {
            "path": str(self.path),
            "inside_root": self.inside_root,
            "diagnostics": [diagnostic.as_dict() for diagnostic in self.diagnostics],
        }
