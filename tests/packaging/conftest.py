# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/conftest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest


RepoReader = Callable[[str], str]
PathAssertion = Callable[[Iterable[str]], None]
TokenAssertion = Callable[[str, Iterable[str]], None]


# --------------------------------------------------------------------------- #
# Canonical 21-item platform & packaging artifact matrix.
#
# This registry is the single source of truth shared by every packaging
# contract test. The docs matrix in docs/release/artifact-contract.md must be a
# superset of the data declared here, never a subset.
# --------------------------------------------------------------------------- #

CANONICAL_CONTRACT_DOC = "docs/release/artifact-contract.md"
CANONICAL_MATRIX_HEADING = "Canonical 21-Item Platform & Packaging Artifact Matrix"
WORKFLOW_CONTRACT_HEADING = "GitHub Actions Workflow Contract Map"

# Release-documentation surfaces that must echo every canonical artifact name
# (separately from the normative contract matrix itself).
RELEASE_DOC_FILES = (
    "docs/release/build-matrix.md",
    "docs/release/packaging-flows.md",
    "docs/release/release-process.md",
    "docs/release/release-checklist.md",
    "docs/product/supported-platforms.md",
)


@dataclass(frozen=True)
class Artifact:
    """One active release-contract artifact/package entry."""

    index: int
    key: str
    name: str
    platform: str
    sources: tuple[str, ...]
    artifact_token: str
    workflow: str | None
    test_file: str
    claude_command: str
    codex_prompt: str


@dataclass(frozen=True)
class UnameStub:
    """Minimal platform-neutral os.uname() stand-in for architecture tests."""

    machine: str


def expected_release_artifact(repo_root: Path, version: str, filename: str) -> Path:
    return repo_root / "releases" / version / filename


CANONICAL_ARTIFACTS: tuple[Artifact, ...] = (
    Artifact(
        index=1,
        key="pypi-wheel",
        name="PyPI wheel",
        platform="PyPI / Python",
        sources=(
            "pyproject.toml",
            "scripts/publish_pypi.py",
            ".github/workflows/pypi-validate.yml",
        ),
        artifact_token="01_pypi_wheel__ecli_editor-<version>-py3-none-any.whl",
        workflow="pypi-validate.yml",
        test_file="tests/packaging/test_packaging_pypi_wheel_contract.py",
        claude_command=".claude/commands/package-pypi.md",
        codex_prompt=".codex/prompts/package-pypi.md",
    ),
    Artifact(
        index=2,
        key="pypi-sdist",
        name="PyPI source distribution",
        platform="PyPI / Python",
        sources=(
            "pyproject.toml",
            "scripts/publish_pypi.py",
            ".github/workflows/pypi-validate.yml",
        ),
        artifact_token="02_pypi_sdist__ecli_editor-<version>.tar.gz",
        workflow="pypi-validate.yml",
        test_file="tests/packaging/test_packaging_pypi_sdist_contract.py",
        claude_command=".claude/commands/package-pypi.md",
        codex_prompt=".codex/prompts/package-pypi.md",
    ),
    Artifact(
        index=3,
        key="linux-pyinstaller",
        name="Linux generic PyInstaller executable",
        platform="Linux",
        sources=(
            "packaging/pyinstaller/ecli.spec",
            "packaging/pyinstaller/rthooks/force_imports.py",
            "scripts/build_pyinstaller_linux.py",
            "main.py",
        ),
        artifact_token="03_linux_pyinstaller__ecli_<version>_linux_x86_64.bin",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_linux_pyinstaller_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=4,
        key="linux-tarball",
        name="Linux release tarball",
        platform="Linux",
        sources=(
            "scripts/build_pyinstaller_linux.py",
            "scripts/verify_runtime.py",
            "Makefile",
        ),
        artifact_token="04_linux_tarball__ecli_<version>_linux_x86_64.tar.gz",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_linux_tarball_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=5,
        key="deb",
        name="Debian / Ubuntu `.deb`",
        platform="Linux (Debian/Ubuntu)",
        sources=(
            "scripts/build_and_package_deb.py",
            "docker/build-linux-deb.Dockerfile",
        ),
        artifact_token="05_debian__ecli_<version>_linux_x86_64.deb",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_deb_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=6,
        key="rpm",
        name="generic RPM `.rpm`",
        platform="Linux (RPM family)",
        sources=(
            "scripts/build_and_package_rpm.py",
            "docker/build-linux-rpm.Dockerfile",
        ),
        artifact_token="06_rpm__ecli_<version>_linux_x86_64.rpm",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_rpm_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=7,
        key="opensuse-rpm",
        name="openSUSE / SUSE RPM",
        platform="Linux (openSUSE/SUSE)",
        sources=("scripts/build_and_package_opensuse_rpm.py",),
        artifact_token="07_opensuse__ecli_<version>_opensuse_x86_64.rpm",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_opensuse_rpm_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=8,
        key="arch-pkgbuild",
        name="Arch Linux `PKGBUILD`",
        platform="Linux (Arch)",
        sources=(
            "packaging/arch/PKGBUILD",
            "scripts/build_and_package_arch.py",
            "docker/build-arch-package.Dockerfile",
        ),
        artifact_token="08_arch__ecli_<version>_arch_x86_64.pkg.tar.zst",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_arch_pkgbuild_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=9,
        key="slackware-txz",
        name="Slackware `.txz`",
        platform="Linux (Slackware)",
        sources=(
            "scripts/build_and_package_slackware.py",
            "docker/build-slackware-package.Dockerfile",
        ),
        artifact_token="09_slackware__ecli_<version>_slackware_x86_64.txz",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_slackware_txz_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=10,
        key="appimage",
        name="AppImage",
        platform="Linux (cross-distro)",
        sources=(
            "packaging/linux/appimage/appimage-builder.yml",
            "scripts/package_appimage.py",
        ),
        artifact_token="10_appimage__ecli_<version>_linux_x86_64.AppImage",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_appimage_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=11,
        key="freebsd-pkg",
        name="FreeBSD `.pkg`",
        platform="FreeBSD",
        sources=(
            "scripts/build_and_package_freebsd.py",
            "scripts/build_freebsd_pkg.py",
            ".github/workflows/freebsd-pkg.yml",
        ),
        artifact_token="11_freebsd_pkg__ecli_<version>_freebsd_x86_64.pkg",
        workflow="freebsd-pkg.yml",
        test_file="tests/packaging/test_packaging_freebsd_pkg_contract.py",
        claude_command=".claude/commands/package-freebsd.md",
        codex_prompt=".codex/prompts/package-freebsd.md",
    ),
    Artifact(
        index=12,
        key="freebsd-ports-chroot",
        name="FreeBSD ports/chroot build path",
        platform="FreeBSD",
        sources=(
            "scripts/build_freebsd_port.py",
            "tools/freebsd-chroot-build.sh",
        ),
        artifact_token=(
            "12_freebsd_ports_chroot__ecli_<version>_freebsd_ports_chroot_evidence.tar.gz"
        ),
        workflow="freebsd-pkg.yml",
        test_file="tests/packaging/test_packaging_freebsd_ports_chroot_contract.py",
        claude_command=".claude/commands/package-freebsd.md",
        codex_prompt=".codex/prompts/package-freebsd.md",
    ),
    Artifact(
        index=13,
        key="macos-app",
        name="macOS `.app`",
        platform="macOS",
        sources=(
            "scripts/build_and_package_macos.py",
            "packaging/pyinstaller/ecli.spec",
            "main.py",
        ),
        artifact_token="13_macos_app__ecli_<version>_macos_universal2_app_evidence.tar.gz",
        workflow="macos-dmg.yml",
        test_file="tests/packaging/test_packaging_macos_app_contract.py",
        claude_command=".claude/commands/package-macos.md",
        codex_prompt=".codex/prompts/package-macos.md",
    ),
    Artifact(
        index=14,
        key="macos-dmg",
        name="macOS `.dmg`",
        platform="macOS",
        sources=(
            "scripts/build_and_package_macos.py",
            ".github/workflows/macos-dmg.yml",
            ".github/workflows/macos-validate.yml",
            "docs/install/macos.md",
        ),
        artifact_token="14_macos_dmg__ecli_<version>_macos_universal2.dmg",
        workflow="macos-dmg.yml",
        test_file="tests/packaging/test_packaging_macos_dmg_contract.py",
        claude_command=".claude/commands/package-macos.md",
        codex_prompt=".codex/prompts/package-macos.md",
    ),
    Artifact(
        index=15,
        key="windows-portable-exe",
        name="Windows portable `.exe`",
        platform="Windows",
        sources=(
            "scripts/build-and-package-windows.ps1",
            "packaging/pyinstaller/ecli.spec",
            "main.py",
        ),
        artifact_token="15_windows_portable__ecli_<version>_win_x86_64.exe",
        workflow="windows-installer.yml",
        test_file="tests/packaging/test_packaging_windows_portable_exe_contract.py",
        claude_command=".claude/commands/package-windows.md",
        codex_prompt=".codex/prompts/package-windows.md",
    ),
    Artifact(
        index=16,
        key="windows-nsis-installer",
        name="Windows NSIS installer `.exe`",
        platform="Windows",
        sources=(
            "packaging/windows/nsis/ecli.nsi",
            "scripts/build-and-package-windows.ps1",
            ".github/workflows/windows-installer.yml",
            ".github/workflows/windows-validate.yml",
            "docs/install/windows.md",
        ),
        artifact_token="16_windows_nsis__ecli_<version>_win_x86_64_setup.exe",
        workflow="windows-installer.yml",
        test_file="tests/packaging/test_packaging_windows_nsis_installer_contract.py",
        claude_command=".claude/commands/package-windows.md",
        codex_prompt=".codex/prompts/package-windows.md",
    ),
    Artifact(
        index=17,
        key="nix-flake",
        name="Nix flake",
        platform="Nix / NixOS",
        sources=("flake.nix",),
        artifact_token="17_nix_flake__ecli_<version>_nix_flake_evidence.tar.gz",
        workflow=None,
        test_file="tests/packaging/test_packaging_nix_flake_contract.py",
        claude_command=".claude/commands/package-nix.md",
        codex_prompt=".codex/prompts/package-nix.md",
    ),
    Artifact(
        index=18,
        key="nixos-package",
        name="Nix/NixOS package expression",
        platform="Nix / NixOS",
        sources=("packaging/nix/package.nix",),
        artifact_token="18_nixos_package__ecli_<version>_nixos_package_evidence.tar.gz",
        workflow=None,
        test_file="tests/packaging/test_packaging_nixos_package_contract.py",
        claude_command=".claude/commands/package-nix.md",
        codex_prompt=".codex/prompts/package-nix.md",
    ),
    Artifact(
        index=19,
        key="docker-deb-helper",
        name="Docker DEB build helper",
        platform="Linux build helper",
        sources=("docker/build-linux-deb.Dockerfile",),
        artifact_token="19_docker_deb_helper__ecli_<version>_docker_deb_helper_evidence.tar.gz",
        workflow=None,
        test_file="tests/packaging/test_packaging_docker_deb_helper_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=20,
        key="docker-rpm-helper",
        name="Docker RPM build helper",
        platform="Linux build helper",
        sources=("docker/build-linux-rpm.Dockerfile",),
        artifact_token="20_docker_rpm_helper__ecli_<version>_docker_rpm_helper_evidence.tar.gz",
        workflow=None,
        test_file="tests/packaging/test_packaging_docker_rpm_helper_contract.py",
        claude_command=".claude/commands/package-linux.md",
        codex_prompt=".codex/prompts/package-linux.md",
    ),
    Artifact(
        index=21,
        key="gha-release-contract",
        name="GitHub Actions release/workflow contract map",
        platform="CI / release automation",
        sources=(
            ".github/workflows/release.yml",
            ".github/workflows/ci.yml",
        ),
        artifact_token="21_workflow_contract__ecli_<version>_workflow_contract_evidence.tar.gz",
        workflow="release.yml",
        test_file="tests/packaging/test_packaging_workflows_contract.py",
        claude_command=".claude/commands/release.md",
        codex_prompt=".codex/prompts/release.md",
    ),
)


def get_artifact(key: str) -> Artifact:
    """Return the canonical artifact entry for ``key`` or raise ``KeyError``."""
    for artifact in CANONICAL_ARTIFACTS:
        if artifact.key == key:
            return artifact
    raise KeyError(f"unknown canonical artifact key: {key}")


def load_script_module(
    repo_root: Path, relative_path: str, module_name: str
) -> ModuleType:
    """Import a standalone ``scripts/`` module by file path for behavior tests."""
    script_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None, (
        f"could not load script module: {relative_path}"
    )
    module = importlib.util.module_from_spec(spec)
    script_dir = str(script_path.parent)
    inserted = script_dir not in sys.path
    if inserted:
        sys.path.insert(0, script_dir)
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted:
            sys.path.remove(script_dir)
    return module


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def read_repo_text(repo_root: Path) -> RepoReader:
    def read(relative_path: str) -> str:
        return (repo_root / relative_path).read_text(encoding="utf-8")

    return read


@pytest.fixture
def assert_paths_non_empty(repo_root: Path) -> PathAssertion:
    def assert_present(relative_paths: Iterable[str]) -> None:
        for relative_path in relative_paths:
            path = repo_root / relative_path
            assert path.exists(), f"missing package contract path: {relative_path}"
            if path.is_file():
                assert path.stat().st_size > 0, (
                    f"empty package contract file: {relative_path}"
                )
            else:
                assert any(path.iterdir()), (
                    f"empty package contract directory: {relative_path}"
                )

    return assert_present


@pytest.fixture
def assert_tokens_present() -> TokenAssertion:
    def assert_present(text: str, tokens: Iterable[str]) -> None:
        for token in tokens:
            assert token in text, f"missing package contract token: {token}"

    return assert_present


def assert_artifact_documented(
    artifact: Artifact,
    read_repo_text: RepoReader,
    assert_paths_non_empty: PathAssertion,
    assert_tokens_present: TokenAssertion,
) -> None:
    """Shared per-artifact contract assertion.

    Verifies that an artifact's required source files exist and are non-empty,
    that it is wired into the canonical 21-item docs matrix (name, expected
    output token, required test file, Claude command, and Codex prompt), that it
    is echoed in the broader release docs, that its agent contracts cover it, and
    that its workflow mapping (when relevant) is documented.
    """
    assert_paths_non_empty(artifact.sources)

    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    assert CANONICAL_MATRIX_HEADING in contract, (
        "canonical 21-item matrix heading missing from artifact-contract.md"
    )
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

    if artifact.workflow is not None:
        assert f".github/workflows/{artifact.workflow}" in contract, (
            f"workflow {artifact.workflow} not mapped in artifact-contract.md"
        )

    release_blob = "\n".join(read_repo_text(path) for path in RELEASE_DOC_FILES)
    assert artifact.name in release_blob, (
        f"artifact {artifact.name!r} not echoed in release docs"
    )

    assert artifact.name in read_repo_text(artifact.claude_command), (
        f"artifact {artifact.name!r} missing Claude command coverage"
    )
    assert artifact.name in read_repo_text(artifact.codex_prompt), (
        f"artifact {artifact.name!r} missing Codex prompt coverage"
    )
