# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_audit_log_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for append-only JSONL AuditLogService behavior."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ecli.services.audit_log_service import (
    REDACTION_TEXT,
    AuditLogService,
    AuditRedactionError,
)
from ecli.services.models.audit import AuditActor, AuditEventType, AuditRecord
from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
    PolicyDecision,
)


FIXED_TIME = datetime(2026, 5, 16, 10, 11, 12, tzinfo=UTC)


@pytest.fixture
def audit_dir(request: pytest.FixtureRequest) -> Iterator[Path]:
    safe_name = request.node.name.replace("/", "_").replace(":", "_")
    path = Path.cwd() / "logs" / f"test-audit-{safe_name}"
    shutil.rmtree(path, ignore_errors=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def sample_step(
    *,
    requires_privilege: bool = False,
    destructive: bool = False,
) -> CommandStep:
    return CommandStep(
        step_id="step-001",
        title="Inspect",
        argv=["echo", "ok"],
        display="echo ok",
        requires_privilege=requires_privilege,
        destructive=destructive,
    )


def sample_plan() -> CommandPlan:
    return CommandPlan(
        plan_id="plan-20260516T101112Z-abcdef12",
        title="Audit test plan",
        category=PlanCategory.SYSTEM,
        risk=PlanRisk.HIGH,
        commands=[sample_step(requires_privilege=True)],
        created_at=FIXED_TIME,
        created_by="tester",
        source=PlanSource.USER,
        confirmation_required=True,
        requires_privilege=True,
        affected_resources=["cluster/prod/database"],
        metadata={"owner": "qa"},
    )


def sample_record(**overrides) -> AuditRecord:
    values = {
        "schema_version": 1,
        "event_id": "audit-fixed-001",
        "timestamp": FIXED_TIME,
        "event_type": AuditEventType.PLAN_CREATED.value,
        "actor": AuditActor.USER.value,
        "details": {"message": "created"},
        "metadata": {"owner": "qa"},
        "plan_id": "plan-20260516T101112Z-abcdef12",
        "category": "SYSTEM",
        "risk": "HIGH",
        "source": "USER",
    }
    values.update(overrides)
    return AuditRecord(**values)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_audit_record_serializes_to_json_compatible_dict() -> None:
    payload = sample_record().as_dict()

    json.dumps(payload)
    assert payload["timestamp"] == "2026-05-16T10:11:12Z"
    assert payload["event_type"] == "plan.created"
    assert payload["redacted_fields"] == []


def test_append_creates_daily_jsonl_under_logs(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    service.append(sample_record())

    audit_file = audit_dir / "audit-2026-05-16.jsonl"
    assert audit_file.is_file()
    assert audit_file.resolve(strict=False).is_relative_to(
        (Path.cwd() / "logs").resolve(strict=False)
    )


def test_each_audit_event_is_one_valid_json_object_per_line(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    service.append(sample_record())

    audit_file = audit_dir / "audit-2026-05-16.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["event_id"] == "audit-fixed-001"


def test_append_only_behavior_writes_multiple_lines(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    service.append(sample_record(event_id="audit-fixed-001"))
    service.append(sample_record(event_id="audit-fixed-002"))

    records = read_jsonl(audit_dir / "audit-2026-05-16.jsonl")

    assert [record["event_id"] for record in records] == [
        "audit-fixed-001",
        "audit-fixed-002",
    ]


def test_required_fields_exist_in_each_record(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    service.append(sample_record())

    record = read_jsonl(audit_dir / "audit-2026-05-16.jsonl")[0]

    for key in (
        "schema_version",
        "event_id",
        "timestamp",
        "event_type",
        "actor",
        "details",
        "metadata",
        "redacted_fields",
    ):
        assert key in record


def test_sensitive_values_are_redacted_before_write(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    service.append(
        sample_record(
            details={"env": {"API_KEY": "raw-secret"}},
            metadata={"authorization": "Bearer raw-token"},
        )
    )

    raw_text = (audit_dir / "audit-2026-05-16.jsonl").read_text(encoding="utf-8")
    record = json.loads(raw_text)

    assert "raw-secret" not in raw_text
    assert "raw-token" not in raw_text
    assert record["details"]["env"]["API_KEY"] == REDACTION_TEXT
    assert record["metadata"]["authorization"] == REDACTION_TEXT


def test_nested_sensitive_fields_are_redacted(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    returned = service.append(
        sample_record(
            details={
                "items": [
                    {"safe": "value"},
                    {"private_key": "raw-private-key"},
                ]
            },
            metadata={"nested": {"session_key": "raw-session"}},
        )
    )

    assert returned.details["items"][1]["private_key"] == REDACTION_TEXT
    assert returned.metadata["nested"]["session_key"] == REDACTION_TEXT


def test_redacted_fields_contains_deterministic_paths(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    returned = service.append(
        sample_record(
            details={"env": {"API_KEY": "raw-secret"}},
            metadata={"authorization": "Bearer raw-token"},
        )
    )

    assert returned.redacted_fields == [
        "details.env.API_KEY",
        "metadata.authorization",
    ]


def test_key_value_sensitive_material_in_string_is_redacted(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    returned = service.append(
        sample_record(details={"stderr": "failed token=raw-token api_key:raw-key"})
    )

    assert returned.details["stderr"] == (
        f"failed token={REDACTION_TEXT} api_key:{REDACTION_TEXT}"
    )
    assert returned.redacted_fields == ["details.stderr"]


def test_redaction_failure_fails_closed_and_writes_nothing(
    audit_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AuditLogService(audit_dir=audit_dir)

    def fail_redaction(value):
        raise ValueError("redaction failed")

    monkeypatch.setattr(service, "redact_sensitive", fail_redaction)

    with pytest.raises(AuditRedactionError):
        service.append(sample_record(details={"token": "raw-token"}))

    assert not audit_dir.exists()


def test_log_plan_created_writes_plan_created_event(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)

    record = service.log_plan_created(sample_plan())

    assert record.event_type == "plan.created"
    assert read_jsonl(service.audit_file_for(record.timestamp))[0]["event_type"] == (
        "plan.created"
    )


def test_log_policy_evaluated_redacts_decision_metadata(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    decision = PolicyDecision(
        allowed=False,
        reason="denied",
        policy_id="BUILTIN-001",
        violated_rules=["BUILTIN-001"],
        metadata={"api_key": "raw-key"},
    )

    record = service.log_policy_evaluated(sample_plan(), decision)
    raw_text = service.audit_file_for(record.timestamp).read_text(encoding="utf-8")

    assert record.event_type == "policy.denied"
    assert "raw-key" not in raw_text
    assert json.loads(raw_text)["details"]["decision"]["metadata"]["api_key"] == (
        REDACTION_TEXT
    )


def test_log_execution_result_writes_execution_result_metadata(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)

    record = service.log_execution_result(
        sample_plan(),
        success=False,
        details={"exit_code": 1, "stderr": "password=raw-password"},
    )

    assert record.event_type == "plan.execution_failed"
    assert record.details["success"] is False
    assert record.details["exit_code"] == 1
    assert record.details["stderr"] == f"password={REDACTION_TEXT}"


def test_audit_service_rejects_paths_outside_logs() -> None:
    with pytest.raises(ValueError):
        AuditLogService(audit_dir=Path.cwd() / "tests" / "audit-output")


def test_audit_service_source_does_not_import_subprocess_or_network_modules() -> None:
    source = Path("src/ecli/services/audit_log_service.py").read_text(encoding="utf-8")

    assert "subprocess" not in source
    assert "requests" not in source
    assert "socket" not in source


def test_deterministic_json_for_identical_fixed_records(audit_dir: Path) -> None:
    service = AuditLogService(audit_dir=audit_dir)
    record = sample_record()
    service.append(record)
    service.append(record)

    lines = (
        (audit_dir / "audit-2026-05-16.jsonl").read_text(encoding="utf-8").splitlines()
    )

    assert len(lines) == 2
    assert lines[0] == lines[1]
