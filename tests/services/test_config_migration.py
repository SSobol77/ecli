# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/services/test_config_migration.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for deterministic configuration migration helpers."""

from __future__ import annotations

from pathlib import Path

from ecli.services.config_service import ConfigService
from ecli.services.migrations.config_migrations import (
    calculate_config_backup_path,
    detect_config_schema_version,
    migrate_to_current,
    migrate_v1_to_v2,
)


def test_existing_legacy_ai_provider_and_key_migrates_to_v2(tmp_path: Path) -> None:
    legacy_config = tmp_path / "legacy.toml"
    legacy_config.write_text(
        """
[ai]
provider = "openai"
key = "secret-value"
""",
        encoding="utf-8",
    )

    result = ConfigService.load(user_config_path=legacy_config, env={})

    assert result.config.schema_version == 2
    assert result.config.ai.default_provider == "openai"
    assert result.config.ai.providers["openai"].api_key == "secret-value"
    assert any(
        diagnostic.code == "config.migration.v1_to_v2"
        for diagnostic in result.diagnostics
    )


def test_migration_preserves_unknown_safe_fields() -> None:
    raw = {
        "ai": {"provider": "gemini", "key": "secret-value"},
        "custom_extension": {"enabled": True, "threshold": 7},
    }

    migrated, diagnostics = migrate_to_current(raw)

    assert migrated["schema"]["version"] == 2
    assert migrated["custom_extension"] == {"enabled": True, "threshold": 7}
    assert diagnostics


def test_detect_config_schema_version_from_explicit_schema() -> None:
    assert detect_config_schema_version({"schema": {"version": 2}}) == 2


def test_detect_config_schema_version_from_legacy_ai_shape() -> None:
    assert detect_config_schema_version({"ai": {"provider": "openai"}}) == 1


def test_migrate_v1_to_v2_preserves_legacy_keys_for_observability() -> None:
    migrated = migrate_v1_to_v2({"ai": {"provider": "openai", "key": "secret"}})

    assert migrated["ai"]["provider"] == "openai"
    assert migrated["ai"]["key"] == "secret"
    assert migrated["ai"]["default_provider"] == "openai"
    assert migrated["ai"]["providers"]["openai"]["api_key"] == "secret"
    assert migrated["schema"]["version"] == 2


def test_calculate_config_backup_path_is_deterministic(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    assert calculate_config_backup_path(config_path) == tmp_path / "config.toml.v2.bak"
