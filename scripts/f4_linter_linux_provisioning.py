#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/f4_linter_linux_provisioning.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Linux F4 provisioning policy manifests for release artifacts.

This module records the first concrete Linux provisioning layer: deterministic
artifact-specific policy manifests, package-manager dependency metadata, Nix
declaration evidence, explicit provenance records, and release blockers where
non-dry-run installation still lacks pinned/checksummed provenance.

It is intentionally non-invasive. Importing this module never runs package
managers, shells, version probes, network requests, or upstream downloads.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, Mapping, NamedTuple, cast


LinuxProvisioningMechanism = Literal[
    "bundled-internal",
    "os-package-manager",
    "language-package-manager",
    "ecli-managed-tools",
    "toolchain-component",
    "jar-shim",
    "nix-derivation",
    "verified-upstream-download",
    "blocked-missing-provenance",
]

LinuxArtifactFamily = Literal[
    "package-manager",
    "self-contained",
    "docker-helper",
    "nix-policy",
]

LinuxProvenanceStatus = Literal[
    "internal-bundled",
    "distro-signed-package",
    "nix-derivation",
    "toolchain-component",
    "pinned-upstream-artifact",
    "pinned-language-package",
    "blocked-missing-version-pin",
    "blocked-missing-checksum",
    "blocked-missing-source-url",
    "blocked-missing-install-strategy",
    "blocked-missing-license-review",
    "blocked-missing-distro-mapping",
]

LinuxTrustBoundary = Literal[
    "ecli-source-tree",
    "distro-package-manager",
    "nix-store",
    "rust-toolchain",
    "upstream-release",
    "language-registry",
    "unresolved",
]

LinuxDistroFamily = Literal[
    "debian",
    "rpm-generic",
    "opensuse",
    "arch",
    "slackware",
]

LinuxDistroMappingStatus = Literal[
    "approved-existing-policy",
    "approved-with-evidence",
    "blocked-missing-distro-mapping",
    "blocked-ambiguous-package-name",
    "blocked-package-not-available",
    "blocked-unverified",
]

LinuxDistroEvidenceSourceType = Literal[
    "repository-local-policy",
    "official-distro-metadata",
    "upstream-project-docs",
]

LinuxDistroEvidenceStatus = Literal[
    "current-policy-baseline",
    "verified-official-source",
    "blocked-missing-evidence",
    "blocked-evidence-drift",
]

LinuxDistroOfficialSourceKind = Literal[
    "distro-package-index",
    "distro-package-recipe",
    "upstream-install-doc",
    "upstream-release-page",
]

LinuxDistroVerificationScope = Literal[
    "package-name-only",
    "package-name-and-executable",
    "package-name-executable-and-license",
]


LINUX_MANIFEST_SCHEMA_VERSION = 1
LINUX_MANIFEST_FILENAME = "f4-linux-tools.json"
EXIT_OK = 0
EXIT_INVALID = 1
EXIT_OFFICIAL_EVIDENCE_DRIFT = 2

LINUX_PACKAGE_MANAGER_ARTIFACT_IDS: tuple[str, ...] = (
    "deb",
    "rpm",
    "opensuse-rpm",
    "arch-pkgbuild",
    "slackware-txz",
)
LINUX_SELF_CONTAINED_ARTIFACT_IDS: tuple[str, ...] = (
    "linux-pyinstaller",
    "linux-tarball",
    "appimage",
)
LINUX_DOCKER_HELPER_ARTIFACT_IDS: tuple[str, ...] = (
    "docker-deb-helper",
    "docker-rpm-helper",
)
LINUX_NIX_ARTIFACT_IDS: tuple[str, ...] = (
    "nix-flake",
    "nixos-package",
)
LINUX_ARTIFACT_IDS: tuple[str, ...] = (
    *LINUX_SELF_CONTAINED_ARTIFACT_IDS,
    *LINUX_PACKAGE_MANAGER_ARTIFACT_IDS,
    *LINUX_DOCKER_HELPER_ARTIFACT_IDS,
    *LINUX_NIX_ARTIFACT_IDS,
)
LINUX_DISTRO_MAPPING_ARTIFACT_IDS: tuple[str, ...] = (
    *LINUX_PACKAGE_MANAGER_ARTIFACT_IDS,
    *LINUX_DOCKER_HELPER_ARTIFACT_IDS,
)

LINUX_ALLOWED_MECHANISMS = frozenset(
    {
        "bundled-internal",
        "os-package-manager",
        "language-package-manager",
        "ecli-managed-tools",
        "toolchain-component",
        "jar-shim",
        "nix-derivation",
        "verified-upstream-download",
        "blocked-missing-provenance",
    }
)

LINUX_ALLOWED_PROVENANCE_STATUSES = frozenset(
    {
        "internal-bundled",
        "distro-signed-package",
        "nix-derivation",
        "toolchain-component",
        "pinned-upstream-artifact",
        "pinned-language-package",
        "blocked-missing-version-pin",
        "blocked-missing-checksum",
        "blocked-missing-source-url",
        "blocked-missing-install-strategy",
        "blocked-missing-license-review",
        "blocked-missing-distro-mapping",
    }
)

LINUX_BLOCKED_PROVENANCE_STATUSES = frozenset(
    {
        "blocked-missing-version-pin",
        "blocked-missing-checksum",
        "blocked-missing-source-url",
        "blocked-missing-install-strategy",
        "blocked-missing-license-review",
        "blocked-missing-distro-mapping",
    }
)

LINUX_ALLOWED_TRUST_BOUNDARIES = frozenset(
    {
        "ecli-source-tree",
        "distro-package-manager",
        "nix-store",
        "rust-toolchain",
        "upstream-release",
        "language-registry",
        "unresolved",
    }
)

LINUX_ALLOWED_DISTRO_FAMILIES = frozenset(
    {
        "debian",
        "rpm-generic",
        "opensuse",
        "arch",
        "slackware",
    }
)

LINUX_ALLOWED_DISTRO_MAPPING_STATUSES = frozenset(
    {
        "approved-existing-policy",
        "approved-with-evidence",
        "blocked-missing-distro-mapping",
        "blocked-ambiguous-package-name",
        "blocked-package-not-available",
        "blocked-unverified",
    }
)

LINUX_BLOCKED_DISTRO_MAPPING_STATUSES = frozenset(
    {
        "blocked-missing-distro-mapping",
        "blocked-ambiguous-package-name",
        "blocked-package-not-available",
        "blocked-unverified",
    }
)

LINUX_ALLOWED_DISTRO_EVIDENCE_SOURCE_TYPES = frozenset(
    {
        "repository-local-policy",
        "official-distro-metadata",
        "upstream-project-docs",
    }
)

LINUX_ALLOWED_DISTRO_EVIDENCE_STATUSES = frozenset(
    {
        "current-policy-baseline",
        "verified-official-source",
        "blocked-missing-evidence",
        "blocked-evidence-drift",
    }
)

LINUX_OFFICIAL_DISTRO_EVIDENCE_SOURCE_TYPES = frozenset(
    {
        "official-distro-metadata",
        "upstream-project-docs",
    }
)

LINUX_ALLOWED_OFFICIAL_SOURCE_KINDS = frozenset(
    {
        "distro-package-index",
        "distro-package-recipe",
        "upstream-install-doc",
        "upstream-release-page",
    }
)

LINUX_ALLOWED_VERIFICATION_SCOPES = frozenset(
    {
        "package-name-only",
        "package-name-and-executable",
        "package-name-executable-and-license",
    }
)

DISTRO_FAMILY_BY_ARTIFACT: dict[str, LinuxDistroFamily] = {
    "deb": "debian",
    "rpm": "rpm-generic",
    "opensuse-rpm": "opensuse",
    "arch-pkgbuild": "arch",
    "slackware-txz": "slackware",
    "docker-deb-helper": "debian",
    "docker-rpm-helper": "rpm-generic",
}

TRUST_BOUNDARY_BY_PROVENANCE_STATUS: dict[str, LinuxTrustBoundary] = {
    "internal-bundled": "ecli-source-tree",
    "distro-signed-package": "distro-package-manager",
    "nix-derivation": "nix-store",
    "toolchain-component": "rust-toolchain",
    "pinned-upstream-artifact": "upstream-release",
    "pinned-language-package": "language-registry",
    "blocked-missing-version-pin": "unresolved",
    "blocked-missing-checksum": "unresolved",
    "blocked-missing-source-url": "unresolved",
    "blocked-missing-install-strategy": "unresolved",
    "blocked-missing-license-review": "unresolved",
    "blocked-missing-distro-mapping": "unresolved",
}

PACKAGE_POLICY_SOURCE_BY_HELPER = {
    "docker-deb-helper": "deb",
    "docker-rpm-helper": "rpm",
}


class DebianOfficialEvidenceSpec(NamedTuple):
    """Canonical official Debian evidence fields that vary by tool."""

    tool_id: str
    evidence_source: str
    evidence_note: str
    official_source_name: str
    official_source_url: str
    verification_note: str


DEBIAN_OFFICIAL_EVIDENCE_SPECS: tuple[DebianOfficialEvidenceSpec, ...] = (
    DebianOfficialEvidenceSpec(
        tool_id="yamllint",
        evidence_source="Debian official package metadata for yamllint",
        evidence_note=(
            "Verified against official Debian package index, package tracker, "
            "source package, and manpage metadata for the existing yamllint "
            "package/executable mapping."
        ),
        official_source_name="Debian Package Search: yamllint",
        official_source_url="https://packages.debian.org/yamllint",
        verification_note=(
            "Verified against official Debian package, package-tracker, source "
            "package, and manpage metadata: package name yamllint and "
            "executable yamllint."
        ),
    ),
    DebianOfficialEvidenceSpec(
        tool_id="shellcheck",
        evidence_source="Debian official package metadata for shellcheck",
        evidence_note=(
            "Verified against official Debian package, filelist, and manpage "
            "metadata for the existing shellcheck package/executable mapping."
        ),
        official_source_name="Debian Package Filelist: shellcheck",
        official_source_url=(
            "https://packages.debian.org/sid/amd64/shellcheck/filelist"
        ),
        verification_note=(
            "Verified against official Debian package, filelist, and manpage "
            "metadata: package name shellcheck and executable shellcheck."
        ),
    ),
    DebianOfficialEvidenceSpec(
        tool_id="clang-tidy",
        evidence_source="Debian official package metadata for clang-tidy",
        evidence_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/clang-tidy, versioned filelist "
            "metadata https://packages.debian.org/sid/i386/clang-tidy-19/filelist, "
            "and manpage metadata "
            "https://manpages.debian.org/trixie/clang-tidy/clang-tidy.1.en.html "
            "for the existing clang-tidy package/executable mapping."
        ),
        official_source_name="Debian Package Search: clang-tidy",
        official_source_url="https://packages.debian.org/clang-tidy",
        verification_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/clang-tidy, versioned filelist "
            "metadata https://packages.debian.org/sid/i386/clang-tidy-19/filelist, "
            "and manpage metadata "
            "https://manpages.debian.org/trixie/clang-tidy/clang-tidy.1.en.html: "
            "package name clang-tidy and executable clang-tidy."
        ),
    ),
    DebianOfficialEvidenceSpec(
        tool_id="cppcheck",
        evidence_source="Debian official package metadata for cppcheck",
        evidence_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/cppcheck, filelist metadata "
            "https://packages.debian.org/sid/amd64/cppcheck/filelist, and "
            "manpage metadata "
            "https://manpages.debian.org/unstable/cppcheck/cppcheck.1.en.html "
            "for the existing cppcheck package/executable mapping."
        ),
        official_source_name="Debian Package Search: cppcheck",
        official_source_url="https://packages.debian.org/cppcheck",
        verification_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/cppcheck, filelist metadata "
            "https://packages.debian.org/sid/amd64/cppcheck/filelist, and "
            "manpage metadata "
            "https://manpages.debian.org/unstable/cppcheck/cppcheck.1.en.html: "
            "package name cppcheck and executable cppcheck."
        ),
    ),
    DebianOfficialEvidenceSpec(
        tool_id="clang-format",
        evidence_source="Debian official package metadata for clang-format",
        evidence_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/clang-format and filelist metadata "
            "https://packages.debian.org/sid/amd64/clang-format/filelist, with "
            "supporting manpage metadata "
            "https://manpages.debian.org/testing/clang-format-15/clang-format-15.1 "
            "for the existing clang-format package/executable mapping."
        ),
        official_source_name="Debian Package Search: clang-format",
        official_source_url="https://packages.debian.org/clang-format",
        verification_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/clang-format and filelist metadata "
            "https://packages.debian.org/sid/amd64/clang-format/filelist, with "
            "supporting manpage metadata "
            "https://manpages.debian.org/testing/clang-format-15/clang-format-15.1: "
            "package name clang-format and executable clang-format."
        ),
    ),
    DebianOfficialEvidenceSpec(
        tool_id="checkstyle",
        evidence_source="Debian official package metadata for checkstyle",
        evidence_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/checkstyle, source package metadata "
            "https://packages.debian.org/source/stable/checkstyle, tracker "
            "metadata https://tracker.debian.org/pkg/checkstyle, and manpage "
            "metadata https://manpages.debian.org/testing/checkstyle/checkstyle.1.en.html "
            "for the existing checkstyle package/executable mapping."
        ),
        official_source_name="Debian Package Search: checkstyle",
        official_source_url="https://packages.debian.org/checkstyle",
        verification_note=(
            "Verified against official Debian package metadata "
            "https://packages.debian.org/checkstyle, source package metadata "
            "https://packages.debian.org/source/stable/checkstyle, tracker "
            "metadata https://tracker.debian.org/pkg/checkstyle, and manpage "
            "metadata https://manpages.debian.org/testing/checkstyle/checkstyle.1.en.html: "
            "package name checkstyle and executable checkstyle."
        ),
    ),
)


def _debian_official_evidence_entry(
    spec: DebianOfficialEvidenceSpec,
) -> dict[str, Any]:
    """Build one official Debian evidence override without repeating constants."""
    return {
        "evidence_source": spec.evidence_source,
        "evidence_source_type": "official-distro-metadata",
        "evidence_status": "verified-official-source",
        "evidence_note": spec.evidence_note,
        "official_source_name": spec.official_source_name,
        "official_source_url": spec.official_source_url,
        "official_source_kind": "distro-package-index",
        "verification_scope": "package-name-and-executable",
        "verification_note": spec.verification_note,
        "external_verification_required_for_new_mappings": False,
        "release_blocking": False,
        "blocker_reason": None,
    }


OFFICIAL_DISTRO_EVIDENCE_BY_POLICY: dict[tuple[str, str], dict[str, Any]] = {
    ("deb", spec.tool_id): _debian_official_evidence_entry(spec)
    for spec in DEBIAN_OFFICIAL_EVIDENCE_SPECS
}

OS_PACKAGE_NAMES: dict[str, dict[str, tuple[str, ...]]] = {
    "deb": {
        "yamllint": ("yamllint",),
        "shellcheck": ("shellcheck",),
        "clang-tidy": ("clang-tidy",),
        "cppcheck": ("cppcheck",),
        "clang-format": ("clang-format",),
        "checkstyle": ("checkstyle",),
    },
    "rpm": {
        "yamllint": ("python3-yamllint",),
        "shellcheck": ("ShellCheck",),
        "clang-tidy": ("clang-tools-extra",),
        "cppcheck": ("cppcheck",),
        "clang-format": ("clang-tools-extra",),
    },
    "opensuse-rpm": {
        "yamllint": ("yamllint",),
        "shellcheck": ("ShellCheck",),
        "clang-tidy": ("clang-tools",),
        "cppcheck": ("cppcheck",),
        "clang-format": ("clang-tools",),
    },
    "arch-pkgbuild": {
        "yamllint": ("yamllint",),
        "shellcheck": ("shellcheck",),
        "clang-tidy": ("clang",),
        "cppcheck": ("cppcheck",),
        "clang-format": ("clang",),
    },
    "slackware-txz": {
        "clang-tidy": ("llvm",),
        "clang-format": ("llvm",),
    },
}

TOOLCHAIN_COMPONENTS: dict[str, str] = {
    "cargo-clippy": "Rust toolchain component: cargo clippy",
}

EVIDENCE_FIELDS_BASE: tuple[str, ...] = (
    "artifact_entry_id",
    "tool_id",
    "mechanism",
    "executable_names",
    "version_probe",
    "target_dir",
    "evidence_dir",
    "network_required",
    "checksum_required",
    "pin_required",
)

PROVENANCE_EVIDENCE_FIELDS: tuple[str, ...] = (
    "provenance_status",
    "trust_boundary",
    "source_name",
    "source_url",
    "package_names",
    "pinned_version",
    "checksum_algorithm",
    "checksum",
    "license_review_required",
    "network_required",
    "release_blocking",
)

PROVENANCE_MANIFEST_FIELDS: tuple[str, ...] = (
    "provenance_status",
    "trust_boundary",
    "source_name",
    "source_url",
    "package_names",
    "pinned_version",
    "checksum_algorithm",
    "checksum",
    "license_review_required",
    "network_required",
    "release_blocking",
    "blocker_reason",
    "evidence_fields_required",
)

DISTRO_MAPPING_MANIFEST_FIELDS: tuple[str, ...] = (
    "artifact_entry_id",
    "distro_family",
    "tool_id",
    "evidence_record_id",
    "package_names",
    "executable_names",
    "provenance_status",
    "trust_boundary",
    "mapping_status",
    "evidence_source",
    "evidence_url",
    "evidence_note",
    "release_blocking",
    "blocker_reason",
    "source_policy_artifact_entry_id",
)

DISTRO_EVIDENCE_MANIFEST_FIELDS: tuple[str, ...] = (
    "artifact_entry_id",
    "source_policy_artifact_entry_id",
    "distro_family",
    "tool_id",
    "package_names",
    "executable_names",
    "evidence_record_id",
    "evidence_source",
    "evidence_source_type",
    "evidence_status",
    "evidence_note",
    "external_verification_required_for_new_mappings",
    "release_blocking",
    "blocker_reason",
    "official_source_name",
    "official_source_url",
    "official_source_kind",
    "verification_scope",
    "verified_package_names",
    "verified_executable_names",
    "verification_note",
)

DISTRO_EVIDENCE_CANONICAL_FIELDS: tuple[str, ...] = (
    "artifact_entry_id",
    "source_policy_artifact_entry_id",
    "distro_family",
    "tool_id",
    "package_names",
    "executable_names",
    "evidence_record_id",
)

DISTRO_EVIDENCE_BASELINE_FIELDS: tuple[str, ...] = (
    "evidence_source",
    "evidence_source_type",
    "evidence_status",
    "evidence_note",
    "external_verification_required_for_new_mappings",
    "release_blocking",
    "blocker_reason",
)

DISTRO_EVIDENCE_PROMOTION_FIELDS: tuple[str, ...] = (
    "official_source_name",
    "official_source_url",
    "official_source_kind",
    "verification_scope",
    "verified_package_names",
    "verified_executable_names",
    "verification_note",
)


class LinuxToolProvisioningPolicy(NamedTuple):
    """Linux provisioning policy for one required tool and artifact."""

    artifact_entry_id: str
    artifact_family: LinuxArtifactFamily
    tool_id: str
    mechanism: LinuxProvisioningMechanism
    executable_names: tuple[str, ...]
    version_probe: tuple[str, ...]
    network_required: bool
    checksum_required: bool
    pin_required: bool
    package_names: tuple[str, ...] = ()
    target_subdir: str = "tools"
    evidence_fields_required: tuple[str, ...] = EVIDENCE_FIELDS_BASE
    source_url: str | None = None
    pinned_version: str | None = None
    release_blocking: bool = False
    blocker_reason: str | None = None


class LinuxDistroMappingRecord(NamedTuple):
    """Auditable distro/package-manager mapping state for one Linux tool."""

    artifact_entry_id: str
    distro_family: LinuxDistroFamily
    tool_id: str
    evidence_record_id: str | None
    package_names: tuple[str, ...]
    executable_names: tuple[str, ...]
    provenance_status: LinuxProvenanceStatus
    trust_boundary: LinuxTrustBoundary
    mapping_status: LinuxDistroMappingStatus
    evidence_note: str
    release_blocking: bool
    evidence_source: str | None = None
    evidence_url: str | None = None
    blocker_reason: str | None = None
    source_policy_artifact_entry_id: str | None = None


class LinuxDistroMappingEvidenceRecord(NamedTuple):
    """Repository-local evidence for one approved distro package mapping."""

    artifact_entry_id: str
    source_policy_artifact_entry_id: str
    distro_family: LinuxDistroFamily
    tool_id: str
    package_names: tuple[str, ...]
    executable_names: tuple[str, ...]
    evidence_record_id: str
    evidence_source: str
    evidence_source_type: LinuxDistroEvidenceSourceType
    evidence_status: LinuxDistroEvidenceStatus
    evidence_note: str
    external_verification_required_for_new_mappings: bool
    release_blocking: bool
    blocker_reason: str | None = None
    official_source_name: str | None = None
    official_source_url: str | None = None
    official_source_kind: LinuxDistroOfficialSourceKind | None = None
    verification_scope: LinuxDistroVerificationScope | None = None
    verified_package_names: tuple[str, ...] = ()
    verified_executable_names: tuple[str, ...] = ()
    verification_note: str | None = None


class LinuxToolProvenanceRecord(NamedTuple):
    """Auditable Linux provenance state for one required tool policy."""

    tool_id: str
    artifact_entry_id: str
    mechanism: LinuxProvisioningMechanism
    provenance_status: LinuxProvenanceStatus
    trust_boundary: LinuxTrustBoundary
    source_name: str
    package_names: tuple[str, ...]
    license_review_required: bool
    network_required: bool
    release_blocking: bool
    evidence_fields_required: tuple[str, ...]
    source_url: str | None = None
    pinned_version: str | None = None
    checksum_algorithm: str | None = None
    checksum: str | None = None
    blocker_reason: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_src_path(root: Path) -> None:
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _provisioning_module(root: Path | None = None) -> Any:
    resolved_root = _repo_root() if root is None else root
    _ensure_src_path(resolved_root)
    return importlib.import_module("ecli.extensions.linters.core.provisioning")


def _registry_module(root: Path | None = None) -> Any:
    resolved_root = _repo_root() if root is None else root
    _ensure_src_path(resolved_root)
    return importlib.import_module("ecli.extensions.linters.core.provisioning_registry")


def _canonical_artifact_entry_id(
    artifact_entry_id: str, root: Path | None = None
) -> str:
    return cast(
        str, _provisioning_module(root).canonical_artifact_entry_id(artifact_entry_id)
    )


def _looks_like_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute():
        return True
    if "/" in value or "\\" in value:
        return True
    return any(part in {"", ".", ".."} for part in (*posix.parts, *windows.parts))


def _validate_path_part(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path segment")
    if _looks_like_path(value):
        raise ValueError(f"{label} must be a plain path segment: {value!r}")
    return value


def _safe_base_dir(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _safe_child(base: Path, *parts: str) -> Path:
    resolved_base = _safe_base_dir(base)
    child = resolved_base
    for index, part in enumerate(parts, start=1):
        child = child / _validate_path_part(part, f"path part {index}")
    resolved_child = child.resolve(strict=False)
    try:
        resolved_child.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"path escapes base directory: {resolved_child}") from exc
    return resolved_child


def _ensure_child(base: Path, child: Path, label: str) -> None:
    try:
        child.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"{label} escapes base directory: {child}") from exc


def linux_artifact_ids() -> tuple[str, ...]:
    """Return the Linux-scope artifact IDs for PR #127."""
    return LINUX_ARTIFACT_IDS


def linux_full_artifact_ids(root: Path | None = None) -> tuple[str, ...]:
    """Return Linux-scope artifacts that claim Full provisioning support."""
    registry = _registry_module(root)
    entries = {
        entry.artifact_entry_id: entry for entry in registry.ARTIFACT_CONTRACT_ENTRIES
    }
    missing = sorted(set(LINUX_ARTIFACT_IDS) - set(entries))
    if missing:
        raise ValueError(f"Linux artifact IDs missing from registry: {missing}")
    return tuple(
        artifact_id
        for artifact_id in LINUX_ARTIFACT_IDS
        if entries[artifact_id].full_provisioning_supported
    )


def is_linux_artifact_id(artifact_entry_id: str, root: Path | None = None) -> bool:
    """Return whether *artifact_entry_id* is a canonical Linux-scope artifact."""
    try:
        canonical_id = _canonical_artifact_entry_id(artifact_entry_id, root)
    except (KeyError, ValueError):
        return False
    return canonical_id in LINUX_ARTIFACT_IDS


def _linux_artifact_entry_id(artifact_entry_id: str, root: Path | None = None) -> str:
    canonical_id = _canonical_artifact_entry_id(artifact_entry_id, root)
    if canonical_id not in LINUX_ARTIFACT_IDS:
        raise ValueError(f"not a Linux F4 provisioning artifact: {canonical_id!r}")
    return canonical_id


def _artifact_family(artifact_entry_id: str) -> LinuxArtifactFamily:
    if artifact_entry_id in LINUX_PACKAGE_MANAGER_ARTIFACT_IDS:
        return "package-manager"
    if artifact_entry_id in LINUX_SELF_CONTAINED_ARTIFACT_IDS:
        return "self-contained"
    if artifact_entry_id in LINUX_DOCKER_HELPER_ARTIFACT_IDS:
        return "docker-helper"
    if artifact_entry_id in LINUX_NIX_ARTIFACT_IDS:
        return "nix-policy"
    raise ValueError(f"not a Linux F4 provisioning artifact: {artifact_entry_id!r}")


def _contracts(root: Path | None = None) -> tuple[Any, ...]:
    return tuple(_registry_module(root).load_linter_tool_contracts())


def _required_contracts(root: Path | None = None) -> tuple[Any, ...]:
    return tuple(
        contract for contract in _contracts(root) if contract.required_for_full
    )


def _package_policy_artifact_id(artifact_entry_id: str) -> str:
    return PACKAGE_POLICY_SOURCE_BY_HELPER.get(artifact_entry_id, artifact_entry_id)


def _os_package_names(artifact_entry_id: str, tool_id: str) -> tuple[str, ...]:
    package_artifact_id = _package_policy_artifact_id(artifact_entry_id)
    return OS_PACKAGE_NAMES.get(package_artifact_id, {}).get(tool_id, ())


def _blocked_policy(
    *,
    artifact_entry_id: str,
    artifact_family: LinuxArtifactFamily,
    contract: Any,
    reason: str,
) -> LinuxToolProvisioningPolicy:
    fields = (*EVIDENCE_FIELDS_BASE, "blocker_reason")
    return LinuxToolProvisioningPolicy(
        artifact_entry_id=artifact_entry_id,
        artifact_family=artifact_family,
        tool_id=contract.tool_id,
        mechanism="blocked-missing-provenance",
        executable_names=tuple(contract.executable_names),
        version_probe=tuple(contract.version_probe.command),
        network_required=False,
        checksum_required=bool(contract.checksum_required_for_downloads),
        pin_required=True,
        source_url=contract.source_url,
        pinned_version=contract.pinned_version,
        release_blocking=True,
        blocker_reason=reason,
        evidence_fields_required=fields,
    )


def _policy_for_contract(
    artifact_entry_id: str,
    contract: Any,
) -> LinuxToolProvisioningPolicy:
    artifact_family = _artifact_family(artifact_entry_id)
    if contract.provider_kind == "internal":
        return LinuxToolProvisioningPolicy(
            artifact_entry_id=artifact_entry_id,
            artifact_family=artifact_family,
            tool_id=contract.tool_id,
            mechanism="bundled-internal",
            executable_names=tuple(contract.executable_names),
            version_probe=tuple(contract.version_probe.command),
            network_required=False,
            checksum_required=False,
            pin_required=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )

    if artifact_family == "nix-policy":
        return LinuxToolProvisioningPolicy(
            artifact_entry_id=artifact_entry_id,
            artifact_family=artifact_family,
            tool_id=contract.tool_id,
            mechanism="nix-derivation",
            executable_names=tuple(contract.executable_names),
            version_probe=tuple(contract.version_probe.command),
            network_required=False,
            checksum_required=False,
            pin_required=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )

    package_names = _os_package_names(artifact_entry_id, contract.tool_id)
    if package_names:
        return LinuxToolProvisioningPolicy(
            artifact_entry_id=artifact_entry_id,
            artifact_family=artifact_family,
            tool_id=contract.tool_id,
            mechanism="os-package-manager",
            executable_names=tuple(contract.executable_names),
            version_probe=tuple(contract.version_probe.command),
            network_required=False,
            checksum_required=False,
            pin_required=False,
            package_names=package_names,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )

    if (
        artifact_family in {"package-manager", "docker-helper"}
        and contract.tool_id in TOOLCHAIN_COMPONENTS
    ):
        return LinuxToolProvisioningPolicy(
            artifact_entry_id=artifact_entry_id,
            artifact_family=artifact_family,
            tool_id=contract.tool_id,
            mechanism="toolchain-component",
            executable_names=tuple(contract.executable_names),
            version_probe=tuple(contract.version_probe.command),
            network_required=False,
            checksum_required=False,
            pin_required=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )

    if artifact_family == "self-contained":
        return _blocked_policy(
            artifact_entry_id=artifact_entry_id,
            artifact_family=artifact_family,
            contract=contract,
            reason=(
                "self-contained Linux artifacts need pinned versions and "
                "checksums before bundling this external Full-required tool"
            ),
        )

    return _blocked_policy(
        artifact_entry_id=artifact_entry_id,
        artifact_family=artifact_family,
        contract=contract,
        reason=(
            "Linux package metadata has no safe package-manager mapping or "
            "pinned/checksummed artifact-managed provisioning source yet"
        ),
    )


def _linux_policies_for_required_contracts(
    artifact_entry_id: str,
    contracts: tuple[Any, ...],
) -> tuple[LinuxToolProvisioningPolicy, ...]:
    return tuple(
        _policy_for_contract(artifact_entry_id, contract) for contract in contracts
    )


def linux_provisioning_policy_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[LinuxToolProvisioningPolicy, ...]:
    """Return required-tool Linux policies for one canonical artifact."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    return _linux_policies_for_required_contracts(
        canonical_id, _required_contracts(root)
    )


def linux_tool_policy_matrix(
    root: Path | None = None,
) -> tuple[LinuxToolProvisioningPolicy, ...]:
    """Return the complete Linux artifact x Full-required tool policy matrix."""
    required_contracts = _required_contracts(root)
    return tuple(
        policy
        for artifact_id in linux_artifact_ids()
        for policy in _linux_policies_for_required_contracts(
            _linux_artifact_entry_id(artifact_id, root),
            required_contracts,
        )
    )


def linux_provenance_record_for_policy(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxToolProvenanceRecord:
    """Return the canonical provenance record for one Linux tool policy."""
    status = _provenance_status_for_policy(policy)
    trust_boundary = TRUST_BOUNDARY_BY_PROVENANCE_STATUS[status]
    blocked = _is_blocked_provenance_status(status)
    return LinuxToolProvenanceRecord(
        tool_id=policy.tool_id,
        artifact_entry_id=policy.artifact_entry_id,
        mechanism=policy.mechanism,
        provenance_status=status,
        trust_boundary=trust_boundary,
        source_name=_provenance_source_name(policy, status),
        source_url=policy.source_url,
        package_names=policy.package_names,
        pinned_version=policy.pinned_version,
        checksum_algorithm=None,
        checksum=None,
        license_review_required=_license_review_required(status),
        network_required=policy.network_required,
        release_blocking=blocked or policy.release_blocking,
        blocker_reason=_provenance_blocker_reason(status, policy) if blocked else None,
        evidence_fields_required=_provenance_evidence_fields(status),
    )


def linux_provenance_catalog_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[LinuxToolProvenanceRecord, ...]:
    """Return provenance records for every Full-required tool in one artifact."""
    return tuple(
        linux_provenance_record_for_policy(policy)
        for policy in linux_provisioning_policy_for_artifact(artifact_entry_id, root)
    )


def linux_provenance_matrix(
    root: Path | None = None,
) -> tuple[LinuxToolProvenanceRecord, ...]:
    """Return the complete Linux artifact x Full-required provenance matrix."""
    return tuple(
        linux_provenance_record_for_policy(policy)
        for policy in linux_tool_policy_matrix(root)
    )


def linux_release_blocking_provenance_items(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[LinuxToolProvenanceRecord, ...]:
    """Return release-blocking provenance records for one Linux artifact."""
    return tuple(
        record
        for record in linux_provenance_catalog_for_artifact(artifact_entry_id, root)
        if record.release_blocking
    )


def linux_provenance_summary_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic provenance counts for one Linux artifact."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    records = linux_provenance_catalog_for_artifact(canonical_id, root)
    release_blocking = tuple(record for record in records if record.release_blocking)
    return {
        "artifact_entry_id": canonical_id,
        "tool_count": len(records),
        "release_blocking_count": len(release_blocking),
        "provenance_status_counts": _record_counts(
            record.provenance_status for record in records
        ),
        "trust_boundary_counts": _record_counts(
            record.trust_boundary for record in records
        ),
        "distro_mapping_status_counts": linux_distro_mapping_summary_for_artifact(
            canonical_id,
            root,
        )["mapping_status_counts"],
    }


def _record_counts(values: tuple[str, ...] | Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def linux_distro_mapping_for_policy(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxDistroMappingRecord | None:
    """Return distro/package-manager mapping evidence for one Linux policy."""
    if policy.artifact_entry_id not in LINUX_DISTRO_MAPPING_ARTIFACT_IDS:
        return None
    if policy.mechanism == "os-package-manager":
        return _approved_distro_mapping_record(policy)
    if _provenance_status_for_policy(policy) == "blocked-missing-distro-mapping":
        return _blocked_distro_mapping_record(policy)
    return None


def linux_distro_mapping_catalog_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[LinuxDistroMappingRecord, ...]:
    """Return distro mapping records for one Linux package-manager artifact."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    if canonical_id not in LINUX_DISTRO_MAPPING_ARTIFACT_IDS:
        return ()
    records: list[LinuxDistroMappingRecord] = []
    for policy in linux_provisioning_policy_for_artifact(canonical_id, root):
        record = linux_distro_mapping_for_policy(policy)
        if record is not None:
            records.append(record)
    return tuple(records)


def linux_distro_mapping_matrix(
    root: Path | None = None,
) -> tuple[LinuxDistroMappingRecord, ...]:
    """Return the complete Linux package-manager distro mapping matrix."""
    required_contracts = _required_contracts(root)
    records: list[LinuxDistroMappingRecord] = []
    for artifact_id in LINUX_DISTRO_MAPPING_ARTIFACT_IDS:
        policies = _linux_policies_for_required_contracts(
            _linux_artifact_entry_id(artifact_id, root),
            required_contracts,
        )
        for policy in policies:
            record = linux_distro_mapping_for_policy(policy)
            if record is not None:
                records.append(record)
    return tuple(records)


def linux_distro_mapping_summary_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic distro mapping counts for one Linux artifact."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    records = linux_distro_mapping_catalog_for_artifact(canonical_id, root)
    blocked = tuple(record for record in records if record.release_blocking)
    approved = tuple(record for record in records if not record.release_blocking)
    return {
        "artifact_entry_id": canonical_id,
        "distro_mapping_count": len(records),
        "approved_count": len(approved),
        "blocked_count": len(blocked),
        "mapping_status_counts": _record_counts(
            record.mapping_status for record in records
        ),
        "distro_family_counts": _record_counts(
            record.distro_family for record in records
        ),
        "evidence_status_counts": linux_distro_mapping_evidence_summary_for_artifact(
            canonical_id,
            root,
        )["evidence_status_counts"],
    }


def linux_unmapped_package_manager_tools(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[LinuxDistroMappingRecord, ...]:
    """Return package-manager tools blocked by missing distro mapping evidence."""
    return tuple(
        record
        for record in linux_distro_mapping_catalog_for_artifact(
            artifact_entry_id,
            root,
        )
        if record.mapping_status in LINUX_BLOCKED_DISTRO_MAPPING_STATUSES
    )


def linux_distro_mapping_evidence_record_id(
    policy: LinuxToolProvisioningPolicy,
) -> str:
    """Return the deterministic distro evidence record ID."""
    source_artifact_id = _package_policy_artifact_id(policy.artifact_entry_id)
    source_type = (
        "official-distro-metadata"
        if (policy.artifact_entry_id, policy.tool_id)
        in OFFICIAL_DISTRO_EVIDENCE_BY_POLICY
        else "repository-local-policy"
    )
    return f"{source_type}:{source_artifact_id}:{policy.tool_id}"


def linux_distro_mapping_evidence_for_policy(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxDistroMappingEvidenceRecord | None:
    """Return distro evidence for one approved distro mapping policy."""
    if policy.mechanism != "os-package-manager":
        return None
    if policy.artifact_entry_id not in LINUX_DISTRO_MAPPING_ARTIFACT_IDS:
        return None
    source_artifact_id = _package_policy_artifact_id(policy.artifact_entry_id)
    package_names = OS_PACKAGE_NAMES.get(source_artifact_id, {}).get(policy.tool_id)
    if package_names != policy.package_names:
        return None
    override = OFFICIAL_DISTRO_EVIDENCE_BY_POLICY.get(
        (policy.artifact_entry_id, policy.tool_id)
    )
    fields: dict[str, Any] = {
        "artifact_entry_id": policy.artifact_entry_id,
        "source_policy_artifact_entry_id": source_artifact_id,
        "distro_family": DISTRO_FAMILY_BY_ARTIFACT[policy.artifact_entry_id],
        "tool_id": policy.tool_id,
        "package_names": policy.package_names,
        "executable_names": policy.executable_names,
        "evidence_record_id": linux_distro_mapping_evidence_record_id(policy),
        "evidence_source": "OS_PACKAGE_NAMES",
        "evidence_source_type": "repository-local-policy",
        "evidence_status": "current-policy-baseline",
        "evidence_note": (
            "Repository-local OS_PACKAGE_NAMES baseline records the package names "
            "currently approved by ECLI policy; new mappings require external "
            "verification before promotion."
        ),
        "external_verification_required_for_new_mappings": True,
        "release_blocking": False,
        "blocker_reason": None,
    }
    if override is not None:
        fields.update(override)
        fields["verified_package_names"] = policy.package_names
        fields["verified_executable_names"] = policy.executable_names
    return LinuxDistroMappingEvidenceRecord(**fields)


def linux_distro_mapping_evidence_catalog_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[LinuxDistroMappingEvidenceRecord, ...]:
    """Return distro evidence records for one Linux artifact."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    if canonical_id not in LINUX_DISTRO_MAPPING_ARTIFACT_IDS:
        return ()
    records: list[LinuxDistroMappingEvidenceRecord] = []
    for policy in linux_provisioning_policy_for_artifact(canonical_id, root):
        record = linux_distro_mapping_evidence_for_policy(policy)
        if record is not None:
            records.append(record)
    return tuple(records)


def linux_distro_mapping_evidence_matrix(
    root: Path | None = None,
) -> tuple[LinuxDistroMappingEvidenceRecord, ...]:
    """Return evidence for every approved Linux distro mapping."""
    required_contracts = _required_contracts(root)
    records: list[LinuxDistroMappingEvidenceRecord] = []
    for artifact_id in LINUX_DISTRO_MAPPING_ARTIFACT_IDS:
        policies = _linux_policies_for_required_contracts(
            _linux_artifact_entry_id(artifact_id, root),
            required_contracts,
        )
        for policy in policies:
            record = linux_distro_mapping_evidence_for_policy(policy)
            if record is not None:
                records.append(record)
    return tuple(records)


def linux_official_distro_evidence_matrix() -> tuple[dict[str, Any], ...]:
    """Return deterministic audit rows for configured official distro evidence."""
    return tuple(
        _official_distro_evidence_row(artifact_entry_id, tool_id, override)
        for (
            artifact_entry_id,
            tool_id,
        ), override in OFFICIAL_DISTRO_EVIDENCE_BY_POLICY.items()
    )


def _official_distro_evidence_row(
    artifact_entry_id: str,
    tool_id: str,
    override: Mapping[str, Any],
) -> dict[str, Any]:
    source_artifact_id = _package_policy_artifact_id(artifact_entry_id)
    return {
        "artifact_entry_id": artifact_entry_id,
        "tool_id": tool_id,
        "expected_evidence_record_id": (
            f"official-distro-metadata:{source_artifact_id}:{tool_id}"
        ),
        "evidence_source": override.get("evidence_source"),
        "evidence_source_type": override.get("evidence_source_type"),
        "evidence_status": override.get("evidence_status"),
        "official_source_name": override.get("official_source_name"),
        "official_source_url": override.get("official_source_url"),
        "official_source_kind": override.get("official_source_kind"),
        "verification_scope": override.get("verification_scope"),
        "release_blocking": override.get("release_blocking"),
        "external_verification_required_for_new_mappings": override.get(
            "external_verification_required_for_new_mappings"
        ),
    }


def linux_official_distro_evidence_summary() -> dict[str, Any]:
    """Return deterministic counts for configured official distro evidence."""
    rows = linux_official_distro_evidence_matrix()
    return {
        "official_override_count": len(rows),
        "artifact_counts": _record_counts(row["artifact_entry_id"] for row in rows),
        "evidence_status_counts": _record_counts(
            row["evidence_status"] for row in rows
        ),
        "evidence_source_type_counts": _record_counts(
            row["evidence_source_type"] for row in rows
        ),
        "official_source_kind_counts": _record_counts(
            row["official_source_kind"] for row in rows
        ),
        "verification_scope_counts": _record_counts(
            row["verification_scope"] for row in rows
        ),
        "release_blocking_count": sum(
            1 for row in rows if row["release_blocking"] is True
        ),
        "non_debian_override_count": sum(
            1 for row in rows if row["artifact_entry_id"] != "deb"
        ),
    }


def linux_official_distro_evidence_drift_errors() -> list[str]:
    """Return drift errors between official overrides and generated evidence."""
    errors: list[str] = []
    for row in linux_official_distro_evidence_matrix():
        generated, missing_error = _generated_official_distro_evidence_record(row)
        if missing_error is not None:
            errors.append(missing_error)
            continue
        if generated is None:
            continue
        errors.extend(_official_distro_evidence_record_drift_errors(row, generated))
    return errors


def linux_official_distro_evidence_audit_report() -> dict[str, Any]:
    """Return a deterministic release-facing official evidence audit report."""
    drift_errors = linux_official_distro_evidence_drift_errors()
    return {
        "summary": linux_official_distro_evidence_summary(),
        "matrix": list(linux_official_distro_evidence_matrix()),
        "drift_errors": drift_errors,
        "ok": not drift_errors,
    }


def _generated_official_distro_evidence_record(
    row: Mapping[str, Any],
) -> tuple[LinuxDistroMappingEvidenceRecord | None, str | None]:
    artifact_entry_id = str(row["artifact_entry_id"])
    tool_id = str(row["tool_id"])
    prefix = f"{artifact_entry_id}/{tool_id}"
    try:
        policies = linux_provisioning_policy_for_artifact(artifact_entry_id)
    except (KeyError, ValueError):
        return (
            None,
            f"{prefix}: official override for unknown artifact/tool policy",
        )
    matching_policy = next(
        (policy for policy in policies if policy.tool_id == tool_id),
        None,
    )
    if matching_policy is None or matching_policy.mechanism != "os-package-manager":
        return (
            None,
            f"{prefix}: official override for unknown artifact/tool policy",
        )

    generated = linux_distro_mapping_evidence_for_policy(matching_policy)
    if generated is None:
        return (
            None,
            f"{prefix}: official override not reflected in generated distro evidence",
        )
    return generated, None


def _official_distro_evidence_record_drift_errors(
    row: Mapping[str, Any],
    generated_record: Any,
) -> list[str]:
    data = _distro_evidence_record_mapping(generated_record)
    prefix = f"{row['artifact_entry_id']}/{row['tool_id']}"
    if data is None:
        return [f"{prefix}: generated distro evidence is not an object"]

    errors: list[str] = []
    if data.get("evidence_record_id") != row.get("expected_evidence_record_id"):
        errors.append(f"{prefix}: evidence_record_id mismatch")
    for field in (
        "evidence_source_type",
        "evidence_status",
        "official_source_kind",
        "verification_scope",
        "official_source_url",
        "release_blocking",
        "external_verification_required_for_new_mappings",
    ):
        if data.get(field) != row.get(field):
            errors.append(f"{prefix}: {field} mismatch")
    return errors


def linux_distro_mapping_evidence_summary_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic distro evidence counts."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    records = linux_distro_mapping_evidence_catalog_for_artifact(canonical_id, root)
    return {
        "artifact_entry_id": canonical_id,
        "evidence_record_count": len(records),
        "evidence_status_counts": _record_counts(
            record.evidence_status for record in records
        ),
        "evidence_source_type_counts": _record_counts(
            record.evidence_source_type for record in records
        ),
    }


def linux_distro_evidence_promotion_requirements() -> dict[str, tuple[str, ...]]:
    """Return the official-source fields required to promote distro evidence."""
    return {
        "required_fields": DISTRO_EVIDENCE_PROMOTION_FIELDS,
        "official_source_types": (
            "official-distro-metadata",
            "upstream-project-docs",
        ),
        "official_source_kinds": (
            "distro-package-index",
            "distro-package-recipe",
            "upstream-install-doc",
            "upstream-release-page",
        ),
        "verification_scopes": (
            "package-name-only",
            "package-name-and-executable",
            "package-name-executable-and-license",
        ),
    }


def linux_distro_mapping_evidence_promotion_errors(record: Any) -> list[str]:
    """Return why one distro evidence record cannot be promoted."""
    data = _distro_evidence_record_mapping(record)
    if data is None:
        return ["distro evidence promotion record must be an object"]
    if data.get("evidence_status") != "verified-official-source":
        return ["evidence_status must be verified-official-source"]
    return _verified_official_source_evidence_errors("distro evidence", data)


def linux_distro_mapping_evidence_can_promote(record: Any) -> bool:
    """Return whether one distro evidence record satisfies promotion policy."""
    return not linux_distro_mapping_evidence_promotion_errors(record)


def linux_distro_mapping_evidence_promotion_matrix(
    root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return promotion-gate state for every generated distro evidence record."""
    return tuple(
        _distro_evidence_promotion_matrix_row(record)
        for record in linux_distro_mapping_evidence_matrix(root)
    )


def linux_distro_mapping_evidence_promotion_summary_for_artifact(
    artifact_entry_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return promotion-gate counts for one Linux artifact."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    rows = tuple(
        _distro_evidence_promotion_matrix_row(record)
        for record in linux_distro_mapping_evidence_catalog_for_artifact(
            canonical_id,
            root,
        )
    )
    return {
        "artifact_entry_id": canonical_id,
        "evidence_record_count": len(rows),
        "promotable_count": sum(1 for row in rows if row["can_promote"]),
        "baseline_not_promoted_count": sum(
            1 for row in rows if row["promotion_state"] == "baseline-not-promoted"
        ),
        "verified_official_source_count": sum(
            1 for row in rows if row["evidence_status"] == "verified-official-source"
        ),
        "promotion_state_counts": _record_counts(
            row["promotion_state"] for row in rows
        ),
    }


def _distro_evidence_promotion_matrix_row(
    record: LinuxDistroMappingEvidenceRecord,
) -> dict[str, Any]:
    errors = linux_distro_mapping_evidence_promotion_errors(record)
    return {
        "artifact_entry_id": record.artifact_entry_id,
        "source_policy_artifact_entry_id": record.source_policy_artifact_entry_id,
        "tool_id": record.tool_id,
        "evidence_record_id": record.evidence_record_id,
        "evidence_source_type": record.evidence_source_type,
        "evidence_status": record.evidence_status,
        "can_promote": not errors,
        "promotion_error_count": len(errors),
        "promotion_state": _distro_evidence_promotion_state(record, errors),
    }


def _distro_evidence_promotion_state(
    record: LinuxDistroMappingEvidenceRecord,
    promotion_errors: list[str],
) -> str:
    if record.evidence_status == "current-policy-baseline":
        return "baseline-not-promoted"
    if record.evidence_status == "verified-official-source" and not promotion_errors:
        return "verified-official-source"
    if record.evidence_status in {"blocked-missing-evidence", "blocked-evidence-drift"}:
        return "blocked-promotion"
    return "invalid-promotion"


def _approved_distro_mapping_record(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxDistroMappingRecord:
    source_artifact_id = _package_policy_artifact_id(policy.artifact_entry_id)
    return LinuxDistroMappingRecord(
        artifact_entry_id=policy.artifact_entry_id,
        distro_family=DISTRO_FAMILY_BY_ARTIFACT[policy.artifact_entry_id],
        tool_id=policy.tool_id,
        evidence_record_id=linux_distro_mapping_evidence_record_id(policy),
        package_names=policy.package_names,
        executable_names=policy.executable_names,
        provenance_status="distro-signed-package",
        trust_boundary="distro-package-manager",
        mapping_status="approved-existing-policy",
        evidence_source="OS_PACKAGE_NAMES",
        evidence_url=None,
        evidence_note=(
            "Repository-local OS_PACKAGE_NAMES policy intentionally maps this "
            f"Full-required tool to {source_artifact_id} package metadata."
        ),
        release_blocking=False,
        blocker_reason=None,
        source_policy_artifact_entry_id=source_artifact_id,
    )


def _blocked_distro_mapping_record(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxDistroMappingRecord:
    source_artifact_id = _package_policy_artifact_id(policy.artifact_entry_id)
    return LinuxDistroMappingRecord(
        artifact_entry_id=policy.artifact_entry_id,
        distro_family=DISTRO_FAMILY_BY_ARTIFACT[policy.artifact_entry_id],
        tool_id=policy.tool_id,
        evidence_record_id=None,
        package_names=(),
        executable_names=policy.executable_names,
        provenance_status="blocked-missing-distro-mapping",
        trust_boundary="unresolved",
        mapping_status="blocked-missing-distro-mapping",
        evidence_source="OS_PACKAGE_NAMES",
        evidence_url=None,
        evidence_note=(
            "No repository-local OS_PACKAGE_NAMES entry exists for this "
            f"Full-required tool in the {source_artifact_id} policy."
        ),
        release_blocking=True,
        blocker_reason=_provenance_blocker_reason(
            "blocked-missing-distro-mapping",
            policy,
        ),
        source_policy_artifact_entry_id=source_artifact_id,
    )


def _provenance_status_for_policy(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxProvenanceStatus:
    if policy.mechanism == "bundled-internal":
        return "internal-bundled"
    if policy.mechanism == "os-package-manager":
        return "distro-signed-package"
    if policy.mechanism == "nix-derivation":
        return "nix-derivation"
    if policy.mechanism == "toolchain-component":
        return "toolchain-component"
    if policy.mechanism == "language-package-manager":
        return "pinned-language-package"
    if policy.mechanism in {
        "ecli-managed-tools",
        "jar-shim",
        "verified-upstream-download",
    }:
        return "pinned-upstream-artifact"
    if policy.mechanism == "blocked-missing-provenance":
        return _blocked_provenance_status(policy)
    raise ValueError(
        f"{policy.tool_id}: unsupported Linux mechanism {policy.mechanism!r}"
    )


def _blocked_provenance_status(
    policy: LinuxToolProvisioningPolicy,
) -> LinuxProvenanceStatus:
    if not policy.source_url:
        return "blocked-missing-source-url"
    if policy.artifact_family in {"package-manager", "docker-helper"}:
        return "blocked-missing-distro-mapping"
    if policy.pinned_version is None:
        return "blocked-missing-version-pin"
    if policy.checksum_required:
        return "blocked-missing-checksum"
    return "blocked-missing-install-strategy"


def _provenance_source_name(
    policy: LinuxToolProvisioningPolicy,
    status: LinuxProvenanceStatus,
) -> str:
    if status == "internal-bundled":
        return "ECLI source tree"
    if status == "distro-signed-package":
        return f"{policy.artifact_entry_id} package metadata"
    if status == "nix-derivation":
        return "Nix derivation/input"
    if status == "toolchain-component":
        return TOOLCHAIN_COMPONENTS.get(policy.tool_id, "toolchain component")
    if policy.source_url:
        return policy.source_url
    return policy.tool_id


def _license_review_required(status: LinuxProvenanceStatus) -> bool:
    return status in {
        "pinned-upstream-artifact",
        "pinned-language-package",
        *LINUX_BLOCKED_PROVENANCE_STATUSES,
    }


def _provenance_blocker_reason(
    status: LinuxProvenanceStatus,
    policy: LinuxToolProvisioningPolicy,
) -> str:
    reasons = {
        "blocked-missing-version-pin": (
            "missing audited pinned version for this Linux Full-required tool"
        ),
        "blocked-missing-checksum": (
            "missing audited checksum for this Linux Full-required tool"
        ),
        "blocked-missing-source-url": (
            "missing audited source URL for this Linux Full-required tool"
        ),
        "blocked-missing-install-strategy": (
            "missing concrete non-dry-run Linux install strategy"
        ),
        "blocked-missing-license-review": (
            "missing license review for this Linux Full-required tool"
        ),
        "blocked-missing-distro-mapping": (
            "missing safe distro package or delegated toolchain mapping for this "
            "Linux Full-required tool"
        ),
    }
    base = reasons.get(status, "blocked Linux provenance state")
    if policy.blocker_reason:
        return f"{base}: {policy.blocker_reason}"
    return base


def _is_blocked_provenance_status(status: str) -> bool:
    return status in LINUX_BLOCKED_PROVENANCE_STATUSES


def _provenance_evidence_fields(
    status: LinuxProvenanceStatus,
) -> tuple[str, ...]:
    fields = (*EVIDENCE_FIELDS_BASE, *PROVENANCE_EVIDENCE_FIELDS)
    if _is_blocked_provenance_status(status):
        fields = (*fields, "blocker_reason")
    return fields


def linux_package_manager_dependency_names(
    artifact_entry_id: str,
    root: Path | None = None,
) -> tuple[str, ...]:
    """Return OS package names declared by one Linux artifact policy."""
    names: list[str] = []
    for policy in linux_provisioning_policy_for_artifact(artifact_entry_id, root):
        if policy.mechanism != "os-package-manager":
            continue
        for package_name in policy.package_names:
            if package_name not in names:
                names.append(package_name)
    return tuple(names)


def linux_artifact_tools_dir(
    target_dir: Path,
    artifact_entry_id: str,
    root: Path | None = None,
) -> Path:
    """Return the artifact-managed Linux tools root inside *target_dir*."""
    _linux_artifact_entry_id(artifact_entry_id, root)
    return _safe_child(target_dir, "tools")


def linux_artifact_manifest_path(
    target_dir: Path,
    artifact_entry_id: str,
    root: Path | None = None,
) -> Path:
    """Return the deterministic Linux tools manifest path inside *target_dir*."""
    _linux_artifact_entry_id(artifact_entry_id, root)
    return _safe_child(target_dir, "manifest", LINUX_MANIFEST_FILENAME)


def _tool_target_dir(target_dir: Path, policy: LinuxToolProvisioningPolicy) -> Path:
    return _safe_child(
        target_dir,
        policy.target_subdir,
        _validate_path_part(policy.tool_id, "tool id"),
    )


def _policy_to_manifest_item(
    policy: LinuxToolProvisioningPolicy,
    *,
    target_dir: Path,
    evidence_dir: Path,
) -> dict[str, Any]:
    data = policy._asdict()
    data.update(
        _provenance_record_to_manifest_fields(
            linux_provenance_record_for_policy(policy)
        )
    )
    data["executable_names"] = list(policy.executable_names)
    data["version_probe"] = list(policy.version_probe)
    data["target_dir"] = str(_tool_target_dir(target_dir, policy))
    data["evidence_dir"] = str(_safe_base_dir(evidence_dir))
    mapping_record = linux_distro_mapping_for_policy(policy)
    if mapping_record is not None:
        data["distro_mapping"] = _distro_mapping_record_to_manifest_fields(
            mapping_record
        )
        evidence_fields = list(data["evidence_fields_required"])
        if "distro_mapping" not in evidence_fields:
            evidence_fields.append("distro_mapping")
        data["evidence_fields_required"] = evidence_fields
    return data


def _provenance_record_to_manifest_fields(
    record: LinuxToolProvenanceRecord,
) -> dict[str, Any]:
    data = record._asdict()
    data["package_names"] = list(record.package_names)
    data["evidence_fields_required"] = list(record.evidence_fields_required)
    return data


def _distro_mapping_record_to_manifest_fields(
    record: LinuxDistroMappingRecord,
) -> dict[str, Any]:
    data = record._asdict()
    data["package_names"] = list(record.package_names)
    data["executable_names"] = list(record.executable_names)
    policy = _policy_from_distro_mapping_record(record)
    evidence = linux_distro_mapping_evidence_for_policy(policy)
    if evidence is not None:
        data["evidence"] = _distro_mapping_evidence_record_to_manifest_fields(evidence)
    return data


def _policy_from_distro_mapping_record(
    record: LinuxDistroMappingRecord,
) -> LinuxToolProvisioningPolicy:
    mechanism: LinuxProvisioningMechanism = (
        "os-package-manager"
        if record.mapping_status
        in {"approved-existing-policy", "approved-with-evidence"}
        else "blocked-missing-provenance"
    )
    return LinuxToolProvisioningPolicy(
        artifact_entry_id=record.artifact_entry_id,
        artifact_family=_artifact_family(record.artifact_entry_id),
        tool_id=record.tool_id,
        mechanism=mechanism,
        executable_names=record.executable_names,
        version_probe=(),
        network_required=False,
        checksum_required=False,
        pin_required=False,
        package_names=record.package_names,
        release_blocking=record.release_blocking,
        blocker_reason=record.blocker_reason,
    )


def _distro_mapping_evidence_record_to_manifest_fields(
    record: LinuxDistroMappingEvidenceRecord,
) -> dict[str, Any]:
    data = record._asdict()
    data["package_names"] = list(record.package_names)
    data["executable_names"] = list(record.executable_names)
    data["verified_package_names"] = list(record.verified_package_names)
    data["verified_executable_names"] = list(record.verified_executable_names)
    return data


def _builder_helper_record(artifact_entry_id: str) -> dict[str, Any] | None:
    inherited = PACKAGE_POLICY_SOURCE_BY_HELPER.get(artifact_entry_id)
    if inherited is None:
        return None
    return {
        "inherits_artifact_policy": inherited,
        "environment_variable": "ECLI_F4_LINTER_EXTRA_ARTIFACT_IDS",
        "records_helper_evidence": True,
    }


def _nix_policy_record(artifact_entry_id: str) -> dict[str, Any] | None:
    if artifact_entry_id not in LINUX_NIX_ARTIFACT_IDS:
        return None
    return {
        "declarative_only": True,
        "imperative_package_manager": False,
        "imperative_upstream_download": False,
    }


def build_linux_provisioning_manifest(
    *,
    artifact_entry_id: str,
    target_dir: Path,
    evidence_dir: Path,
    selected_tool_ids: tuple[str, ...] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic Linux F4 tools manifest."""
    canonical_id = _linux_artifact_entry_id(artifact_entry_id, root)
    target_base = _safe_base_dir(target_dir)
    evidence_base = _safe_base_dir(evidence_dir)
    policies = linux_provisioning_policy_for_artifact(canonical_id, root)
    required_ids = tuple(policy.tool_id for policy in policies)
    selected = required_ids if selected_tool_ids is None else selected_tool_ids
    unknown = sorted(set(selected) - set(required_ids))
    if unknown:
        raise ValueError(f"unknown selected Linux Full tool id(s): {unknown}")
    duplicates = _duplicates(list(selected))
    if duplicates:
        raise ValueError(f"duplicate selected Linux Full tool id(s): {duplicates}")

    selected_set = set(selected)
    selected_policies = tuple(
        policy for policy in policies if policy.tool_id in selected_set
    )
    manifest_path = linux_artifact_manifest_path(target_base, canonical_id, root)
    tools = tuple(
        _policy_to_manifest_item(
            policy,
            target_dir=target_base,
            evidence_dir=evidence_base,
        )
        for policy in selected_policies
    )
    release_blocking = any(item["release_blocking"] for item in tools)
    manifest: dict[str, Any] = {
        "schema_version": LINUX_MANIFEST_SCHEMA_VERSION,
        "artifact_entry_id": canonical_id,
        "policy_kind": "linux-f4-provisioning-policy",
        "artifact_family": _artifact_family(canonical_id),
        "target_dir": str(target_base),
        "evidence_dir": str(evidence_base),
        "manifest_path": str(manifest_path),
        "full_required_tool_count": len(required_ids),
        "selected_tools": list(selected),
        "release_blocking": release_blocking,
        "tools": list(tools),
    }
    builder_helper = _builder_helper_record(canonical_id)
    if builder_helper is not None:
        manifest["builder_helper"] = builder_helper
    nix_policy = _nix_policy_record(canonical_id)
    if nix_policy is not None:
        manifest["nix_policy"] = nix_policy
    return manifest


def write_linux_provisioning_manifest(manifest: Mapping[str, Any]) -> Path:
    """Write *manifest* to its validated manifest path and return that path."""
    path_value = manifest.get("manifest_path")
    target_value = manifest.get("target_dir")
    if not isinstance(path_value, str) or not isinstance(target_value, str):
        raise ValueError("Linux manifest must include manifest_path and target_dir")
    target_base = _safe_base_dir(Path(target_value))
    path = _safe_base_dir(Path(path_value))
    _ensure_child(target_base, path, "Linux manifest path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _load_manifest(path_or_manifest: Path | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(path_or_manifest, Path):
        path = path_or_manifest.expanduser().resolve(strict=True)
        if path.suffix.lower() != ".json" or not path.is_file():
            raise ValueError(f"expected an existing Linux manifest JSON file: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Linux manifest must contain a JSON object: {path}")
        return data
    return path_or_manifest


def verify_linux_provenance_record(
    record: Mapping[str, Any],
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    """Return validation errors for one tool provenance record."""
    prefix = str(record.get("tool_id", expected_policy.tool_id))
    expected_record = linux_provenance_record_for_policy(expected_policy)
    expected = _provenance_record_to_manifest_fields(expected_record)
    if linux_distro_mapping_for_policy(expected_policy) is not None:
        expected["evidence_fields_required"].append("distro_mapping")
    errors = _provenance_required_field_errors(prefix, record)
    errors.extend(_provenance_value_mismatch_errors(prefix, record, expected))
    errors.extend(_provenance_semantic_errors(prefix, record, expected_policy))
    return errors


def verify_linux_distro_mapping_record(
    record: Any,
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    """Return validation errors for one distro mapping record."""
    prefix = expected_policy.tool_id
    expected_record = linux_distro_mapping_for_policy(expected_policy)
    if record is None:
        if expected_record is not None:
            return [f"{prefix}: missing distro_mapping"]
        return []
    if not isinstance(record, Mapping):
        return [f"{prefix}: distro_mapping must be an object"]
    if expected_record is None:
        return [_unexpected_distro_mapping_error(prefix, expected_policy)]

    expected = _distro_mapping_record_to_manifest_fields(expected_record)
    errors = _distro_mapping_required_field_errors(prefix, record)
    errors.extend(_distro_mapping_value_mismatch_errors(prefix, record, expected))
    errors.extend(_distro_mapping_semantic_errors(prefix, record, expected_policy))
    errors.extend(
        verify_linux_distro_mapping_evidence_record(
            record.get("evidence"),
            expected_policy,
        )
    )
    return errors


def verify_linux_distro_mapping_evidence_record(
    record: Any,
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    """Return validation errors for one repository-local distro evidence record."""
    prefix = expected_policy.tool_id
    expected_record = linux_distro_mapping_evidence_for_policy(expected_policy)
    if record is None:
        if expected_record is not None:
            return [f"{prefix}: approved distro_mapping requires evidence"]
        return []
    if not isinstance(record, Mapping):
        return [f"{prefix}: distro_mapping evidence must be an object"]
    if expected_record is None:
        return [_unexpected_distro_mapping_evidence_error(prefix, expected_policy)]

    expected = _distro_mapping_evidence_record_to_manifest_fields(expected_record)
    errors = _distro_mapping_evidence_required_field_errors(prefix, record)
    errors.extend(
        _distro_mapping_evidence_value_mismatch_errors(prefix, record, expected)
    )
    errors.extend(
        _distro_mapping_evidence_semantic_errors(prefix, record, expected_policy)
    )
    return errors


def _unexpected_distro_mapping_evidence_error(
    prefix: str,
    expected_policy: LinuxToolProvisioningPolicy,
) -> str:
    if expected_policy.artifact_family == "self-contained":
        return f"{prefix}: self-contained artifact must not declare distro evidence"
    if expected_policy.artifact_family == "nix-policy":
        return f"{prefix}: Nix artifact must not declare distro evidence"
    return f"{prefix}: blocked distro_mapping must not declare approved evidence"


def _distro_mapping_evidence_required_field_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    source_type = record.get("evidence_source_type")
    status = record.get("evidence_status")
    if source_type not in LINUX_ALLOWED_DISTRO_EVIDENCE_SOURCE_TYPES:
        errors.append(f"{prefix}: unknown evidence_source_type {source_type!r}")
    if status not in LINUX_ALLOWED_DISTRO_EVIDENCE_STATUSES:
        errors.append(f"{prefix}: unknown evidence_status {status!r}")
    return errors


def _distro_mapping_evidence_value_mismatch_errors(
    prefix: str,
    record: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    fields = DISTRO_EVIDENCE_CANONICAL_FIELDS
    if record.get("evidence_status") == "current-policy-baseline":
        fields = (*fields, *DISTRO_EVIDENCE_BASELINE_FIELDS)
    if expected.get("evidence_status") == "verified-official-source":
        fields = (
            *fields,
            *DISTRO_EVIDENCE_BASELINE_FIELDS,
            *DISTRO_EVIDENCE_PROMOTION_FIELDS,
        )
    for field in fields:
        actual_value = _normalized_distro_evidence_value(field, record.get(field))
        expected_value = _normalized_distro_evidence_value(field, expected.get(field))
        if actual_value != expected_value:
            errors.append(
                f"{prefix}: distro_mapping evidence {field} differs from canonical evidence"
            )
    return errors


def _normalized_distro_evidence_value(field: str, value: Any) -> Any:
    if field in {
        "package_names",
        "executable_names",
        "verified_package_names",
        "verified_executable_names",
    }:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value)
        if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
            return value
        return ()
    return value


def _distro_mapping_evidence_semantic_errors(
    prefix: str,
    record: Mapping[str, Any],
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    errors: list[str] = []
    if record.get("artifact_entry_id") != expected_policy.artifact_entry_id:
        errors.append(f"{prefix}: distro_mapping evidence artifact_entry_id mismatch")
    expected_source = _package_policy_artifact_id(expected_policy.artifact_entry_id)
    if record.get("source_policy_artifact_entry_id") != expected_source:
        errors.append(
            f"{prefix}: distro_mapping evidence source_policy_artifact_entry_id mismatch"
        )
    if expected_policy.artifact_entry_id in PACKAGE_POLICY_SOURCE_BY_HELPER:
        inherited = PACKAGE_POLICY_SOURCE_BY_HELPER[expected_policy.artifact_entry_id]
        if record.get("source_policy_artifact_entry_id") != inherited:
            errors.append(
                f"{prefix}: docker helper distro evidence must inherit {inherited}"
            )
    if (
        _normalized_distro_evidence_value(
            "package_names",
            record.get("package_names"),
        )
        != expected_policy.package_names
    ):
        errors.append(
            f"{prefix}: distro_mapping evidence package_names differs from mapping"
        )
    expected_package_names = OS_PACKAGE_NAMES.get(expected_source, {}).get(
        expected_policy.tool_id,
    )
    if expected_package_names != expected_policy.package_names:
        errors.append(f"{prefix}: distro_mapping evidence has no OS_PACKAGE_NAMES base")
    errors.extend(_distro_mapping_evidence_promotion_state_errors(prefix, record))
    return errors


def _distro_evidence_record_mapping(record: Any) -> Mapping[str, Any] | None:
    if isinstance(record, Mapping):
        return record
    asdict = getattr(record, "_asdict", None)
    if callable(asdict):
        data = asdict()
        if isinstance(data, Mapping):
            return data
    return None


def _distro_mapping_evidence_promotion_state_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    status = record.get("evidence_status")
    if status == "verified-official-source":
        return _verified_official_source_evidence_errors(
            f"{prefix}: distro_mapping evidence",
            record,
        )
    if status == "current-policy-baseline":
        return _current_policy_baseline_evidence_errors(
            f"{prefix}: distro_mapping evidence",
            record,
        )
    if status in {"blocked-missing-evidence", "blocked-evidence-drift"}:
        return _blocked_official_evidence_errors(
            f"{prefix}: distro_mapping evidence",
            record,
        )
    return []


def _verified_official_source_evidence_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    source_type = record.get("evidence_source_type")
    if source_type == "repository-local-policy":
        errors.append(
            f"{prefix}: verified-official-source evidence cannot use repository-local-policy"
        )
    elif source_type not in LINUX_OFFICIAL_DISTRO_EVIDENCE_SOURCE_TYPES:
        errors.append(
            f"{prefix}: verified-official-source evidence requires official source type"
        )
    errors.extend(_required_text_field_errors(prefix, record))
    kind = record.get("official_source_kind")
    if kind not in LINUX_ALLOWED_OFFICIAL_SOURCE_KINDS:
        errors.append(f"{prefix}: unknown official_source_kind {kind!r}")
    scope = record.get("verification_scope")
    if scope not in LINUX_ALLOWED_VERIFICATION_SCOPES:
        errors.append(f"{prefix}: unknown verification_scope {scope!r}")
    errors.extend(_verified_name_field_errors(prefix, record))
    if record.get("external_verification_required_for_new_mappings") is not False:
        errors.append(
            f"{prefix}: verified-official-source evidence must not require external verification for new mappings"
        )
    if errors and record.get("release_blocking") is False:
        errors.append(
            f"{prefix}: release_blocking false requires complete official-source promotion evidence"
        )
    elif not errors and record.get("release_blocking") is not False:
        errors.append(
            f"{prefix}: verified-official-source evidence must not be release_blocking"
        )
    return errors


def _required_text_field_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field in ("official_source_name", "official_source_url", "verification_note"):
        if not _has_text(record.get(field)):
            errors.append(f"{prefix}: missing {field}")
    return errors


def _verified_name_field_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    verified_packages = _normalized_distro_evidence_value(
        "verified_package_names",
        record.get("verified_package_names"),
    )
    package_names = _normalized_distro_evidence_value(
        "package_names",
        record.get("package_names"),
    )
    if not verified_packages:
        errors.append(f"{prefix}: missing verified_package_names")
    elif verified_packages != package_names:
        errors.append(f"{prefix}: verified_package_names differ from package_names")

    verified_executables = _normalized_distro_evidence_value(
        "verified_executable_names",
        record.get("verified_executable_names"),
    )
    executable_names = _normalized_distro_evidence_value(
        "executable_names",
        record.get("executable_names"),
    )
    if not verified_executables:
        errors.append(f"{prefix}: missing verified_executable_names")
    elif verified_executables != executable_names:
        errors.append(
            f"{prefix}: verified_executable_names differ from executable_names"
        )
    return errors


def _current_policy_baseline_evidence_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if record.get("evidence_source_type") != "repository-local-policy":
        errors.append(
            f"{prefix}: current-policy-baseline evidence must use repository-local-policy"
        )
    if record.get("external_verification_required_for_new_mappings") is not True:
        errors.append(
            f"{prefix}: current-policy-baseline evidence must require external verification for new mappings"
        )
    for field in ("official_source_name", "official_source_url", "verification_note"):
        if _has_text(record.get(field)):
            errors.append(
                f"{prefix}: current-policy-baseline evidence must not claim {field}"
            )
    for field in ("official_source_kind", "verification_scope"):
        value = record.get(field)
        if value not in (None, ""):
            errors.append(
                f"{prefix}: current-policy-baseline evidence must not claim {field}"
            )
    for field in ("verified_package_names", "verified_executable_names"):
        if _normalized_distro_evidence_value(field, record.get(field)):
            errors.append(
                f"{prefix}: current-policy-baseline evidence must not claim {field}"
            )
    return errors


def _blocked_official_evidence_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if record.get("release_blocking") is not True:
        errors.append(
            f"{prefix}: blocked/missing official evidence must be release_blocking"
        )
    reason = record.get("blocker_reason")
    if not _has_text(reason):
        errors.append(
            f"{prefix}: blocked/missing official evidence requires blocker_reason"
        )
    return errors


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unexpected_distro_mapping_error(
    prefix: str,
    expected_policy: LinuxToolProvisioningPolicy,
) -> str:
    if expected_policy.artifact_family == "self-contained":
        return f"{prefix}: self-contained artifact must not declare distro_mapping"
    if expected_policy.artifact_family == "nix-policy":
        return f"{prefix}: Nix artifact must not declare distro_mapping"
    return (
        f"{prefix}: unexpected distro_mapping for mechanism {expected_policy.mechanism}"
    )


def _distro_mapping_required_field_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    distro_family = record.get("distro_family")
    mapping_status = record.get("mapping_status")
    if distro_family not in LINUX_ALLOWED_DISTRO_FAMILIES:
        errors.append(f"{prefix}: unknown distro_family {distro_family!r}")
    if mapping_status not in LINUX_ALLOWED_DISTRO_MAPPING_STATUSES:
        errors.append(f"{prefix}: unknown mapping_status {mapping_status!r}")
    return errors


def _distro_mapping_value_mismatch_errors(
    prefix: str,
    record: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field in DISTRO_MAPPING_MANIFEST_FIELDS:
        actual_value = _normalized_distro_mapping_value(field, record.get(field))
        expected_value = _normalized_distro_mapping_value(field, expected.get(field))
        if actual_value != expected_value:
            errors.append(
                f"{prefix}: distro_mapping {field} differs from canonical mapping"
            )
    return errors


def _normalized_distro_mapping_value(field: str, value: Any) -> Any:
    if field in {"package_names", "executable_names"}:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value)
        if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
            return value
        return ()
    return value


def _distro_mapping_semantic_errors(
    prefix: str,
    record: Mapping[str, Any],
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    errors: list[str] = []
    if record.get("artifact_entry_id") != expected_policy.artifact_entry_id:
        errors.append(f"{prefix}: distro_mapping artifact_entry_id mismatch")
    if expected_policy.artifact_entry_id in PACKAGE_POLICY_SOURCE_BY_HELPER:
        expected_source = PACKAGE_POLICY_SOURCE_BY_HELPER[
            expected_policy.artifact_entry_id
        ]
        if record.get("source_policy_artifact_entry_id") != expected_source:
            errors.append(
                f"{prefix}: docker helper distro_mapping must inherit {expected_source}"
            )
    status = record.get("mapping_status")
    if status in {"approved-existing-policy", "approved-with-evidence"}:
        if not record.get("package_names"):
            errors.append(f"{prefix}: approved distro_mapping requires package_names")
    if status in LINUX_BLOCKED_DISTRO_MAPPING_STATUSES:
        if record.get("release_blocking") is not True:
            errors.append(f"{prefix}: blocked distro_mapping must be release_blocking")
        reason = record.get("blocker_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}: blocked distro_mapping requires blocker_reason")
    return errors


def _provenance_required_field_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if "provenance_status" not in record:
        errors.append(f"{prefix}: missing provenance_status")
    elif record.get("provenance_status") not in LINUX_ALLOWED_PROVENANCE_STATUSES:
        errors.append(
            f"{prefix}: unknown provenance_status {record.get('provenance_status')!r}"
        )
    if "trust_boundary" not in record:
        errors.append(f"{prefix}: missing trust_boundary")
    elif record.get("trust_boundary") not in LINUX_ALLOWED_TRUST_BOUNDARIES:
        errors.append(
            f"{prefix}: unknown trust_boundary {record.get('trust_boundary')!r}"
        )
    return errors


def _provenance_value_mismatch_errors(
    prefix: str,
    record: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field in PROVENANCE_MANIFEST_FIELDS:
        actual_value = _normalized_provenance_value(field, record.get(field))
        expected_value = _normalized_provenance_value(field, expected.get(field))
        if actual_value != expected_value:
            errors.append(f"{prefix}: {field} differs from canonical provenance")
    return errors


def _normalized_provenance_value(field: str, value: Any) -> Any:
    if field in {"package_names", "evidence_fields_required"}:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value)
        if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
            return value
        return ()
    return value


def _provenance_semantic_errors(
    prefix: str,
    record: Mapping[str, Any],
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    errors: list[str] = []
    status = record.get("provenance_status")
    trust_boundary = record.get("trust_boundary")
    mechanism = record.get("mechanism")
    if isinstance(status, str) and status in LINUX_ALLOWED_PROVENANCE_STATUSES:
        errors.extend(
            _provenance_status_semantic_errors(
                prefix,
                record,
                status,
                trust_boundary,
                mechanism,
                expected_policy,
            )
        )
    return errors


def _provenance_status_semantic_errors(
    prefix: str,
    record: Mapping[str, Any],
    status: str,
    trust_boundary: Any,
    mechanism: Any,
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    errors: list[str] = []
    expected_trust = TRUST_BOUNDARY_BY_PROVENANCE_STATUS[status]
    if (
        trust_boundary in LINUX_ALLOWED_TRUST_BOUNDARIES
        and trust_boundary != expected_trust
    ):
        errors.append(
            f"{prefix}: trust_boundary is inconsistent with provenance_status"
        )
    if isinstance(mechanism, str) and mechanism in LINUX_ALLOWED_MECHANISMS:
        allowed_statuses = _provenance_statuses_for_mechanism(mechanism)
        if status not in allowed_statuses:
            errors.append(f"{prefix}: provenance_status is inconsistent with mechanism")
    if status == "distro-signed-package" and not record.get("package_names"):
        errors.append(
            f"{prefix}: distro-signed-package provenance requires package_names"
        )
    if status == "pinned-upstream-artifact":
        errors.extend(_pinned_upstream_errors(prefix, record))
    if status == "pinned-language-package":
        errors.extend(_pinned_language_package_errors(prefix, record))
    if _is_blocked_provenance_status(status):
        errors.extend(_blocked_provenance_errors(prefix, record))
    elif (
        record.get("release_blocking") is True
        and expected_policy.release_blocking is not True
    ):
        errors.append(f"{prefix}: non-blocked provenance must not be release_blocking")
    return errors


def _provenance_statuses_for_mechanism(mechanism: str) -> frozenset[str]:
    if mechanism == "bundled-internal":
        return frozenset({"internal-bundled"})
    if mechanism == "os-package-manager":
        return frozenset({"distro-signed-package"})
    if mechanism == "nix-derivation":
        return frozenset({"nix-derivation"})
    if mechanism == "toolchain-component":
        return frozenset({"toolchain-component"})
    if mechanism == "language-package-manager":
        return frozenset({"pinned-language-package"})
    if mechanism in {"ecli-managed-tools", "jar-shim", "verified-upstream-download"}:
        return frozenset({"pinned-upstream-artifact"})
    if mechanism == "blocked-missing-provenance":
        return LINUX_BLOCKED_PROVENANCE_STATUSES
    return frozenset()


def _pinned_upstream_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if (
        not isinstance(record.get("pinned_version"), str)
        or not record["pinned_version"].strip()
    ):
        errors.append(f"{prefix}: pinned-upstream-artifact requires pinned_version")
    if not isinstance(record.get("checksum"), str) or not record["checksum"].strip():
        errors.append(f"{prefix}: pinned-upstream-artifact requires checksum")
    if (
        not isinstance(record.get("checksum_algorithm"), str)
        or not record["checksum_algorithm"].strip()
    ):
        errors.append(f"{prefix}: pinned-upstream-artifact requires checksum_algorithm")
    return errors


def _pinned_language_package_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if (
        not isinstance(record.get("pinned_version"), str)
        or not record["pinned_version"].strip()
    ):
        errors.append(f"{prefix}: pinned-language-package requires pinned_version")
    if (
        not isinstance(record.get("source_url"), str)
        or not record["source_url"].strip()
    ):
        errors.append(f"{prefix}: pinned-language-package requires source_url")
    return errors


def _blocked_provenance_errors(
    prefix: str,
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if record.get("release_blocking") is not True:
        errors.append(f"{prefix}: blocked provenance must be release_blocking")
    reason = record.get("blocker_reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(f"{prefix}: blocked provenance requires blocker_reason")
    return errors


def verify_linux_provisioning_manifest(
    path_or_manifest: Path | Mapping[str, Any],
    *,
    root: Path | None = None,
) -> list[str]:
    """Return validation errors for a Linux F4 tools manifest."""
    try:
        manifest = _load_manifest(path_or_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    errors: list[str] = []
    artifact_id = manifest.get("artifact_entry_id")
    if not isinstance(artifact_id, str):
        return ["missing artifact_entry_id"]
    try:
        canonical_id = _linux_artifact_entry_id(artifact_id, root)
    except (KeyError, ValueError) as exc:
        return [str(exc)]

    expected_policies = _expected_policy_by_tool_id(canonical_id, root)
    if manifest.get("schema_version") != LINUX_MANIFEST_SCHEMA_VERSION:
        errors.append("unsupported or missing Linux manifest schema_version")
    if manifest.get("policy_kind") != "linux-f4-provisioning-policy":
        errors.append("missing Linux provisioning policy kind")
    errors.extend(_manifest_path_errors(manifest))
    errors.extend(_manifest_summary_errors(manifest, expected_policies))
    errors.extend(_manifest_tool_errors(manifest, canonical_id, expected_policies))
    return errors


def _expected_policy_by_tool_id(
    artifact_entry_id: str,
    root: Path | None,
) -> dict[str, LinuxToolProvisioningPolicy]:
    return {
        policy.tool_id: policy
        for policy in linux_provisioning_policy_for_artifact(artifact_entry_id, root)
    }


def _manifest_path_errors(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        target_dir = _safe_base_dir(Path(str(manifest["target_dir"])))
        manifest_path = _safe_base_dir(Path(str(manifest["manifest_path"])))
        _ensure_child(target_dir, manifest_path, "Linux manifest path")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def _manifest_summary_errors(
    manifest: Mapping[str, Any],
    expected_policies: Mapping[str, LinuxToolProvisioningPolicy],
) -> list[str]:
    errors: list[str] = []
    expected_count = len(expected_policies)
    if manifest.get("full_required_tool_count") != expected_count:
        errors.append(
            "Linux manifest full_required_tool_count does not match "
            f"expected policy count {expected_count}"
        )

    tools = manifest.get("tools")
    if isinstance(tools, list):
        release_blocking = any(
            isinstance(tool, dict) and tool.get("release_blocking") is True
            for tool in tools
        )
        if manifest.get("release_blocking") is not release_blocking:
            errors.append(
                "Linux manifest release_blocking does not match tool policy state"
            )
    return errors


def _manifest_tool_errors(
    manifest: Mapping[str, Any],
    artifact_entry_id: str,
    expected_policies: Mapping[str, LinuxToolProvisioningPolicy],
) -> list[str]:
    tools = manifest.get("tools")
    if not isinstance(tools, list):
        return ["Linux manifest tools must be a list"]

    selected = manifest.get("selected_tools")
    if not isinstance(selected, list) or not all(
        isinstance(item, str) for item in selected
    ):
        return ["Linux manifest selected_tools must be a string list"]
    tool_ids = [
        tool.get("tool_id")
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("tool_id"), str)
    ]
    missing = sorted(set(selected) - set(tool_ids))
    errors = [
        f"selected Linux tool missing from manifest: {tool_id}" for tool_id in missing
    ]
    errors.extend(
        f"duplicate selected Linux tool: {tool_id}" for tool_id in _duplicates(selected)
    )
    errors.extend(
        f"duplicate Linux manifest tool entry: {tool_id}"
        for tool_id in _duplicates(tool_ids)
    )
    unknown = sorted(set(selected) - set(expected_policies))
    errors.extend(f"unknown selected Linux Full tool: {tool_id}" for tool_id in unknown)
    for item in tools:
        if not isinstance(item, dict):
            errors.append("Linux manifest tool entry must be an object")
            continue
        tool_id = item.get("tool_id")
        expected_policy = (
            expected_policies.get(tool_id) if isinstance(tool_id, str) else None
        )
        if isinstance(tool_id, str) and expected_policy is None:
            errors.append(
                f"{tool_id}: unexpected Linux tool for artifact {artifact_entry_id}"
            )
        errors.extend(_tool_item_errors(item, manifest, expected_policy))
    return errors


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _tool_item_errors(
    item: Mapping[str, Any],
    manifest: Mapping[str, Any],
    expected_policy: LinuxToolProvisioningPolicy | None,
) -> list[str]:
    prefix = str(item.get("tool_id", "<unknown>"))
    errors: list[str] = []
    tool_id = item.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id:
        errors.append(f"{prefix}: missing tool_id")
    item_artifact_id = item.get("artifact_entry_id")
    if item_artifact_id is not None and item_artifact_id != manifest.get(
        "artifact_entry_id"
    ):
        errors.append(
            f"{prefix}: artifact_entry_id differs from manifest artifact_entry_id"
        )
    mechanism = item.get("mechanism")
    if mechanism not in LINUX_ALLOWED_MECHANISMS:
        errors.append(f"{prefix}: invalid Linux mechanism {mechanism!r}")
    if expected_policy is not None:
        errors.extend(_tool_policy_mismatch_errors(prefix, item, expected_policy))
        errors.extend(verify_linux_provenance_record(item, expected_policy))
        if item.get("distro_evidence") is not None:
            if expected_policy.artifact_family == "self-contained":
                errors.append(
                    f"{prefix}: self-contained artifact must not declare distro evidence"
                )
            elif expected_policy.artifact_family == "nix-policy":
                errors.append(
                    f"{prefix}: Nix artifact must not declare distro evidence"
                )
            else:
                errors.append(f"{prefix}: unexpected top-level distro_evidence")
        errors.extend(
            verify_linux_distro_mapping_record(
                item.get("distro_mapping"),
                expected_policy,
            )
        )
    if (
        not isinstance(item.get("executable_names"), list)
        or not item["executable_names"]
    ):
        errors.append(f"{prefix}: missing executable_names")
    if not isinstance(item.get("version_probe"), list) or not item["version_probe"]:
        errors.append(f"{prefix}: missing version_probe")
    if mechanism == "os-package-manager" and not item.get("package_names"):
        errors.append(f"{prefix}: os-package-manager policy requires package_names")
    if mechanism == "blocked-missing-provenance":
        if item.get("release_blocking") is not True:
            errors.append(f"{prefix}: blocked policy must be release_blocking")
        reason = item.get("blocker_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}: blocked policy requires blocker_reason")
    errors.extend(_tool_path_errors(prefix, item, manifest))
    return errors


def _tool_policy_mismatch_errors(
    prefix: str,
    item: Mapping[str, Any],
    expected_policy: LinuxToolProvisioningPolicy,
) -> list[str]:
    errors: list[str] = []
    if item.get("mechanism") != expected_policy.mechanism:
        errors.append(
            f"{prefix}: mechanism differs from expected {expected_policy.mechanism!r}"
        )
    package_names = item.get("package_names")
    if isinstance(package_names, list) and all(
        isinstance(package_name, str) for package_name in package_names
    ):
        actual_package_names = tuple(package_names)
    else:
        actual_package_names = ()
    if actual_package_names != expected_policy.package_names:
        errors.append(f"{prefix}: package_names differ from expected policy")
    if item.get("release_blocking") is not expected_policy.release_blocking:
        errors.append(f"{prefix}: release_blocking differs from expected policy")
    if expected_policy.mechanism == "blocked-missing-provenance":
        reason = item.get("blocker_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}: blocked policy requires blocker_reason")
    return errors


def _tool_path_errors(
    prefix: str,
    item: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        target_base = _safe_base_dir(Path(str(manifest["target_dir"])))
        evidence_base = _safe_base_dir(Path(str(manifest["evidence_dir"])))
        tool_target = _safe_base_dir(Path(str(item["target_dir"])))
        tool_evidence = _safe_base_dir(Path(str(item["evidence_dir"])))
        _ensure_child(target_base, tool_target, f"{prefix} target_dir")
        _ensure_child(evidence_base, tool_evidence, f"{prefix} evidence_dir")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{prefix}: {exc}")
    return errors


class _ContractArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID)


def build_parser() -> argparse.ArgumentParser:
    parser = _ContractArgumentParser(
        prog="f4_linter_linux_provisioning.py",
        description="Audit Linux F4 linter provisioning policy metadata.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--official-evidence-audit",
        action="store_true",
        help="print the official distro evidence audit report as JSON",
    )
    mode.add_argument(
        "--check-official-evidence-drift",
        action="store_true",
        help="fail if official distro evidence drift is detected",
    )
    return parser


def _official_evidence_drift_check_message(drift_errors: list[str]) -> str:
    if not drift_errors:
        return "PASS: Linux official distro evidence drift audit clean"
    lines = ["FAIL: Linux official distro evidence drift detected"]
    lines.extend(f"ERROR: {error}" for error in drift_errors)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.official_evidence_audit:
        print(
            json.dumps(
                linux_official_distro_evidence_audit_report(),
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK

    drift_errors = linux_official_distro_evidence_drift_errors()
    message = _official_evidence_drift_check_message(drift_errors)
    print(message, file=sys.stderr if drift_errors else sys.stdout)
    return EXIT_OFFICIAL_EVIDENCE_DRIFT if drift_errors else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
