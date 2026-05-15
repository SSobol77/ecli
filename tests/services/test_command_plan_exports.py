# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/services/test_command_plan_exports.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Tests for service-owned command plan exports."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ecli.services.command_plan_service import CommandPlanService
from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
)


NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def export_plan() -> CommandPlan:
    return CommandPlan(
        plan_id="plan-20260515T120000Z-abcdef12",
        title="Export plan",
        category=PlanCategory.SYSTEM,
        risk=PlanRisk.HIGH,
        commands=[
            CommandStep(
                step_id="step-001",
                title="Quoted command",
                argv=["printf", "hello world"],
                display="printf 'hello world'",
                metadata={"token": "do-not-export", "safe": "value"},
            ),
            CommandStep(
                step_id="step-002",
                title="Privileged destructive command",
                argv=["sudo", "rm", "-rf", "/example"],
                display="sudo rm -rf /example",
                requires_privilege=True,
                destructive=True,
            ),
        ],
        created_at=NOW,
        created_by="tester",
        source=PlanSource.USER,
        confirmation_required=True,
        requires_privilege=True,
        metadata={"api_key": "secret", "owner": "qa"},
    )


def test_json_export_is_deterministic() -> None:
    service = CommandPlanService()
    plan = export_plan()

    assert service.export_json(plan) == service.export_json(plan)


def test_json_export_redacts_secrets() -> None:
    payload = json.loads(CommandPlanService().export_json(export_plan()))

    assert payload["metadata"]["api_key"] == "<redacted>"
    assert payload["commands"][0]["metadata"]["token"] == "<redacted>"
    assert "secret" not in json.dumps(payload)
    assert "do-not-export" not in json.dumps(payload)


def test_shell_export_contains_shebang_and_strict_mode() -> None:
    exported = CommandPlanService().export_shell(export_plan())

    assert exported.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")


def test_shell_export_uses_shlex_style_quoting() -> None:
    exported = CommandPlanService().export_shell(export_plan())

    assert "printf 'hello world'" in exported


def test_shell_export_includes_privileged_and_destructive_warnings() -> None:
    exported = CommandPlanService().export_shell(export_plan())

    assert "# WARNING: this step requires privilege" in exported
    assert "# WARNING: this step is destructive" in exported


def test_markdown_export_includes_summary_and_redacted_metadata() -> None:
    exported = CommandPlanService().export_markdown(export_plan())

    assert "# Command Plan: Export plan" in exported
    assert "- Plan ID: `plan-20260515T120000Z-abcdef12`" in exported
    assert "- Category: `SYSTEM`" in exported
    assert "- Risk: `HIGH`" in exported
    assert "<redacted>" in exported
    assert "secret" not in exported
    assert "do-not-export" not in exported
