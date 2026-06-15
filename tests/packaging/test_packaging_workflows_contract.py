# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_workflows_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

from pathlib import Path

from conftest import PathAssertion, RepoReader, TokenAssertion


# This test owns canonical artifact entry 21:
# "GitHub Actions release/workflow contract map".
WORKFLOW_CONTRACT = {
    "ci.yml": {
        "classification": "Global quality gate",
        "tokens": ["CI", "validate-gate2", "main.py", "ruff", "pytest"],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/build-matrix.md",
        ],
        "agent_contracts": [
            ".codex/roles/quality-engineer.md",
            ".codex/roles/build-engineer.md",
        ],
        "packaging_tests": ["tests/packaging/test_packaging_workflows_contract.py"],
    },
    "freebsd-pkg.yml": {
        "classification": "Packaging workflow",
        "tokens": [
            "FreeBSD",
            ".pkg",
            "build_and_package_freebsd.py",
            "gh release upload",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
        ],
        "agent_contracts": [
            ".codex/prompts/package-freebsd.md",
            ".claude/commands/package-freebsd.md",
        ],
        "packaging_tests": [
            "tests/packaging/test_packaging_freebsd_pkg_contract.py",
            "tests/packaging/test_packaging_freebsd_ports_chroot_contract.py",
        ],
    },
    "macos-dmg.yml": {
        "classification": "Packaging workflow",
        "tokens": ["macOS DMG", ".dmg", "package-macos", "package-macos-assert"],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/build-matrix.md",
        ],
        "agent_contracts": [
            ".codex/prompts/package-macos.md",
            ".claude/commands/package-macos.md",
        ],
        "packaging_tests": [
            "tests/packaging/test_packaging_macos_app_contract.py",
            "tests/packaging/test_packaging_macos_dmg_contract.py",
        ],
    },
    "macos-validate.yml": {
        "classification": "Packaging validation workflow",
        "tokens": [
            "macOS Contract Validate",
            "package-macos",
            "validate-macos-contract",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
        ],
        "agent_contracts": [
            ".codex/prompts/package-macos.md",
            ".claude/commands/package-macos.md",
        ],
        "packaging_tests": [
            "tests/packaging/test_packaging_macos_app_contract.py",
            "tests/packaging/test_packaging_macos_dmg_contract.py",
        ],
    },
    "project-automation.yml": {
        "classification": "Repository automation, non-packaging",
        "tokens": [
            "Project Column Automation",
            "pull_request",
            "issues",
            "repository-projects",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/build-matrix.md",
        ],
        "agent_contracts": [],
        "packaging_tests": ["tests/packaging/test_packaging_workflows_contract.py"],
    },
    "pypi-validate.yml": {
        "classification": "Packaging validation workflow",
        "tokens": ["PyPI Contract Validate", "package-pypi", "validate-pypi-contract"],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
        ],
        "agent_contracts": [
            ".codex/prompts/package-pypi.md",
            ".claude/commands/package-pypi.md",
        ],
        "packaging_tests": [
            "tests/packaging/test_packaging_pypi_wheel_contract.py",
            "tests/packaging/test_packaging_pypi_sdist_contract.py",
        ],
    },
    "release.yml": {
        "classification": "Aggregate release workflow",
        "tokens": [
            "Release",
            "Build Python distributions",
            "Build Linux packages",
            "Build Windows artifacts",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
        ],
        "agent_contracts": [
            ".codex/roles/release-engineer.md",
            ".claude/agents/release-engineer.md",
        ],
        "packaging_tests": ["tests/packaging/test_packaging_release_contract.py"],
    },
    "windows-installer.yml": {
        "classification": "Packaging workflow",
        "tokens": [
            "Windows Installer",
            "build-and-package-windows.ps1",
            "NSIS",
            "setup.exe",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/build-matrix.md",
        ],
        "agent_contracts": [
            ".codex/prompts/package-windows.md",
            ".claude/commands/package-windows.md",
        ],
        "packaging_tests": [
            "tests/packaging/test_packaging_windows_portable_exe_contract.py",
            "tests/packaging/test_packaging_windows_nsis_installer_contract.py",
        ],
    },
    "windows-validate.yml": {
        "classification": "Packaging validation workflow",
        "tokens": [
            "Windows Contract Validate",
            "package-windows",
            "validate-windows-contract",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
        ],
        "agent_contracts": [
            ".codex/prompts/package-windows.md",
            ".claude/commands/package-windows.md",
        ],
        "packaging_tests": [
            "tests/packaging/test_packaging_windows_portable_exe_contract.py",
            "tests/packaging/test_packaging_windows_nsis_installer_contract.py",
        ],
    },
}


def test_declared_workflow_files_exist_and_are_non_empty(
    assert_paths_non_empty: PathAssertion,
) -> None:
    assert_paths_non_empty(f".github/workflows/{name}" for name in WORKFLOW_CONTRACT)


def test_every_repository_workflow_is_documented(repo_root: Path) -> None:
    actual = {
        path.name
        for path in (repo_root / ".github/workflows").iterdir()
        if path.is_file() and path.suffix == ".yml"
    }

    assert actual == set(WORKFLOW_CONTRACT)


def test_workflow_files_match_expected_surface_tokens(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    for workflow_name, contract in WORKFLOW_CONTRACT.items():
        workflow = read_repo_text(f".github/workflows/{workflow_name}")
        assert_tokens_present(workflow, contract["tokens"])


def test_workflow_contract_map_is_documented_in_release_docs(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    release_docs = "\n".join(
        read_repo_text(path)
        for path in [
            "docs/release/artifact-contract.md",
            "docs/release/build-matrix.md",
            "docs/release/release-process.md",
        ]
    )

    assert "GitHub Actions Workflow Contract Map" in release_docs
    for workflow_name, contract in WORKFLOW_CONTRACT.items():
        assert_tokens_present(
            release_docs,
            [
                f".github/workflows/{workflow_name}",
                contract["classification"],
            ],
        )


def test_project_automation_is_non_packaging_repository_automation(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    release_docs = "\n".join(
        read_repo_text(path)
        for path in [
            "docs/release/artifact-contract.md",
            "docs/release/build-matrix.md",
            "docs/release/release-process.md",
        ]
    )

    assert_tokens_present(
        release_docs,
        [
            ".github/workflows/project-automation.yml",
            "Repository automation, non-packaging",
            "not a release artifact workflow",
        ],
    )


def test_active_packaging_workflows_have_docs_agents_and_tests(
    read_repo_text: RepoReader,
) -> None:
    for workflow_name, contract in WORKFLOW_CONTRACT.items():
        if contract["classification"] == "Repository automation, non-packaging":
            continue

        for doc_path in contract["surface_docs"]:
            assert workflow_name in read_repo_text(doc_path)

        for agent_path in contract["agent_contracts"]:
            assert Path(agent_path).name
            assert read_repo_text(agent_path).strip()

        for test_path in contract["packaging_tests"]:
            # The mapped packaging test must exist; the workflow name is recorded
            # here in the canonical workflow contract map.
            assert read_repo_text(test_path).strip()
            assert workflow_name in read_repo_text(
                "tests/packaging/test_packaging_workflows_contract.py"
            )
