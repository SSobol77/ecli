# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_system_doctor.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the read-only SystemDoctor skeleton."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Iterator

import pytest

from ecli.services.models.doctor import DoctorContext, DoctorFinding, DoctorSeverity
from ecli.services.models.plan import CommandPlan, PlanSource, PlanStatus
from ecli.services.system_doctor import SystemDoctor


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-system-doctor"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def snapshot_tree(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def test_doctor_severity_values_are_stable() -> None:
    assert [severity.value for severity in DoctorSeverity] == [
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]


def test_doctor_finding_is_typed_and_json_serializable() -> None:
    finding = DoctorFinding(
        finding_id="DOCTOR-TEST-001",
        title="Example",
        severity=DoctorSeverity.WARNING,
        category="config",
        description="Example finding",
        affected_resources=("logs",),
        remediation_available=True,
        remediation_plan_id="plan-20260101T000000Z-12345678",
        metadata={"nested": {"path": Path("logs")}},
    )

    payload = finding.as_dict()

    assert payload["severity"] == "WARNING"
    assert payload["affected_resources"] == ["logs"]
    json.dumps(payload, sort_keys=True)


def test_doctor_context_copies_mutable_fields() -> None:
    categories = ["config"]
    metadata = {"key": "value"}
    context = DoctorContext(categories=categories, metadata=metadata)

    categories.append("tooling")
    metadata["key"] = "changed"

    assert context.categories == ("config",)
    assert isinstance(context.metadata, MappingProxyType)
    assert context.metadata["key"] == "value"
    with pytest.raises(TypeError):
        context.metadata["new"] = "blocked"  # type: ignore[index]


def test_detect_problems_returns_findings_list(workspace: Path) -> None:
    doctor = SystemDoctor(
        logs_root=workspace,
        kvm_path=workspace / "missing-kvm",
        tool_checks=(),
    )

    findings = doctor.detect_problems(
        DoctorContext(project_root=workspace, categories=("virtualization",))
    )

    assert isinstance(findings, list)
    assert all(isinstance(finding, DoctorFinding) for finding in findings)


def test_category_filtering_works_deterministically(workspace: Path) -> None:
    missing_logs = workspace / "missing-logs"
    doctor = SystemDoctor(
        logs_root=missing_logs,
        kvm_path=workspace / "missing-kvm",
        tool_checks=("missing-tool",),
    )

    findings = doctor.detect_problems(DoctorContext(categories=("config",)))

    assert [finding.finding_id for finding in findings] == ["DOCTOR-CONFIG-001"]
    assert {finding.category for finding in findings} == {"config"}


def test_check_tool_available_uses_monkeypatched_shutil_which(monkeypatch) -> None:
    calls: list[str] = []

    def fake_which(tool_name: str) -> str | None:
        calls.append(tool_name)
        return "/usr/bin/git" if tool_name == "git" else None

    monkeypatch.setattr("ecli.services.system_doctor.shutil.which", fake_which)

    doctor = SystemDoctor(tool_checks=())

    assert doctor.check_tool_available("git") is True
    assert doctor.check_tool_available("missing") is False
    assert calls == ["git", "missing"]


def test_check_kvm_access_handles_missing_device_without_crashing(
    workspace: Path,
) -> None:
    doctor = SystemDoctor(kvm_path=workspace / "missing-kvm")

    assert doctor.check_kvm_access() is False


def test_existing_project_root_produces_no_error_finding(workspace: Path) -> None:
    doctor = SystemDoctor(tool_checks=())

    findings = doctor.check_project_root(DoctorContext(project_root=workspace))

    assert findings == []


def test_missing_project_root_produces_structured_finding(workspace: Path) -> None:
    missing_project = workspace / "does-not-exist"
    doctor = SystemDoctor(tool_checks=())

    findings = doctor.check_project_root(DoctorContext(project_root=missing_project))

    assert [finding.finding_id for finding in findings] == ["DOCTOR-PATH-002"]
    assert findings[0].severity is DoctorSeverity.ERROR
    assert findings[0].affected_resources == (str(missing_project.resolve()),)


def test_logs_directory_check_is_read_only_and_does_not_create_files(
    workspace: Path,
) -> None:
    missing_logs = workspace / "missing-logs"
    doctor = SystemDoctor(logs_root=missing_logs, tool_checks=())

    findings = doctor.check_logs_directory(DoctorContext(project_root=workspace))

    assert [finding.finding_id for finding in findings] == ["DOCTOR-CONFIG-001"]
    assert findings[0].remediation_available is True
    assert not missing_logs.exists()


def test_propose_remediation_returns_command_plan_without_execution(
    workspace: Path,
) -> None:
    missing_logs = workspace / "missing-logs"
    doctor = SystemDoctor(logs_root=missing_logs, tool_checks=())
    finding = doctor.check_logs_directory(DoctorContext(project_root=workspace))[0]

    plan = doctor.propose_remediation(finding)

    assert isinstance(plan, CommandPlan)
    assert plan.status is PlanStatus.DRAFT
    assert plan.source is PlanSource.DOCTOR
    assert plan.confirmation_required is True
    assert plan.commands[0].argv == ["mkdir", "-p", str(missing_logs.resolve())]


def test_proposed_remediation_is_traceable_to_finding_id(workspace: Path) -> None:
    doctor = SystemDoctor(logs_root=workspace / "missing-logs", tool_checks=())
    finding = doctor.check_logs_directory(DoctorContext(project_root=workspace))[0]

    plan = doctor.propose_remediation(finding)

    assert plan is not None
    assert plan.metadata["finding_id"] == finding.finding_id
    assert plan.commands[0].metadata["finding_id"] == finding.finding_id
    assert plan.plan_id == finding.remediation_plan_id


def test_propose_remediation_returns_none_when_not_available() -> None:
    finding = DoctorFinding(
        finding_id="DOCTOR-PATH-001",
        title="Project root is not set",
        severity=DoctorSeverity.WARNING,
        category="path-policy",
        description="No project root",
        remediation_available=False,
    )

    assert SystemDoctor(tool_checks=()).propose_remediation(finding) is None


def test_no_mutation_occurs_during_read_only_checks(workspace: Path) -> None:
    project = workspace / "project"
    project.mkdir()
    before = snapshot_tree(workspace)
    doctor = SystemDoctor(
        logs_root=workspace,
        kvm_path=workspace / "missing-kvm",
        tool_checks=(),
    )

    doctor.detect_problems(DoctorContext(project_root=project))

    assert snapshot_tree(workspace) == before


def test_source_scan_has_no_execution_privilege_or_network_calls() -> None:
    source = Path("src/ecli/services/system_doctor.py").read_text(encoding="utf-8")

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
    assert all(token not in source for token in forbidden_tokens)


def test_all_test_workspaces_remain_under_logs(workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_root)
