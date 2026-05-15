# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/services/test_config_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Tests for the Phase 1 ConfigService."""

from __future__ import annotations

import json
from pathlib import Path

from ecli.services.config_service import ConfigService
from ecli.services.models.config import ConfigDiagnosticLevel


def write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_default_config_loads_successfully() -> None:
    result = ConfigService.load(env={})

    assert not result.has_errors
    assert result.config.editor.tab_size == 4
    assert result.config.editor.encoding == "utf-8"
    assert result.config.ui.theme == "dark"
    assert result.config.ai.default_provider == "gemini"
    assert result.config.safety.logs_dir == "logs"


def test_missing_user_and_project_config_is_not_fatal(tmp_path: Path) -> None:
    result = ConfigService.load(
        user_config_path=tmp_path / "missing-user.toml",
        project_config_path=tmp_path / "missing-project.toml",
        env={},
    )

    assert not result.has_errors
    assert result.config.git.enabled is True
    assert [
        source.loaded for source in result.sources if source.name in {"user", "project"}
    ] == [
        False,
        False,
    ]


def test_malformed_toml_returns_structured_diagnostic(tmp_path: Path) -> None:
    user_config = write_config(tmp_path / "config.toml", "[editor]\ntab_size = ")

    result = ConfigService.load(user_config_path=user_config, env={})

    assert result.has_errors
    assert result.config.editor.tab_size == 4
    assert any(
        diagnostic.level is ConfigDiagnosticLevel.ERROR
        and diagnostic.code == "config.toml.malformed"
        and diagnostic.path == str(user_config)
        for diagnostic in result.diagnostics
    )


def test_user_config_overrides_defaults(tmp_path: Path) -> None:
    user_config = write_config(
        tmp_path / "user.toml",
        """
[editor]
tab_size = 2
encoding = "latin-1"

[ui]
theme = "light"
""",
    )

    result = ConfigService.load(user_config_path=user_config, env={})

    assert result.config.editor.tab_size == 2
    assert result.config.editor.encoding == "latin-1"
    assert result.config.ui.theme == "light"


def test_project_config_overrides_user_config(tmp_path: Path) -> None:
    user_config = write_config(tmp_path / "user.toml", "[editor]\ntab_size = 2\n")
    project_config = write_config(tmp_path / "project.toml", "[editor]\ntab_size = 8\n")

    result = ConfigService.load(
        user_config_path=user_config,
        project_config_path=project_config,
        env={},
    )

    assert result.config.editor.tab_size == 8


def test_environment_overrides_project_and_user_config(tmp_path: Path) -> None:
    user_config = write_config(tmp_path / "user.toml", "[editor]\ntab_size = 2\n")
    project_config = write_config(tmp_path / "project.toml", "[editor]\ntab_size = 8\n")

    result = ConfigService.load(
        user_config_path=user_config,
        project_config_path=project_config,
        env={
            "ECLI_EDITOR_TAB_SIZE": "6",
            "ECLI_UI_THEME": "env-theme",
            "ECLI_GIT_ENABLED": "off",
        },
    )

    assert result.config.editor.tab_size == 6
    assert result.config.ui.theme == "env-theme"
    assert result.config.git.enabled is False


def test_cli_overrides_all_other_sources(tmp_path: Path) -> None:
    user_config = write_config(tmp_path / "user.toml", "[editor]\ntab_size = 2\n")
    project_config = write_config(tmp_path / "project.toml", "[editor]\ntab_size = 8\n")

    result = ConfigService.load(
        user_config_path=user_config,
        project_config_path=project_config,
        env={"ECLI_EDITOR_TAB_SIZE": "6", "ECLI_AI_DEFAULT_PROVIDER": "gemini"},
        cli_overrides={
            "editor.tab_size": 3,
            "ui.theme": "cli-theme",
            "ai.default_provider": "openai",
        },
    )

    assert result.config.editor.tab_size == 3
    assert result.config.ui.theme == "cli-theme"
    assert result.config.ai.default_provider == "openai"


def test_safety_policy_cannot_be_weakened_by_user_config(tmp_path: Path) -> None:
    user_config = write_config(
        tmp_path / "user.toml",
        """
[safety]
require_confirmation = false
allow_privileged_without_plan = true
redact_exports_by_default = false
""",
    )

    result = ConfigService.load(user_config_path=user_config, env={})

    assert result.config.safety.require_confirmation is True
    assert result.config.safety.allow_privileged_without_plan is False
    assert result.config.safety.redact_exports_by_default is True
    assert any(
        diagnostic.code == "config.safety.weakened_ignored"
        for diagnostic in result.diagnostics
    )


def test_logs_dir_cannot_change_away_from_logs(tmp_path: Path) -> None:
    user_config = write_config(
        tmp_path / "user.toml",
        """
[safety]
logs_dir = "tmp"
""",
    )

    result = ConfigService.load(user_config_path=user_config, env={})

    assert result.config.safety.logs_dir == "logs"
    assert any(
        diagnostic.path == "safety.logs_dir"
        and diagnostic.code == "config.safety.logs_dir_enforced"
        for diagnostic in result.diagnostics
    )


def test_invalid_env_boolean_produces_diagnostic_and_does_not_override() -> None:
    result = ConfigService.load(env={"ECLI_GIT_ENABLED": "sometimes"})

    assert result.config.git.enabled is True
    assert any(
        diagnostic.path == "git.enabled"
        and diagnostic.code == "config.env.invalid_bool"
        for diagnostic in result.diagnostics
    )


def test_get_keybinding_returns_configured_binding_or_none(tmp_path: Path) -> None:
    user_config = write_config(
        tmp_path / "user.toml",
        """
[keybindings]
save_file = "ctrl+s"
extend_selection_left = ["shift+left", "alt-h"]
""",
    )
    result = ConfigService.load(user_config_path=user_config, env={})
    service = ConfigService(result.config)

    assert service.get_keybinding("save_file") == "ctrl+s"
    assert service.get_keybinding("extend_selection_left") == "shift+left"
    assert service.get_keybinding("missing") is None


def test_as_dict_returns_json_serializable_data(tmp_path: Path) -> None:
    user_config = write_config(
        tmp_path / "user.toml",
        """
[editor]
tab_size = 2

[custom_extension]
enabled = true
""",
    )
    result = ConfigService.load(user_config_path=user_config, env={})
    service = ConfigService(result.config)

    payload = service.as_dict()
    json.dumps(payload)
    assert payload["editor"]["tab_size"] == 2
    assert payload["custom_extension"]["enabled"] is True


def test_config_service_load_does_not_touch_real_home(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    result = ConfigService.load(env={})

    assert not result.has_errors
    assert not (fake_home / ".config" / "ecli").exists()
