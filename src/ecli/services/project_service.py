# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/project_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Phase 1 project discovery and workspace context service."""

from __future__ import annotations

from pathlib import Path

from ecli.services.config_service import ConfigService
from ecli.services.models.project import (
    ProjectDiagnostic,
    ProjectDiagnosticLevel,
    ProjectDiscoveryResult,
    ProjectMarker,
    ProjectMetadata,
)


PROJECT_MARKERS: tuple[str, ...] = (
    ".ecli.toml",
    ".ecli",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    ".git",
)

LANGUAGE_HINT_MARKERS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("setup.cfg", "python"),
    ("package.json", "javascript/typescript"),
    ("Cargo.toml", "rust"),
    ("go.mod", "go"),
    ("pom.xml", "java"),
    ("build.gradle", "java"),
    ("Makefile", "make"),
    ("Dockerfile", "docker"),
)

FORBIDDEN_PATH_EXPANSIONS: tuple[str, ...] = ("$HOME", "${HOME}", "$(", "`")


class UnsafeProjectPathError(ValueError):
    """Raised when project-safe path resolution rejects an unsafe path."""


class ProjectService:
    """Project workspace discovery and path normalization service."""

    def __init__(
        self,
        discovery: ProjectDiscoveryResult,
        diagnostics: tuple[ProjectDiagnostic, ...] = (),
    ) -> None:
        """Initialize ProjectService from a discovery result."""
        self._discovery = discovery
        self._diagnostics = (*discovery.diagnostics, *diagnostics)

    @classmethod
    def discover(cls, start_path: Path | str | None = None) -> ProjectDiscoveryResult:
        """Discover project root and metadata from a file or directory path."""
        start = Path.cwd() if start_path is None else Path(start_path)
        start_dir = _normalize_start_directory(start)
        diagnostics: list[ProjectDiagnostic] = []

        for candidate in _walk_up(start_dir):
            markers = _find_project_markers(candidate)
            if markers:
                metadata = _build_metadata(candidate, markers)
                diagnostics.append(
                    ProjectDiagnostic(
                        level=ProjectDiagnosticLevel.INFO,
                        path=str(candidate),
                        code="project.discovery.marker_found",
                        message=(
                            f"Discovered project root from marker {metadata.markers[0]}"
                        ),
                    )
                )
                return ProjectDiscoveryResult(
                    root=candidate,
                    metadata=metadata,
                    diagnostics=tuple(diagnostics),
                    discovered=True,
                )

        metadata = _build_metadata(start_dir, ())
        diagnostics.append(
            ProjectDiagnostic(
                level=ProjectDiagnosticLevel.INFO,
                path=str(start_dir),
                code="project.discovery.fallback",
                message="No project marker found; using normalized start directory",
            )
        )
        return ProjectDiscoveryResult(
            root=start_dir,
            metadata=metadata,
            diagnostics=tuple(diagnostics),
            discovered=False,
        )

    @classmethod
    def from_discovery(cls, discovery: ProjectDiscoveryResult) -> ProjectService:
        """Create a service instance from an existing discovery result."""
        return cls(discovery)

    @property
    def root(self) -> Path:
        """Absolute path to the project root."""
        return self._discovery.root

    @property
    def metadata(self) -> ProjectMetadata:
        """Return project metadata captured during discovery."""
        return self._discovery.metadata

    @property
    def diagnostics(self) -> tuple[ProjectDiagnostic, ...]:
        """Return service diagnostics accumulated so far."""
        return self._diagnostics

    def resolve_path(self, relative_or_absolute: str | Path) -> Path:
        """Resolve a project-relative or absolute path without root confinement."""
        raw_path = _reject_shell_expansion(relative_or_absolute)
        if raw_path.is_absolute():
            return raw_path.resolve(strict=False)
        return (self.root / raw_path).resolve(strict=False)

    def resolve_path_safe(self, relative_or_absolute: str | Path) -> Path:
        """Resolve a path and reject paths escaping the project root."""
        resolved = self.resolve_path(relative_or_absolute)
        root = self.root.resolve(strict=False)
        if _is_relative_to(resolved, root):
            return resolved
        raise UnsafeProjectPathError(
            f"Resolved path escapes project root: {resolved} is outside {root}"
        )

    def get_project_config_path(self) -> Path | None:
        """Return the project-local ECLI config path if present."""
        return self.metadata.project_config_path

    def get_effective_config(self, user_config: ConfigService) -> ConfigService:
        """Return effective config bridge for Phase 1 ProjectService.

        The current ConfigService does not retain the source path for the already
        loaded user configuration. Re-loading with only project_config_path would
        discard that caller-provided user layer, so Phase 1 preserves the supplied
        ConfigService and records an integration diagnostic for ServiceRegistry.
        """
        project_config_path = self.get_project_config_path()
        if project_config_path is not None:
            self._diagnostics = (
                *self._diagnostics,
                ProjectDiagnostic(
                    level=ProjectDiagnosticLevel.WARNING,
                    path=str(project_config_path),
                    code="project.config.integration_deferred",
                    message=(
                        "Project-local config was discovered, but full user/project "
                        "merge is deferred until ServiceRegistry wires source paths"
                    ),
                ),
            )
        return user_config


def _normalize_start_directory(start: Path) -> Path:
    normalized = start
    if normalized.exists() and normalized.is_file():
        normalized = normalized.parent
    return normalized.resolve(strict=False)


def _walk_up(start_dir: Path) -> tuple[Path, ...]:
    directories = [start_dir]
    directories.extend(start_dir.parents)
    return tuple(directories)


def _find_project_markers(root: Path) -> tuple[ProjectMarker, ...]:
    markers: list[ProjectMarker] = []
    for priority, marker_name in enumerate(PROJECT_MARKERS):
        marker_path = root / marker_name
        if marker_path.exists():
            markers.append(
                ProjectMarker(name=marker_name, path=marker_path, priority=priority)
            )
    return tuple(markers)


def _build_metadata(root: Path, markers: tuple[ProjectMarker, ...]) -> ProjectMetadata:
    marker_names = tuple(marker.name for marker in markers)
    return ProjectMetadata(
        name=root.name or str(root),
        root=root,
        vcs="git" if ".git" in marker_names else None,
        markers=marker_names,
        primary_language_hints=_extract_language_hints(root),
        project_config_path=_project_config_path(root),
    )


def _extract_language_hints(root: Path) -> tuple[str, ...]:
    hints: list[str] = []
    for marker_name, language in LANGUAGE_HINT_MARKERS:
        if (root / marker_name).exists() and language not in hints:
            hints.append(language)
    return tuple(hints)


def _project_config_path(root: Path) -> Path | None:
    config_path = root / ".ecli.toml"
    if config_path.is_file():
        return config_path
    return None


def _reject_shell_expansion(path_value: str | Path) -> Path:
    raw = str(path_value)
    if raw.startswith("~"):
        raise UnsafeProjectPathError("Shell-style home expansion is not allowed")
    if any(token in raw for token in FORBIDDEN_PATH_EXPANSIONS):
        raise UnsafeProjectPathError(
            "Shell-style variable or command expansion is not allowed"
        )
    return Path(raw)


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True
