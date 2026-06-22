# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_states.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""F4 state tests using the shipped provider registry (#104)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ecli.extensions.ecli_integration.diagnostics import (
    DiagnosticsService,
    DiagnosticsStatus,
    ProviderRegistry,
    RuffDiagnosticsProvider,
    build_default_registry,
)


def _service(tmp_path: Path) -> DiagnosticsService:
    return DiagnosticsService(
        registry=build_default_registry(), workspace_root=tmp_path
    )


# Exact product-spec messages for planned languages.
_PLANNED_MESSAGES = [
    (
        "App.java",
        "No active bundled diagnostics provider for Java in this build.",
        "Planned providers: JDT LS, Checkstyle, PMD, SpotBugs, Maven/Gradle diagnostics.",
    ),
    (
        "index.php",
        "No active bundled diagnostics provider for PHP in this build.",
        "Planned providers: PHPStan, Psalm, PHP_CodeSniffer.",
    ),
    (
        "pyproject.toml",
        "No active bundled diagnostics provider for TOML in this build.",
        "Planned provider: Taplo.",
    ),
    (
        "config.yaml",
        "No active bundled diagnostics provider for YAML in this build.",
        "Planned providers: yamllint, YAML schema diagnostics.",
    ),
    (
        "Dockerfile",
        "No active bundled diagnostics provider for Dockerfile in this build.",
        "Planned provider: Hadolint.",
    ),
    (
        "main.rs",
        "No active bundled diagnostics provider for Rust in this build.",
        "Planned providers: rust-analyzer, cargo check, cargo clippy.",
    ),
    (
        "main.c",
        "No active bundled diagnostics provider for C/C++ in this build.",
        "Planned providers: clangd, clang-tidy, cppcheck.",
    ),
    (
        "boot.asm",
        "No active bundled diagnostics provider for assembler in this build.",
        "Planned providers depend on syntax: nasm, yasm, GNU as/GAS.",
    ),
    (
        "styles.css",
        "No active bundled diagnostics provider for CSS in this build.",
        "Planned providers: Stylelint, Biome.",
    ),
    (
        "App.tsx",
        "No active bundled diagnostics provider for TSX in this build.",
        "Planned providers: Biome, ESLint.",
    ),
    (
        "data.json",
        "No active bundled diagnostics provider for JSON in this build.",
        "Planned providers: Biome, JSON schema diagnostics.",
    ),
    (
        "run.sh",
        "No active bundled diagnostics provider for shell scripts in this build.",
        "Planned provider: ShellCheck.",
    ),
]


@pytest.mark.parametrize(("filename", "detail", "hint"), _PLANNED_MESSAGES)
def test_planned_state_messages(
    tmp_path: Path, filename: str, detail: str, hint: str
) -> None:
    service = _service(tmp_path)
    state = service.collect(str(tmp_path / filename), text="x")
    assert state.status is DiagnosticsStatus.PLANNED
    assert state.detail == detail
    assert state.hint == hint


def test_python_ruff_missing_executable_state(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        active_providers=(RuffDiagnosticsProvider(executable="ruff-not-here-xyz"),),
        labels={"python": "Python"},
    )
    service = DiagnosticsService(registry=registry, workspace_root=tmp_path)
    state = service.collect(str(tmp_path / "mod.py"), text="import os\n")
    assert state.status is DiagnosticsStatus.PROVIDER_UNAVAILABLE
    assert state.detail == (
        "Ruff provider is registered for Python but the Ruff executable is not "
        "available."
    )
    assert state.hint == (
        "This build expects Ruff to be provided by the ECLI diagnostics toolchain."
    )


def test_sonarqube_planned_project_quality_is_exposed() -> None:
    service = DiagnosticsService(registry=build_default_registry())
    providers = service.project_quality_providers()
    sonar = next(p for p in providers if p.id == "sonarqube")
    assert sonar.status.value == "planned"
    assert sonar.category.value == "project_quality"
    assert sonar.summary_lines == (
        "SonarQube project-quality provider is planned.",
        "Future mode: cached/manual project scan, not per-render linting.",
    )


def test_outside_workspace_current_file_is_not_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    service = DiagnosticsService(
        registry=build_default_registry(), workspace_root=workspace
    )
    state = service.collect(str(tmp_path / "outside.py"), text="import os\n")
    # Ruff is a safe current-file (stdin) provider, so a file outside the
    # workspace is linted rather than blocked at the workspace boundary.
    assert state.status is not DiagnosticsStatus.OUTSIDE_WORKSPACE
    if state.status in (DiagnosticsStatus.OK, DiagnosticsStatus.NO_DIAGNOSTICS):
        assert state.external is True


def test_no_active_file_state() -> None:
    service = DiagnosticsService(registry=build_default_registry())
    assert service.collect(None).status is DiagnosticsStatus.NO_ACTIVE_FILE


def test_disabled_state() -> None:
    service = DiagnosticsService(
        config={"linter": {"enabled": False}}, registry=build_default_registry()
    )
    assert service.collect("a.py", text="x").status is DiagnosticsStatus.DISABLED
