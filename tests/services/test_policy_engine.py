# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_policy_engine.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the deterministic built-in policy engine."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
)
from ecli.services.policy import BuiltInPolicyEngine, PolicyContext


NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
RULE_IDS = (
    "BUILTIN-001",
    "BUILTIN-002",
    "BUILTIN-003",
    "BUILTIN-004",
    "BUILTIN-005",
    "BUILTIN-006",
)


def step(
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


def plan(
    *,
    risk: PlanRisk = PlanRisk.LOW,
    source: PlanSource = PlanSource.USER,
    confirmation_required: bool = False,
    command: CommandStep | None = None,
    affected_resources: list[str] | None = None,
) -> CommandPlan:
    return CommandPlan(
        plan_id="plan-20260515T120000Z-abcdef12",
        title="Policy test plan",
        category=PlanCategory.GENERAL,
        risk=risk,
        commands=[step() if command is None else command],
        created_at=NOW,
        created_by="tester",
        source=source,
        confirmation_required=confirmation_required,
        requires_privilege=(
            command.requires_privilege if command is not None else False
        ),
        affected_resources=[] if affected_resources is None else affected_resources,
    )


def test_builtin_policy_engine_exposes_stable_rule_ids() -> None:
    assert BuiltInPolicyEngine().get_registered_rules() == RULE_IDS


@pytest.mark.asyncio
async def test_low_risk_user_plan_is_allowed() -> None:
    decision = await BuiltInPolicyEngine().evaluate(plan(), PolicyContext())

    assert decision.allowed is True
    assert decision.reason == "Policy check passed"
    assert decision.policy_id == "builtin:allow"
    assert decision.violated_rules == []
    assert decision.override_allowed is False


@pytest.mark.asyncio
async def test_ai_high_risk_plan_without_human_review_is_denied_by_builtin_001() -> (
    None
):
    decision = await BuiltInPolicyEngine().evaluate(
        plan(risk=PlanRisk.HIGH, source=PlanSource.AI_ASSISTANT),
        PolicyContext(human_reviewed=False),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-001"
    assert decision.violated_rules == ["BUILTIN-001"]
    assert decision.override_allowed is False
    assert (
        decision.reason == "AI-generated high-risk plans require explicit human review."
    )


@pytest.mark.asyncio
async def test_ai_high_risk_plan_with_human_review_is_allowed() -> None:
    decision = await BuiltInPolicyEngine().evaluate(
        plan(
            risk=PlanRisk.HIGH,
            source=PlanSource.AI_ASSISTANT,
            confirmation_required=True,
        ),
        PolicyContext(human_reviewed=True),
    )

    assert decision.allowed is True


@pytest.mark.asyncio
async def test_critical_plan_without_confirmation_is_denied_by_builtin_002() -> None:
    decision = await BuiltInPolicyEngine().evaluate(
        plan(risk=PlanRisk.CRITICAL),
        PolicyContext(),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-002"
    assert decision.violated_rules == ["BUILTIN-002"]


@pytest.mark.asyncio
async def test_privileged_plan_without_privileged_route_is_denied_by_builtin_003() -> (
    None
):
    decision = await BuiltInPolicyEngine().evaluate(
        plan(
            risk=PlanRisk.MEDIUM,
            confirmation_required=True,
            command=step(requires_privilege=True),
        ),
        PolicyContext(privileged_route_available=False),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-003"
    assert decision.violated_rules == ["BUILTIN-003"]


@pytest.mark.asyncio
async def test_privileged_plan_with_privileged_route_is_allowed() -> None:
    decision = await BuiltInPolicyEngine().evaluate(
        plan(
            risk=PlanRisk.MEDIUM,
            confirmation_required=True,
            command=step(requires_privilege=True),
        ),
        PolicyContext(privileged_route_available=True),
    )

    assert decision.allowed is True


@pytest.mark.asyncio
async def test_destructive_production_without_override_is_denied_by_builtin_004() -> (
    None
):
    decision = await BuiltInPolicyEngine().evaluate(
        plan(
            risk=PlanRisk.MEDIUM,
            confirmation_required=True,
            command=step(destructive=True),
        ),
        PolicyContext(environment="production", override_approved=False),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-004"
    assert decision.violated_rules == ["BUILTIN-004"]
    assert decision.override_allowed is True


@pytest.mark.asyncio
async def test_destructive_production_with_override_missing_reason_is_denied_by_builtin_006() -> (
    None
):
    decision = await BuiltInPolicyEngine().evaluate(
        plan(
            risk=PlanRisk.MEDIUM,
            confirmation_required=True,
            command=step(destructive=True),
        ),
        PolicyContext(
            environment="production",
            override_approved=True,
            override_reason=None,
        ),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-006"
    assert decision.violated_rules == ["BUILTIN-006"]


@pytest.mark.asyncio
async def test_destructive_production_with_override_reason_is_allowed() -> None:
    decision = await BuiltInPolicyEngine().evaluate(
        plan(
            risk=PlanRisk.MEDIUM,
            confirmation_required=True,
            command=step(destructive=True),
        ),
        PolicyContext(
            environment="production",
            override_approved=True,
            override_reason="approved maintenance window",
        ),
    )

    assert decision.allowed is True


@pytest.mark.asyncio
async def test_forbidden_exact_resource_match_is_denied_by_builtin_005() -> None:
    decision = await BuiltInPolicyEngine().evaluate(
        plan(affected_resources=["cluster/prod/database"]),
        PolicyContext(forbidden_resource_patterns=("cluster/prod/database",)),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-005"
    assert decision.violated_rules == ["BUILTIN-005"]


@pytest.mark.asyncio
async def test_forbidden_prefix_pattern_is_denied_by_builtin_005() -> None:
    decision = await BuiltInPolicyEngine().evaluate(
        plan(affected_resources=["cluster/prod/database"]),
        PolicyContext(forbidden_resource_patterns=("cluster/prod/*",)),
    )

    assert decision.allowed is False
    assert decision.policy_id == "BUILTIN-005"
    assert decision.violated_rules == ["BUILTIN-005"]


@pytest.mark.asyncio
async def test_first_hard_deny_behavior_is_deterministic() -> None:
    policy_engine = BuiltInPolicyEngine()
    candidate = plan(
        risk=PlanRisk.CRITICAL,
        source=PlanSource.AI_ASSISTANT,
        confirmation_required=False,
        command=step(requires_privilege=True),
        affected_resources=["cluster/prod/database"],
    )
    context = PolicyContext(
        human_reviewed=False,
        privileged_route_available=False,
        forbidden_resource_patterns=("cluster/prod/*",),
    )

    first = await policy_engine.evaluate(candidate, context)
    second = await policy_engine.evaluate(candidate, context)

    assert first.as_dict() == second.as_dict()
    assert first.policy_id == "BUILTIN-001"
    assert first.violated_rules == [
        "BUILTIN-001",
        "BUILTIN-002",
        "BUILTIN-003",
        "BUILTIN-005",
    ]


@pytest.mark.asyncio
async def test_evaluation_does_not_mutate_command_plan() -> None:
    candidate = plan(
        risk=PlanRisk.HIGH,
        source=PlanSource.AI_ASSISTANT,
        affected_resources=["cluster/prod/database"],
    )
    before = candidate.as_dict()

    await BuiltInPolicyEngine().evaluate(
        candidate,
        PolicyContext(forbidden_resource_patterns=("cluster/prod/*",)),
    )

    assert candidate.as_dict() == before


@pytest.mark.asyncio
async def test_async_evaluate_works_under_pytest() -> None:
    decision = await BuiltInPolicyEngine().evaluate(plan(), PolicyContext())

    assert decision.allowed is True
