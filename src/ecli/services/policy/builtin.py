# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/policy/builtin.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Built-in deterministic policy engine rules."""

from __future__ import annotations

from collections.abc import Callable

from ecli.services.models.plan import CommandPlan, PlanRisk, PlanSource, PolicyDecision
from ecli.services.policy.engine import PolicyContext, PolicyEngine, PolicyRuleResult


RuleCallable = Callable[[CommandPlan, PolicyContext], PolicyRuleResult]


class BuiltInPolicyEngine(PolicyEngine):
    """Deterministic built-in policy engine for Phase 1A."""

    def __init__(self) -> None:
        """Initialize built-in rules in stable evaluation order."""
        self._rules: tuple[tuple[str, RuleCallable], ...] = (
            ("BUILTIN-001", _block_ai_high_risk_no_review),
            ("BUILTIN-002", _require_confirmation_for_critical),
            ("BUILTIN-003", _require_privileged_path),
            ("BUILTIN-004", _block_destructive_production),
            ("BUILTIN-005", _block_forbidden_resources),
            ("BUILTIN-006", _require_audit_on_override),
        )

    async def evaluate(
        self,
        plan: CommandPlan,
        context: PolicyContext,
    ) -> PolicyDecision:
        """Evaluate a command plan against deterministic built-in rules."""
        violated_rules: list[str] = []
        first_deny: PolicyRuleResult | None = None

        for rule_id, rule in self._rules:
            result = rule(plan, context)
            if result.rule_id != rule_id:
                raise RuntimeError(
                    f"Policy rule returned unexpected ID: {result.rule_id}"
                )
            if result.matched and not result.allowed:
                violated_rules.append(result.rule_id)
                if first_deny is None:
                    first_deny = result

        if first_deny is not None:
            return PolicyDecision(
                allowed=False,
                reason=first_deny.reason,
                policy_id=first_deny.rule_id,
                violated_rules=violated_rules,
                override_allowed=first_deny.override_allowed,
            )

        return PolicyDecision(
            allowed=True,
            reason="Policy check passed",
            policy_id="builtin:allow",
            violated_rules=[],
            override_allowed=False,
        )

    def get_registered_rules(self) -> tuple[str, ...]:
        """Return built-in policy rule IDs in deterministic evaluation order."""
        return tuple(rule_id for rule_id, _rule in self._rules)


def _block_ai_high_risk_no_review(
    plan: CommandPlan,
    context: PolicyContext,
) -> PolicyRuleResult:
    matched = (
        plan.source is PlanSource.AI_ASSISTANT
        and plan.risk in {PlanRisk.HIGH, PlanRisk.CRITICAL}
        and not context.human_reviewed
    )
    return _deny_if_matched(
        rule_id="BUILTIN-001",
        matched=matched,
        reason="AI-generated high-risk plans require explicit human review.",
        override_allowed=False,
    )


def _require_confirmation_for_critical(
    plan: CommandPlan,
    context: PolicyContext,
) -> PolicyRuleResult:
    del context
    matched = plan.risk is PlanRisk.CRITICAL and not plan.confirmation_required
    return _deny_if_matched(
        rule_id="BUILTIN-002",
        matched=matched,
        reason="Critical operations require explicit confirmation.",
        override_allowed=False,
    )


def _require_privileged_path(
    plan: CommandPlan,
    context: PolicyContext,
) -> PolicyRuleResult:
    matched = (
        any(step.requires_privilege for step in plan.commands)
        and not context.privileged_route_available
    )
    return _deny_if_matched(
        rule_id="BUILTIN-003",
        matched=matched,
        reason="Privileged steps must route through PrivilegedActionService.",
        override_allowed=False,
    )


def _block_destructive_production(
    plan: CommandPlan,
    context: PolicyContext,
) -> PolicyRuleResult:
    matched = (
        context.environment == "production"
        and any(step.destructive for step in plan.commands)
        and not context.override_approved
    )
    return _deny_if_matched(
        rule_id="BUILTIN-004",
        matched=matched,
        reason="Destructive production operations require explicit policy override.",
        override_allowed=True,
    )


def _block_forbidden_resources(
    plan: CommandPlan,
    context: PolicyContext,
) -> PolicyRuleResult:
    matched = any(
        _resource_matches_pattern(resource, pattern)
        for resource in plan.affected_resources
        for pattern in context.forbidden_resource_patterns
    )
    return _deny_if_matched(
        rule_id="BUILTIN-005",
        matched=matched,
        reason="Plan affects forbidden resource.",
        override_allowed=False,
    )


def _require_audit_on_override(
    plan: CommandPlan,
    context: PolicyContext,
) -> PolicyRuleResult:
    del plan
    matched = context.override_approved and not _has_text(context.override_reason)
    return _deny_if_matched(
        rule_id="BUILTIN-006",
        matched=matched,
        reason="Policy override requires actor and reason for auditability.",
        override_allowed=False,
    )


def _deny_if_matched(
    rule_id: str,
    matched: bool,
    reason: str,
    override_allowed: bool,
) -> PolicyRuleResult:
    return PolicyRuleResult(
        rule_id=rule_id,
        matched=matched,
        allowed=not matched,
        reason=reason if matched else "",
        override_allowed=override_allowed if matched else False,
    )


def _resource_matches_pattern(resource: str, pattern: str) -> bool:
    if pattern.endswith("/*"):
        return resource.startswith(pattern[:-1])
    return resource == pattern


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())
