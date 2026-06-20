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
        "tokens": ["CI", "validate-release-contract", "main.py", "ruff", "pytest"],
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
            "Official GitHub Release publication waits",
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
            "verify_release_assets.py",
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


def test_release_workflow_uses_docker_package_targets_not_legacy_shell(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")

    # The Linux package job must drive the containerized DEB/RPM builds through the
    # Makefile targets, which now invoke the canonical Python packaging scripts
    # inside the Docker helpers.
    assert "make package-deb-docker" in release
    assert "make package-rpm-docker" in release
    # No removed shell packaging entrypoint may reappear in the release workflow
    # (regression guard for #93).
    assert "build-and-package-deb.sh" not in release
    assert "build-and-package-rpm.sh" not in release


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


# --------------------------------------------------------------------------- #
# #93 regression guard: the Docker DEB/RPM builds run as root and leave
# root-owned files in build/, dist/, and releases/<version>/ (including
# releases/<version>/.linux.env). The host-side openSUSE build then fails with
# PermissionError when it tries to rewrite .linux.env. The release workflow must
# reset ownership of every Docker-touched output path -- including releases/ --
# after each Docker package build and before the openSUSE build.
# --------------------------------------------------------------------------- #


def test_release_workflow_resets_release_ownership_after_docker_builds(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")

    # Anchor on the 'run:' step bodies so prose/comments that mention these make
    # targets (e.g. the reset-step comments) cannot be mistaken for the steps.
    deb_build = release.index("run: make package-deb-docker")
    rpm_build = release.index("run: make package-rpm-docker")
    opensuse_build = release.index("run: make package-opensuse-rpm")

    deb_reset = release.index("Reset ownership after Docker DEB build")
    rpm_reset = release.index("Reset ownership after Docker RPM build")

    # 1 & 2: an ownership reset exists after each Docker package build.
    assert deb_build < deb_reset
    assert rpm_build < rpm_reset

    # 4: both resets happen before the host-side openSUSE build that rewrites
    # releases/<version>/.linux.env.
    assert deb_reset < opensuse_build
    assert rpm_reset < opensuse_build

    # 3: each reset must cover the release output directory, not only build/ and
    # dist/, because that is where the root-owned .linux.env lives.
    deb_reset_block = release[deb_reset:rpm_build]
    rpm_reset_block = release[rpm_reset:opensuse_build]
    for block in (deb_reset_block, rpm_reset_block):
        assert "chown -R" in block
        assert "releases" in block


def test_release_workflow_does_not_ignore_opensuse_failure(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")

    # Anchor on the 'run:' step body, not the prose mention in the reset comment.
    opensuse = release.index("run: make package-opensuse-rpm")

    # 5: the openSUSE build line must not be neutralized with '|| true'.
    line_start = release.rfind("\n", 0, opensuse) + 1
    line_end = release.index("\n", opensuse)
    assert "|| true" not in release[line_start:line_end]

    # ...and the step that owns it must not opt into continue-on-error.
    step_start = release.rfind("- name:", 0, opensuse)
    next_step = release.index("- name:", opensuse)
    assert "continue-on-error" not in release[step_start:next_step]


def test_release_workflow_preserves_exact_21_asset_contract(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")

    # 6: the exact-21 release contract is unchanged -- the workflow still
    # assembles/verifies exactly 21 assets through the canonical verifier.
    assert "Assemble and verify exact 21 GitHub Release assets" in release
    assert "exactly 21 physical GitHub Release" in release
    assert "verify_release_assets.py" in release


def test_makefile_docker_package_targets_reset_release_ownership(
    read_repo_text: RepoReader,
) -> None:
    # Local 'make package-*-docker' targets bind-mount the repo into a root
    # container and leave root-owned output too. They must reset ownership of the
    # release dir so a subsequent local 'make package-opensuse-rpm' is not blocked
    # by the same #93 PermissionError.
    makefile = read_repo_text("Makefile")
    for target in ("package-deb-docker", "package-rpm-docker"):
        start = makefile.index(f"\n{target}:")
        end = makefile.index("\n.PHONY:", start)
        recipe = makefile[start:end]
        assert "chown" in recipe
        assert "$(RELEASE_DIR)" in recipe
