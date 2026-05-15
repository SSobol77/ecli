# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/models/plan.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Typed command plan models for Phase 1A services."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class PlanRisk(StrEnum):
    """Risk classification for command plans."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PlanStatus(StrEnum):
    """Lifecycle status for command plans."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    POLICY_CHECKED = "POLICY_CHECKED"
    CONFIRMED = "CONFIRMED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PlanCategory(StrEnum):
    """Operational category for command plans."""

    GENERAL = "GENERAL"
    SYSTEM = "SYSTEM"
    FILE = "FILE"
    VM = "VM"
    KUBERNETES = "KUBERNETES"
    TERRAFORM = "TERRAFORM"
    ANSIBLE = "ANSIBLE"
    CI = "CI"
    DOCTOR = "DOCTOR"


class PlanSource(StrEnum):
    """Source that produced a command plan."""

    USER = "USER"
    DOCTOR = "DOCTOR"
    AI_ASSISTANT = "AI_ASSISTANT"
    SERVICE = "SERVICE"


@dataclass(frozen=True)
class CommandStep:
    """One argv-first command step in a command plan."""

    step_id: str
    title: str
    argv: list[str]
    display: str
    requires_privilege: bool = False
    destructive: bool = False
    expected_exit_codes: list[int] = field(default_factory=lambda: [0])
    timeout_seconds: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable command step dictionary."""
        return {
            "step_id": self.step_id,
            "title": self.title,
            "argv": list(self.argv),
            "display": self.display,
            "requires_privilege": self.requires_privilege,
            "destructive": self.destructive,
            "expected_exit_codes": list(self.expected_exit_codes),
            "timeout_seconds": self.timeout_seconds,
            "metadata": _json_safe_copy(self.metadata),
        }


@dataclass(frozen=True)
class PolicyDecision:
    """Policy decision attached to future command plan evaluation."""

    allowed: bool
    reason: str
    policy_id: str | None = None
    violated_rules: list[str] = field(default_factory=list)
    override_allowed: bool = False
    confirmation_required: bool = False
    route_via: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable policy decision dictionary."""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "violated_rules": list(self.violated_rules),
            "override_allowed": self.override_allowed,
            "confirmation_required": self.confirmation_required,
            "route_via": self.route_via,
            "metadata": _json_safe_copy(self.metadata),
        }


@dataclass(frozen=True, kw_only=True)
class CommandPlan:
    """Pure typed command plan data model."""

    plan_id: str
    title: str
    category: PlanCategory
    risk: PlanRisk
    commands: list[CommandStep]
    created_at: datetime
    created_by: str
    schema_version: int = 1
    description: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    rollback: list[CommandStep] = field(default_factory=list)
    confirmation_required: bool = False
    requires_privilege: bool = False
    source: PlanSource = PlanSource.USER
    affected_resources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable command plan dictionary."""
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "risk": self.risk.value,
            "status": self.status.value,
            "commands": [command.as_dict() for command in self.commands],
            "rollback": [command.as_dict() for command in self.rollback],
            "confirmation_required": self.confirmation_required,
            "requires_privilege": self.requires_privilege,
            "created_at": _format_datetime(self.created_at),
            "created_by": self.created_by,
            "source": self.source.value,
            "affected_resources": list(self.affected_resources),
            "metadata": _json_safe_copy(self.metadata),
        }


def new_plan_id(
    now: datetime | None = None,
    random_suffix: str | None = None,
) -> str:
    """Create a command plan identifier with deterministic test injection."""
    timestamp = _format_plan_id_time(datetime.now(UTC) if now is None else now)
    suffix = secrets.token_hex(4) if random_suffix is None else random_suffix.lower()
    if not re.fullmatch(r"[0-9a-f]{8}", suffix):
        raise ValueError("random_suffix must contain exactly 8 hexadecimal characters")
    return f"plan-{timestamp}-{suffix}"


def needs_confirmation(plan: CommandPlan) -> bool:
    """Return true when a plan requires explicit user confirmation."""
    if plan.confirmation_required:
        return True
    if plan.risk in {PlanRisk.HIGH, PlanRisk.CRITICAL}:
        return True
    if plan.requires_privilege:
        return True
    if any(command.requires_privilege for command in plan.commands):
        return True
    if any(command.destructive for command in plan.commands):
        return True
    return plan.source is PlanSource.AI_ASSISTANT and plan.risk in {
        PlanRisk.MEDIUM,
        PlanRisk.HIGH,
        PlanRisk.CRITICAL,
    }


def _format_plan_id_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC).replace(microsecond=0)
    return value.strftime("%Y%m%dT%H%M%SZ")


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_safe_copy(value: Any) -> Any:
    primitive_types = str | int | float | bool
    if isinstance(value, dict):
        return {str(key): _json_safe_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_copy(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_copy(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return _format_datetime(value)
    return value if isinstance(value, primitive_types) or value is None else str(value)
