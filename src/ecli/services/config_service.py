# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/config_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Phase 1 typed ConfigService foundation."""

from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from ecli.services.migrations.config_migrations import (
    detect_config_schema_version,
    migrate_to_current,
)
from ecli.services.models.config import (
    CURRENT_CONFIG_SCHEMA_VERSION,
    AIConfig,
    ConfigDiagnostic,
    ConfigDiagnosticLevel,
    ConfigLoadResult,
    ConfigSource,
    ECLIConfig,
    EditorConfig,
    GitConfig,
    LSPConfig,
    SafetyPolicyConfig,
    UIConfig,
)


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "ECLI_EDITOR_TAB_SIZE": ("editor.tab_size", "int"),
    "ECLI_EDITOR_ENCODING": ("editor.encoding", "str"),
    "ECLI_UI_THEME": ("ui.theme", "str"),
    "ECLI_AI_DEFAULT_PROVIDER": ("ai.default_provider", "str"),
    "ECLI_GIT_ENABLED": ("git.enabled", "bool"),
    "ECLI_SAFETY_REQUIRE_CONFIRMATION": ("safety.require_confirmation", "bool"),
}


class ConfigService:
    """Typed configuration access service for ECLI."""

    def __init__(self, config: ECLIConfig) -> None:
        """Initialize the service with an immutable typed config view."""
        self._config = config

    @classmethod
    def load(
        cls,
        user_config_path: Path | None = None,
        project_config_path: Path | None = None,
        cli_overrides: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ConfigLoadResult:
        """Load defaults, optional files, environment, and CLI overrides."""
        diagnostics: list[ConfigDiagnostic] = []
        sources: list[ConfigSource] = [
            ConfigSource(
                name="defaults",
                loaded=True,
                schema_version=CURRENT_CONFIG_SCHEMA_VERSION,
            )
        ]
        raw_config = _default_config()

        if user_config_path is not None:
            user_raw = _read_toml_source(user_config_path, "user", diagnostics, sources)
            if user_raw is not None:
                migrated, migration_diagnostics = migrate_to_current(user_raw)
                diagnostics.extend(
                    _with_source(migration_diagnostics, "user", user_config_path)
                )
                raw_config = _merge_layer(
                    raw_config,
                    migrated,
                    source_name="user",
                    diagnostics=diagnostics,
                    allow_safety_weakening=False,
                    diagnostic_path=str(user_config_path),
                )
        else:
            sources.append(ConfigSource(name="user", exists=False, loaded=False))

        if project_config_path is not None:
            project_raw = _read_toml_source(
                project_config_path, "project", diagnostics, sources
            )
            if project_raw is not None:
                migrated, migration_diagnostics = migrate_to_current(project_raw)
                diagnostics.extend(
                    _with_source(migration_diagnostics, "project", project_config_path)
                )
                raw_config = _merge_layer(
                    raw_config,
                    migrated,
                    source_name="project",
                    diagnostics=diagnostics,
                    allow_safety_weakening=True,
                    diagnostic_path=str(project_config_path),
                )
        else:
            sources.append(ConfigSource(name="project", exists=False, loaded=False))

        env_overrides = _env_to_overrides(
            os.environ if env is None else env, diagnostics
        )
        if env_overrides:
            raw_config = _merge_layer(
                raw_config,
                env_overrides,
                source_name="env",
                diagnostics=diagnostics,
                allow_safety_weakening=True,
                diagnostic_path="environment",
            )
            sources.append(ConfigSource(name="env", loaded=True))
        else:
            sources.append(ConfigSource(name="env", loaded=False))

        if cli_overrides:
            cli_tree = _dotted_mapping_to_tree(cli_overrides, diagnostics, "cli")
            _diagnose_cli_safety_weakening(raw_config, cli_tree, diagnostics)
            raw_config = _merge_layer(
                raw_config,
                cli_tree,
                source_name="cli",
                diagnostics=diagnostics,
                allow_safety_weakening=True,
                diagnostic_path="cli",
            )
            sources.append(ConfigSource(name="cli", loaded=True))
        else:
            sources.append(ConfigSource(name="cli", loaded=False))

        typed_config = ECLIConfig.from_mapping(raw_config, diagnostics)
        return ConfigLoadResult(
            config=typed_config,
            diagnostics=diagnostics,
            sources=sources,
        )

    def get_editor_config(self) -> EditorConfig:
        """Return typed editor configuration."""
        return self._config.editor

    def get_ui_config(self) -> UIConfig:
        """Return typed UI configuration."""
        return self._config.ui

    def get_ai_config(self) -> AIConfig:
        """Return typed AI configuration."""
        return self._config.ai

    def get_git_config(self) -> GitConfig:
        """Return typed Git configuration."""
        return self._config.git

    def get_lsp_config(self) -> LSPConfig:
        """Return typed LSP configuration."""
        return self._config.lsp

    def get_keybinding(self, action: str) -> str | None:
        """Return the configured keybinding for an action."""
        return self._config.keybindings.get(action)

    def get_safety_policy(self) -> SafetyPolicyConfig:
        """Return typed safety policy configuration."""
        return self._config.safety

    def as_dict(self) -> dict[str, Any]:
        """Return the effective typed configuration as a JSON-serializable dict."""
        return self._config.as_dict()


def _default_config() -> dict[str, Any]:
    return {
        "schema": {"version": CURRENT_CONFIG_SCHEMA_VERSION},
        "editor": {
            "tab_size": 4,
            "encoding": "utf-8",
            "use_spaces": True,
            "use_system_clipboard": True,
            "show_line_numbers": True,
            "auto_indent": True,
            "auto_brackets": True,
            "word_wrap": False,
        },
        "ui": {"theme": "dark"},
        "ai": {
            "default_provider": "gemini",
            "providers": {
                "openai": {"model": "gpt-5-codex", "api_key": ""},
                "gemini": {"model": "gemini-2.5-pro", "api_key": ""},
                "mistral": {"model": "magistral-medium-1.2", "api_key": ""},
                "claude": {"model": "claude-4-opus", "api_key": ""},
                "grok": {"model": "grok-4-fast", "api_key": ""},
                "huggingface": {
                    "model": "meta-llama/Meta-Llama-3.1-405B-Instruct",
                    "api_key": "",
                },
            },
        },
        "git": {"enabled": True},
        "lsp": {"enabled": False, "servers": {}},
        "keybindings": {},
        "safety": {
            "require_confirmation": True,
            "allow_privileged_without_plan": False,
            "redact_exports_by_default": True,
            "logs_dir": "logs",
        },
    }


def _read_toml_source(
    path: Path,
    name: str,
    diagnostics: list[ConfigDiagnostic],
    sources: list[ConfigSource],
) -> dict[str, Any] | None:
    if not path.exists():
        sources.append(
            ConfigSource(name=name, path=str(path), exists=False, loaded=False)
        )
        return None
    if not path.is_file():
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.ERROR,
                path=str(path),
                source=name,
                code="config.source.not_file",
                message=f"{name} config path is not a regular file",
            )
        )
        sources.append(
            ConfigSource(name=name, path=str(path), exists=True, loaded=False)
        )
        return None
    try:
        with path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as exc:
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.ERROR,
                path=str(path),
                source=name,
                code="config.toml.malformed",
                message=f"Could not parse {name} config TOML: {exc}",
            )
        )
        sources.append(
            ConfigSource(name=name, path=str(path), exists=True, loaded=False)
        )
        return None
    except OSError as exc:
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.ERROR,
                path=str(path),
                source=name,
                code="config.source.read_error",
                message=f"Could not read {name} config: {exc}",
            )
        )
        sources.append(
            ConfigSource(name=name, path=str(path), exists=True, loaded=False)
        )
        return None

    sources.append(
        ConfigSource(
            name=name,
            path=str(path),
            exists=True,
            loaded=True,
            schema_version=detect_config_schema_version(raw),
        )
    )
    return raw


def _merge_layer(  # noqa: PLR0913
    base: Mapping[str, Any],
    override: Mapping[str, Any],
    source_name: str,
    diagnostics: list[ConfigDiagnostic],
    allow_safety_weakening: bool,
    diagnostic_path: str,
) -> dict[str, Any]:
    sanitized_override = deepcopy(dict(override))
    safety_override = sanitized_override.get("safety")
    if isinstance(safety_override, Mapping):
        base_safety = base.get("safety")
        if not isinstance(base_safety, Mapping):
            base_safety = {}
        sanitized_override["safety"] = _merge_safety_policy(
            base_safety=base_safety,
            override=safety_override,
            source_name=source_name,
            diagnostics=diagnostics,
            allow_safety_weakening=allow_safety_weakening,
            diagnostic_path=diagnostic_path,
        )
    return _deep_merge(dict(base), sanitized_override)


def _merge_safety_policy(  # noqa: PLR0913
    base_safety: Mapping[str, Any],
    override: Mapping[str, Any],
    source_name: str,
    diagnostics: list[ConfigDiagnostic],
    allow_safety_weakening: bool,
    diagnostic_path: str,
) -> dict[str, Any]:
    result = deepcopy(dict(override))

    logs_dir = result.get("logs_dir")
    if logs_dir is not None and logs_dir != "logs":
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.WARNING,
                path="safety.logs_dir",
                source=source_name,
                code="config.safety.logs_dir_enforced",
                message=(
                    f"{source_name} config attempted to set safety.logs_dir away "
                    "from 'logs'; using enforced value"
                ),
            )
        )
        result["logs_dir"] = "logs"

    if allow_safety_weakening:
        return result

    strict_true_fields = ("require_confirmation", "redact_exports_by_default")
    for field in strict_true_fields:
        if base_safety.get(field) is True and result.get(field) is False:
            diagnostics.append(
                ConfigDiagnostic(
                    level=ConfigDiagnosticLevel.WARNING,
                    path=f"safety.{field}",
                    source=source_name,
                    code="config.safety.weakened_ignored",
                    message=(
                        f"{source_name} config attempted to weaken safety.{field}; "
                        "keeping stricter effective value"
                    ),
                )
            )
            result[field] = True

    if (
        base_safety.get("allow_privileged_without_plan") is False
        and result.get("allow_privileged_without_plan") is True
    ):
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.WARNING,
                path="safety.allow_privileged_without_plan",
                source=source_name,
                code="config.safety.weakened_ignored",
                message=(
                    f"{source_name} config attempted to allow privileged operations "
                    "without a plan; keeping stricter effective value"
                ),
            )
        )
        result["allow_privileged_without_plan"] = False

    return result


def _env_to_overrides(
    env: Mapping[str, str],
    diagnostics: list[ConfigDiagnostic],
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for env_name, (config_path, value_type) in ENV_OVERRIDES.items():
        if env_name not in env:
            continue
        value = _parse_env_value(
            env_name=env_name,
            raw_value=env[env_name],
            value_type=value_type,
            config_path=config_path,
            diagnostics=diagnostics,
        )
        if value is _INVALID_ENV:
            continue
        _set_dotted(overrides, config_path, value)
    return overrides


class _InvalidEnv:
    pass


_INVALID_ENV = _InvalidEnv()


def _parse_env_value(
    env_name: str,
    raw_value: str,
    value_type: str,
    config_path: str,
    diagnostics: list[ConfigDiagnostic],
) -> str | int | bool | _InvalidEnv:
    if value_type == "str":
        return raw_value
    if value_type == "int":
        return _parse_env_int(env_name, raw_value, config_path, diagnostics)
    if value_type == "bool":
        return _parse_env_bool(env_name, raw_value, config_path, diagnostics)
    diagnostics.append(
        ConfigDiagnostic(
            level=ConfigDiagnosticLevel.WARNING,
            path=config_path,
            source="env",
            code="config.env.invalid_mapping",
            message=f"{env_name} has unsupported override type; override ignored",
        )
    )
    return _INVALID_ENV


def _parse_env_int(
    env_name: str,
    raw_value: str,
    config_path: str,
    diagnostics: list[ConfigDiagnostic],
) -> int | _InvalidEnv:
    try:
        return int(raw_value)
    except ValueError:
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.WARNING,
                path=config_path,
                source="env",
                code="config.env.invalid_int",
                message=f"{env_name} must be an integer; override ignored",
            )
        )
        return _INVALID_ENV


def _parse_env_bool(
    env_name: str,
    raw_value: str,
    config_path: str,
    diagnostics: list[ConfigDiagnostic],
) -> bool | _InvalidEnv:
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    diagnostics.append(
        ConfigDiagnostic(
            level=ConfigDiagnosticLevel.WARNING,
            path=config_path,
            source="env",
            code="config.env.invalid_bool",
            message=(
                f"{env_name} must be one of 1,true,yes,on,0,false,no,off; "
                "override ignored"
            ),
        )
    )
    return _INVALID_ENV


def _dotted_mapping_to_tree(
    overrides: Mapping[str, Any],
    diagnostics: list[ConfigDiagnostic],
    source_name: str,
) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path, value in overrides.items():
        if not isinstance(path, str) or not path:
            diagnostics.append(
                ConfigDiagnostic(
                    level=ConfigDiagnosticLevel.WARNING,
                    path=str(path),
                    source=source_name,
                    code="config.override.invalid_key",
                    message="CLI override keys must be non-empty dotted strings; override ignored",
                )
            )
            continue
        _set_dotted(tree, path, value)
    return tree


def _set_dotted(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _diagnose_cli_safety_weakening(
    current_raw: Mapping[str, Any],
    cli_tree: Mapping[str, Any],
    diagnostics: list[ConfigDiagnostic],
) -> None:
    current_safety = current_raw.get("safety")
    cli_safety = cli_tree.get("safety")
    if not isinstance(current_safety, Mapping) or not isinstance(cli_safety, Mapping):
        return

    if (
        current_safety.get("require_confirmation") is True
        and cli_safety.get("require_confirmation") is False
    ):
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.WARNING,
                path="safety.require_confirmation",
                source="cli",
                code="config.safety.cli_weakened",
                message=(
                    "CLI override explicitly weakens safety.require_confirmation; "
                    "override applied by caller request"
                ),
            )
        )
    if (
        current_safety.get("redact_exports_by_default") is True
        and cli_safety.get("redact_exports_by_default") is False
    ):
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.WARNING,
                path="safety.redact_exports_by_default",
                source="cli",
                code="config.safety.cli_weakened",
                message=(
                    "CLI override explicitly weakens safety.redact_exports_by_default; "
                    "override applied by caller request"
                ),
            )
        )
    if (
        current_safety.get("allow_privileged_without_plan") is False
        and cli_safety.get("allow_privileged_without_plan") is True
    ):
        diagnostics.append(
            ConfigDiagnostic(
                level=ConfigDiagnosticLevel.WARNING,
                path="safety.allow_privileged_without_plan",
                source="cli",
                code="config.safety.cli_weakened",
                message=(
                    "CLI override explicitly weakens safety.allow_privileged_without_plan; "
                    "override applied by caller request"
                ),
            )
        )


def _with_source(
    diagnostics: list[ConfigDiagnostic],
    source_name: str,
    source_path: Path,
) -> list[ConfigDiagnostic]:
    return [
        ConfigDiagnostic(
            level=diagnostic.level,
            message=diagnostic.message,
            path=diagnostic.path,
            source=diagnostic.source or f"{source_name}:{source_path}",
            code=diagnostic.code,
        )
        for diagnostic in diagnostics
    ]


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
