# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/system_doctor.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Read-only SystemDoctor skeleton for Phase 1C."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ecli.services.models.doctor import DoctorContext, DoctorFinding, DoctorSeverity
from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
    PlanStatus,
    new_plan_id,
)


SUPPORTED_CATEGORIES: tuple[str, ...] = (
    "config",
    "permissions",
    "tooling",
    "virtualization",
    "path-policy",
)

DEFAULT_TOOL_CHECKS: tuple[str, ...] = ("git",)


class SystemDoctor:
    """Read-only environment inspection service.

    The Phase 1C implementation only reports findings and can propose command
    plans. It never performs remediation and never invokes external processes.
    """

    def __init__(
        self,
        logs_root: Path | None = None,
        kvm_path: Path | None = None,
        tool_checks: tuple[str, ...] = DEFAULT_TOOL_CHECKS,
    ) -> None:
        """Initialize read-only check paths without touching the filesystem."""
        self._logs_root = (
            _repo_logs_root() if logs_root is None else Path(logs_root)
        ).resolve(strict=False)
        self._kvm_path = Path("/dev/kvm") if kvm_path is None else Path(kvm_path)
        self._tool_checks = tuple(tool_checks)

    def detect_problems(self, context: DoctorContext) -> list[DoctorFinding]:
        """Run deterministic read-only checks for selected doctor categories."""
        categories = _selected_categories(context)
        findings: list[DoctorFinding] = []

        if "config" in categories:
            findings.extend(self.check_logs_directory(context))
        if "permissions" in categories:
            findings.extend(self.check_permissions_context(context))
        if "tooling" in categories:
            findings.extend(self.check_tooling(context))
        if "virtualization" in categories:
            findings.extend(self.check_virtualization(context))
        if "path-policy" in categories:
            findings.extend(self.check_project_root(context))

        return sorted(findings, key=lambda finding: finding.finding_id)

    def check_tool_available(self, tool_name: str) -> bool:
        """Return whether a tool is present using read-only PATH lookup."""
        return shutil.which(tool_name) is not None

    def check_kvm_access(self) -> bool:
        """Return whether /dev/kvm exists and is readable/writable."""
        return self._kvm_path.exists() and os.access(self._kvm_path, os.R_OK | os.W_OK)

    def check_project_root(self, context: DoctorContext) -> list[DoctorFinding]:
        """Validate project root presence without creating or modifying paths."""
        if context.project_root is None:
            return [
                DoctorFinding(
                    finding_id="DOCTOR-PATH-001",
                    title="Project root is not set",
                    severity=DoctorSeverity.WARNING,
                    category="path-policy",
                    description="SystemDoctor has no project root context to inspect.",
                    remediation_available=False,
                    metadata={"check": "project_root"},
                )
            ]

        project_root = Path(context.project_root).resolve(strict=False)
        if not project_root.exists():
            return [
                DoctorFinding(
                    finding_id="DOCTOR-PATH-002",
                    title="Project root does not exist",
                    severity=DoctorSeverity.ERROR,
                    category="path-policy",
                    description="Configured project root is not present on disk.",
                    affected_resources=(str(project_root),),
                    remediation_available=False,
                    metadata={"check": "project_root"},
                )
            ]
        return []

    def check_logs_directory(self, context: DoctorContext) -> list[DoctorFinding]:
        """Check repository-level logs/ presence without creating it."""
        if self._logs_root.exists() and self._logs_root.is_dir():
            return []
        plan_id = _remediation_plan_id("DOCTOR-CONFIG-001")
        return [
            DoctorFinding(
                finding_id="DOCTOR-CONFIG-001",
                title="Repository logs directory is missing",
                severity=DoctorSeverity.WARNING,
                category="config",
                description=(
                    "Repository-level logs/ is absent; generated diagnostics must "
                    "remain confined under logs/."
                ),
                affected_resources=(str(self._logs_root),),
                remediation_available=True,
                remediation_plan_id=plan_id,
                metadata={"check": "logs_directory", "user": context.user},
            )
        ]

    def check_permissions_context(self, context: DoctorContext) -> list[DoctorFinding]:
        """Report non-dry-run context while keeping the doctor read-only."""
        if context.dry_run:
            return []
        return [
            DoctorFinding(
                finding_id="DOCTOR-PERM-001",
                title="SystemDoctor remains read-only",
                severity=DoctorSeverity.INFO,
                category="permissions",
                description=(
                    "The supplied context requested non-dry-run mode, but Phase 1C "
                    "SystemDoctor only performs read-only inspection."
                ),
                remediation_available=False,
                metadata={"check": "dry_run", "environment": context.environment},
            )
        ]

    def check_tooling(self, context: DoctorContext) -> list[DoctorFinding]:
        """Check configured developer tools through read-only PATH lookup."""
        findings: list[DoctorFinding] = []
        for tool_name in self._tool_checks:
            if self.check_tool_available(tool_name):
                continue
            findings.append(
                DoctorFinding(
                    finding_id=f"DOCTOR-TOOL-001-{tool_name}",
                    title=f"Required tool is not available: {tool_name}",
                    severity=DoctorSeverity.WARNING,
                    category="tooling",
                    description=(
                        f"{tool_name} was not found on PATH during read-only lookup."
                    ),
                    affected_resources=(tool_name,),
                    remediation_available=False,
                    metadata={"check": "tool_available", "user": context.user},
                )
            )
        return findings

    def check_virtualization(self, context: DoctorContext) -> list[DoctorFinding]:
        """Check KVM device access without changing kernel or user state."""
        if self.check_kvm_access():
            return []
        return [
            DoctorFinding(
                finding_id="DOCTOR-VIRT-001",
                title="KVM access is unavailable",
                severity=DoctorSeverity.WARNING,
                category="virtualization",
                description=(
                    "KVM device access is unavailable for future virtualization "
                    "workflows."
                ),
                affected_resources=(str(self._kvm_path),),
                remediation_available=False,
                metadata={"check": "kvm_access", "environment": context.environment},
            )
        ]

    def propose_remediation(self, finding: DoctorFinding) -> CommandPlan | None:
        """Return a proposed CommandPlan for supported findings without execution."""
        if not finding.remediation_available:
            return None
        if finding.finding_id != "DOCTOR-CONFIG-001":
            return None

        plan_id = finding.remediation_plan_id or _remediation_plan_id(
            finding.finding_id
        )
        logs_path = (
            finding.affected_resources[0]
            if finding.affected_resources
            else str(self._logs_root)
        )
        return CommandPlan(
            plan_id=plan_id,
            title="Create repository logs directory",
            description="Proposed remediation only; SystemDoctor does not execute it.",
            category=PlanCategory.DOCTOR,
            risk=PlanRisk.LOW,
            status=PlanStatus.DRAFT,
            commands=[
                CommandStep(
                    step_id="doctor-create-logs-dir",
                    title="Create logs directory",
                    argv=["mkdir", "-p", logs_path],
                    display=f"mkdir -p {logs_path}",
                    destructive=False,
                    metadata={"finding_id": finding.finding_id},
                )
            ],
            confirmation_required=True,
            requires_privilege=False,
            created_at=_fixed_doctor_plan_time(),
            created_by="system_doctor",
            source=PlanSource.DOCTOR,
            affected_resources=[logs_path],
            metadata={
                "finding_id": finding.finding_id,
                "service": "SystemDoctor",
                "readonly": True,
            },
        )


def _selected_categories(context: DoctorContext) -> tuple[str, ...]:
    if not context.categories:
        return SUPPORTED_CATEGORIES
    selected = []
    for category in context.categories:
        if category in SUPPORTED_CATEGORIES and category not in selected:
            selected.append(category)
    return tuple(selected)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _repo_logs_root() -> Path:
    return (_repo_root() / "logs").resolve(strict=False)


def _remediation_plan_id(finding_id: str) -> str:
    suffix = hashlib.sha256(finding_id.encode("utf-8")).hexdigest()[:8]
    return new_plan_id(now=_fixed_doctor_plan_time(), random_suffix=suffix)


def _fixed_doctor_plan_time() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
