# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/command_plan_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Service-owned export behavior for command plans."""

from __future__ import annotations

import json
import shlex
from typing import Any

from ecli.services.models.plan import CommandPlan, CommandStep
from ecli.services.validators.plan_validator import SENSITIVE_METADATA_KEYS


REDACTION_TEXT = "<redacted>"


class CommandPlanService:
    """Command plan service utilities for Phase 1A."""

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
