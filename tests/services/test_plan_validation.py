# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_plan_validation.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for command plan validators."""

from __future__ import annotations

from datetime import UTC, datetime

from ecli.services.models.plan import CommandPlan, CommandStep, PlanCategory, PlanRisk
from ecli.services.validators.plan_validator import (
    validate_command_plan,
    validate_command_step,
)


NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def step(**overrides) -> CommandStep:
    values = {
        "step_id": "step-001",
        "title": "Echo",
        "argv": ["echo", "hello"],
        "display": "echo hello",
    }
    values.update(overrides)
    return CommandStep(**values)


def plan(**overrides) -> CommandPlan:
    values = {
        "plan_id": "plan-20260515T120000Z-abcdef12",
        "title": "Validation plan",
        "category": PlanCategory.GENERAL,
        "risk": PlanRisk.MEDIUM,
        "commands": [step()],
        "created_at": NOW,
        "created_by": "tester",
        "confirmation_required": True,
    }
    values.update(overrides)
    return CommandPlan(**values)


def test_validate_command_plan_rejects_empty_commands() -> None:
    diagnostics = validate_command_plan(plan(commands=[]))

    assert any("plan.commands must be non-empty" in item for item in diagnostics)


def test_validate_command_step_rejects_empty_argv() -> None:
    diagnostics = validate_command_step(step(argv=[]))

    assert any("argv must be non-empty" in item for item in diagnostics)


def test_validate_command_step_flags_standalone_shell_operators() -> None:
    diagnostics = validate_command_step(step(argv=["echo", "safe;literal", "&&", "ok"]))

    assert any(
        "standalone shell-like operator token: &&" in item for item in diagnostics
    )
    assert not any("safe;literal" in item for item in diagnostics)


def test_validate_command_step_rejects_invalid_expected_exit_codes() -> None:
    diagnostics = validate_command_step(step(expected_exit_codes=[0, 256, -1]))

    assert (
        sum(
            "expected_exit_codes values must be in 0..255" in item
            for item in diagnostics
        )
        == 2
    )


def test_validate_command_plan_rejects_low_risk_privileged_command() -> None:
    diagnostics = validate_command_plan(
        plan(
            risk=PlanRisk.LOW,
            commands=[step(requires_privilege=True)],
            requires_privilege=True,
            confirmation_required=True,
        )
    )

    assert any("cannot remain LOW risk" in item for item in diagnostics)


def test_validate_command_plan_requires_privilege_field_consistency() -> None:
    diagnostics = validate_command_plan(
        plan(commands=[step(requires_privilege=True)], requires_privilege=False)
    )

    assert any("plan.requires_privilege must be true" in item for item in diagnostics)


def test_validate_command_plan_requires_critical_confirmation() -> None:
    diagnostics = validate_command_plan(
        plan(risk=PlanRisk.CRITICAL, confirmation_required=False)
    )

    assert any(
        "CRITICAL plans must require confirmation" in item for item in diagnostics
    )


def test_validate_command_plan_flags_secret_like_metadata_keys() -> None:
    diagnostics = validate_command_plan(
        plan(metadata={"token": "secret", "nested": {"api_key": "secret"}})
    )

    assert any(
        "metadata.token contains secret-like metadata key" in item
        for item in diagnostics
    )
    assert any(
        "metadata.nested.api_key contains secret-like metadata key" in item
        for item in diagnostics
    )
