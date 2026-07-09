#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/f4_linter_packaging.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Shared packaging hooks for F4 linter provisioning evidence gates.

Packaging scripts use this module to call the provider-neutral F4 provisioning
entrypoints with deterministic artifact-specific target and evidence paths. The
helpers construct explicit argv lists only; they do not use a shell and do not
install, download, or bundle actual linter tools themselves.

Concrete non-dry-run installer/download/bundling implementations are handled by
the next implementation PR.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, NamedTuple, cast


ProvisioningPolicyKind = Literal[
    "full-provisioning-hook",
    "constrained-minimal",
    "nix-policy",
]

ProvisioningMode = Literal["dry-run", "verify-only", "provision"]
ProvisioningProfile = Literal["full", "custom", "minimal"]

# Packaging evidence generation is dry-run by default: it is deterministic,
# network-safe, and does not install tools. Real non-dry-run provisioning remains
# an explicit opt-in via ECLI_F4_LINTER_PROVISIONING_MODE=provision.
DEFAULT_PROVISIONING_MODE: ProvisioningMode = "dry-run"
DEFAULT_PROVISIONING_PROFILE: ProvisioningProfile = "full"

PROFILE_ENV = "ECLI_F4_LINTER_PROFILE"
MODE_ENV = "ECLI_F4_LINTER_PROVISIONING_MODE"
INCLUDE_TOOLS_ENV = "ECLI_F4_LINTER_INCLUDE_TOOLS"
EXCLUDE_TOOLS_ENV = "ECLI_F4_LINTER_EXCLUDE_TOOLS"
SELECTION_JSON_ENV = "ECLI_F4_LINTER_SELECTION_JSON"
EXTRA_ARTIFACT_IDS_ENV = "ECLI_F4_LINTER_EXTRA_ARTIFACT_IDS"
ARTIFACT_ID_ENV = "ECLI_F4_LINTER_ARTIFACT_ID"

_VALID_MODES = frozenset({"dry-run", "verify-only", "provision"})
_VALID_PROFILES = frozenset({"full", "custom", "minimal"})

FULL_PROVISIONING_HOOK_ARTIFACT_IDS: tuple[str, ...] = (
    "linux-pyinstaller",
    "linux-tarball",
    "deb",
    "rpm",
    "opensuse-rpm",
    "arch-pkgbuild",
    "slackware-txz",
    "appimage",
    "freebsd-pkg",
    "freebsd-ports-chroot",
    "macos-app",
    "macos-dmg",
    "windows-portable-exe",
    "windows-nsis-installer",
    "docker-deb-helper",
    "docker-rpm-helper",
    "gha-release-contract",
)
CONSTRAINED_ARTIFACT_IDS: tuple[str, ...] = ("pypi-wheel", "pypi-sdist")
NIX_POLICY_ARTIFACT_IDS: tuple[str, ...] = ("nix-flake", "nixos-package")


class ArtifactProvisioningPolicy(NamedTuple):
    """Packaging-level F4 evidence policy for one canonical artifact."""

    artifact_entry_id: str
    kind: ProvisioningPolicyKind
    default_mode: ProvisioningMode = DEFAULT_PROVISIONING_MODE
    default_profile: ProvisioningProfile = DEFAULT_PROVISIONING_PROFILE
    reason: str | None = None


class ProvisioningSelection(NamedTuple):
    """Non-interactive F4 evidence selection resolved from environment."""

    mode: ProvisioningMode
    profile: ProvisioningProfile
    include_tools: tuple[str, ...] = ()
    exclude_tools: tuple[str, ...] = ()
    selection_json: Path | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_src_path(root: Path) -> None:
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def canonical_artifact_ids(root: Path | None = None) -> tuple[str, ...]:
    """Return the canonical 21 artifact IDs from the provisioning registry."""
    resolved_root = _repo_root() if root is None else root
    _ensure_src_path(resolved_root)
    registry = importlib.import_module(
        "ecli.extensions.linters.core.provisioning_registry"
    )

    return tuple(
        entry.artifact_entry_id for entry in registry.ARTIFACT_CONTRACT_ENTRIES
    )


def canonical_artifact_entry_id(
    artifact_entry_id: str, root: Path | None = None
) -> str:
    """Return a canonical artifact id, rejecting unknown and path-like values."""
    resolved_root = _repo_root() if root is None else root
    _ensure_src_path(resolved_root)
    provisioning = importlib.import_module("ecli.extensions.linters.core.provisioning")

    return provisioning.canonical_artifact_entry_id(artifact_entry_id)


def artifact_provisioning_policies(
    root: Path | None = None,
) -> tuple[ArtifactProvisioningPolicy, ...]:
    """Return packaging policies for exactly the canonical 21 artifact IDs."""
    policies: dict[str, ArtifactProvisioningPolicy] = {
        artifact_id: ArtifactProvisioningPolicy(
            artifact_entry_id=artifact_id,
            kind="full-provisioning-hook",
            reason=(
                "Artifact-specific packaging hook records Full-profile F4 "
                "provisioning evidence."
            ),
        )
        for artifact_id in FULL_PROVISIONING_HOOK_ARTIFACT_IDS
    }
    policies.update(
        {
            artifact_id: ArtifactProvisioningPolicy(
                artifact_entry_id=artifact_id,
                kind="constrained-minimal",
                reason=(
                    "Python package metadata cannot provision non-Python F4 "
                    "toolchains; evidence must remain explicitly constrained."
                ),
            )
            for artifact_id in CONSTRAINED_ARTIFACT_IDS
        }
    )
    policies.update(
        {
            artifact_id: ArtifactProvisioningPolicy(
                artifact_entry_id=artifact_id,
                kind="nix-policy",
                reason="Nix derivation/input policy provides F4 toolchain evidence.",
            )
            for artifact_id in NIX_POLICY_ARTIFACT_IDS
        }
    )

    ordered_ids = canonical_artifact_ids(root)
    if set(policies) != set(ordered_ids):
        missing = sorted(set(ordered_ids) - set(policies))
        extra = sorted(set(policies) - set(ordered_ids))
        msg = f"F4 provisioning policy drift: missing={missing} extra={extra}"
        raise RuntimeError(msg)
    return tuple(policies[artifact_id] for artifact_id in ordered_ids)


def artifact_provisioning_policy(
    artifact_entry_id: str,
    root: Path | None = None,
) -> ArtifactProvisioningPolicy:
    """Return the packaging policy for one canonical artifact."""
    canonical_id = canonical_artifact_entry_id(artifact_entry_id, root)
    for policy in artifact_provisioning_policies(root):
        if policy.artifact_entry_id == canonical_id:
            return policy
    raise KeyError(f"unknown artifact provisioning policy: {canonical_id!r}")


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


def _safe_child(base: Path, *parts: str) -> Path:
    resolved_base = base.expanduser().resolve(strict=False)
    child = resolved_base
    for index, part in enumerate(parts, start=1):
        child = child / _validate_path_part(part, f"path part {index}")
    resolved_child = child.resolve(strict=False)
    try:
        resolved_child.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"path escapes base directory: {resolved_child}") from exc
    return resolved_child


def provisioning_target_dir(
    root: Path,
    artifact_entry_id: str,
    build_dir: Path | None = None,
) -> Path:
    """Return the artifact-specific target path recorded in F4 evidence."""
    canonical_id = canonical_artifact_entry_id(artifact_entry_id, root)
    base = root / "build" if build_dir is None else build_dir
    return _safe_child(base, "f4-linter-provisioning", canonical_id, "target")


def provisioning_evidence_dir(
    root: Path,
    artifact_entry_id: str,
    build_dir: Path | None = None,
) -> Path:
    """Return the artifact-specific F4 provisioning evidence directory."""
    canonical_id = canonical_artifact_entry_id(artifact_entry_id, root)
    base = root / "build" if build_dir is None else build_dir
    return _safe_child(base, "f4-linter-provisioning", canonical_id, "evidence")


def release_provisioning_evidence_dir(
    root: Path, build_dir: Path | None = None
) -> Path:
    """Return the aggregate all-artifacts F4 release evidence directory."""
    base = root / "build" if build_dir is None else build_dir
    return _safe_child(base, "f4-linter-provisioning", "release", "evidence")


def _split_env_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    normalized = value.replace(",", " ").replace(";", " ")
    return tuple(item for item in (part.strip() for part in normalized.split()) if item)


def _env_choice(
    env: dict[str, str],
    key: str,
    default: str,
    allowed: frozenset[str],
) -> str:
    value = env.get(key, default).strip().lower()
    if value not in allowed:
        raise ValueError(f"{key} must be one of {sorted(allowed)}, got {value!r}")
    return value


def selection_from_env(
    env: dict[str, str] | None = None,
    *,
    default_mode: ProvisioningMode = DEFAULT_PROVISIONING_MODE,
    default_profile: ProvisioningProfile = DEFAULT_PROVISIONING_PROFILE,
) -> ProvisioningSelection:
    """Resolve non-interactive F4 evidence mode/profile/tool selection."""
    resolved_env = os.environ if env is None else env
    mode = cast(
        ProvisioningMode,
        _env_choice(resolved_env, MODE_ENV, default_mode, _VALID_MODES),
    )
    profile = cast(
        ProvisioningProfile,
        _env_choice(
            resolved_env,
            PROFILE_ENV,
            default_profile,
            _VALID_PROFILES,
        ),
    )
    selection_json_value = resolved_env.get(SELECTION_JSON_ENV)
    selection_json = Path(selection_json_value) if selection_json_value else None
    return ProvisioningSelection(
        mode=mode,
        profile=profile,
        include_tools=_split_env_list(resolved_env.get(INCLUDE_TOOLS_ENV)),
        exclude_tools=_split_env_list(resolved_env.get(EXCLUDE_TOOLS_ENV)),
        selection_json=selection_json,
    )


def artifact_ids_from_env(
    default_artifact_ids: tuple[str, ...],
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> tuple[str, ...]:
    """Return default artifact IDs with optional non-interactive env wiring."""
    resolved_env = os.environ if env is None else env
    override = resolved_env.get(ARTIFACT_ID_ENV)
    ids = (override,) if override else default_artifact_ids
    ids = (*ids, *_split_env_list(resolved_env.get(EXTRA_ARTIFACT_IDS_ENV)))

    result: list[str] = []
    for artifact_id in ids:
        canonical_id = canonical_artifact_entry_id(artifact_id, root)
        if canonical_id not in result:
            result.append(canonical_id)
    return tuple(result)


def build_provisioning_command(
    root: Path,
    *,
    artifact_entry_id: str | None = None,
    all_artifacts: bool = False,
    target_dir: Path,
    evidence_dir: Path,
    mode: ProvisioningMode = DEFAULT_PROVISIONING_MODE,
    profile: ProvisioningProfile = DEFAULT_PROVISIONING_PROFILE,
    include_tools: tuple[str, ...] = (),
    exclude_tools: tuple[str, ...] = (),
    selection_json: Path | None = None,
    json_output: bool = False,
) -> list[str]:
    """Build the provision_f4_linters.py evidence-generation argv list."""
    if all_artifacts == (artifact_entry_id is not None):
        raise ValueError("provide exactly one of artifact_entry_id or all_artifacts")

    command = [
        sys.executable,
        str(root / "scripts" / "provision_f4_linters.py"),
    ]
    if all_artifacts:
        command.append("--all-artifacts")
    else:
        command += [
            "--artifact",
            canonical_artifact_entry_id(str(artifact_entry_id), root),
        ]
    command += [
        "--target-dir",
        str(target_dir),
        "--evidence-dir",
        str(evidence_dir),
        "--mode",
        mode,
        "--profile",
        profile,
    ]
    for tool_id in include_tools:
        command += ["--include-tool", tool_id]
    for tool_id in exclude_tools:
        command += ["--exclude-tool", tool_id]
    if selection_json is not None:
        command += ["--selection-json", str(selection_json)]
    if json_output:
        command.append("--json")
    return command


def build_verification_command(
    root: Path,
    *,
    artifact_entry_id: str | None = None,
    all_artifacts: bool = False,
    evidence_dir: Path,
    json_output: bool = False,
) -> list[str]:
    """Build the verify_f4_linter_provisioning.py argv list."""
    if all_artifacts == (artifact_entry_id is not None):
        raise ValueError("provide exactly one of artifact_entry_id or all_artifacts")

    command = [
        sys.executable,
        str(root / "scripts" / "verify_f4_linter_provisioning.py"),
    ]
    if all_artifacts:
        command.append("--all-artifacts")
    else:
        command += [
            "--artifact",
            canonical_artifact_entry_id(str(artifact_entry_id), root),
        ]
    command += ["--evidence-dir", str(evidence_dir)]
    if json_output:
        command.append("--json")
    return command


def _run_command(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def run_or_record_f4_linter_provisioning(
    root: Path,
    artifact_entry_id: str,
    *,
    build_dir: Path | None = None,
    selection: ProvisioningSelection | None = None,
) -> int:
    """Run configured evidence generation and then verify that evidence."""
    policy = artifact_provisioning_policy(artifact_entry_id, root)
    resolved_selection = selection or selection_from_env(
        default_mode=policy.default_mode,
        default_profile=policy.default_profile,
    )
    target_dir = provisioning_target_dir(root, policy.artifact_entry_id, build_dir)
    evidence_dir = provisioning_evidence_dir(root, policy.artifact_entry_id, build_dir)
    provision_rc = _run_command(
        build_provisioning_command(
            root,
            artifact_entry_id=policy.artifact_entry_id,
            target_dir=target_dir,
            evidence_dir=evidence_dir,
            mode=resolved_selection.mode,
            profile=resolved_selection.profile,
            include_tools=resolved_selection.include_tools,
            exclude_tools=resolved_selection.exclude_tools,
            selection_json=resolved_selection.selection_json,
            json_output=True,
        ),
        root,
    )
    if provision_rc != 0:
        return provision_rc
    return require_f4_linter_provisioning_evidence(
        root,
        policy.artifact_entry_id,
        evidence_dir=evidence_dir,
    )


def run_or_record_f4_linter_provisioning_for_artifacts(
    root: Path,
    artifact_entry_ids: tuple[str, ...],
    *,
    build_dir: Path | None = None,
) -> int:
    """Run F4 evidence hooks for multiple artifact IDs in order."""
    for artifact_entry_id in artifact_entry_ids:
        rc = run_or_record_f4_linter_provisioning(
            root,
            artifact_entry_id,
            build_dir=build_dir,
        )
        if rc != 0:
            return rc
    return 0


def require_f4_linter_provisioning_evidence(
    root: Path,
    artifact_entry_id: str,
    *,
    evidence_dir: Path,
) -> int:
    """Verify one artifact's F4 provisioning evidence."""
    return _run_command(
        build_verification_command(
            root,
            artifact_entry_id=artifact_entry_id,
            evidence_dir=evidence_dir,
        ),
        root,
    )


def provision_release_f4_linter_evidence(
    root: Path,
    *,
    build_dir: Path | None = None,
) -> int:
    """Write and verify aggregate all-artifacts F4 evidence."""
    target_dir = _safe_child(
        root / "build" if build_dir is None else build_dir,
        "f4-linter-provisioning",
        "release",
        "target",
    )
    evidence_dir = release_provisioning_evidence_dir(root, build_dir)
    provision_rc = _run_command(
        build_provisioning_command(
            root,
            all_artifacts=True,
            target_dir=target_dir,
            evidence_dir=evidence_dir,
            mode=DEFAULT_PROVISIONING_MODE,
            profile=DEFAULT_PROVISIONING_PROFILE,
            json_output=True,
        ),
        root,
    )
    if provision_rc != 0:
        return provision_rc
    return require_release_f4_linter_provisioning_evidence(root, evidence_dir)


def require_release_f4_linter_provisioning_evidence(
    root: Path,
    evidence_dir: Path,
) -> int:
    """Verify aggregate all-artifacts F4 provisioning evidence."""
    return _run_command(
        build_verification_command(
            root,
            all_artifacts=True,
            evidence_dir=evidence_dir,
        ),
        root,
    )
