# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/models/doctor.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Typed models for the read-only SystemDoctor skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


class DoctorSeverity(StrEnum):
    """Severity level for SystemDoctor findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class DoctorFinding:
    """One structured read-only SystemDoctor finding."""

    finding_id: str
    title: str
    severity: DoctorSeverity
    category: str
    description: str
    affected_resources: tuple[str, ...] = ()
    remediation_available: bool = False
    remediation_plan_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize mutable inputs into stable immutable containers."""
        object.__setattr__(
            self,
            "affected_resources",
            tuple(str(resource) for resource in self.affected_resources),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable doctor finding dictionary."""
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "severity": self.severity.value,
            "category": self.category,
            "description": self.description,
            "affected_resources": list(self.affected_resources),
            "remediation_available": self.remediation_available,
            "remediation_plan_id": self.remediation_plan_id,
            "metadata": _json_safe_copy(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DoctorContext:
    """Read-only SystemDoctor execution context."""

    user: str = "user"
    project_root: Path | str | None = None
    categories: tuple[str, ...] = ()
    verbosity: int = 0
    dry_run: bool = True
    environment: str = "local"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize mutable inputs into stable immutable containers."""
        object.__setattr__(
            self,
            "categories",
            tuple(str(category) for category in self.categories),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def _json_safe_copy(value: Any) -> Any:
    primitive_types = str | int | float | bool
    if isinstance(value, dict | Mapping):
        return {str(key): _json_safe_copy(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe_copy(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Path) or not isinstance(value, primitive_types | None):
        return str(value)
    return value
