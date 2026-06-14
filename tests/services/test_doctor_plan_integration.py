# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_doctor_plan_integration.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for SystemDoctor finding to CommandPlan integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterator

import pytest

from ecli.services.command_plan_service import CommandPlanService
from ecli.services.models.doctor import DoctorContext, DoctorFinding, DoctorSeverity
from ecli.services.models.plan import (
    CommandPlan,
    PlanCategory,
    PlanRisk,
    PlanSource,
    PlanStatus,
)
from ecli.services.system_doctor import SystemDoctor
from ecli.services.validators.plan_validator import validate_command_plan


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-doctor-plan-integration"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def snapshot_tree(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def finding(
    *,
    finding_id: str = "DOCTOR-CONFIG-001",
    severity: DoctorSeverity = DoctorSeverity.WARNING,
    category: str = "config",
    remediation_available: bool = True,
    affected_resources: tuple[str, ...] = ("logs",),
) -> DoctorFinding:
    return DoctorFinding(
        finding_id=finding_id,
        title="Repository logs directory is missing",
        severity=severity,
        category=category,
        description="Repository-level logs/ is absent.",
        affected_resources=affected_resources,
        remediation_available=remediation_available,
        remediation_plan_id="plan-20260101T000000Z-12345678"
        if remediation_available
        else None,
        metadata={"check": "logs_directory"},
    )


def test_remediation_available_finding_converts_to_command_plan() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(finding())

    assert isinstance(plan, CommandPlan)
    assert plan.commands
    assert plan.commands[0].argv == ["mkdir", "-p", "logs"]


def test_remediation_unavailable_finding_returns_none() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(
        finding(remediation_available=False)
    )

    assert plan is None


def test_plan_metadata_includes_finding_id_category_and_severity() -> None:
    source_finding = finding(severity=DoctorSeverity.ERROR, category="path-policy")

    plan = CommandPlanService().create_plan_from_doctor_finding(source_finding)

    assert plan is not None
    assert plan.metadata["doctor_finding_id"] == source_finding.finding_id
    assert plan.metadata["doctor_finding_category"] == "path-policy"
    assert plan.metadata["doctor_finding_severity"] == "ERROR"
    assert plan.metadata["doctor_remediation_source"] == "system_doctor"


def test_plan_title_and_description_are_deterministic_preview_context() -> None:
    source_finding = finding()

    first = CommandPlanService().create_plan_from_doctor_finding(source_finding)
    second = CommandPlanService().create_plan_from_doctor_finding(source_finding)

    assert first is not None
    assert second is not None
    assert first.title == second.title
    assert first.description == second.description
    assert "Doctor remediation preview" in first.title
    assert source_finding.finding_id in first.description


def test_plan_status_is_draft_and_non_executing() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(finding())

    assert plan is not None
    assert plan.status is PlanStatus.DRAFT
    assert plan.status is not PlanStatus.EXECUTING
    assert "executed" not in plan.as_dict()


def test_plan_source_is_doctor() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(finding())

    assert plan is not None
    assert plan.source is PlanSource.DOCTOR


@pytest.mark.parametrize(
    ("category", "severity", "expected_category", "expected_risk"),
    [
        ("config", DoctorSeverity.WARNING, PlanCategory.DOCTOR, PlanRisk.LOW),
        ("path-policy", DoctorSeverity.ERROR, PlanCategory.FILE, PlanRisk.MEDIUM),
        ("permissions", DoctorSeverity.WARNING, PlanCategory.SYSTEM, PlanRisk.MEDIUM),
        ("virtualization", DoctorSeverity.ERROR, PlanCategory.VM, PlanRisk.HIGH),
        ("tooling", DoctorSeverity.CRITICAL, PlanCategory.SYSTEM, PlanRisk.CRITICAL),
    ],
)
def test_plan_risk_and_category_mapping_is_deterministic(
    category: str,
    severity: DoctorSeverity,
    expected_category: PlanCategory,
    expected_risk: PlanRisk,
) -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(
        finding(
            finding_id=f"DOCTOR-{category.upper()}-001",
            category=category,
            severity=severity,
        )
    )

    assert plan is not None
    assert plan.category is expected_category
    assert plan.risk is expected_risk


def test_critical_finding_produces_confirmation_required_plan() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(
        finding(severity=DoctorSeverity.CRITICAL, category="tooling")
    )

    assert plan is not None
    assert plan.confirmation_required is True
    assert plan.risk is PlanRisk.CRITICAL


def test_informational_finding_does_not_create_privileged_or_destructive_step() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(
        finding(severity=DoctorSeverity.INFO, category="config")
    )

    assert plan is not None
    assert plan.requires_privilege is False
    assert plan.commands[0].requires_privilege is False
    assert plan.commands[0].destructive is False


def test_generated_plan_has_no_runtime_side_effects(workspace: Path) -> None:
    before = snapshot_tree(workspace)

    CommandPlanService().create_plan_from_doctor_finding(
        finding(affected_resources=(str(workspace / "missing-logs"),))
    )

    assert snapshot_tree(workspace) == before
    assert not (workspace / "missing-logs").exists()


def test_generated_plan_exports_to_json_and_markdown() -> None:
    service = CommandPlanService()
    plan = service.create_plan_from_doctor_finding(finding())

    assert plan is not None
    json_payload = json.loads(service.export_json(plan))
    markdown = service.export_markdown(plan)

    assert json_payload["metadata"]["doctor_finding_id"] == "DOCTOR-CONFIG-001"
    assert "# Command Plan: Doctor remediation preview" in markdown
    assert "doctor_finding_id" in markdown


def test_generated_plan_validates_with_existing_plan_validator() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(finding())

    assert plan is not None
    assert validate_command_plan(plan) == []


def test_system_doctor_propose_remediation_delegates_to_command_plan_service(
    workspace: Path,
) -> None:
    doctor = SystemDoctor(logs_root=workspace / "missing-logs", tool_checks=())
    source_finding = doctor.check_logs_directory(DoctorContext(project_root=workspace))[
        0
    ]

    plan = doctor.propose_remediation(source_finding)

    assert plan is not None
    assert plan.metadata["doctor_finding_id"] == source_finding.finding_id
    assert plan.commands[0].argv == ["mkdir", "-p", str(workspace / "missing-logs")]


def test_source_scan_has_no_execution_privilege_or_network_usage() -> None:
    combined_source = "\n".join(
        [
            Path("src/ecli/services/system_doctor.py").read_text(encoding="utf-8"),
            Path("src/ecli/services/command_plan_service.py").read_text(
                encoding="utf-8"
            ),
        ]
    )

    forbidden_tokens = (
        "subprocess",
        "Popen",
        "os.system",
        ".run(",
        "sudo",
        "doas",
        "pkexec",
        "chmod",
        "chown",
        "usermod",
        "modprobe",
        "socket",
        "requests",
        "urllib",
        "aiohttp",
    )
    assert all(token not in combined_source for token in forbidden_tokens)


def test_all_test_workspaces_remain_under_logs(workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_root)
