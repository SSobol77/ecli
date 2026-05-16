# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/privileged_action_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Refusal-only PrivilegedActionService skeleton for Phase 1B."""

from __future__ import annotations

import shutil
from typing import Any, Protocol

from ecli.services.models.plan import CommandPlan, PlanStatus, PolicyDecision
from ecli.services.models.privileged import (
    ExecutionRequest,
    ExecutionResult,
    PrivilegeBackend,
)


PRIVILEGE_BACKEND_NAMES: tuple[str, ...] = ("sudo", "doas", "pkexec")
REDACTION_TEXT = "***REDACTED***"
SENSITIVE_KEY_TOKENS: tuple[str, ...] = (
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "secret",
    "private_key",
    "credential",
    "authorization",
    "bearer",
    "x-api-key",
    "access_key",
    "secret_key",
    "session_key",
)


class AuditSink(Protocol):
    """Minimal injectable audit sink protocol."""

    def log_execution_result(
        self,
        plan: CommandPlan,
        success: bool,
        actor: str = "service",
        details: dict[str, Any] | None = None,
    ) -> object:
        """Record an execution/refusal result."""


class PrivilegedActionService:
    """Refusal-only privileged action service.

    This skeleton never executes commands. It validates that a plan could enter
    the future privileged execution path and returns structured refusal/dry-run
    results.
    """

    def __init__(self, audit_sink: AuditSink | None = None) -> None:
        """Initialize with optional injected audit sink and no global state."""
        self._audit_sink = audit_sink

    def detect_backends(self) -> tuple[PrivilegeBackend, ...]:
        """Detect configured privilege backends using read-only lookup only."""
        backends: list[PrivilegeBackend] = []
        for name in PRIVILEGE_BACKEND_NAMES:
            path = shutil.which(name)
            backends.append(
                PrivilegeBackend(
                    name=name,
                    available=path is not None,
                    path=path,
                    reason=None if path is not None else f"{name} not found on PATH",
                )
            )
        return tuple(backends)

    def build_request(
        self,
        request_id: str,
        plan: CommandPlan,
        policy_decision: PolicyDecision | None,
        dry_run: bool = True,
        actor: str = "user",
    ) -> ExecutionRequest:
        """Build an execution request without executing or mutating host state."""
        return ExecutionRequest(
            request_id=request_id,
            plan=plan,
            dry_run=dry_run,
            actor=actor,
            policy_decision=policy_decision,
        )

    def evaluate(self, request: ExecutionRequest) -> ExecutionResult:
        """Return a fail-closed refusal or dry-run result for a plan request."""
        plan = request.plan
        selected_backend = (
            self._select_backend() if _plan_requires_privilege(plan) else None
        )

        if plan.status is not PlanStatus.CONFIRMED:
            return self._result(
                request,
                accepted=False,
                reason="Refused: command plan status must be CONFIRMED.",
                backend=selected_backend,
            )
        if request.policy_decision is None:
            return self._result(
                request,
                accepted=False,
                reason="Refused: missing policy decision.",
                backend=selected_backend,
            )
        if not request.policy_decision.allowed:
            return self._result(
                request,
                accepted=False,
                reason=f"Refused: policy denied plan ({request.policy_decision.reason}).",
                backend=selected_backend,
            )
        if not request.dry_run:
            return self._result(
                request,
                accepted=False,
                reason="Refused: non-dry-run execution is unsupported in Phase 1B.",
                backend=selected_backend,
            )
        if _plan_requires_privilege(plan) and selected_backend is None:
            return self._result(
                request,
                accepted=False,
                reason="Refused: privileged plan has no available privilege backend.",
                backend=None,
            )

        return self._result(
            request,
            accepted=True,
            reason="Accepted for dry run only; no commands were executed.",
            backend=selected_backend,
        )

    def _result(
        self,
        request: ExecutionRequest,
        accepted: bool,
        reason: str,
        backend: str | None,
    ) -> ExecutionResult:
        result = ExecutionResult(
            request_id=request.request_id,
            plan_id=request.plan.plan_id,
            accepted=accepted,
            executed=False,
            dry_run=request.dry_run,
            exit_code=None,
            reason=reason,
            backend=backend,
            command_count=len(request.plan.commands),
            redacted_summary=_build_redacted_summary(request),
        )
        self._audit_result(request, result)
        return result

    def _select_backend(self) -> str | None:
        for backend in self.detect_backends():
            if backend.available:
                return backend.name
        return None

    def _audit_result(self, request: ExecutionRequest, result: ExecutionResult) -> None:
        if self._audit_sink is None:
            return
        self._audit_sink.log_execution_result(
            request.plan,
            success=result.accepted,
            actor=request.actor,
            details=result.as_dict(),
        )


def _plan_requires_privilege(plan: CommandPlan) -> bool:
    return plan.requires_privilege or any(
        step.requires_privilege for step in plan.commands
    )


def _build_redacted_summary(request: ExecutionRequest) -> dict[str, object]:
    return {
        "plan_id": request.plan.plan_id,
        "actor": request.actor,
        "status": request.plan.status.value,
        "risk": request.plan.risk.value,
        "category": request.plan.category.value,
        "requires_privilege": _plan_requires_privilege(request.plan),
        "command_count": len(request.plan.commands),
        "plan_metadata": _redact_sensitive(request.plan.metadata),
        "command_metadata": [
            _redact_sensitive(command.metadata) for command in request.plan.commands
        ],
        "policy": None
        if request.policy_decision is None
        else _redact_sensitive(request.policy_decision.as_dict()),
    }


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): REDACTION_TEXT
            if _is_sensitive_key(str(key))
            else _redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_sensitive(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in SENSITIVE_KEY_TOKENS)
