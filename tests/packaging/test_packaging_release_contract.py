# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_packaging_release_contract.py
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

from conftest import (
    CANONICAL_ARTIFACTS,
    CANONICAL_CONTRACT_DOC,
    CANONICAL_MATRIX_HEADING,
    PathAssertion,
    RepoReader,
    TokenAssertion,
)


# Packaging scripts and descriptors that must each be represented in the
# canonical contract document. Active per-artifact build scripts and packaging
# descriptors are covered here so that nothing exists undocumented.
PACKAGING_SCRIPT_GLOBS = (
    "scripts/build-and-package-*.ps1",
    "scripts/build_and_package_*.py",
    "scripts/build_pyinstaller_linux.py",
    "scripts/build_freebsd_pkg.py",
    "scripts/build_freebsd_port.py",
    "scripts/build_docker.py",
    "scripts/package_appimage.py",
    "scripts/publish_pypi.py",
    "scripts/sign_checksums.py",
    "scripts/verify_artifact.py",
    "scripts/verify_runtime.py",
    "scripts/check_log_invariant.py",
)

PACKAGING_DESCRIPTORS = (
    "docker/build-linux-deb.Dockerfile",
    "docker/build-linux-rpm.Dockerfile",
    "packaging/arch/PKGBUILD",
    "packaging/nix/package.nix",
    "packaging/windows/nsis/ecli.nsi",
    "packaging/pyinstaller/ecli.spec",
    "packaging/linux/appimage/appimage-builder.yml",
    "flake.nix",
)

EVIDENCE_CLASS_TOKENS = (
    "product and release documentation",
    "Codex and Claude agent contracts",
    "build, validation, and release runbooks",
    "repository-local validation tests or contract checks",
    "Release readiness is blocked",
    "Empty, stale, decorative, or unused packaging files are forbidden",
)


# --------------------------------------------------------------------------- #
# Registry shape
# --------------------------------------------------------------------------- #


def test_registry_has_exactly_twenty_one_canonical_entries() -> None:
    assert len(CANONICAL_ARTIFACTS) == 21
    assert [a.index for a in CANONICAL_ARTIFACTS] == list(range(1, 22))
    assert len({a.key for a in CANONICAL_ARTIFACTS}) == 21
    assert len({a.name for a in CANONICAL_ARTIFACTS}) == 21


def test_all_canonical_sources_exist_and_are_non_empty(
    assert_paths_non_empty: PathAssertion,
) -> None:
    seen: list[str] = []
    for artifact in CANONICAL_ARTIFACTS:
        seen.extend(artifact.sources)
    assert_paths_non_empty(seen)


# --------------------------------------------------------------------------- #
# Docs matrix coverage
# --------------------------------------------------------------------------- #


def test_canonical_matrix_section_exists(read_repo_text: RepoReader) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    assert CANONICAL_MATRIX_HEADING in contract
    # The summary matrix and workflow map must remain present too.
    assert "Platform & Packaging Release Contract Matrix" in contract
    assert "GitHub Actions Workflow Contract Map" in contract


def test_every_canonical_item_is_documented_in_matrix(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    for artifact in CANONICAL_ARTIFACTS:
        assert_tokens_present(
            contract,
            (
                artifact.name,
                artifact.artifact_token,
                artifact.test_file,
                artifact.claude_command,
                artifact.codex_prompt,
            ),
        )


def test_release_contract_defines_evidence_classes(
    read_repo_text: RepoReader,
    assert_tokens_present: TokenAssertion,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    assert_tokens_present(contract, EVIDENCE_CLASS_TOKENS)


# --------------------------------------------------------------------------- #
# Test coverage parity: every matrix item has a tests/packaging/ test file
# --------------------------------------------------------------------------- #


def test_every_canonical_item_has_a_packaging_test_file(repo_root: Path) -> None:
    for artifact in CANONICAL_ARTIFACTS:
        test_path = repo_root / artifact.test_file
        assert test_path.is_file(), (
            f"missing packaging test for {artifact.name!r}: {artifact.test_file}"
        )
        assert test_path.parent == repo_root / "tests" / "packaging"
        assert test_path.stat().st_size > 0


def test_no_docs_matrix_item_lacks_test_coverage(read_repo_text: RepoReader) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    for artifact in CANONICAL_ARTIFACTS:
        assert artifact.test_file in contract


# --------------------------------------------------------------------------- #
# Agent coverage parity: Claude commands and Codex prompts cover every item and
# the two coverage sets are equal.
# --------------------------------------------------------------------------- #


def test_every_canonical_item_has_claude_command_coverage(
    read_repo_text: RepoReader,
) -> None:
    for artifact in CANONICAL_ARTIFACTS:
        assert artifact.name in read_repo_text(artifact.claude_command), (
            f"{artifact.name!r} missing from {artifact.claude_command}"
        )


def test_every_canonical_item_has_codex_prompt_coverage(
    read_repo_text: RepoReader,
) -> None:
    for artifact in CANONICAL_ARTIFACTS:
        assert artifact.name in read_repo_text(artifact.codex_prompt), (
            f"{artifact.name!r} missing from {artifact.codex_prompt}"
        )


def test_claude_and_codex_coverage_are_equal(read_repo_text: RepoReader) -> None:
    claude_covered = {
        artifact.name
        for artifact in CANONICAL_ARTIFACTS
        if artifact.name in read_repo_text(artifact.claude_command)
    }
    codex_covered = {
        artifact.name
        for artifact in CANONICAL_ARTIFACTS
        if artifact.name in read_repo_text(artifact.codex_prompt)
    }
    all_names = {artifact.name for artifact in CANONICAL_ARTIFACTS}

    assert claude_covered == codex_covered == all_names


def test_no_docs_matrix_item_lacks_agent_coverage(read_repo_text: RepoReader) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    for artifact in CANONICAL_ARTIFACTS:
        assert artifact.claude_command in contract
        assert artifact.codex_prompt in contract


# --------------------------------------------------------------------------- #
# Workflow coverage parity
# --------------------------------------------------------------------------- #


def test_every_relevant_workflow_is_documented_and_tested(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    workflows_test = read_repo_text(
        "tests/packaging/test_packaging_workflows_contract.py"
    )
    for artifact in CANONICAL_ARTIFACTS:
        if artifact.workflow is None:
            continue
        workflow_path = f".github/workflows/{artifact.workflow}"
        assert (repo_root / workflow_path).is_file()
        assert workflow_path in contract
        assert artifact.workflow in workflows_test


# --------------------------------------------------------------------------- #
# No undocumented packaging script / descriptor
# --------------------------------------------------------------------------- #


def test_no_packaging_script_or_descriptor_is_undocumented(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)

    discovered: set[str] = set()
    for pattern in PACKAGING_SCRIPT_GLOBS:
        for path in repo_root.glob(pattern):
            discovered.add(str(path.relative_to(repo_root)))
    discovered.update(PACKAGING_DESCRIPTORS)

    for relative_path in sorted(discovered):
        assert (repo_root / relative_path).exists()
        assert relative_path in contract, (
            f"packaging file is undocumented in artifact-contract.md: {relative_path}"
        )


def test_no_shell_wrappers_remain_under_scripts(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    script_shell_files = sorted((repo_root / "scripts").glob("*.sh"))

    assert script_shell_files == []
    assert "Canonical Python implementation" in contract


def test_canonical_registry_sources_do_not_use_migrated_shell_wrappers() -> None:
    migrated_shell_sources = [
        source
        for artifact in CANONICAL_ARTIFACTS
        for source in artifact.sources
        if source.startswith("scripts/") and source.endswith(".sh")
    ]

    assert migrated_shell_sources == []


# --------------------------------------------------------------------------- #
# Test-suite relocation invariants
# --------------------------------------------------------------------------- #


def test_general_release_contract_test_was_moved_into_packaging(
    repo_root: Path,
) -> None:
    legacy = repo_root / "tests" / "test_packaging_release_contract.py"
    moved = repo_root / "tests" / "packaging" / "test_packaging_release_contract.py"

    assert not legacy.exists()
    assert moved.is_file()


def test_moved_test_has_correct_gpl_header_path(read_repo_text: RepoReader) -> None:
    # Scope to the GPL header region so the assertion strings in this module's
    # own body cannot satisfy the negative check.
    full = read_repo_text("tests/packaging/test_packaging_release_contract.py")
    header = "\n".join(full.splitlines()[:13])
    assert "# File: tests/packaging/test_packaging_release_contract.py" in header
    # Build the legacy path by concatenation so the contiguous old-path literal
    # never appears in the tree (keeps the relocation reference scan clean).
    legacy_header_line = "# File: tests/" + "test_packaging_release_contract.py"
    assert legacy_header_line not in header


def test_no_root_only_arch_pkgbuild_contract_is_required(repo_root: Path) -> None:
    assert not (repo_root / "PKGBUILD").exists()
    assert (repo_root / "packaging/arch/PKGBUILD").is_file()
