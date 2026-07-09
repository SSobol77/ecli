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
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
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


def evidence_filename(artifact_entry_id: str) -> str:
    """Return the deterministic evidence filename for an artifact entry."""
    return f"f4-linter-provisioning-{artifact_entry_id}.json"


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


def _selection_json(path: Path | None) -> tuple[set[str], set[str]]:
    if path is None:
        return set(), set()
    data = json.loads(path.read_text(encoding="utf-8"))
    include: set[str] = set()
    exclude: set[str] = set()
    if isinstance(data, list):
        include.update(str(item) for item in data)
        return include, exclude
    if not isinstance(data, dict):
        raise ValueError("selection JSON must be an object or list")

    for key in ("include", "include_tool", "include_tools", "selected_tools"):
        values = data.get(key)
        if isinstance(values, list):
            include.update(str(item) for item in values)
    for key in ("exclude", "exclude_tool", "exclude_tools", "skipped_tools"):
        values = data.get(key)
        if isinstance(values, list):
            exclude.update(str(item) for item in values)
    tools = data.get("tools")
    if isinstance(tools, dict):
        for tool_id, selected in tools.items():
            if selected is True:
                include.add(str(tool_id))
            elif selected is False:
                exclude.add(str(tool_id))
    return include, exclude


def resolve_profile(
    contracts: tuple[LinterToolContract, ...],
    artifact: ArtifactContractEntry,
    requested_profile: LinterSelectionProfile,
    include_tools: Iterable[str] = (),
    exclude_tools: Iterable[str] = (),
    selection_json: Path | None = None,
) -> ProvisioningProfile:
    """Resolve profile/include/exclude inputs into selected tool ids."""
    known = {contract.tool_id for contract in contracts}
    required = {contract.tool_id for contract in contracts if contract.required_for_full}
    internal = {
        contract.tool_id for contract in contracts if contract.provider_kind == "internal"
    }
    json_include, json_exclude = _selection_json(selection_json)
    include = set(include_tools) | json_include
    exclude = set(exclude_tools) | json_exclude
    unknown = sorted((include | exclude) - known)
    if unknown:
        raise ValueError(f"unknown linter tool id(s): {unknown}")

    if requested_profile == "full":
        selected = set(required)
    elif requested_profile == "minimal":
        selected = set(internal)
    else:
        selected = set(include)

    selected.update(include)
    selected.difference_update(exclude)

    effective_profile = requested_profile
    full_complete = requested_profile == "full" and required <= selected
    custom_reasons: list[str] = []
    missing_required = sorted(required - selected)
    if missing_required:
        full_complete = False
        if requested_profile == "full":
            effective_profile = "custom"
            custom_reasons.append(
                "required Full tool(s) explicitly deselected: "
                + ", ".join(missing_required)
            )
    if not artifact.full_provisioning_supported and requested_profile == "full":
        full_complete = False
        effective_profile = "minimal"
        if artifact.minimal_reason:
            custom_reasons.append(artifact.minimal_reason)
    if requested_profile in ("custom", "minimal"):
        full_complete = False
        if requested_profile == "custom":
            custom_reasons.append("custom linter selection requested")
        else:
            custom_reasons.append("minimal F4 provisioning requested")

    skipped = tuple(contract.tool_id for contract in contracts if contract.tool_id not in selected)
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


def _mechanism_allowed(
    contract: LinterToolContract, mechanism: str
) -> bool:
    return mechanism in contract.allowed_install_mechanisms


def choose_strategy(
    artifact: ArtifactContractEntry,
    contract: LinterToolContract,
) -> ProvisioningStrategy:
    """Choose a deterministic default strategy for an artifact/tool pair."""
    if contract.provider_kind == "internal":
        return ProvisioningStrategy(
            mechanism="bundled-internal",
            description="Bundled internal ECLI provider; no external tool download.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
    if not artifact.full_provisioning_supported:
        return ProvisioningStrategy(
            mechanism="artifact-policy",
            description="Documented minimal/constrained artifact entry.",
            requires_network=False,
            requires_upstream_download=False,
            requires_checksum=False,
            source_url=contract.source_url,
            pinned_version=contract.pinned_version,
        )
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
    if artifact.artifact_entry_id in PACKAGE_MANAGER_ARTIFACT_IDS and _mechanism_allowed(
        contract, "os-package-manager"
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
    if artifact.artifact_entry_id in PORTABLE_BUNDLE_ARTIFACT_IDS and _mechanism_allowed(
        contract, "bundled-binary"
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
    return ProvisioningStrategy(
        mechanism="artifact-policy",
        description="Artifact policy must provide a concrete mechanism.",
        requires_network=False,
        requires_upstream_download=False,
        requires_checksum=False,
        source_url=contract.source_url,
        pinned_version=contract.pinned_version,
    )


def _planned_path(target_dir: Path, executable_name: str) -> str:
    return str(target_dir / "bin" / executable_name)


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


def _action_for_contract(
    *,
    contract: LinterToolContract,
    artifact: ArtifactContractEntry,
    profile: ProvisioningProfile,
    mode: ProvisioningMode,
    target_dir: Path,
    allow_network: bool,
    allow_upstream_downloads: bool,
    include_tools: set[str],
    exclude_tools: set[str],
) -> ProvisioningAction:
    selected = contract.tool_id in profile.selected_tool_ids
    executable_name = contract.executable_names[0]
    executable_path = shutil.which(executable_name)
    strategy = choose_strategy(artifact, contract)
    selected_by_default = (
        profile.requested_profile == "full" and contract.required_for_full
    )
    user_selected = contract.tool_id in include_tools
    user_opted_out = contract.tool_id in exclude_tools and contract.required_for_full
    warnings: list[str] = []
    errors: list[str] = []

    status: ActionStatus
    verification_result: VerificationResult
    observed_version: str | None = None
    planned_version: str | None = None

    if not selected:
        status = "skipped"
        verification_result = "skipped"
    elif not artifact.full_provisioning_supported and contract.required_for_full:
        status = "skipped"
        verification_result = "skipped"
        if artifact.minimal_reason:
            warnings.append(artifact.minimal_reason)
    elif contract.provider_kind == "internal":
        status = "bundled"
        verification_result = "verified"
        planned_version = "bundled-with-ecli"
    elif mode == "dry-run":
        if executable_path is not None:
            status = "already-present"
            planned_version = "version-probe-deferred-in-dry-run"
        else:
            status = "planned"
            planned_version = "planned-by-artifact-policy"
        verification_result = "planned"
    elif executable_path is not None:
        observed_version, error = _run_version_probe(
            contract.version_probe.command,
            timeout_seconds=contract.version_probe.timeout_seconds,
        )
        status = "already-present"
        verification_result = "verified"
        if error is not None:
            status = "failed"
            verification_result = "failed"
            errors.append(error)
    elif mode == "verify-only":
        status = "failed"
        verification_result = "failed"
        errors.append(f"required executable is missing: {executable_name}")
    else:
        status = "failed"
        verification_result = "failed"
        if strategy.requires_network and not allow_network:
            errors.append("network provisioning disabled by policy")
        if strategy.requires_upstream_download and not allow_upstream_downloads:
            errors.append("upstream downloads disabled by policy")
        errors.append(
            "concrete artifact installer integration is not implemented in this "
            "provider-neutral planner"
        )

    return ProvisioningAction(
        tool_id=contract.tool_id,
        display_name=contract.display_name,
        required_for_full=contract.required_for_full,
        selected=selected,
        selected_by_default=selected_by_default,
        user_selected=user_selected,
        user_opted_out=user_opted_out,
        status=status,
        executable_name=executable_name,
        executable_path=executable_path,
        planned_path=_planned_path(target_dir, executable_name),
        version_command=contract.version_probe.command,
        observed_version=observed_version,
        planned_version=planned_version,
        strategy=strategy,
        verification_result=verification_result,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def build_provisioning_plan(
    *,
    artifact_entry_id: str,
    target_dir: Path,
    evidence_dir: Path,
    mode: ProvisioningMode,
    profile: LinterSelectionProfile,
    include_tools: Iterable[str] = (),
    exclude_tools: Iterable[str] = (),
    selection_json: Path | None = None,
    allow_network: bool = False,
    allow_upstream_downloads: bool = False,
    contracts: tuple[LinterToolContract, ...] | None = None,
) -> ProvisioningPlan:
    """Build an artifact-aware F4 linter provisioning plan."""
    artifact = get_artifact_entry(artifact_entry_id)
    loaded = load_linter_tool_contracts() if contracts is None else contracts
    json_include, json_exclude = _selection_json(selection_json)
    include = set(include_tools) | json_include
    exclude = set(exclude_tools) | json_exclude
    resolved = resolve_profile(
        loaded,
        artifact,
        profile,
        include_tools=include,
        exclude_tools=exclude,
    )
    component_model = build_component_model(artifact, profile, loaded)
    actions = tuple(
        _action_for_contract(
            contract=contract,
            artifact=artifact,
            profile=resolved,
            mode=mode,
            target_dir=target_dir,
            allow_network=allow_network,
            allow_upstream_downloads=allow_upstream_downloads,
            include_tools=include,
            exclude_tools=exclude,
        )
        for contract in loaded
    )
    return ProvisioningPlan(
        artifact=artifact,
        mode=mode,
        target_dir=str(target_dir),
        evidence_dir=str(evidence_dir),
        profile=resolved,
        component_model=component_model,
        actions=actions,
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
    evidence_dir = Path(plan.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = plan_to_evidence(plan, ecli_version=ecli_version)
    path = evidence_dir / evidence_filename(plan.artifact.artifact_entry_id)
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
    artifact_entry_id = payload.get("artifact_entry_id")
    if not isinstance(artifact_entry_id, str):
        return ["missing artifact_entry_id"]
    if is_github_generated_source_archive(artifact_entry_id):
        return []
    try:
        artifact = get_artifact_entry(artifact_entry_id)
    except KeyError:
        return [f"unknown artifact_entry_id: {artifact_entry_id}"]

    loaded = load_linter_tool_contracts() if contracts is None else contracts
    required = [contract for contract in loaded if contract.required_for_full]
    tools = _tool_by_id(payload)
    errors: list[str] = []

    if payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append("unsupported or missing schema_version")
    if "run_mode" not in payload:
        errors.append("missing run_mode")
    if "os_context" not in payload:
        errors.append("missing os_context")
    if "selection_profile" not in payload:
        errors.append("missing selection_profile")

    full_complete = payload.get("full_profile_complete")
    if artifact.full_provisioning_supported and full_complete is not True:
        errors.append(
            f"{artifact_entry_id}: Full provisioning evidence is incomplete"
        )

    for contract in required:
        tool = tools.get(contract.tool_id)
        if tool is None:
            errors.append(f"{artifact_entry_id}: missing required tool {contract.tool_id}")
            continue
        if not _has_probe(tool):
            errors.append(f"{artifact_entry_id}/{contract.tool_id}: missing version probe")
        if not _has_executable_record(tool):
            errors.append(
                f"{artifact_entry_id}/{contract.tool_id}: missing executable record"
            )
        errors.extend(
            f"{artifact_entry_id}/{contract.tool_id}: {error}"
            for error in _strategy_errors(tool)
        )
        if not artifact.full_provisioning_supported:
            continue
        if tool.get("selected") is not True:
            errors.append(f"{artifact_entry_id}/{contract.tool_id}: required tool not selected")
        status = tool.get("status")
        if status not in {"already-present", "bundled", "planned", "provisioned"}:
            errors.append(
                f"{artifact_entry_id}/{contract.tool_id}: invalid required "
                f"status {status!r}"
            )
        verification = tool.get("verification_result")
        if verification not in {"planned", "verified"}:
            errors.append(
                f"{artifact_entry_id}/{contract.tool_id}: invalid verification "
                f"result {verification!r}"
            )
    return errors


def load_evidence_file(path: Path) -> Mapping[str, Any]:
    """Read one evidence JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"evidence file must contain a JSON object: {path}")
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
        errors: list[str] = []
        for artifact in ARTIFACT_CONTRACT_ENTRIES:
            path = evidence_dir / evidence_filename(artifact.artifact_entry_id)
            if not path.is_file():
                errors.append(f"missing evidence file: {path.name}")
                continue
            errors.extend(verify_evidence_payload(load_evidence_file(path), contracts=loaded))
        for path in sorted(evidence_dir.glob("*.json")):
            payload = load_evidence_file(path)
            entry_id = payload.get("artifact_entry_id")
            if isinstance(entry_id, str) and is_github_generated_source_archive(entry_id):
                continue
            if isinstance(entry_id, str) and entry_id not in {
                item.artifact_entry_id for item in ARTIFACT_CONTRACT_ENTRIES
            }:
                errors.append(f"unknown evidence artifact entry: {entry_id}")
        return errors

    if artifact_entry_id is None:
        raise ValueError("artifact_entry_id is required unless all_artifacts=True")
    path = evidence_dir / evidence_filename(artifact_entry_id)
    if not path.is_file():
        return [f"missing evidence file: {path.name}"]
    return verify_evidence_payload(load_evidence_file(path), contracts=loaded)
