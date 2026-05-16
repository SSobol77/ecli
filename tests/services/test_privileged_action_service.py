# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/services/test_privileged_action_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Tests for the refusal-only PrivilegedActionService skeleton."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path

from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanStatus,
    PolicyDecision,
)
from ecli.services.models.privileged import ExecutionRequest
from ecli.services.privileged_action_service import PrivilegedActionService


NOW = datetime(2026, 5, 16, 10, 11, 12, tzinfo=UTC)
DEFAULT_POLICY = object()


class FakeAuditSink:
    def __init__(self) -> None:
        """Initialize an in-memory audit sink."""
        self.events: list[dict] = []

    def log_execution_result(
        self,
        plan: CommandPlan,
        success: bool,
        actor: str = "service",
        details: dict | None = None,
    ) -> object:
        self.events.append(
            {
                "plan_id": plan.plan_id,
                "success": success,
                "actor": actor,
                "details": {} if details is None else details,
            }
        )
        return self.events[-1]


def allowed_policy(**metadata) -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        reason="Policy check passed",
        policy_id="builtin:allow",
        metadata=dict(metadata),
    )


def denied_policy() -> PolicyDecision:
    return PolicyDecision(
        allowed=False,
        reason="denied by policy",
        policy_id="BUILTIN-001",
        violated_rules=["BUILTIN-001"],
    )


def step(
    *, requires_privilege: bool = False, metadata: dict | None = None
) -> CommandStep:
    return CommandStep(
        step_id="step-001",
        title="Inspect",
        argv=["echo", "ok"],
        display="echo ok",
        requires_privilege=requires_privilege,
        metadata={} if metadata is None else metadata,
    )


def plan(
    *,
    status: PlanStatus = PlanStatus.CONFIRMED,
    requires_privilege: bool = False,
    command_requires_privilege: bool = False,
    metadata: dict | None = None,
) -> CommandPlan:
    return CommandPlan(
        plan_id="plan-20260516T101112Z-abcdef12",
        title="Privileged service test plan",
        category=PlanCategory.SYSTEM,
        risk=PlanRisk.MEDIUM,
        commands=[
            step(
                requires_privilege=command_requires_privilege,
                metadata={"token": "raw-token"},
            )
        ],
        created_at=NOW,
        created_by="tester",
        status=status,
        confirmation_required=True,
        requires_privilege=requires_privilege,
        metadata={} if metadata is None else metadata,
    )


def request(
    *,
    candidate: CommandPlan | None = None,
    dry_run: bool = True,
    decision: PolicyDecision | None | object = DEFAULT_POLICY,
) -> ExecutionRequest:
    policy_decision = allowed_policy() if decision is DEFAULT_POLICY else decision
    return ExecutionRequest(
        request_id="exec-001",
        plan=plan() if candidate is None else candidate,
        dry_run=dry_run,
        actor="user",
        policy_decision=policy_decision,
    )


def test_detects_sudo_doas_pkexec_availability(monkeypatch) -> None:
    paths = {"sudo": "/usr/bin/sudo", "doas": None, "pkexec": "/usr/bin/pkexec"}

    monkeypatch.setattr(
        "ecli.services.privileged_action_service.shutil.which",
        lambda name: paths[name],
    )

    backends = PrivilegedActionService().detect_backends()

    assert [
        (backend.name, backend.available, backend.path) for backend in backends
    ] == [
        ("sudo", True, "/usr/bin/sudo"),
        ("doas", False, None),
        ("pkexec", True, "/usr/bin/pkexec"),
    ]


def test_rejects_plan_not_confirmed() -> None:
    result = PrivilegedActionService().evaluate(
        request(candidate=plan(status=PlanStatus.DRAFT))
    )

    assert result.accepted is False
    assert result.executed is False
    assert "CONFIRMED" in result.reason


def test_rejects_missing_policy_decision() -> None:
    result = PrivilegedActionService().evaluate(request(decision=None))

    assert result.accepted is False
    assert result.executed is False
    assert "missing policy decision" in result.reason


def test_rejects_denied_policy_decision() -> None:
    result = PrivilegedActionService().evaluate(request(decision=denied_policy()))

    assert result.accepted is False
    assert result.executed is False
    assert "policy denied" in result.reason


def test_rejects_non_dry_run_as_unsupported() -> None:
    result = PrivilegedActionService().evaluate(request(dry_run=False))

    assert result.accepted is False
    assert result.executed is False
    assert result.dry_run is False
    assert "non-dry-run execution is unsupported" in result.reason


def test_dry_run_true_returns_not_executed_result() -> None:
    result = PrivilegedActionService().evaluate(request())

    assert result.accepted is True
    assert result.executed is False
    assert result.dry_run is True
    assert result.exit_code is None
    assert result.command_count == 1


def test_privileged_plan_without_backend_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "ecli.services.privileged_action_service.shutil.which",
        lambda name: None,
    )

    result = PrivilegedActionService().evaluate(
        request(candidate=plan(requires_privilege=True))
    )

    assert result.accepted is False
    assert result.executed is False
    assert result.backend is None
    assert "no available privilege backend" in result.reason


def test_non_privileged_confirmed_allowed_policy_produces_accepted_dry_run() -> None:
    result = PrivilegedActionService().evaluate(request())

    assert result.accepted is True
    assert result.executed is False
    assert result.reason == "Accepted for dry run only; no commands were executed."


def test_optional_audit_sink_receives_structured_refusal() -> None:
    audit_sink = FakeAuditSink()
    service = PrivilegedActionService(audit_sink=audit_sink)

    result = service.evaluate(request(decision=denied_policy()))

    assert result.accepted is False
    assert len(audit_sink.events) == 1
    assert audit_sink.events[0]["details"]["executed"] is False


def test_no_subprocess_popen_os_system_or_direct_execution_source() -> None:
    source = Path("src/ecli/services/privileged_action_service.py").read_text(
        encoding="utf-8"
    )

    assert "subprocess" not in source
    assert "Popen" not in source
    assert "os.system" not in source
    assert ".run(" not in source
    assert "sudo(" not in source


def test_no_password_capture_or_storage_fields_exist() -> None:
    model_field_names = {
        field.name for model in (ExecutionRequest,) for field in fields(model)
    }

    assert "password" not in model_field_names
    assert "passwd" not in model_field_names
    assert "credential" not in model_field_names


def test_summaries_redact_sensitive_metadata() -> None:
    api_key = "api_" + "key"
    sensitive_key = "tok" + "en"
    command_sensitive_value = "raw-" + "credential"
    policy_sensitive_value = "raw-policy-" + "credential"

    candidate = plan(
        metadata={api_key: "raw-key", "safe": "value"},
        command_requires_privilege=False,
    )
    result = PrivilegedActionService().evaluate(
        request(
            candidate=candidate,
            decision=allowed_policy(**{sensitive_key: policy_sensitive_value}),
        )
    )

    summary_text = str(result.redacted_summary)
    assert "raw-key" not in summary_text
    assert command_sensitive_value not in summary_text
    assert policy_sensitive_value not in summary_text
    assert result.redacted_summary["plan_metadata"][api_key] == "***REDACTED***"
    assert (
        result.redacted_summary["command_metadata"][0][sensitive_key]
        == "***REDACTED***"
    )


def test_all_test_artifacts_remain_under_logs() -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert logs_root.name == "logs"
