# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/migrations/config_migrations.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Deterministic configuration schema migration helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from ecli.services.models.config import (
    CURRENT_CONFIG_SCHEMA_VERSION,
    ConfigDiagnostic,
    ConfigDiagnosticLevel,
)


def detect_config_schema_version(raw: Mapping[str, Any]) -> int:
    """Detect the raw configuration schema version."""
    schema = raw.get("schema")
    if isinstance(schema, Mapping):
        version = schema.get("version")
        if isinstance(version, int) and not isinstance(version, bool) and version > 0:
            return version

    ai = raw.get("ai")
    if isinstance(ai, Mapping) and ("provider" in ai or "key" in ai):
        return 1

    return CURRENT_CONFIG_SCHEMA_VERSION


def migrate_v1_to_v2(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate legacy v1 AI keys into the v2 canonical AI provider layout."""
    migrated = deepcopy(dict(raw))
    ai = migrated.setdefault("ai", {})
    if not isinstance(ai, dict):
        migrated["ai"] = ai = {}

    provider = ai.get("provider")
    if isinstance(provider, str) and provider:
        ai.setdefault("default_provider", provider)

    api_key = ai.get("key")
    effective_provider = ai.get("default_provider")
    if (
        isinstance(api_key, str)
        and isinstance(effective_provider, str)
        and effective_provider
    ):
        providers = ai.setdefault("providers", {})
        if isinstance(providers, dict):
            provider_config = providers.setdefault(effective_provider, {})
            if isinstance(provider_config, dict):
                provider_config.setdefault("api_key", api_key)

    schema = migrated.setdefault("schema", {})
    if not isinstance(schema, dict):
        migrated["schema"] = schema = {}
    schema["version"] = CURRENT_CONFIG_SCHEMA_VERSION
    return migrated


def migrate_to_current(
    raw: Mapping[str, Any],
) -> tuple[dict[str, Any], list[ConfigDiagnostic]]:
    """Migrate a raw configuration mapping to the current schema version."""
    version = detect_config_schema_version(raw)
    diagnostics: list[ConfigDiagnostic] = []
    if version == CURRENT_CONFIG_SCHEMA_VERSION:
        migrated = deepcopy(dict(raw))
        schema = migrated.setdefault("schema", {})
        if isinstance(schema, dict):
            schema.setdefault("version", CURRENT_CONFIG_SCHEMA_VERSION)
        return migrated, diagnostics

    if version == 1:
        migrated = migrate_v1_to_v2(raw)
        ai = raw.get("ai")
        if isinstance(ai, Mapping) and "provider" in ai:
            diagnostics.append(
                ConfigDiagnostic(
                    level=ConfigDiagnosticLevel.WARNING,
                    path="ai.provider",
                    code="config.migration.v1_to_v2",
                    message="Migrated legacy ai.provider to ai.default_provider",
                )
            )
        if isinstance(ai, Mapping) and "key" in ai:
            diagnostics.append(
                ConfigDiagnostic(
                    level=ConfigDiagnosticLevel.WARNING,
                    path="ai.key",
                    code="config.migration.v1_to_v2",
                    message="Migrated legacy ai.key to ai.providers.<provider>.api_key when provider was known",
                )
            )
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.INFO,
                path="schema.version",
                code="config.migration.v1_to_v2",
                message="Updated configuration schema version to 2",
            )
        )
        return migrated, diagnostics

    migrated = deepcopy(dict(raw))
    diagnostics.append(
        ConfigDiagnostic(
            level=ConfigDiagnosticLevel.WARNING,
            path="schema.version",
            code="config.migration.unsupported_version",
            message=f"Unsupported config schema version {version}; loading with compatibility fallback",
        )
    )
    return migrated, diagnostics


def calculate_config_backup_path(
    config_path: Path,
    target_version: int = CURRENT_CONFIG_SCHEMA_VERSION,
) -> Path:
    """Return the deterministic backup path for an explicit future migration."""
    return config_path.with_name(f"{config_path.name}.v{target_version}.bak")
