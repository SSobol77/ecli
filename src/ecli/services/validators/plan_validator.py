# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/validators/plan_validator.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Validation helpers for command plan models."""

from __future__ import annotations

from typing import Any

from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanRisk,
    needs_confirmation,
)


SENSITIVE_METADATA_KEYS: frozenset[str] = frozenset(
    {
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
    }
)

SHELL_OPERATOR_TOKENS: frozenset[str] = frozenset(
    {";", "&&", "||", "|", ">", ">>", "<", "$()", "`"}
)


def validate_command_step(step: CommandStep) -> list[str]:
    """Validate one command step and return human-readable diagnostics."""
    diagnostics: list[str] = []

    if not step.step_id.strip():
        diagnostics.append("step_id must be non-empty and stable")
    if not step.display.strip():
        diagnostics.append("display must be non-empty")
    if step.timeout_seconds is not None and step.timeout_seconds <= 0:
        diagnostics.append("timeout_seconds must be None or > 0")
    argv_valid, argv_diagnostics = _validate_argv(step.argv)
    diagnostics.extend(argv_diagnostics)
    if argv_valid:
        diagnostics.extend(_validate_shell_tokens(step.argv))
    diagnostics.extend(_validate_expected_exit_codes(step.expected_exit_codes))
    diagnostics.extend(_validate_metadata_keys(step.metadata, "metadata"))
    return diagnostics


def validate_command_plan(plan: CommandPlan) -> list[str]:
    """Validate a command plan and return human-readable diagnostics."""
    diagnostics: list[str] = []

    if not plan.commands:
        diagnostics.append("plan.commands must be non-empty")
    for index, command in enumerate(plan.commands):
        for diagnostic in validate_command_step(command):
            diagnostics.append(f"commands[{index}]: {diagnostic}")
    for index, command in enumerate(plan.rollback):
        for diagnostic in validate_command_step(command):
            diagnostics.append(f"rollback[{index}]: {diagnostic}")

    has_privileged_command = any(
        command.requires_privilege for command in plan.commands
    )
    has_destructive_command = any(command.destructive for command in plan.commands)

    if (
        has_privileged_command or has_destructive_command
    ) and plan.risk is PlanRisk.LOW:
        diagnostics.append("destructive or privileged commands cannot remain LOW risk")
    if plan.risk is PlanRisk.CRITICAL and not plan.confirmation_required:
        diagnostics.append("CRITICAL plans must require confirmation")
    if has_privileged_command and not plan.requires_privilege:
        diagnostics.append(
            "plan.requires_privilege must be true if any step requires privilege"
        )
    if needs_confirmation(plan) and not plan.confirmation_required:
        diagnostics.append(
            "plan.confirmation_required should be true when confirmation is needed"
        )
    diagnostics.extend(_validate_metadata_keys(plan.metadata, "metadata"))
    return diagnostics


def _validate_shell_tokens(argv: list[str]) -> list[str]:
    diagnostics: list[str] = []
    for token in argv:
        if token in SHELL_OPERATOR_TOKENS:
            diagnostics.append(
                f"argv contains standalone shell-like operator token: {token}"
            )
        elif token.startswith("`") and token.endswith("`"):
            diagnostics.append(
                "argv contains standalone backtick command substitution token"
            )
        elif token.startswith("$(") and token.endswith(")"):
            diagnostics.append("argv contains standalone command substitution token")
    return diagnostics


def _validate_argv(argv: list[str]) -> tuple[bool, list[str]]:
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return False, ["argv must be list[str]"]
    if not argv:
        return False, ["argv must be non-empty"]
    if not argv[0].strip():
        return False, ["argv[0] must not be empty"]
    return True, []


def _validate_expected_exit_codes(expected_exit_codes: list[int]) -> list[str]:
    diagnostics: list[str] = []
    if not expected_exit_codes:
        return ["expected_exit_codes must not be empty"]
    for exit_code in expected_exit_codes:
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            diagnostics.append("expected_exit_codes values must be integers")
            continue
        if exit_code < 0 or exit_code > 255:
            diagnostics.append("expected_exit_codes values must be in 0..255")
    return diagnostics


def _validate_metadata_keys(metadata: dict[str, Any], prefix: str) -> list[str]:
    diagnostics: list[str] = []
    for key, value in metadata.items():
        key_text = str(key)
        path = f"{prefix}.{key_text}"
        if _is_sensitive_key(key_text):
            diagnostics.append(f"{path} contains secret-like metadata key")
        if isinstance(value, dict):
            diagnostics.extend(_validate_metadata_keys(value, path))
    return diagnostics


def _is_sensitive_key(key: str) -> bool:
    return key.lower() in SENSITIVE_METADATA_KEYS
