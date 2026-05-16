# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/audit_log_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Append-only JSONL audit logging with mandatory redaction."""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ecli.services.models.audit import AuditActor, AuditEventType, AuditRecord
from ecli.services.models.plan import CommandPlan, PolicyDecision


AUDIT_SCHEMA_VERSION = 1
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

_KEY_VALUE_SECRET_RE = re.compile(
    r"(?P<key>password|passwd|token|api_key|apikey|secret|private_key|credential|"
    r"authorization|bearer|x-api-key|access_key|secret_key|session_key)"
    r"(?P<sep>\s*[=:]\s*)"
    r"(?P<value>[^\s,;&]+)",
    re.IGNORECASE,
)


class AuditLogError(RuntimeError):
    """Base error for audit log service failures."""


class AuditRedactionError(AuditLogError):
    """Raised when audit redaction fails closed before writing."""


class AuditWriteError(AuditLogError):
    """Raised when an audit record cannot be written."""


class AuditLogService:
    """Append-only JSONL audit log service."""

    def __init__(self, audit_dir: Path | None = None) -> None:
        """Initialize without creating audit directories or files."""
        self._logs_root = _repo_logs_root()
        self._audit_dir = self._resolve_audit_dir(audit_dir)

    @property
    def audit_dir(self) -> Path:
        """Return the resolved audit directory."""
        return self._audit_dir

    def redact_sensitive(self, value: Any) -> tuple[Any, list[str]]:
        """Redact sensitive fields and return deterministic redacted paths."""
        return _redact_value(value, "")

    def append(self, record: AuditRecord) -> AuditRecord:
        """Redact and append one audit record to the daily JSONL file."""
        try:
            redacted_payload, redacted_paths = self.redact_sensitive(
                {"details": record.details, "metadata": record.metadata}
            )
            redacted_fields = _deduplicate_paths(
                [*record.redacted_fields, *redacted_paths]
            )
            redacted_record = replace(
                record,
                details=redacted_payload["details"],
                metadata=redacted_payload["metadata"],
                redacted_fields=redacted_fields,
            )
            line = _record_to_json_line(redacted_record)
        except Exception as exc:
            raise AuditRedactionError(
                "Audit redaction failed; record was not written"
            ) from exc

        audit_file = self.audit_file_for(redacted_record.timestamp)
        self._assert_path_under_logs(audit_file)
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            _chmod_if_supported(self._audit_dir, 0o700)
            _append_jsonl_line(audit_file, line)
        except OSError as exc:
            raise AuditWriteError(f"Audit write failed for {audit_file}") from exc
        return redacted_record

    def log_plan_created(
        self,
        plan: CommandPlan,
        actor: str = AuditActor.USER.value,
    ) -> AuditRecord:
        """Record that a command plan was created."""
        record = self.build_record(
            event_type=AuditEventType.PLAN_CREATED,
            actor=actor,
            plan=plan,
            details={
                "title": plan.title,
                "command_count": len(plan.commands),
                "rollback_count": len(plan.rollback),
                "affected_resources": list(plan.affected_resources),
            },
        )
        return self.append(record)

    def log_policy_evaluated(
        self,
        plan: CommandPlan,
        decision: PolicyDecision,
        actor: str = AuditActor.SERVICE.value,
    ) -> AuditRecord:
        """Record a policy evaluation decision for a command plan."""
        event_type = (
            AuditEventType.POLICY_EVALUATED
            if decision.allowed
            else AuditEventType.POLICY_DENIED
        )
        record = self.build_record(
            event_type=event_type,
            actor=actor,
            plan=plan,
            details={"decision": decision.as_dict()},
            metadata={
                "policy_id": decision.policy_id,
                "violated_rules": list(decision.violated_rules),
                "override_allowed": decision.override_allowed,
            },
        )
        return self.append(record)

    def log_execution_result(
        self,
        plan: CommandPlan,
        success: bool,
        actor: str = AuditActor.SERVICE.value,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Record a future execution result without performing execution."""
        record = self.build_record(
            event_type=(
                AuditEventType.PLAN_EXECUTION_COMPLETED
                if success
                else AuditEventType.PLAN_EXECUTION_FAILED
            ),
            actor=actor,
            plan=plan,
            details={"success": success, **({} if details is None else details)},
        )
        return self.append(record)

    def build_record(  # noqa: PLR0913
        self,
        event_type: AuditEventType | str,
        actor: AuditActor | str,
        details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        plan: CommandPlan | None = None,
        event_id: str | None = None,
        timestamp: datetime | str | None = None,
    ) -> AuditRecord:
        """Build an audit record without writing it."""
        event_timestamp = _utc_now() if timestamp is None else timestamp
        return AuditRecord(
            schema_version=AUDIT_SCHEMA_VERSION,
            event_id=event_id or _new_event_id(event_timestamp),
            timestamp=event_timestamp,
            event_type=_enum_or_str(event_type),
            actor=_enum_or_str(actor),
            details={} if details is None else dict(details),
            metadata={} if metadata is None else dict(metadata),
            plan_id=None if plan is None else plan.plan_id,
            category=None if plan is None else plan.category.value,
            risk=None if plan is None else plan.risk.value,
            source=None if plan is None else plan.source.value,
        )

    def audit_file_for(self, timestamp: datetime | str | date) -> Path:
        """Return the deterministic daily audit JSONL path for a timestamp."""
        return self._audit_dir / f"audit-{_date_string(timestamp)}.jsonl"

    def read_records_for_day(self, day: date) -> list[dict[str, Any]]:
        """Read audit records for tests and diagnostics."""
        audit_file = self.audit_file_for(day)
        if not audit_file.exists():
            return []
        return [
            json.loads(line)
            for line in audit_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _resolve_audit_dir(self, audit_dir: Path | None) -> Path:
        if audit_dir is None:
            resolved = (self._logs_root / "audit").resolve(strict=False)
        else:
            resolved = Path(audit_dir).resolve(strict=False)
        if not _is_relative_to(resolved, self._logs_root):
            raise ValueError("Audit directory must be under repository-level logs/")
        return resolved

    def _assert_path_under_logs(self, path: Path) -> None:
        if not _is_relative_to(path.resolve(strict=False), self._logs_root):
            raise AuditWriteError("Audit path escaped repository-level logs/")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _repo_logs_root() -> Path:
    return (_repo_root() / "logs").resolve(strict=False)


def _redact_value(value: Any, path: str) -> tuple[Any, list[str]]:
    if isinstance(value, dict):
        return _redact_dict(value, path)
    if isinstance(value, list):
        return _redact_sequence(value, path)
    if isinstance(value, tuple):
        return _redact_sequence(list(value), path)
    if isinstance(value, str):
        return _redact_string(value, path)
    return value, []


def _redact_dict(value: dict[Any, Any], path: str) -> tuple[dict[str, Any], list[str]]:
    redacted: dict[str, Any] = {}
    redacted_paths: list[str] = []
    for key, item in value.items():
        key_text = str(key)
        child_path = _join_path(path, key_text)
        if _is_sensitive_key(key_text):
            redacted[key_text] = REDACTION_TEXT
            redacted_paths.append(child_path)
            continue
        redacted_item, child_paths = _redact_value(item, child_path)
        redacted[key_text] = redacted_item
        redacted_paths.extend(child_paths)
    return redacted, redacted_paths


def _redact_sequence(value: list[Any], path: str) -> tuple[list[Any], list[str]]:
    redacted: list[Any] = []
    redacted_paths: list[str] = []
    for index, item in enumerate(value):
        child_path = f"{path}[{index}]" if path else f"[{index}]"
        redacted_item, child_paths = _redact_value(item, child_path)
        redacted.append(redacted_item)
        redacted_paths.extend(child_paths)
    return redacted, redacted_paths


def _redact_string(value: str, path: str) -> tuple[str, list[str]]:
    if not _KEY_VALUE_SECRET_RE.search(value):
        return value, []
    return _KEY_VALUE_SECRET_RE.sub(
        lambda match: f"{match.group('key')}{match.group('sep')}{REDACTION_TEXT}",
        value,
    ), [path]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in SENSITIVE_KEY_TOKENS)


def _join_path(parent: str, child: str) -> str:
    return child if not parent else f"{parent}.{child}"


def _deduplicate_paths(paths: list[str]) -> list[str]:
    deduplicated: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path and path not in seen:
            deduplicated.append(path)
            seen.add(path)
    return deduplicated


def _record_to_json_line(record: AuditRecord) -> str:
    return json.dumps(
        record.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _append_jsonl_line(path: Path, line: str) -> None:
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
    finally:
        _chmod_if_supported(path, 0o600)


def _chmod_if_supported(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def _new_event_id(timestamp: datetime | str) -> str:
    return f"audit-{_timestamp_for_id(timestamp)}-{secrets.token_hex(4)}"


def _timestamp_for_id(timestamp: datetime | str) -> str:
    if isinstance(timestamp, str):
        return (
            timestamp.replace("-", "")
            .replace(":", "")
            .replace("+", "")
            .replace("Z", "Z")
        )
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")


def _date_string(timestamp: datetime | str | date) -> str:
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC).date().isoformat()
    if isinstance(timestamp, date):
        return timestamp.isoformat()
    return timestamp[:10]


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _enum_or_str(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True
