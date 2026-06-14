# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/models/config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Typed configuration models for the Phase 1 ConfigService."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping


CURRENT_CONFIG_SCHEMA_VERSION = 2


class ConfigDiagnosticLevel(StrEnum):
    """Severity for configuration diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ConfigDiagnostic:
    """Structured, user-readable configuration diagnostic."""

    level: ConfigDiagnosticLevel
    message: str
    path: str | None = None
    source: str | None = None
    code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable diagnostic dictionary."""
        return {
            "level": self.level.value,
            "message": self.message,
            "path": self.path,
            "source": self.source,
            "code": self.code,
        }


@dataclass(frozen=True)
class ConfigSource:
    """Metadata describing one configuration source considered during load."""

    name: str
    path: str | None = None
    exists: bool = True
    loaded: bool = False
    schema_version: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable source dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "exists": self.exists,
            "loaded": self.loaded,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class EditorConfig:
    """Typed editor configuration used by runtime services."""

    tab_size: int = 4
    encoding: str = "utf-8"
    use_spaces: bool = True
    use_system_clipboard: bool = True
    show_line_numbers: bool = True
    auto_indent: bool = True
    auto_brackets: bool = True
    word_wrap: bool = False

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> EditorConfig:
        """Build editor config with explicit validation and fallback."""
        section = _mapping_or_empty(raw, "editor", diagnostics, source)
        default = cls()
        return cls(
            tab_size=_read_int(
                section,
                "tab_size",
                default.tab_size,
                "editor.tab_size",
                diagnostics,
                source,
                minimum=1,
            ),
            encoding=_read_str(
                section,
                "encoding",
                default.encoding,
                "editor.encoding",
                diagnostics,
                source,
            ),
            use_spaces=_read_bool(
                section,
                "use_spaces",
                default.use_spaces,
                "editor.use_spaces",
                diagnostics,
                source,
            ),
            use_system_clipboard=_read_bool(
                section,
                "use_system_clipboard",
                default.use_system_clipboard,
                "editor.use_system_clipboard",
                diagnostics,
                source,
            ),
            show_line_numbers=_read_bool(
                section,
                "show_line_numbers",
                default.show_line_numbers,
                "editor.show_line_numbers",
                diagnostics,
                source,
            ),
            auto_indent=_read_bool(
                section,
                "auto_indent",
                default.auto_indent,
                "editor.auto_indent",
                diagnostics,
                source,
            ),
            auto_brackets=_read_bool(
                section,
                "auto_brackets",
                default.auto_brackets,
                "editor.auto_brackets",
                diagnostics,
                source,
            ),
            word_wrap=_read_bool(
                section,
                "word_wrap",
                default.word_wrap,
                "editor.word_wrap",
                diagnostics,
                source,
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable editor configuration."""
        return {
            "tab_size": self.tab_size,
            "encoding": self.encoding,
            "use_spaces": self.use_spaces,
            "use_system_clipboard": self.use_system_clipboard,
            "show_line_numbers": self.show_line_numbers,
            "auto_indent": self.auto_indent,
            "auto_brackets": self.auto_brackets,
            "word_wrap": self.word_wrap,
        }


@dataclass(frozen=True)
class UIConfig:
    """Typed UI configuration used by runtime services."""

    theme: str = "dark"
    colors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> UIConfig:
        """Build UI config while tolerating current and target theme layouts."""
        ui_section = _mapping_or_empty(raw.get("ui"), "ui", diagnostics, source)
        theme_section = _mapping_or_empty(
            raw.get("theme"), "theme", diagnostics, source
        )
        colors_section = _mapping_or_empty(
            raw.get("colors"), "colors", diagnostics, source
        )

        default = cls()
        theme = default.theme
        if isinstance(theme_section.get("name"), str) and theme_section["name"]:
            theme = theme_section["name"]
        if isinstance(ui_section.get("theme"), str) and ui_section["theme"]:
            theme = ui_section["theme"]
        elif "theme" in ui_section:
            diagnostics.append(
                _invalid_value(
                    "ui.theme",
                    "expected a non-empty string; using fallback",
                    source,
                )
            )

        colors: dict[str, str] = {}
        for key, value in colors_section.items():
            if isinstance(key, str) and isinstance(value, str):
                colors[key] = value
            else:
                diagnostics.append(
                    _invalid_value(
                        f"colors.{key}",
                        "expected string color key and value; entry ignored",
                        source,
                    )
                )

        return cls(theme=theme, colors=colors)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable UI configuration."""
        return {"theme": self.theme, "colors": dict(self.colors)}


@dataclass(frozen=True)
class AIProviderConfig:
    """Typed configuration for one AI provider."""

    model: str | None = None
    api_key: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable AI provider configuration."""
        return {"model": self.model, "api_key": self.api_key}


@dataclass(frozen=True)
class AIConfig:
    """Typed AI configuration."""

    default_provider: str = "gemini"
    providers: dict[str, AIProviderConfig] = field(default_factory=dict)

    @classmethod
    def from_mapping(  # noqa: C901, PLR0912
        cls,
        raw: Mapping[str, Any],
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> AIConfig:
        """Build AI config from canonical and legacy-compatible layouts."""
        ai_section = _mapping_or_empty(raw.get("ai"), "ai", diagnostics, source)
        default = cls()
        default_provider = _read_str(
            ai_section,
            "default_provider",
            default.default_provider,
            "ai.default_provider",
            diagnostics,
            source,
        )

        provider_records: dict[str, dict[str, str | None]] = {}
        providers_section = _mapping_or_empty(
            ai_section.get("providers"), "ai.providers", diagnostics, source
        )
        for provider, provider_raw in providers_section.items():
            if not isinstance(provider, str):
                diagnostics.append(
                    _invalid_value(
                        f"ai.providers.{provider}",
                        "provider names must be strings; entry ignored",
                        source,
                    )
                )
                continue
            if not isinstance(provider_raw, Mapping):
                diagnostics.append(
                    _invalid_value(
                        f"ai.providers.{provider}",
                        "expected provider table; entry ignored",
                        source,
                    )
                )
                continue
            record = provider_records.setdefault(provider, {})
            if isinstance(provider_raw.get("model"), str):
                record["model"] = provider_raw["model"]
            if isinstance(provider_raw.get("api_key"), str):
                record["api_key"] = provider_raw["api_key"]

        model_sections = [
            _mapping_or_empty(
                ai_section.get("models"), "ai.models", diagnostics, source
            ),
            _mapping_or_empty(raw.get("ai.models"), "ai.models", diagnostics, source),
        ]
        for model_section in model_sections:
            for provider, model in model_section.items():
                if isinstance(provider, str) and isinstance(model, str):
                    provider_records.setdefault(provider, {})["model"] = model
                else:
                    diagnostics.append(
                        _invalid_value(
                            f"ai.models.{provider}",
                            "expected string provider model; entry ignored",
                            source,
                        )
                    )

        key_sections = [
            _mapping_or_empty(ai_section.get("keys"), "ai.keys", diagnostics, source),
            _mapping_or_empty(raw.get("ai.keys"), "ai.keys", diagnostics, source),
        ]
        for key_section in key_sections:
            for provider, api_key in key_section.items():
                if isinstance(provider, str) and isinstance(api_key, str):
                    provider_records.setdefault(provider, {})["api_key"] = api_key
                else:
                    diagnostics.append(
                        _invalid_value(
                            f"ai.keys.{provider}",
                            "expected string provider API key; entry ignored",
                            source,
                        )
                    )

        providers = {
            provider: AIProviderConfig(
                model=record.get("model"),
                api_key=record.get("api_key"),
            )
            for provider, record in sorted(provider_records.items())
        }
        return cls(default_provider=default_provider, providers=providers)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable AI configuration."""
        return {
            "default_provider": self.default_provider,
            "providers": {
                provider: config.as_dict()
                for provider, config in sorted(self.providers.items())
            },
        }


@dataclass(frozen=True)
class GitConfig:
    """Typed Git integration configuration."""

    enabled: bool = True

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> GitConfig:
        """Build Git config with explicit validation and fallback."""
        section = _mapping_or_empty(raw, "git", diagnostics, source)
        default = cls()
        return cls(
            enabled=_read_bool(
                section,
                "enabled",
                default.enabled,
                "git.enabled",
                diagnostics,
                source,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable Git configuration."""
        return {"enabled": self.enabled}


@dataclass(frozen=True)
class LSPConfig:
    """Typed LSP configuration."""

    enabled: bool = False
    servers: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> LSPConfig:
        """Build LSP config with explicit validation and fallback."""
        section = _mapping_or_empty(raw, "lsp", diagnostics, source)
        default = cls()
        servers_raw = _mapping_or_empty(
            section.get("servers"), "lsp.servers", diagnostics, source
        )
        servers: dict[str, dict[str, Any]] = {}
        for name, server_config in servers_raw.items():
            if isinstance(name, str) and isinstance(server_config, Mapping):
                servers[name] = dict(server_config)
            else:
                diagnostics.append(
                    _invalid_value(
                        f"lsp.servers.{name}",
                        "expected server table; entry ignored",
                        source,
                    )
                )

        return cls(
            enabled=_read_bool(
                section,
                "enabled",
                default.enabled,
                "lsp.enabled",
                diagnostics,
                source,
            ),
            servers=servers,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable LSP configuration."""
        return {"enabled": self.enabled, "servers": dict(self.servers)}


@dataclass(frozen=True)
class KeybindingConfig:
    """Typed keybinding configuration."""

    bindings: dict[str, str | list[str]] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> KeybindingConfig:
        """Build keybinding config, accepting existing string/list bindings."""
        section = _mapping_or_empty(raw, "keybindings", diagnostics, source)
        bindings: dict[str, str | list[str]] = {}
        for action, binding in section.items():
            if not isinstance(action, str):
                diagnostics.append(
                    _invalid_value(
                        f"keybindings.{action}",
                        "action names must be strings; entry ignored",
                        source,
                    )
                )
                continue
            if isinstance(binding, str):
                bindings[action] = binding
                continue
            if isinstance(binding, list) and all(
                isinstance(item, str) for item in binding
            ):
                bindings[action] = list(binding)
                continue
            diagnostics.append(
                _invalid_value(
                    f"keybindings.{action}",
                    "expected string or list of strings; entry ignored",
                    source,
                )
            )
        return cls(bindings=bindings)

    def get(self, action: str) -> str | None:
        """Return the configured binding for an action, if present."""
        binding = self.bindings.get(action)
        if isinstance(binding, str):
            return binding
        if isinstance(binding, list) and binding:
            return binding[0]
        return None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable keybinding configuration."""
        return {
            action: list(binding) if isinstance(binding, list) else binding
            for action, binding in sorted(self.bindings.items())
        }


@dataclass(frozen=True)
class SafetyPolicyConfig:
    """Safety policy fields that require guarded precedence semantics."""

    require_confirmation: bool = True
    allow_privileged_without_plan: bool = False
    redact_exports_by_default: bool = True
    logs_dir: str = "logs"

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> SafetyPolicyConfig:
        """Build safety policy with invariant checks."""
        section = _mapping_or_empty(raw, "safety", diagnostics, source)
        default = cls()
        logs_dir = _read_str(
            section,
            "logs_dir",
            default.logs_dir,
            "safety.logs_dir",
            diagnostics,
            source,
        )
        if logs_dir != default.logs_dir:
            diagnostics.append(
                ConfigDiagnostic(
                    level=ConfigDiagnosticLevel.WARNING,
                    path="safety.logs_dir",
                    source=source,
                    code="safety.logs_dir.fixed",
                    message="safety.logs_dir must remain 'logs'; using enforced value",
                )
            )
            logs_dir = default.logs_dir

        return cls(
            require_confirmation=_read_bool(
                section,
                "require_confirmation",
                default.require_confirmation,
                "safety.require_confirmation",
                diagnostics,
                source,
            ),
            allow_privileged_without_plan=_read_bool(
                section,
                "allow_privileged_without_plan",
                default.allow_privileged_without_plan,
                "safety.allow_privileged_without_plan",
                diagnostics,
                source,
            ),
            redact_exports_by_default=_read_bool(
                section,
                "redact_exports_by_default",
                default.redact_exports_by_default,
                "safety.redact_exports_by_default",
                diagnostics,
                source,
            ),
            logs_dir=logs_dir,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable safety policy configuration."""
        return {
            "require_confirmation": self.require_confirmation,
            "allow_privileged_without_plan": self.allow_privileged_without_plan,
            "redact_exports_by_default": self.redact_exports_by_default,
            "logs_dir": self.logs_dir,
        }


@dataclass(frozen=True)
class ECLIConfig:
    """Typed runtime configuration view for ECLI."""

    schema_version: int = CURRENT_CONFIG_SCHEMA_VERSION
    editor: EditorConfig = field(default_factory=EditorConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    git: GitConfig = field(default_factory=GitConfig)
    lsp: LSPConfig = field(default_factory=LSPConfig)
    keybindings: KeybindingConfig = field(default_factory=KeybindingConfig)
    safety: SafetyPolicyConfig = field(default_factory=SafetyPolicyConfig)
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        diagnostics: list[ConfigDiagnostic],
        source: str = "effective",
    ) -> ECLIConfig:
        """Build the typed runtime config from a merged raw configuration tree."""
        schema_section = _mapping_or_empty(
            raw.get("schema"), "schema", diagnostics, source
        )
        schema_version = _read_int(
            schema_section,
            "version",
            CURRENT_CONFIG_SCHEMA_VERSION,
            "schema.version",
            diagnostics,
            source,
            minimum=1,
        )
        known_top_level = {
            "schema",
            "editor",
            "ui",
            "ai",
            "git",
            "lsp",
            "keybindings",
            "safety",
        }
        extras = {
            key: _json_safe_copy(value)
            for key, value in raw.items()
            if key not in known_top_level
        }
        return cls(
            schema_version=schema_version,
            editor=EditorConfig.from_mapping(raw.get("editor"), diagnostics, source),
            ui=UIConfig.from_mapping(raw, diagnostics, source),
            ai=AIConfig.from_mapping(raw, diagnostics, source),
            git=GitConfig.from_mapping(raw.get("git"), diagnostics, source),
            lsp=LSPConfig.from_mapping(raw.get("lsp"), diagnostics, source),
            keybindings=KeybindingConfig.from_mapping(
                raw.get("keybindings"), diagnostics, source
            ),
            safety=SafetyPolicyConfig.from_mapping(
                raw.get("safety"), diagnostics, source
            ),
            extras=extras,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable configuration dictionary."""
        result = {
            "schema": {"version": self.schema_version},
            "editor": self.editor.as_dict(),
            "ui": self.ui.as_dict(),
            "ai": self.ai.as_dict(),
            "git": self.git.as_dict(),
            "lsp": self.lsp.as_dict(),
            "keybindings": self.keybindings.as_dict(),
            "safety": self.safety.as_dict(),
        }
        for key, value in self.extras.items():
            if key not in result:
                result[key] = _json_safe_copy(value)
        return result


@dataclass(frozen=True)
class ConfigLoadResult:
    """Result of configuration loading and validation."""

    config: ECLIConfig
    diagnostics: list[ConfigDiagnostic] = field(default_factory=list)
    sources: list[ConfigSource] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Return true if any diagnostic is an error."""
        return any(
            diagnostic.level is ConfigDiagnosticLevel.ERROR
            for diagnostic in self.diagnostics
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable load result."""
        return {
            "config": self.config.as_dict(),
            "diagnostics": [diagnostic.as_dict() for diagnostic in self.diagnostics],
            "sources": [source.as_dict() for source in self.sources],
            "has_errors": self.has_errors,
        }


def path_to_source(path: Path | None) -> str | None:
    """Return a stable string representation for an optional path."""
    return None if path is None else str(path)


def _mapping_or_empty(
    value: Any,
    path: str,
    diagnostics: list[ConfigDiagnostic],
    source: str,
) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    diagnostics.append(_invalid_value(path, "expected a table; using fallback", source))
    return {}


def _read_str(  # noqa: PLR0913
    section: Mapping[str, Any],
    key: str,
    default: str,
    path: str,
    diagnostics: list[ConfigDiagnostic],
    source: str,
) -> str:
    if key not in section:
        return default
    value = section[key]
    if isinstance(value, str) and value:
        return value
    diagnostics.append(
        _invalid_value(path, "expected a non-empty string; using fallback", source)
    )
    return default


def _read_bool(  # noqa: PLR0913
    section: Mapping[str, Any],
    key: str,
    default: bool,
    path: str,
    diagnostics: list[ConfigDiagnostic],
    source: str,
) -> bool:
    if key not in section:
        return default
    value = section[key]
    if isinstance(value, bool):
        return value
    diagnostics.append(
        _invalid_value(path, "expected a boolean; using fallback", source)
    )
    return default


def _read_int(  # noqa: PLR0913
    section: Mapping[str, Any],
    key: str,
    default: int,
    path: str,
    diagnostics: list[ConfigDiagnostic],
    source: str,
    minimum: int | None = None,
) -> int:
    if key not in section:
        return default
    value = section[key]
    if isinstance(value, int) and not isinstance(value, bool):
        if minimum is None or value >= minimum:
            return value
    diagnostics.append(
        _invalid_value(path, "expected a valid integer; using fallback", source)
    )
    return default


def _invalid_value(path: str, message: str, source: str) -> ConfigDiagnostic:
    return ConfigDiagnostic(
        level=ConfigDiagnosticLevel.WARNING,
        path=path,
        source=source,
        code="config.invalid_value",
        message=message,
    )


def _json_safe_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_copy(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_copy(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
