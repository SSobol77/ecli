# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/provisioning.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Planner, evidence writer, and verifier for F4 linter provisioning.

This module is provider-neutral. It never imports F4 panel code, never parses
linter diagnostics, and never runs linter diagnostics. The only external
processes it may run are explicit version probes in ``verify-only`` or
``provision`` mode.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from ecli.extensions.linters.core.provisioning_contract import (
    ActionStatus,
    ArtifactContractEntry,
    InstallerComponentModel,
    LinterSelectionOption,
    LinterSelectionProfile,
    LinterToolContract,
    ProvisioningAction,
    ProvisioningEvidence,
    ProvisioningMode,
    ProvisioningPlan,
    ProvisioningProfile,
    ProvisioningStrategy,
    VerificationResult,
)
from ecli.extensions.linters.core.provisioning_registry import (
    ARTIFACT_CONTRACT_ENTRIES,
    get_artifact_entry,
    is_github_generated_source_archive,
    load_linter_tool_contracts,
)


EVIDENCE_SCHEMA_VERSION = 1
DETERMINISTIC_TIMESTAMP_ENV = "ECLI_F4_PROVISIONING_TIMESTAMP"
DETERMINISTIC_TIMESTAMP = "1970-01-01T00:00:00Z"

PACKAGE_MANAGER_ARTIFACT_IDS = frozenset(
    {
        "deb",
        "rpm",
        "opensuse-rpm",
        "arch-pkgbuild",
        "slackware-txz",
        "freebsd-pkg",
        "docker-deb-helper",
        "docker-rpm-helper",
    }
)
PORTABLE_BUNDLE_ARTIFACT_IDS = frozenset(
    {
        "linux-pyinstaller",
        "linux-tarball",
        "appimage",
        "macos-app",
        "macos-dmg",
        "windows-portable-exe",
        "windows-nsis-installer",
        "freebsd-ports-chroot",
        "gha-release-contract",
    }
)
NIX_ARTIFACT_IDS = frozenset({"nix-flake", "nixos-package"})
CANONICAL_ARTIFACT_ENTRY_IDS = frozenset(
    entry.artifact_entry_id for entry in ARTIFACT_CONTRACT_ENTRIES
)
_SELECTION_INCLUDE_KEYS = (
    "include",
    "include_tool",
    "include_tools",
    "selected_tools",
)
_SELECTION_EXCLUDE_KEYS = (
    "exclude",
    "exclude_tool",
    "exclude_tools",
    "skipped_tools",
)


@dataclass(frozen=True)
class _ActionOutcome:
    status: ActionStatus
    verification_result: VerificationResult
    observed_version: str | None = None
    planned_version: str | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ActionRequest:
    contract: LinterToolContract
    artifact: ArtifactContractEntry
    profile: ProvisioningProfile
    mode: ProvisioningMode
    target_dir: Path
    allow_network: bool
    allow_upstream_downloads: bool
    include_tools: set[str]
    exclude_tools: set[str]


@dataclass(frozen=True)
class _PlanRequest:
    artifact_entry_id: str
    target_dir: Path
    evidence_dir: Path
    mode: ProvisioningMode
    profile: LinterSelectionProfile
    include_tools: Iterable[str]
    exclude_tools: Iterable[str]
    selection_json: Path | None
    allow_network: bool
    allow_upstream_downloads: bool
    contracts: tuple[LinterToolContract, ...] | None


def _contains_parent_reference(path: Path) -> bool:
    return ".." in path.parts


def _looks_like_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute():
        return True
    if "/" in value or "\\" in value:
        return True
    return any(part in {"", ".", ".."} for part in (*posix.parts, *windows.parts))


def canonical_artifact_entry_id(artifact_entry_id: str) -> str:
    """Return a canonical artifact id or reject path-like values."""
    if not isinstance(artifact_entry_id, str) or not artifact_entry_id:
        raise ValueError("artifact_entry_id must be a non-empty string")
    if _looks_like_path(artifact_entry_id):
        raise ValueError(
            f"artifact_entry_id must be a canonical registry id: {artifact_entry_id!r}"
        )
    if artifact_entry_id not in CANONICAL_ARTIFACT_ENTRY_IDS:
        raise KeyError(f"unknown artifact entry id: {artifact_entry_id!r}")
    return artifact_entry_id


def _canonical_artifact_entry(artifact_entry_id: str) -> ArtifactContractEntry:
    return get_artifact_entry(canonical_artifact_entry_id(artifact_entry_id))


def _safe_base_dir(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _safe_json_file(path: Path) -> Path:
    if _contains_parent_reference(path):
        raise ValueError(f"JSON path must not contain parent traversal: {path}")
    resolved = path.expanduser().resolve(strict=True)
    if resolved.suffix.lower() != ".json" or not resolved.is_file():
        raise ValueError(f"expected an existing JSON file: {path}")
    return resolved


def _validate_relative_path_part(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path segment")
    if _looks_like_path(value):
        raise ValueError(f"{label} must be a relative path segment: {value!r}")
    return value


def _ensure_child_path(base_dir: Path, child_path: Path) -> Path:
    try:
        child_path.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"path escapes base directory: {child_path}") from exc
    return child_path


def _safe_child_path(base_dir: Path, *parts: str) -> Path:
    base = _safe_base_dir(base_dir)
    child = base
    for index, part in enumerate(parts, start=1):
        child = child / _validate_relative_path_part(part, f"path part {index}")
    return _ensure_child_path(base, child.resolve(strict=False))


def evidence_path_for_artifact(evidence_dir: Path, artifact_entry_id: str) -> Path:
    """Return the safe evidence path for one canonical artifact."""
    return _safe_child_path(
        evidence_dir,
        evidence_filename(canonical_artifact_entry_id(artifact_entry_id)),
    )


def evidence_filename(artifact_entry_id: str) -> str:
    """Return the deterministic evidence filename for an artifact entry."""
    canonical_id = canonical_artifact_entry_id(artifact_entry_id)
    return f"f4-linter-provisioning-{canonical_id}.json"


def read_project_version(root: Path) -> str:
    """Read the project version from ``pyproject.toml``."""
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def generated_at() -> str:
    """Return an evidence timestamp, with deterministic override for tests."""
    override = os.environ.get(DETERMINISTIC_TIMESTAMP_ENV)
    if override is not None:
        return override or DETERMINISTIC_TIMESTAMP
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def os_context() -> dict[str, str]:
    """Return stable host context for evidence."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "platform": platform.platform(),
    }


def build_component_model(
    artifact: ArtifactContractEntry,
    profile: LinterSelectionProfile,
    contracts: tuple[LinterToolContract, ...] | None = None,
) -> InstallerComponentModel:
    """Build structured installer-renderable linter selection data."""
    loaded = load_linter_tool_contracts() if contracts is None else contracts
    options = tuple(
        LinterSelectionOption(
            tool_id=contract.tool_id,
            display_name=contract.display_name,
            required_for_full=contract.required_for_full,
            selected_by_default=contract.required_for_full,
            tier=contract.tier,
            install_group=contract.install_group,
            languages=contract.languages,
            executable_names=contract.executable_names,
        )
        for contract in loaded
    )
    return InstallerComponentModel(
        artifact_entry_id=artifact.artifact_entry_id,
        selection_profile=profile,
        full_label="Install all recommended F4 linters and toolchains",
        custom_label="Custom linter selection",
        options=options,
    )


def _tool_id_set(values: Iterable[Any]) -> set[str]:
    return {str(item) for item in values}


def _selection_values(data: Mapping[str, Any], keys: Iterable[str]) -> set[str]:
    selected: set[str] = set()
    for key in keys:
        values = data.get(key)
        if isinstance(values, list):
            selected.update(_tool_id_set(values))
    return selected


def _merge_tools_mapping(
    tools: Any,
    include: set[str],
    exclude: set[str],
) -> None:
    if not isinstance(tools, dict):
        return
    for tool_id, selected in tools.items():
        if selected is True:
            include.add(str(tool_id))
        elif selected is False:
            exclude.add(str(tool_id))


def _load_selection_json(path: Path) -> Any:
    safe_path = _safe_json_file(path)
    return json.loads(safe_path.read_text(encoding="utf-8"))


def _selection_json(path: Path | None) -> tuple[set[str], set[str]]:
    if path is None:
        return set(), set()
    data = _load_selection_json(path)
    if isinstance(data, list):
        return _tool_id_set(data), set()
    if not isinstance(data, dict):
        raise ValueError("selection JSON must be an object or list")

    include = _selection_values(data, _SELECTION_INCLUDE_KEYS)
    exclude = _selection_values(data, _SELECTION_EXCLUDE_KEYS)
    _merge_tools_mapping(data.get("tools"), include, exclude)
    return include, exclude


def resolve_profile(
    contracts: tuple[LinterToolContract, ...],
    artifact: ArtifactContractEntry,
    requested_profile: LinterSelectionProfile,
    **kwargs: Any,
) -> ProvisioningProfile:
    """Resolve profile/include/exclude inputs into selected tool ids."""
    include_tools, exclude_tools, selection_json = _resolve_profile_kwargs(kwargs)
    known, required, internal = _profile_tool_sets(contracts)
    json_include, json_exclude = _selection_json(selection_json)
    include = set(include_tools) | json_include
    exclude = set(exclude_tools) | json_exclude
    _validate_requested_tool_ids(include, exclude, known)

    selected = _selected_tool_ids_for_profile(
        requested_profile,
        required,
        internal,
        include,
        exclude,
    )
    effective_profile, full_complete, custom_reasons = _profile_completion(
        artifact,
        requested_profile,
        selected,
        required,
    )

    skipped = tuple(
        contract.tool_id for contract in contracts if contract.tool_id not in selected
    )
    return ProvisioningProfile(
        requested_profile=requested_profile,
        effective_profile=effective_profile,
        selected_tool_ids=tuple(
            contract.tool_id for contract in contracts if contract.tool_id in selected
        ),
        skipped_tool_ids=skipped,
        full_profile_complete=full_complete,
        custom_profile_reason="; ".join(custom_reasons) or None,
    )


def _resolve_profile_kwargs(
    kwargs: dict[str, Any],
) -> tuple[Iterable[str], Iterable[str], Path | None]:
    include_tools = kwargs.pop("include_tools", ())
    exclude_tools = kwargs.pop("exclude_tools", ())
    selection_json = kwargs.pop("selection_json", None)
    if kwargs:
        raise TypeError(f"unexpected resolve_profile argument(s): {sorted(kwargs)}")
    return include_tools, exclude_tools, selection_json


def _profile_tool_sets(
    contracts: tuple[LinterToolContract, ...],
) -> tuple[set[str], set[str], set[str]]:
    known = {contract.tool_id for contract in contracts}
    required = {
        contract.tool_id for contract in contracts if contract.required_for_full
    }
    internal = {
        contract.tool_id
        for contract in contracts
        if contract.provider_kind == "internal"
    }
    return known, required, internal


def _validate_requested_tool_ids(
    include: set[str],
    exclude: set[str],
    known: set[str],
) -> None:
    unknown = sorted((include | exclude) - known)
    if unknown:
        raise ValueError(f"unknown linter tool id(s): {unknown}")


def _selected_tool_ids_for_profile(
    requested_profile: LinterSelectionProfile,
    required: set[str],
    internal: set[str],
    include: set[str],
    exclude: set[str],
) -> set[str]:
    if requested_profile == "full":
        selected = set(required)
    elif requested_profile == "minimal":
        selected = set(internal)
    else:
        selected = set(include)
    selected.update(include)
    selected.difference_update(exclude)
    return selected


def _profile_completion(
    artifact: ArtifactContractEntry,
    requested_profile: LinterSelectionProfile,
    selected: set[str],
    required: set[str],
) -> tuple[LinterSelectionProfile, bool, list[str]]:
    effective_profile = requested_profile
    full_complete = requested_profile == "full" and required <= selected
    custom_reasons: list[str] = []

    missing_required = sorted(required - selected)
    if missing_required and requested_profile == "full":
        effective_profile = "custom"
        custom_reasons.append(
            "required Full tool(s) explicitly deselected: "
            + ", ".join(missing_required)
        )
    if missing_required:
        full_complete = False

    if requested_profile == "full" and not artifact.full_provisioning_supported:
        full_complete = False
        effective_profile = "minimal"
        if artifact.minimal_reason:
            custom_reasons.append(artifact.minimal_reason)

    if requested_profile in ("custom", "minimal"):
        full_complete = False
        custom_reasons.append(
            "custom linter selection requested"
            if requested_profile == "custom"
            else "minimal F4 provisioning requested"
        )
    return effective_profile, full_complete, custom_reasons


def _mechanism_allowed(contract: LinterToolContract, mechanism: str) -> bool:
    return mechanism in contract.allowed_install_mechanisms


def choose_strategy(
    artifact: ArtifactContractEntry,
    contract: LinterToolContract,
) -> ProvisioningStrategy:
    """Choose a deterministic default strategy for an artifact/tool pair."""
    strategy: ProvisioningStrategy | None = None
    if contract.provider_kind == "internal":
        strategy = ProvisioningStrategy(
            mechanism="bundled-internal",
            description="Bundled internal ECLI provider; no external tool download.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    elif not artifact.full_provisioning_supported:
        strategy = ProvisioningStrategy(
            mechanism="artifact-policy",
            description="Documented minimal/constrained artifact entry.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    else:
        strategy = _artifact_strategy(artifact, contract) or _contract_strategy(
            contract
        )

    return strategy or ProvisioningStrategy(
        mechanism="artifact-policy",
        description="Artifact policy must provide a concrete mechanism.",
        requires_network=False,
        requires_upstream_download=False,
        requires_checksum=False,
        source_url=contract.source_url,
        pinned_version=contract.pinned_version,
    )


def _artifact_strategy(
    artifact: ArtifactContractEntry,
    contract: LinterToolContract,
) -> ProvisioningStrategy | None:
    if artifact.artifact_entry_id in NIX_ARTIFACT_IDS and _mechanism_allowed(
        contract, "nix-derivation"
    ):
        return ProvisioningStrategy(
            mechanism="nix-derivation",
            description="Nix derivation/input provides the executable.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    if (
        artifact.artifact_entry_id in PACKAGE_MANAGER_ARTIFACT_IDS
        and _mechanism_allowed(contract, "os-package-manager")
    ):
        return ProvisioningStrategy(
            mechanism="os-package-manager",
            description="Native package metadata or helper evidence provides the tool.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    if (
        artifact.artifact_entry_id in PORTABLE_BUNDLE_ARTIFACT_IDS
        and _mechanism_allowed(contract, "bundled-binary")
    ):
        return ProvisioningStrategy(
            mechanism="bundled-binary",
            description="Bundled or adjacent artifact-managed runtime payload.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    return None


def _contract_strategy(contract: LinterToolContract) -> ProvisioningStrategy | None:
    if "toolchain-component" in contract.allowed_install_mechanisms:
        return ProvisioningStrategy(
            mechanism="toolchain-component",
            description="Toolchain component provisioned by artifact policy.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    if "jar-shim" in contract.allowed_install_mechanisms:
        return ProvisioningStrategy(
            mechanism="jar-shim",
            description="Pinned JAR/distribution plus wrapper shim.",
            requires_network=False,
            requires_upstream_download=True,
            requires_checksum=contract.checksum_required_for_downloads,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version or "release-policy-pin-required",
            checksum_source="release-provenance",
            checksum_value="release-policy-checksum-required",
        )
    if "language-package-manager" in contract.allowed_install_mechanisms:
        return ProvisioningStrategy(
            mechanism="language-package-manager",
            description="Pinned language package-manager install into ECLI tools path.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    if "verified-upstream-download" in contract.allowed_install_mechanisms:
        return ProvisioningStrategy(
            mechanism="verified-upstream-download",
            description="Verified upstream/GitHub release artifact.",
            requires_network=True,
            requires_upstream_download=True,
            requires_checksum=contract.checksum_required_for_downloads,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version or "release-policy-pin-required",
            checksum_source="release-provenance",
            checksum_value="release-policy-checksum-required",
        )
    return None


def _planned_path(target_dir: Path, executable_name: str) -> str:
    return str(_safe_child_path(target_dir, "bin", executable_name))


def _run_version_probe(
    command: tuple[str, ...],
    *,
    timeout_seconds: float,
) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    output = (completed.stdout or completed.stderr).strip().splitlines()
    version = output[0] if output else f"exit {completed.returncode}"
    if completed.returncode != 0:
        return version, f"version probe exited {completed.returncode}"
    return version, None


def _action_for_contract(request: _ActionRequest) -> ProvisioningAction:
    contract = request.contract
    selected = contract.tool_id in request.profile.selected_tool_ids
    executable_name = contract.executable_names[0]
    executable_path = shutil.which(executable_name)
    strategy = choose_strategy(request.artifact, contract)
    selected_by_default = (
        request.profile.requested_profile == "full" and contract.required_for_full
    )
    user_selected = contract.tool_id in request.include_tools
    user_opted_out = (
        contract.tool_id in request.exclude_tools and contract.required_for_full
    )
    outcome = _action_outcome(
        request,
        selected=selected,
        executable_name=executable_name,
        executable_path=executable_path,
        strategy=strategy,
    )

    return ProvisioningAction(
        tool_id=contract.tool_id,
        display_name=contract.display_name,
        required_for_full=contract.required_for_full,
        selected=selected,
        selected_by_default=selected_by_default,
        user_selected=user_selected,
        user_opted_out=user_opted_out,
        status=outcome.status,
        executable_name=executable_name,
        executable_path=executable_path,
        planned_path=_planned_path(request.target_dir, executable_name),
        version_command=contract.version_probe.command,
        observed_version=outcome.observed_version,
        planned_version=outcome.planned_version,
        strategy=strategy,
        verification_result=outcome.verification_result,
        errors=outcome.errors,
        warnings=outcome.warnings,
    )


def _action_outcome(
    request: _ActionRequest,
    *,
    selected: bool,
    executable_name: str,
    executable_path: str | None,
    strategy: ProvisioningStrategy,
) -> _ActionOutcome:
    contract = request.contract
    outcome: _ActionOutcome
    if not selected:
        outcome = _ActionOutcome(status="skipped", verification_result="skipped")
    elif (
        not request.artifact.full_provisioning_supported and contract.required_for_full
    ):
        outcome = _unsupported_artifact_outcome(request.artifact)
    elif contract.provider_kind == "internal":
        outcome = _ActionOutcome(
            status="bundled",
            verification_result="verified",
            planned_version="bundled-with-ecli",
        )
    elif request.mode == "dry-run":
        outcome = _dry_run_outcome(executable_path)
    elif executable_path is not None:
        outcome = _existing_executable_outcome(contract)
    elif request.mode == "verify-only":
        outcome = _ActionOutcome(
            status="failed",
            verification_result="failed",
            errors=(f"required executable is missing: {executable_name}",),
        )
    else:
        outcome = _unimplemented_provision_outcome(
            strategy,
            allow_network=request.allow_network,
            allow_upstream_downloads=request.allow_upstream_downloads,
        )
    return outcome


def _unsupported_artifact_outcome(
    artifact: ArtifactContractEntry,
) -> _ActionOutcome:
    warnings = (artifact.minimal_reason,) if artifact.minimal_reason else ()
    return _ActionOutcome(
        status="skipped",
        verification_result="skipped",
        warnings=warnings,
    )


def _dry_run_outcome(executable_path: str | None) -> _ActionOutcome:
    if executable_path is not None:
        return _ActionOutcome(
            status="already-present",
            verification_result="planned",
            planned_version="version-probe-deferred-in-dry-run",
        )
    return _ActionOutcome(
        status="planned",
        verification_result="planned",
        planned_version="planned-by-artifact-policy",
    )


def _existing_executable_outcome(
    contract: LinterToolContract,
) -> _ActionOutcome:
    observed_version, error = _run_version_probe(
        contract.version_probe.command,
        timeout_seconds=contract.version_probe.timeout_seconds,
    )
    if error is not None:
        return _ActionOutcome(
            status="failed",
            verification_result="failed",
            observed_version=observed_version,
            errors=(error,),
        )
    return _ActionOutcome(
        status="already-present",
        verification_result="verified",
        observed_version=observed_version,
    )


def _unimplemented_provision_outcome(
    strategy: ProvisioningStrategy,
    *,
    allow_network: bool,
    allow_upstream_downloads: bool,
) -> _ActionOutcome:
    errors: list[str] = []
    if strategy.requires_network and not allow_network:
        errors.append("network provisioning disabled by policy")
    if strategy.requires_upstream_download and not allow_upstream_downloads:
        errors.append("upstream downloads disabled by policy")
    errors.append(
        "concrete artifact installer integration is not implemented in this "
        "provider-neutral planner"
    )
    return _ActionOutcome(
        status="failed",
        verification_result="failed",
        errors=tuple(errors),
    )


def build_provisioning_plan(
    *,
    artifact_entry_id: str,
    target_dir: Path,
    evidence_dir: Path,
    **kwargs: Any,
) -> ProvisioningPlan:
    """Build an artifact-aware F4 linter provisioning plan."""
    request = _plan_request(artifact_entry_id, target_dir, evidence_dir, kwargs)
    artifact = _canonical_artifact_entry(request.artifact_entry_id)
    loaded = (
        load_linter_tool_contracts() if request.contracts is None else request.contracts
    )
    json_include, json_exclude = _selection_json(request.selection_json)
    include = set(request.include_tools) | json_include
    exclude = set(request.exclude_tools) | json_exclude
    resolved = resolve_profile(
        loaded,
        artifact,
        request.profile,
        include_tools=include,
        exclude_tools=exclude,
    )
    component_model = build_component_model(artifact, request.profile, loaded)
    actions = tuple(
        _action_for_contract(
            _ActionRequest(
                contract=contract,
                artifact=artifact,
                profile=resolved,
                mode=request.mode,
                target_dir=request.target_dir,
                allow_network=request.allow_network,
                allow_upstream_downloads=request.allow_upstream_downloads,
                include_tools=include,
                exclude_tools=exclude,
            )
        )
        for contract in loaded
    )
    return ProvisioningPlan(
        artifact=artifact,
        mode=request.mode,
        target_dir=str(request.target_dir),
        evidence_dir=str(request.evidence_dir),
        profile=resolved,
        component_model=component_model,
        actions=actions,
    )


def _plan_request(
    artifact_entry_id: str,
    target_dir: Path,
    evidence_dir: Path,
    kwargs: dict[str, Any],
) -> _PlanRequest:
    mode = kwargs.pop("mode")
    profile = kwargs.pop("profile")
    include_tools = kwargs.pop("include_tools", ())
    exclude_tools = kwargs.pop("exclude_tools", ())
    selection_json = kwargs.pop("selection_json", None)
    allow_network = bool(kwargs.pop("allow_network", False))
    allow_upstream_downloads = bool(kwargs.pop("allow_upstream_downloads", False))
    contracts = kwargs.pop("contracts", None)
    if kwargs:
        raise TypeError(
            f"unexpected build_provisioning_plan argument(s): {sorted(kwargs)}"
        )
    return _PlanRequest(
        artifact_entry_id=artifact_entry_id,
        target_dir=target_dir,
        evidence_dir=evidence_dir,
        mode=mode,
        profile=profile,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        selection_json=selection_json,
        allow_network=allow_network,
        allow_upstream_downloads=allow_upstream_downloads,
        contracts=contracts,
    )


def action_to_dict(action: ProvisioningAction) -> dict[str, Any]:
    """Serialize one action using stable field names required by evidence."""
    data = asdict(action)
    data["version_command"] = list(action.version_command)
    data["strategy"] = asdict(action.strategy)
    return data


def component_model_to_dict(model: InstallerComponentModel) -> dict[str, Any]:
    """Serialize installer component model."""
    return {
        "artifact_entry_id": model.artifact_entry_id,
        "selection_profile": model.selection_profile,
        "full_label": model.full_label,
        "custom_label": model.custom_label,
        "options": [asdict(option) for option in model.options],
    }


def plan_to_evidence(
    plan: ProvisioningPlan,
    *,
    ecli_version: str,
    timestamp: str | None = None,
) -> ProvisioningEvidence:
    """Convert a plan to evidence."""
    return ProvisioningEvidence(
        artifact_entry_id=plan.artifact.artifact_entry_id,
        run_mode=plan.mode,
        os_context=os_context(),
        generated_at=timestamp or generated_at(),
        ecli_version=ecli_version,
        target_dir=plan.target_dir,
        selection_profile=plan.profile.requested_profile,
        effective_profile=plan.profile.effective_profile,
        full_profile_complete=plan.profile.full_profile_complete,
        custom_profile_reason=plan.profile.custom_profile_reason,
        tools=plan.actions,
    )


def evidence_to_dict(evidence: ProvisioningEvidence) -> dict[str, Any]:
    """Serialize evidence to deterministic JSON-compatible data."""
    required = [tool for tool in evidence.tools if tool.required_for_full]
    selected = [tool for tool in evidence.tools if tool.selected]
    statuses: dict[str, int] = {}
    for tool in evidence.tools:
        statuses[tool.status] = statuses.get(tool.status, 0) + 1
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "artifact_entry_id": evidence.artifact_entry_id,
        "run_mode": evidence.run_mode,
        "os_context": evidence.os_context,
        "generated_at": evidence.generated_at,
        "ecli_version": evidence.ecli_version,
        "target_dir": evidence.target_dir,
        "selection_profile": evidence.selection_profile,
        "effective_profile": evidence.effective_profile,
        "full_profile_complete": evidence.full_profile_complete,
        "custom_profile_reason": evidence.custom_profile_reason,
        "tools": [action_to_dict(tool) for tool in evidence.tools],
        "summary": {
            "required_total": len(required),
            "selected_total": len(selected),
            "status_counts": statuses,
        },
    }


def write_evidence(plan: ProvisioningPlan, *, ecli_version: str) -> Path:
    """Write deterministic JSON evidence for ``plan`` and return the path."""
    evidence_dir = _safe_base_dir(Path(plan.evidence_dir))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = plan_to_evidence(plan, ecli_version=ecli_version)
    path = evidence_path_for_artifact(evidence_dir, plan.artifact.artifact_entry_id)
    path.write_text(
        json.dumps(evidence_to_dict(evidence), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def plan_has_release_blocking_failure(plan: ProvisioningPlan) -> bool:
    """Return whether a plan violates the Full provisioning contract."""
    if plan.mode == "dry-run":
        return False
    if not plan.artifact.full_provisioning_supported:
        return False
    for action in plan.actions:
        if action.required_for_full and action.selected and action.status == "failed":
            return True
        if action.required_for_full and not action.selected:
            return True
    return False


def _tool_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for item in tools:
        if isinstance(item, dict) and isinstance(item.get("tool_id"), str):
            result[item["tool_id"]] = item
    return result


def _has_probe(tool: Mapping[str, Any]) -> bool:
    command = tool.get("version_command")
    return isinstance(command, list) and all(isinstance(item, str) for item in command)


def _has_executable_record(tool: Mapping[str, Any]) -> bool:
    return isinstance(tool.get("executable_name"), str) and (
        isinstance(tool.get("executable_path"), str)
        or isinstance(tool.get("planned_path"), str)
    )


def _strategy_errors(tool: Mapping[str, Any]) -> list[str]:
    strategy = tool.get("strategy")
    if not isinstance(strategy, dict):
        return ["missing strategy record"]
    errors: list[str] = []
    if strategy.get("requires_upstream_download") is True:
        if not strategy.get("source_url"):
            errors.append("missing source URL for upstream download strategy")
        if not strategy.get("pinned_version"):
            errors.append("missing pinned version for upstream download strategy")
        if strategy.get("requires_checksum") is True:
            if not strategy.get("checksum_source"):
                errors.append("missing checksum source for upstream strategy")
            if not strategy.get("checksum_value"):
                errors.append("missing checksum value for upstream strategy")
    return errors


def verify_evidence_payload(
    payload: Mapping[str, Any],
    *,
    contracts: tuple[LinterToolContract, ...] | None = None,
) -> list[str]:
    """Return validation errors for one provisioning evidence payload."""
    artifact, ignored, errors = _payload_artifact(payload)
    if ignored:
        return []
    if artifact is None:
        return errors

    loaded = load_linter_tool_contracts() if contracts is None else contracts
    required = [contract for contract in loaded if contract.required_for_full]
    tools = _tool_by_id(payload)
    errors.extend(_payload_required_field_errors(payload))
    errors.extend(_payload_full_profile_errors(payload, artifact))
    for contract in required:
        errors.extend(
            _required_tool_errors(
                artifact=artifact,
                contract=contract,
                tool=tools.get(contract.tool_id),
            )
        )
    return errors


def _payload_artifact(
    payload: Mapping[str, Any],
) -> tuple[ArtifactContractEntry | None, bool, list[str]]:
    artifact_entry_id = payload.get("artifact_entry_id")
    if not isinstance(artifact_entry_id, str):
        return None, False, ["missing artifact_entry_id"]
    if is_github_generated_source_archive(artifact_entry_id):
        return None, True, []
    try:
        return _canonical_artifact_entry(artifact_entry_id), False, []
    except (KeyError, ValueError):
        return None, False, [f"unknown artifact_entry_id: {artifact_entry_id}"]


def _payload_required_field_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append("unsupported or missing schema_version")
    if "run_mode" not in payload:
        errors.append("missing run_mode")
    if "os_context" not in payload:
        errors.append("missing os_context")
    if "selection_profile" not in payload:
        errors.append("missing selection_profile")
    return errors


def _payload_full_profile_errors(
    payload: Mapping[str, Any],
    artifact: ArtifactContractEntry,
) -> list[str]:
    full_complete = payload.get("full_profile_complete")
    if artifact.full_provisioning_supported and full_complete is not True:
        return [
            f"{artifact.artifact_entry_id}: Full provisioning evidence is incomplete"
        ]
    return []


def _required_tool_errors(
    *,
    artifact: ArtifactContractEntry,
    contract: LinterToolContract,
    tool: Mapping[str, Any] | None,
) -> list[str]:
    artifact_entry_id = artifact.artifact_entry_id
    if tool is None:
        return [f"{artifact_entry_id}: missing required tool {contract.tool_id}"]

    errors = _required_tool_record_errors(artifact_entry_id, contract, tool)
    if artifact.full_provisioning_supported:
        errors.extend(_required_tool_state_errors(artifact_entry_id, contract, tool))
    return errors


def _required_tool_record_errors(
    artifact_entry_id: str,
    contract: LinterToolContract,
    tool: Mapping[str, Any],
) -> list[str]:
    prefix = f"{artifact_entry_id}/{contract.tool_id}"
    errors: list[str] = []
    if not _has_probe(tool):
        errors.append(f"{prefix}: missing version probe")
    if not _has_executable_record(tool):
        errors.append(f"{prefix}: missing executable record")
    errors.extend(f"{prefix}: {error}" for error in _strategy_errors(tool))
    return errors


def _required_tool_state_errors(
    artifact_entry_id: str,
    contract: LinterToolContract,
    tool: Mapping[str, Any],
) -> list[str]:
    prefix = f"{artifact_entry_id}/{contract.tool_id}"
    errors: list[str] = []
    if tool.get("selected") is not True:
        errors.append(f"{prefix}: required tool not selected")
    status = tool.get("status")
    if status not in {"already-present", "bundled", "planned", "provisioned"}:
        errors.append(f"{prefix}: invalid required status {status!r}")
    verification = tool.get("verification_result")
    if verification not in {"planned", "verified"}:
        errors.append(f"{prefix}: invalid verification result {verification!r}")
    return errors


def load_evidence_file(path: Path) -> Mapping[str, Any]:
    """Read one evidence JSON file."""
    safe_path = _safe_json_file(path)
    data = json.loads(safe_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"evidence file must contain a JSON object: {safe_path}")
    return data


def verify_evidence_dir(
    evidence_dir: Path,
    *,
    artifact_entry_id: str | None = None,
    all_artifacts: bool = False,
    contracts: tuple[LinterToolContract, ...] | None = None,
) -> list[str]:
    """Verify F4 provisioning evidence for one artifact or all 21 entries."""
    loaded = load_linter_tool_contracts() if contracts is None else contracts
    if all_artifacts:
        return _verify_all_evidence(evidence_dir, loaded)

    if artifact_entry_id is None:
        raise ValueError("artifact_entry_id is required unless all_artifacts=True")
    artifact_id = canonical_artifact_entry_id(artifact_entry_id)
    path = evidence_path_for_artifact(evidence_dir, artifact_id)
    if not path.is_file():
        return [f"missing evidence file: {path.name}"]
    return verify_evidence_payload(load_evidence_file(path), contracts=loaded)


def _verify_all_evidence(
    evidence_dir: Path,
    contracts: tuple[LinterToolContract, ...],
) -> list[str]:
    errors: list[str] = []
    for artifact in ARTIFACT_CONTRACT_ENTRIES:
        errors.extend(_verify_expected_evidence_file(evidence_dir, artifact, contracts))
    errors.extend(_unknown_evidence_entry_errors(evidence_dir))
    return errors


def _verify_expected_evidence_file(
    evidence_dir: Path,
    artifact: ArtifactContractEntry,
    contracts: tuple[LinterToolContract, ...],
) -> list[str]:
    path = evidence_path_for_artifact(evidence_dir, artifact.artifact_entry_id)
    if not path.is_file():
        return [f"missing evidence file: {path.name}"]
    return verify_evidence_payload(load_evidence_file(path), contracts=contracts)


def _safe_evidence_json_files(evidence_dir: Path) -> tuple[Path, ...]:
    base = _safe_base_dir(evidence_dir)
    if not base.exists():
        return ()
    return tuple(
        _ensure_child_path(base, path.resolve(strict=False))
        for path in sorted(base.glob("*.json"))
    )


def _unknown_evidence_entry_errors(evidence_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in _safe_evidence_json_files(evidence_dir):
        entry_id = load_evidence_file(path).get("artifact_entry_id")
        if isinstance(entry_id, str) and is_github_generated_source_archive(entry_id):
            continue
        if isinstance(entry_id, str) and entry_id not in CANONICAL_ARTIFACT_ENTRY_IDS:
            errors.append(f"unknown evidence artifact entry: {entry_id}")
    return errors
