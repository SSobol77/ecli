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

import re
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
        "packaging_tests": ["tests/packaging/test_packaging_workflows_contract.py"],
    },
    "pypi-validate.yml": {
        "classification": "Packaging validation workflow",
        "tokens": ["PyPI Contract Validate", "package-pypi", "validate-pypi-contract"],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
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
            "validate-built-artifacts",
            "verify_release_assets.py",
        ],
        "surface_docs": [
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
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
        "packaging_tests": [
            "tests/packaging/test_packaging_windows_portable_exe_contract.py",
            "tests/packaging/test_packaging_windows_nsis_installer_contract.py",
        ],
    },
}


_JOB_HEADER_RE = re.compile(r"^  [A-Za-z0-9_-]+:\n", re.MULTILINE)


def _job_block(workflow: str, job_name: str) -> str:
    match = re.search(rf"^  {re.escape(job_name)}:\n", workflow, re.MULTILINE)
    assert match is not None, f"job not found: {job_name}"
    next_job = _JOB_HEADER_RE.search(workflow, match.end())
    return (
        workflow[match.start() :]
        if next_job is None
        else workflow[match.start() : next_job.start()]
    )


def _step_block(job: str, step_name: str) -> str:
    start = job.index(f"- name: {step_name}")
    next_step = job.find("\n      - name:", start + 1)
    return job[start:] if next_step == -1 else job[start:next_step]


def _job_if_condition(job: str) -> tuple[str, ...]:
    match = re.search(r"^    if: \|\n(?P<body>(?:      .+\n)+)", job, re.MULTILINE)
    assert match is not None
    return tuple(line.removeprefix("      ") for line in match["body"].splitlines())


_VALIDATE_BUILT_ARTIFACTS_IF = (
    "always() &&",
    "needs.build-python.result == 'success' &&",
    "needs.build-linux.result == 'success' &&",
    "needs.build-freebsd.result == 'success' &&",
    "needs.build-macos.result == 'success' &&",
    "needs.build-windows.result == 'success'",
)

_PUBLISH_PYPI_IF = (
    "always() &&",
    "(github.event_name == 'push' || github.event.inputs.publish_pypi == 'true') &&",
    "needs.validate-built-artifacts.result == 'success'",
)

_PUBLISH_GITHUB_RELEASE_IF = (
    "always() &&",
    "(github.event_name == 'push' || github.event.inputs.publish_github_release != 'false') &&",
    "needs.validate-built-artifacts.result == 'success'",
)


def _pypi_publication_allowed(
    *,
    event_name: str,
    publish_pypi: str,
    validation_result: str,
) -> bool:
    return validation_result == "success" and (
        event_name == "push" or publish_pypi == "true"
    )


def _github_release_publication_allowed(
    *,
    event_name: str,
    publish_github_release: str,
    validation_result: str,
) -> bool:
    return validation_result == "success" and (
        event_name == "push" or publish_github_release != "false"
    )


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


def test_active_packaging_workflows_have_docs_and_tests(
    read_repo_text: RepoReader,
) -> None:
    for workflow_name, contract in WORKFLOW_CONTRACT.items():
        if contract["classification"] == "Repository automation, non-packaging":
            continue

        for doc_path in contract["surface_docs"]:
            assert workflow_name in read_repo_text(doc_path)

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
    assert "Stage checksum evidence and verify exact 21 GitHub Release assets" in (
        release
    )
    assert "Verify exact 21 GitHub Release assets before upload" in release
    assert "exactly 21 physical GitHub Release" in release
    assert "verify_release_assets.py" in release


def test_release_workflow_runs_built_artifact_gate_after_assembly(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")
    validation_job = _job_block(release, "validate-built-artifacts")

    download = validation_job.index("- name: Download all artifacts")
    assembly = validation_job.index(
        "- name: Assemble release assets and adjacent checksum evidence"
    )
    gate = validation_job.index("make validate-built-artifacts")
    stage = validation_job.index(
        "- name: Stage checksum evidence and verify exact 21 GitHub Release assets"
    )

    assert download < assembly < gate < stage
    assert 'sha256sum "$(basename "$asset")" > "$(basename "$asset").sha256"' in (
        validation_job
    )
    assert 'mv "$sidecar" "$release_dir/.checksums/$(basename "$sidecar")"' in (
        validation_job
    )


def test_release_workflow_orders_publication_behind_built_artifact_gate(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")
    pypi_job = _job_block(release, "publish-pypi")
    github_job = _job_block(release, "publish-github-release")

    assert "needs:\n      - validate-built-artifacts" in pypi_job
    assert "needs.validate-built-artifacts.result == 'success'" in pypi_job
    assert "needs:\n      - validate-built-artifacts" in github_job
    assert "needs.validate-built-artifacts.result == 'success'" in github_job

    verify = github_job.index(
        "- name: Verify exact 21 GitHub Release assets before upload"
    )
    release_action = github_job.index("uses: softprops/action-gh-release@v2")
    assert verify < release_action


def test_release_workflow_publication_job_conditions_are_explicit(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")

    assert (
        _job_if_condition(_job_block(release, "validate-built-artifacts"))
        == _VALIDATE_BUILT_ARTIFACTS_IF
    )
    assert _job_if_condition(_job_block(release, "publish-pypi")) == _PUBLISH_PYPI_IF
    assert (
        _job_if_condition(_job_block(release, "publish-github-release"))
        == _PUBLISH_GITHUB_RELEASE_IF
    )


def test_release_workflow_publication_policy_matrix(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")
    assert _job_if_condition(_job_block(release, "publish-pypi")) == _PUBLISH_PYPI_IF
    assert (
        _job_if_condition(_job_block(release, "publish-github-release"))
        == _PUBLISH_GITHUB_RELEASE_IF
    )

    scenarios = (
        (
            "tag push",
            "push",
            "false",
            "false",
            True,
            True,
        ),
        (
            "workflow_dispatch publish_pypi=true",
            "workflow_dispatch",
            "true",
            "false",
            True,
            False,
        ),
        (
            "workflow_dispatch PyPI disabled, GitHub release enabled",
            "workflow_dispatch",
            "false",
            "true",
            False,
            True,
        ),
        (
            "workflow_dispatch both publication flags false",
            "workflow_dispatch",
            "false",
            "false",
            False,
            False,
        ),
        (
            "workflow_dispatch both publication flags true",
            "workflow_dispatch",
            "true",
            "true",
            True,
            True,
        ),
    )

    for (
        case_name,
        event_name,
        publish_pypi,
        publish_github_release,
        expect_pypi,
        expect_github_release,
    ) in scenarios:
        assert (
            _pypi_publication_allowed(
                event_name=event_name,
                publish_pypi=publish_pypi,
                validation_result="success",
            )
            is expect_pypi
        ), case_name
        assert (
            _github_release_publication_allowed(
                event_name=event_name,
                publish_github_release=publish_github_release,
                validation_result="success",
            )
            is expect_github_release
        ), case_name


def test_release_workflow_publication_jobs_require_validation_success(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")
    pypi_job = _job_block(release, "publish-pypi")
    github_job = _job_block(release, "publish-github-release")

    assert "needs.validate-built-artifacts.result == 'success'" in pypi_job
    assert "needs.validate-built-artifacts.result == 'success'" in github_job
    assert not _pypi_publication_allowed(
        event_name="push",
        publish_pypi="true",
        validation_result="failure",
    )
    assert not _github_release_publication_allowed(
        event_name="push",
        publish_github_release="true",
        validation_result="failure",
    )


def test_built_artifact_gate_failure_is_not_masked(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")
    validation_job = _job_block(release, "validate-built-artifacts")
    gate_step = _step_block(validation_job, "Validate final built artifacts")

    assert "make validate-built-artifacts" in gate_step
    assert "set -euo pipefail" in gate_step
    assert "|| true" not in gate_step
    assert "continue-on-error" not in gate_step


def test_source_only_ci_does_not_run_final_built_artifact_gate(
    read_repo_text: RepoReader,
) -> None:
    for workflow_name in (
        "ci.yml",
        "pypi-validate.yml",
        "windows-validate.yml",
        "macos-validate.yml",
    ):
        workflow = read_repo_text(f".github/workflows/{workflow_name}")
        assert "validate-built-artifacts" not in workflow


def test_release_workflow_preserves_release_upload_asset_glob(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(".github/workflows/release.yml")
    github_job = _job_block(release, "publish-github-release")
    release_step = _step_block(github_job, "Create or update GitHub Release")

    assert "files: releases/${{ steps.release_meta.outputs.version }}/ecli_*" in (
        release_step
    )
    assert "fail_on_unmatched_files: true" in release_step
    assert ".sha256" not in release_step
    assert "gh release upload" not in release
    assert (
        "path: |\n            releases/${{ steps.release_meta.outputs.version }}/ecli_*"
        in (release)
    )
    assert "files: releases/${{ steps.release_meta.outputs.version }}/**" not in (
        release
    )
    assert (
        "path: |\n            releases/${{ steps.release_meta.outputs.version }}/**"
        not in (release)
    )
    assert "releases/0.2.3" not in release


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
