# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/models/audit.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Typed audit log models for the Phase 1B AuditLogService."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AuditActor(StrEnum):
    """Actor categories recorded in audit events."""

    USER = "user"
    SERVICE = "service"
    AI_ASSISTANT = "ai_assistant"
    DOCTOR = "doctor"
    SYSTEM = "system"


class AuditEventType(StrEnum):
    """Audit event types owned by Phase 1 service foundations."""

    PLAN_CREATED = "plan.created"
    PLAN_VALIDATED = "plan.validated"
    PLAN_POLICY_CHECKED = "plan.policy_checked"
    PLAN_VIEWED = "plan.viewed"
    PLAN_CONFIRMED = "plan.confirmed"
    PLAN_REJECTED = "plan.rejected"
    PLAN_CANCELLED = "plan.cancelled"
    PLAN_EXECUTION_STARTED = "plan.execution_started"
    PLAN_STEP_STARTED = "plan.step_started"
    PLAN_STEP_COMPLETED = "plan.step_completed"
    PLAN_STEP_FAILED = "plan.step_failed"
    PLAN_EXECUTION_COMPLETED = "plan.execution_completed"
    PLAN_EXECUTION_FAILED = "plan.execution_failed"
    PLAN_ROLLBACK_AVAILABLE = "plan.rollback_available"
    PLAN_ROLLBACK_STARTED = "plan.rollback_started"
    PLAN_ROLLBACK_COMPLETED = "plan.rollback_completed"
    PLAN_ROLLBACK_FAILED = "plan.rollback_failed"
    AUDIT_REDACTION_FAILED = "audit.redaction_failed"
    AUDIT_WRITE_FAILED = "audit.write_failed"
    POLICY_EVALUATED = "policy.evaluated"
    POLICY_DENIED = "policy.denied"
    SERVICE_REFUSED = "service.refused"


@dataclass(frozen=True)
class AuditRecord:
    """One append-only JSONL audit event record."""

    schema_version: int
    event_id: str
    timestamp: datetime | str
    event_type: str
    actor: str
    details: dict[str, Any]
    metadata: dict[str, Any]
    plan_id: str | None = None
    category: str | None = None
    risk: str | None = None
    source: str | None = None
    redacted_fields: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible audit record dictionary."""
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": _serialize_timestamp(self.timestamp),
            "event_type": self.event_type,
            "actor": self.actor,
            "details": _json_safe_copy(self.details),
            "metadata": _json_safe_copy(self.metadata),
            "plan_id": self.plan_id,
            "category": self.category,
            "risk": self.risk,
            "source": self.source,
            "redacted_fields": list(self.redacted_fields),
        }


def _serialize_timestamp(value: datetime | str) -> str:
    if isinstance(value, str):
        return value
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
        return _serialize_timestamp(value)
    return value if isinstance(value, primitive_types) or value is None else str(value)
