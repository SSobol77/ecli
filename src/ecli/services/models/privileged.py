# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/models/privileged.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Typed models for the refusal-only PrivilegedActionService skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ecli.services.models.plan import CommandPlan, PolicyDecision


@dataclass(frozen=True)
class PrivilegeBackend:
    """Read-only privilege backend detection result."""

    name: str
    available: bool
    path: str | None
    reason: str | None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible privilege backend dictionary."""
        return {
            "name": self.name,
            "available": self.available,
            "path": self.path,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExecutionRequest:
    """Request to evaluate privileged action handling for a command plan."""

    request_id: str
    plan: CommandPlan
    dry_run: bool = True
    actor: str = "user"
    policy_decision: PolicyDecision | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Refusal-only execution result for Phase 1B."""

    request_id: str
    plan_id: str
    accepted: bool
    executed: bool
    dry_run: bool
    exit_code: int | None
    reason: str
    backend: str | None
    command_count: int
    redacted_summary: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible execution result dictionary."""
        return {
            "request_id": self.request_id,
            "plan_id": self.plan_id,
            "accepted": self.accepted,
            "executed": self.executed,
            "dry_run": self.dry_run,
            "exit_code": self.exit_code,
            "reason": self.reason,
            "backend": self.backend,
            "command_count": self.command_count,
            "redacted_summary": dict(self.redacted_summary),
        }
