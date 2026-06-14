# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_command_plan_models.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for command plan data models."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
    PlanStatus,
    needs_confirmation,
    new_plan_id,
)


FIXED_NOW = datetime(2026, 5, 15, 12, 34, 56, tzinfo=UTC)


def make_step(
    *,
    requires_privilege: bool = False,
    destructive: bool = False,
) -> CommandStep:
    return CommandStep(
        step_id="step-001",
        title="List files",
        argv=["ls", "-la"],
        display="ls -la",
        requires_privilege=requires_privilege,
        destructive=destructive,
    )


def make_plan(
    *,
    risk: PlanRisk = PlanRisk.LOW,
    source: PlanSource = PlanSource.USER,
    confirmation_required: bool = False,
    requires_privilege: bool = False,
    step: CommandStep | None = None,
) -> CommandPlan:
    return CommandPlan(
        plan_id="plan-20260515T123456Z-abcdef12",
        title="Inspect workspace",
        category=PlanCategory.GENERAL,
        risk=risk,
        commands=[make_step() if step is None else step],
        created_at=FIXED_NOW,
        created_by="tester",
        source=source,
        confirmation_required=confirmation_required,
        requires_privilege=requires_privilege,
    )


def test_valid_command_step_defaults() -> None:
    step = make_step()

    assert step.step_id == "step-001"
    assert step.expected_exit_codes == [0]
    assert step.timeout_seconds is None
    assert step.metadata == {}


def test_valid_command_plan_defaults() -> None:
    plan = make_plan()

    assert plan.schema_version == 1
    assert plan.status is PlanStatus.DRAFT
    assert plan.rollback == []
    assert plan.affected_resources == []
    assert plan.metadata == {}


def test_enum_string_values_are_stable() -> None:
    assert PlanRisk.HIGH.value == "HIGH"
    assert str(PlanStatus.DRAFT) == "DRAFT"
    assert PlanCategory.KUBERNETES.value == "KUBERNETES"
    assert PlanSource.AI_ASSISTANT.value == "AI_ASSISTANT"


def test_command_plan_as_dict_serializes_enums_and_datetime() -> None:
    plan = make_plan(risk=PlanRisk.MEDIUM)

    payload = plan.as_dict()

    assert payload["risk"] == "MEDIUM"
    assert payload["category"] == "GENERAL"
    assert payload["created_at"] == "2026-05-15T12:34:56Z"


def test_new_plan_id_matches_format() -> None:
    plan_id = new_plan_id()

    assert re.fullmatch(r"plan-\d{8}T\d{6}Z-[0-9a-f]{8}", plan_id)


def test_new_plan_id_is_deterministic_with_fixed_inputs() -> None:
    assert new_plan_id(now=FIXED_NOW, random_suffix="ABCDEF12") == (
        "plan-20260515T123456Z-abcdef12"
    )


def test_low_non_privileged_non_destructive_user_plan_needs_no_confirmation() -> None:
    assert needs_confirmation(make_plan()) is False


def test_high_risk_plan_needs_confirmation() -> None:
    assert needs_confirmation(make_plan(risk=PlanRisk.HIGH)) is True


def test_critical_risk_plan_needs_confirmation() -> None:
    assert needs_confirmation(make_plan(risk=PlanRisk.CRITICAL)) is True


def test_privileged_step_needs_confirmation() -> None:
    assert (
        needs_confirmation(make_plan(step=make_step(requires_privilege=True))) is True
    )


def test_destructive_step_needs_confirmation() -> None:
    assert needs_confirmation(make_plan(step=make_step(destructive=True))) is True


def test_ai_assistant_medium_plan_needs_confirmation() -> None:
    assert (
        needs_confirmation(
            make_plan(risk=PlanRisk.MEDIUM, source=PlanSource.AI_ASSISTANT)
        )
        is True
    )
