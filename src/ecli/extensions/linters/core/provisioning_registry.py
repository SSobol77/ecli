# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/provisioning_registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Artifact and linter-contract registry for F4 provisioning.

The loader reads each linter's ``manifest.py`` and ``package_contract.py`` by
file path. It does not call provider classes, run linters, parse diagnostics, or
invoke package managers.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from ecli.extensions.linters.core.provisioning_contract import (
    ArtifactContractEntry,
    LinterToolContract,
    VersionProbe,
)
from ecli.extensions.linters.core.registry import (
    CANONICAL_ARTIFACT_ENTRY_IDS,
    LinterDefinition,
    PackageContract,
)


ARTIFACT_CONTRACT_ENTRIES: tuple[ArtifactContractEntry, ...] = (
    ArtifactContractEntry(
        1,
        "pypi-wheel",
        "PyPI wheel",
        "PyPI / Python",
        "ecli_editor-<version>-py3-none-any.whl",
        False,
        "Python wheel metadata cannot reliably provision Node, Rust, Go, Zig, "
        "Java, or system binaries.",
    ),
    ArtifactContractEntry(
        2,
        "pypi-sdist",
        "PyPI source distribution",
        "PyPI / Python",
        "ecli_editor-<version>.tar.gz",
        False,
        "Source distribution installs are developer/source installs and may be "
        "minimal for non-Python F4 toolchains.",
    ),
    ArtifactContractEntry(
        3,
        "linux-pyinstaller",
        "Linux generic PyInstaller executable",
        "Linux",
        "ecli_<version>_linux_x86_64.bin",
    ),
    ArtifactContractEntry(
        4,
        "linux-tarball",
        "Linux release tarball",
        "Linux",
        "ecli_<version>_linux_x86_64.tar.gz",
    ),
    ArtifactContractEntry(
        5,
        "deb",
        "Debian / Ubuntu `.deb`",
        "Linux (Debian/Ubuntu)",
        "ecli_<version>_linux_x86_64.deb",
    ),
    ArtifactContractEntry(
        6,
        "rpm",
        "generic RPM `.rpm`",
        "Linux (RPM family)",
        "ecli_<version>_linux_x86_64.rpm",
    ),
    ArtifactContractEntry(
        7,
        "opensuse-rpm",
        "openSUSE / SUSE RPM",
        "Linux (openSUSE/SUSE)",
        "ecli_<version>_opensuse_x86_64.rpm",
    ),
    ArtifactContractEntry(
        8,
        "arch-pkgbuild",
        "Arch Linux `PKGBUILD`",
        "Linux (Arch)",
        "ecli_<version>_arch_x86_64.pkg.tar.zst",
    ),
    ArtifactContractEntry(
        9,
        "slackware-txz",
        "Slackware `.txz`",
        "Linux (Slackware)",
        "ecli_<version>_slackware_x86_64.txz",
    ),
    ArtifactContractEntry(
        10,
        "appimage",
        "AppImage",
        "Linux (cross-distro)",
        "ecli_<version>_linux_x86_64.AppImage",
    ),
    ArtifactContractEntry(
        11,
        "freebsd-pkg",
        "FreeBSD `.pkg`",
        "FreeBSD",
        "ecli_<version>_freebsd_x86_64.pkg",
    ),
    ArtifactContractEntry(
        12,
        "freebsd-ports-chroot",
        "FreeBSD ports/chroot build path",
        "FreeBSD",
        "ecli_<version>_freebsd_ports_chroot_evidence.tar.gz",
    ),
    ArtifactContractEntry(
        13,
        "macos-app",
        "macOS `.app`",
        "macOS",
        "ecli_<version>_macos_universal2_app_evidence.tar.gz",
    ),
    ArtifactContractEntry(
        14,
        "macos-dmg",
        "macOS `.dmg`",
        "macOS",
        "ecli_<version>_macos_universal2.dmg",
    ),
    ArtifactContractEntry(
        15,
        "windows-portable-exe",
        "Windows portable `.exe`",
        "Windows",
        "ecli_<version>_win_x86_64.exe",
    ),
    ArtifactContractEntry(
        16,
        "windows-nsis-installer",
        "Windows NSIS installer `.exe`",
        "Windows",
        "ecli_<version>_win_x86_64_setup.exe",
    ),
    ArtifactContractEntry(
        17,
        "nix-flake",
        "Nix flake",
        "Nix / NixOS",
        "ecli_<version>_nix_flake_evidence.tar.gz",
    ),
    ArtifactContractEntry(
        18,
        "nixos-package",
        "Nix/NixOS package expression",
        "Nix / NixOS",
        "ecli_<version>_nixos_package_evidence.tar.gz",
    ),
    ArtifactContractEntry(
        19,
        "docker-deb-helper",
        "Docker DEB build helper",
        "Linux build helper",
        "ecli_<version>_docker_deb_helper_evidence.tar.gz",
    ),
    ArtifactContractEntry(
        20,
        "docker-rpm-helper",
        "Docker RPM build helper",
        "Linux build helper",
        "ecli_<version>_docker_rpm_helper_evidence.tar.gz",
    ),
    ArtifactContractEntry(
        21,
        "gha-release-contract",
        "GitHub Actions release/workflow contract map",
        "CI / release automation",
        "ecli_<version>_workflow_contract_evidence.tar.gz",
    ),
)


LINTER_DIR_ORDER: tuple[str, ...] = (
    "ruff",
    "biome",
    "markdownlint",
    "yamllint",
    "shellcheck",
    "zig",
    "hadolint",
    "taplo",
    "actionlint",
    "clang_tidy",
    "cppcheck",
    "clang_format",
    "java_checkstyle",
    "java_pmd",
    "java_spotbugs",
    "cargo_clippy",
    "golangci_lint",
    "sqlfluff",
    "tflint",
    "eslint",
    "stylelint",
    "oxlint",
    "pylint",
)


GITHUB_SOURCE_ARCHIVE_IDS = frozenset(
    {"Source code (zip)", "Source code (tar.gz)", "source-code-zip", "source-code-tar-gz"}
)


def linters_root() -> Path:
    """Return the ``src/ecli/extensions/linters`` directory."""
    return Path(__file__).resolve().parents[1]


def get_artifact_entry(artifact_entry_id: str) -> ArtifactContractEntry:
    """Return one canonical artifact entry by id."""
    for entry in ARTIFACT_CONTRACT_ENTRIES:
        if entry.artifact_entry_id == artifact_entry_id:
            return entry
    raise KeyError(f"unknown artifact entry id: {artifact_entry_id!r}")


def is_github_generated_source_archive(artifact_entry_id: str) -> bool:
    """Return whether an id/named entry is a GitHub-generated source archive."""
    return artifact_entry_id in GITHUB_SOURCE_ARCHIVE_IDS


def _load_module_from_path(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_manifest(path: Path, directory: str) -> LinterDefinition:
    module = _load_module_from_path(path, f"_ecli_f4_{directory}_manifest")
    manifest = getattr(module, "MANIFEST", None)
    if not isinstance(manifest, LinterDefinition):
        raise RuntimeError(f"{path} does not define MANIFEST as LinterDefinition")
    return manifest


def _load_package_contract(path: Path, directory: str) -> PackageContract:
    module = _load_module_from_path(path, f"_ecli_f4_{directory}_package_contract")
    contract = getattr(module, "PACKAGE_CONTRACT", None)
    if not isinstance(contract, PackageContract):
        raise RuntimeError(f"{path} does not define PACKAGE_CONTRACT")
    return contract


def _tool_contract(
    manifest: LinterDefinition, package_contract: PackageContract
) -> LinterToolContract:
    if package_contract.service_name != manifest.name:
        raise RuntimeError(
            f"package_contract service_name {package_contract.service_name!r} "
            f"does not match manifest name {manifest.name!r}"
        )
    if package_contract.bundled_with_full_install != manifest.bundled_with_full_install:
        raise RuntimeError(
            f"{manifest.name!r} bundled_with_full_install mismatch between "
            "manifest.py and package_contract.py"
        )
    if tuple(package_contract.artifact_entry_ids) != CANONICAL_ARTIFACT_ENTRY_IDS:
        raise RuntimeError(
            f"{manifest.name!r} package contract must cover exactly 21 "
            "canonical artifact entry ids"
        )

    return LinterToolContract(
        tool_id=manifest.name,
        display_name=manifest.display_name,
        languages=manifest.languages,
        install_group=manifest.install_group,
        tier=manifest.tier,
        provider_kind=manifest.provider_kind,
        required_for_full=package_contract.mandatory_for_full_install,
        bundled_with_full_install=package_contract.bundled_with_full_install,
        selected_by_default=package_contract.mandatory_for_full_install,
        executable_names=package_contract.binary_names,
        version_probe=VersionProbe(command=package_contract.version_probe),
        allowed_install_mechanisms=package_contract.allowed_install_mechanisms,
        provenance_requirements=package_contract.provenance_requirements,
        source_url=package_contract.source_url or manifest.homepage_url,
        pinned_version=package_contract.pinned_version,
        checksum_required_for_downloads=(
            package_contract.checksum_required_for_downloads
        ),
        artifact_entry_ids=package_contract.artifact_entry_ids,
        delivery_notes=package_contract.delivery_notes,
    )


def load_linter_tool_contracts(root: Path | None = None) -> tuple[LinterToolContract, ...]:
    """Load every linter manifest/package contract in deterministic order."""
    base = linters_root() if root is None else root
    contracts: list[LinterToolContract] = []
    for directory in LINTER_DIR_ORDER:
        service_dir = base / directory
        manifest_path = service_dir / "manifest.py"
        package_contract_path = service_dir / "package_contract.py"
        if not manifest_path.is_file():
            raise RuntimeError(f"known linter {directory!r} lacks manifest.py")
        if not package_contract_path.is_file():
            raise RuntimeError(
                f"known linter {directory!r} lacks package_contract.py"
            )
        manifest = _load_manifest(manifest_path, directory)
        package_contract = _load_package_contract(package_contract_path, directory)
        contracts.append(_tool_contract(manifest, package_contract))

    tool_ids = [contract.tool_id for contract in contracts]
    if len(tool_ids) != len(set(tool_ids)):
        raise RuntimeError(f"duplicate linter tool id(s): {tool_ids}")
    return tuple(contracts)


def required_full_tool_ids(
    contracts: tuple[LinterToolContract, ...] | None = None,
) -> tuple[str, ...]:
    """Return Full-required tool ids from package_contract.py metadata."""
    loaded = load_linter_tool_contracts() if contracts is None else contracts
    return tuple(contract.tool_id for contract in loaded if contract.required_for_full)


def optional_tool_ids(
    contracts: tuple[LinterToolContract, ...] | None = None,
) -> tuple[str, ...]:
    """Return non-Full-required tool ids from package_contract.py metadata."""
    loaded = load_linter_tool_contracts() if contracts is None else contracts
    return tuple(contract.tool_id for contract in loaded if not contract.required_for_full)
