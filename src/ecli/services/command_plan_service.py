# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/command_plan_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Service-owned export behavior for command plans."""

from __future__ import annotations

import hashlib
import json
import shlex
from datetime import UTC, datetime
from typing import Any

from ecli.services.models.doctor import DoctorFinding, DoctorSeverity
from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
    PlanStatus,
    new_plan_id,
)
from ecli.services.validators.plan_validator import SENSITIVE_METADATA_KEYS


REDACTION_TEXT = "<redacted>"


class CommandPlanService:
    """Command plan service utilities for Phase 1A."""

    def create_plan_from_doctor_finding(
        self,
        finding: DoctorFinding,
        *,
        actor: str = "system-doctor",
    ) -> CommandPlan | None:
        """Create a draft-only remediation preview plan from a doctor finding."""
        if not finding.remediation_available:
            return None

        command = _doctor_finding_step(finding)
        requires_privilege = _doctor_finding_requires_privilege(finding)
        return CommandPlan(
            plan_id=finding.remediation_plan_id or _doctor_plan_id(finding),
            title=f"Doctor remediation preview: {finding.title}",
            description=(
                "Preview-only remediation plan generated from SystemDoctor finding "
                f"{finding.finding_id}: {finding.description}"
            ),
            category=_plan_category_for_finding(finding),
            risk=_plan_risk_for_finding(finding),
            status=PlanStatus.DRAFT,
            commands=[command],
            confirmation_required=_doctor_finding_requires_confirmation(finding),
            requires_privilege=requires_privilege,
            created_at=_doctor_plan_time(),
            created_by=actor,
            source=PlanSource.DOCTOR,
            affected_resources=list(finding.affected_resources),
            metadata=_doctor_trace_metadata(finding),
        )

    def export_json(self, plan: CommandPlan) -> str:
        """Export a command plan as deterministic redacted JSON."""
        return json.dumps(
            _redact_sensitive(plan.as_dict()),
            sort_keys=True,
            separators=(",", ":"),
        )

    def export_shell(self, plan: CommandPlan) -> str:
        """Export a command plan as a non-executed bash script string."""
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            f"# plan_id: {_safe_comment(plan.plan_id)}",
            f"# title: {_safe_comment(plan.title)}",
            f"# category: {plan.category.value}",
            f"# risk: {plan.risk.value}",
            f"# source: {plan.source.value}",
        ]
        if plan.metadata:
            lines.append(
                f"# metadata: {_safe_comment(json.dumps(_redact_sensitive(plan.metadata), sort_keys=True))}"
            )
        lines.append("")

        for index, step in enumerate(plan.commands, start=1):
            lines.extend(_shell_step_lines(index, step))
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, plan: CommandPlan) -> str:
        """Export a command plan as redacted human-readable markdown."""
        lines = [
            f"# Command Plan: {_markdown_text(plan.title)}",
            "",
            f"- Plan ID: `{_markdown_text(plan.plan_id)}`",
            f"- Category: `{plan.category.value}`",
            f"- Risk: `{plan.risk.value}`",
            f"- Status: `{plan.status.value}`",
            f"- Source: `{plan.source.value}`",
            f"- Requires privilege: `{plan.requires_privilege}`",
            f"- Confirmation required: `{plan.confirmation_required}`",
            "",
        ]
        if plan.description:
            lines.extend([_markdown_text(plan.description), ""])
        if plan.metadata:
            metadata = json.dumps(_redact_sensitive(plan.metadata), sort_keys=True)
            lines.extend(["## Metadata", "", f"```json\n{metadata}\n```", ""])

        lines.extend(["## Command Steps", ""])
        for index, step in enumerate(plan.commands, start=1):
            lines.extend(_markdown_step_lines(index, step))
        return "\n".join(lines).rstrip() + "\n"


def _shell_step_lines(index: int, step: CommandStep) -> list[str]:
    lines = [
        f"# step {index}: {_safe_comment(step.title)}",
        f"# display: {_safe_comment(step.display)}",
    ]
    if step.requires_privilege:
        lines.append("# WARNING: this step requires privilege")
    if step.destructive:
        lines.append("# WARNING: this step is destructive")
    if step.metadata:
        metadata = json.dumps(_redact_sensitive(step.metadata), sort_keys=True)
        lines.append(f"# metadata: {_safe_comment(metadata)}")
    lines.extend([shlex.join(step.argv), ""])
    return lines


def _markdown_step_lines(index: int, step: CommandStep) -> list[str]:
    warnings: list[str] = []
    if step.requires_privilege:
        warnings.append("requires privilege")
    if step.destructive:
        warnings.append("destructive")

    lines = [
        f"### {index}. {_markdown_text(step.title)}",
        "",
        f"- Step ID: `{_markdown_text(step.step_id)}`",
        f"- Display: `{_markdown_text(step.display)}`",
        f"- Command: `{_markdown_text(shlex.join(step.argv))}`",
    ]
    if warnings:
        lines.append(f"- Warnings: {', '.join(warnings)}")
    if step.metadata:
        metadata = json.dumps(_redact_sensitive(step.metadata), sort_keys=True)
        lines.extend(["", f"```json\n{metadata}\n```"])
    lines.append("")
    return lines


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_METADATA_KEYS:
                redacted[key_text] = REDACTION_TEXT
            else:
                redacted[key_text] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_sensitive(item) for item in value]
    return value


def _safe_comment(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")


def _markdown_text(value: str) -> str:
    return value.replace("`", "\\`")


def _doctor_finding_step(finding: DoctorFinding) -> CommandStep:
    if finding.finding_id == "DOCTOR-CONFIG-001":
        target = finding.affected_resources[0] if finding.affected_resources else "logs"
        return CommandStep(
            step_id=_doctor_step_id(finding),
            title="Create repository logs directory",
            argv=["mkdir", "-p", target],
            display=f"mkdir -p {target}",
            requires_privilege=False,
            destructive=False,
            metadata=_doctor_trace_metadata(finding),
        )

    category = _safe_token(finding.category)
    return CommandStep(
        step_id=_doctor_step_id(finding),
        title=f"Preview remediation for {finding.finding_id}",
        argv=["ecli-doctor-remediation-preview", category, finding.finding_id],
        display=f"Preview remediation for {finding.finding_id}",
        requires_privilege=_doctor_finding_requires_privilege(finding),
        destructive=False,
        metadata=_doctor_trace_metadata(finding),
    )


def _doctor_trace_metadata(finding: DoctorFinding) -> dict[str, Any]:
    return {
        "doctor_finding_id": finding.finding_id,
        "doctor_finding_category": finding.category,
        "doctor_finding_severity": finding.severity.value,
        "doctor_remediation_source": "system_doctor",
        "finding_id": finding.finding_id,
        "readonly": True,
    }


def _plan_risk_for_finding(finding: DoctorFinding) -> PlanRisk:
    if finding.severity is DoctorSeverity.CRITICAL:
        return PlanRisk.CRITICAL
    if finding.severity is DoctorSeverity.ERROR:
        return (
            PlanRisk.HIGH
            if _doctor_finding_requires_privilege(finding)
            else PlanRisk.MEDIUM
        )
    if _doctor_finding_requires_privilege(finding):
        return PlanRisk.MEDIUM
    return PlanRisk.LOW


def _plan_category_for_finding(finding: DoctorFinding) -> PlanCategory:
    return {
        "config": PlanCategory.DOCTOR,
        "permissions": PlanCategory.SYSTEM,
        "tooling": PlanCategory.SYSTEM,
        "virtualization": PlanCategory.VM,
        "path-policy": PlanCategory.FILE,
    }.get(finding.category, PlanCategory.DOCTOR)


def _doctor_finding_requires_confirmation(finding: DoctorFinding) -> bool:
    return finding.severity is DoctorSeverity.CRITICAL or finding.category in {
        "config",
        "permissions",
        "tooling",
        "virtualization",
        "path-policy",
    }


def _doctor_finding_requires_privilege(finding: DoctorFinding) -> bool:
    return finding.category in {"permissions", "virtualization"}


def _doctor_plan_id(finding: DoctorFinding) -> str:
    suffix = hashlib.sha256(finding.finding_id.encode("utf-8")).hexdigest()[:8]
    return new_plan_id(now=_doctor_plan_time(), random_suffix=suffix)


def _doctor_step_id(finding: DoctorFinding) -> str:
    return f"doctor-remediation-{_safe_token(finding.finding_id)}"


def _doctor_plan_time() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


def _safe_token(value: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else "-" for character in value
    ).strip("-")
