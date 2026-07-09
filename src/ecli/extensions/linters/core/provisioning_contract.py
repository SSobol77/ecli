# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/provisioning_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Provider-neutral provisioning contracts for the ECLI F4 Linter Pack.

This module is deliberately data-only. It has no F4 UI knowledge, no provider
registration, no parser imports, no package-manager calls, and no linter
execution. It defines the typed records used by the planner/verifier layer to
turn per-linter ``package_contract.py`` metadata into artifact-aware evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ecli.extensions.linters.core.registry import (
    InstallMechanism,
    ProvenanceRequirement,
)


ProvisioningMode = Literal["dry-run", "verify-only", "provision"]
LinterSelectionProfile = Literal["full", "custom", "minimal"]

ActionStatus = Literal[
    "already-present",
    "bundled",
    "failed",
    "planned",
    "provisioned",
    "skipped",
]

VerificationResult = Literal[
    "not-required",
    "planned",
    "skipped",
    "verified",
    "failed",
]


@dataclass(frozen=True)
class ArtifactContractEntry:
    """One canonical release artifact entry from the 21-entry contract."""

    index: int
    artifact_entry_id: str
    name: str
    platform: str
    output_template: str
    full_provisioning_supported: bool = True
    minimal_reason: str | None = None


@dataclass(frozen=True)
class VersionProbe:
    """Executable/version probe contract for a linter tool."""

    command: tuple[str, ...]
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class LinterToolContract:
    """Merged manifest/package contract for one linter tool."""

    tool_id: str
    display_name: str
    languages: tuple[str, ...]
    install_group: str
    tier: str
    provider_kind: str
    required_for_full: bool
    bundled_with_full_install: bool
    selected_by_default: bool
    executable_names: tuple[str, ...]
    version_probe: VersionProbe
    allowed_install_mechanisms: tuple[InstallMechanism, ...]
    provenance_requirements: tuple[ProvenanceRequirement, ...]
    source_url: str | None
    pinned_version: str | None
    checksum_required_for_downloads: bool
    artifact_entry_ids: tuple[str, ...]
    delivery_notes: str


@dataclass(frozen=True)
class ProvisioningStrategy:
    """Chosen artifact/tool provisioning mechanism."""

    mechanism: InstallMechanism
    description: str
    requires_network: bool
    requires_upstream_download: bool
    requires_checksum: bool
    source_url: str | None = None
    pinned_version: str | None = None
    checksum_source: str | None = None
    checksum_value: str | None = None


@dataclass(frozen=True)
class LinterSelectionOption:
    """Installer-renderable selection row for one linter."""

    tool_id: str
    display_name: str
    required_for_full: bool
    selected_by_default: bool
    tier: str
    install_group: str
    languages: tuple[str, ...]
    executable_names: tuple[str, ...]


@dataclass(frozen=True)
class InstallerComponentModel:
    """Structured component model for installer frontends."""

    artifact_entry_id: str
    selection_profile: LinterSelectionProfile
    full_label: str
    custom_label: str
    options: tuple[LinterSelectionOption, ...]


@dataclass(frozen=True)
class ProvisioningProfile:
    """Resolved selection profile after include/exclude policy is applied."""

    requested_profile: LinterSelectionProfile
    effective_profile: LinterSelectionProfile
    selected_tool_ids: tuple[str, ...]
    skipped_tool_ids: tuple[str, ...]
    full_profile_complete: bool
    custom_profile_reason: str | None = None


@dataclass(frozen=True)
class ProvisioningAction:
    """Planned or executed action for one linter tool."""

    tool_id: str
    display_name: str
    required_for_full: bool
    selected: bool
    selected_by_default: bool
    user_selected: bool
    user_opted_out: bool
    status: ActionStatus
    executable_name: str
    executable_path: str | None
    planned_path: str
    version_command: tuple[str, ...]
    observed_version: str | None
    planned_version: str | None
    strategy: ProvisioningStrategy
    verification_result: VerificationResult
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProvisioningPlan:
    """Artifact-aware provisioning plan for a selected linter profile."""

    artifact: ArtifactContractEntry
    mode: ProvisioningMode
    target_dir: str
    evidence_dir: str
    profile: ProvisioningProfile
    component_model: InstallerComponentModel
    actions: tuple[ProvisioningAction, ...]


@dataclass(frozen=True)
class ProvisioningEvidence:
    """Serialized release/install evidence for one artifact provisioning run."""

    artifact_entry_id: str
    run_mode: ProvisioningMode
    os_context: dict[str, str]
    generated_at: str
    ecli_version: str
    target_dir: str
    selection_profile: LinterSelectionProfile
    effective_profile: LinterSelectionProfile
    full_profile_complete: bool
    custom_profile_reason: str | None
    tools: tuple[ProvisioningAction, ...]
