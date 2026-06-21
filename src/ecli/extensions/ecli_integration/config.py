# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Typed ``[extensions]`` configuration for the Extensions Layer (#101).

This module reads the deterministic ``[extensions]`` table that ECLI ships in
``config.toml`` (and in the legacy ``DEFAULT_CONFIG`` fallback) and exposes it as
an immutable :class:`ExtensionLayerConfig`. It only turns configuration data into
typed flags — it never activates an extension runtime.

The Extensions Layer is data-only. There is **no** configuration value that can
enable a VS Code extension host, Node/TypeScript activation, ``activationEvents``,
``package.json`` scripts, or a Copilot runtime. Any such key found in the table
is ignored with a diagnostic.

``syntax_engine`` accepts ``"legacy"`` (default, authoritative) and ``"extension"``
(selects the #102 extension-backed syntax-service boundary). Selecting
``"extension"`` routes rendering through the TextMate syntax service when the
optional tokenizer and selected grammar are usable. It never enables a runtime;
missing tokenizer or grammar failures fall back to the legacy highlighter (see
``syntax_service.py``). Unknown values fall back to ``"legacy"`` with a
diagnostic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .manifest import RegistryDiagnostic


_CONFIG_SOURCE = "config.extensions"

# Keys that would imply executing extension runtime behaviour. They are never
# honoured; their presence only produces a deterministic diagnostic.
_FORBIDDEN_RUNTIME_KEYS = frozenset(
    {
        "runtime",
        "execute",
        "execution",
        "activation",
        "activation_events",
        "activationevents",
        "extension_host",
        "host",
        "node",
        "npm",
        "scripts",
        "copilot",
    }
)


class SyntaxEngine(StrEnum):
    """Selectable syntax engine."""

    LEGACY = "legacy"
    EXTENSION = "extension"


@dataclass(frozen=True)
class ExtensionLayerConfig:
    """Immutable, data-only view of the ``[extensions]`` configuration table."""

    enabled: bool = True
    metadata_registry: bool = True
    grammar_catalog: bool = True
    language_detection: bool = True
    syntax_engine: str = SyntaxEngine.LEGACY.value
    diagnostics: tuple[RegistryDiagnostic, ...] = field(default_factory=tuple)

    @property
    def uses_legacy_syntax(self) -> bool:
        """Return ``True`` while the legacy regex highlighter stays authoritative."""
        return self.syntax_engine == SyntaxEngine.LEGACY.value

    @property
    def allows_runtime_execution(self) -> bool:
        """Always ``False``: no setting can enable extension runtime execution."""
        return False

    @classmethod
    def from_config(
        cls, config: Mapping[str, object] | None, source: str = _CONFIG_SOURCE
    ) -> ExtensionLayerConfig:
        """Build from a full ECLI config mapping by reading its ``extensions`` table."""
        section = config.get("extensions") if isinstance(config, Mapping) else None
        return cls.from_section(section, source)

    @classmethod
    def from_section(
        cls, section: object, source: str = _CONFIG_SOURCE
    ) -> ExtensionLayerConfig:
        """Build from the ``[extensions]`` table itself, validating every field."""
        if section is None:
            return cls()
        diagnostics: list[RegistryDiagnostic] = []
        if not isinstance(section, Mapping):
            diagnostics.append(
                RegistryDiagnostic("warning", source, "extensions must be a table")
            )
            return cls(diagnostics=tuple(diagnostics))

        _diagnose_forbidden_keys(section, source, diagnostics)
        default = cls()
        return cls(
            enabled=_read_bool(
                section, "enabled", default.enabled, source, diagnostics
            ),
            metadata_registry=_read_bool(
                section,
                "metadata_registry",
                default.metadata_registry,
                source,
                diagnostics,
            ),
            grammar_catalog=_read_bool(
                section, "grammar_catalog", default.grammar_catalog, source, diagnostics
            ),
            language_detection=_read_bool(
                section,
                "language_detection",
                default.language_detection,
                source,
                diagnostics,
            ),
            syntax_engine=_read_syntax_engine(section, source, diagnostics),
            diagnostics=tuple(diagnostics),
        )


def _diagnose_forbidden_keys(
    section: Mapping[str, object], source: str, diagnostics: list[RegistryDiagnostic]
) -> None:
    for key in section:
        if isinstance(key, str) and key.lower() in _FORBIDDEN_RUNTIME_KEYS:
            diagnostics.append(
                RegistryDiagnostic(
                    "warning",
                    source,
                    f"runtime execution settings are not permitted; ignored: {key!r}",
                )
            )


def _read_bool(
    section: Mapping[str, object],
    key: str,
    default: bool,  # noqa: FBT001
    source: str,
    diagnostics: list[RegistryDiagnostic],
) -> bool:
    if key not in section:
        return default
    value = section[key]
    if isinstance(value, bool):
        return value
    diagnostics.append(
        RegistryDiagnostic(
            "warning", source, f"{key} must be a boolean; using {default!r}"
        )
    )
    return default


def _read_syntax_engine(
    section: Mapping[str, object], source: str, diagnostics: list[RegistryDiagnostic]
) -> str:
    if "syntax_engine" not in section:
        return SyntaxEngine.LEGACY.value
    value = section["syntax_engine"]
    # "extension" is a valid selection as of #102: it routes through the
    # extension-backed syntax-service boundary. It never enables a runtime, and
    # rendering falls back to legacy when tokenization is unavailable.
    if value == SyntaxEngine.LEGACY.value:
        return SyntaxEngine.LEGACY.value
    if value == SyntaxEngine.EXTENSION.value:
        return SyntaxEngine.EXTENSION.value
    diagnostics.append(
        RegistryDiagnostic(
            "warning", source, f"unknown syntax_engine {value!r}; using 'legacy'"
        )
    )
    return SyntaxEngine.LEGACY.value
