# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/policy/engine.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Mockable policy engine interface and typed policy context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from ecli.services.models.plan import CommandPlan, PolicyDecision


@dataclass(frozen=True)
class PolicyContext:
    """Policy evaluation context supplied by future service wiring."""

    actor: str = "user"
    environment: str = "local"
    human_reviewed: bool = False
    privileged_route_available: bool = False
    override_approved: bool = False
    override_reason: str | None = None
    forbidden_resource_patterns: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze mutable context containers for deterministic evaluation."""
        object.__setattr__(
            self,
            "forbidden_resource_patterns",
            tuple(self.forbidden_resource_patterns),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class PolicyRuleResult:
    """Result of evaluating one deterministic policy rule."""

    rule_id: str
    matched: bool
    allowed: bool
    reason: str = ""
    override_allowed: bool = False


class PolicyEngine(ABC):
    """Abstract async policy engine interface."""

    @abstractmethod
    async def evaluate(
        self,
        plan: CommandPlan,
        context: PolicyContext,
    ) -> PolicyDecision:
        """Evaluate a plan against a policy context."""

    @abstractmethod
    def get_registered_rules(self) -> tuple[str, ...]:
        """Return registered policy rule IDs in deterministic evaluation order."""
