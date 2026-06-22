# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/config.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Typed, data-only view of the ``[linter]`` configuration table (#104).

ECLI already ships a small, user-facing ``[linter]`` table in ``config.toml``
(and the in-code ``DEFAULT_CONFIG`` fallback)::

    [linter]
    enabled = true
    auto_install = true
    exclude = [".git", "**pycache**", ".venv"]

This module reads that table and exposes it as an immutable
:class:`LinterLayerConfig`. It only turns configuration data into typed flags; it
never installs anything and never runs a tool.

Important: ``auto_install`` is parsed and preserved for forward compatibility but
is **not acted upon** by the diagnostics layer. The F4 Diagnostics panel works
without installing anything: when a provider's executable is missing the panel
reports a structured *unavailable* state instead of fetching or installing it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import PurePath

from ..manifest import RegistryDiagnostic


_CONFIG_SOURCE = "config.linter"

_DEFAULT_EXCLUDE: tuple[str, ...] = (".git", "**pycache**", ".venv")


@dataclass(frozen=True)
class LinterLayerConfig:
    """Immutable, data-only view of the ``[linter]`` configuration table."""

    enabled: bool = True
    auto_install: bool = True
    exclude: tuple[str, ...] = _DEFAULT_EXCLUDE
    diagnostics: tuple[RegistryDiagnostic, ...] = field(default_factory=tuple)

    @property
    def performs_auto_install(self) -> bool:
        """Always ``False``: the diagnostics layer never auto-installs tools.

        The ``auto_install`` flag is retained for forward compatibility, but no
        code path in #104 acts on it. Missing tools surface as an explicit
        *unavailable* diagnostics state.
        """
        return False

    def is_excluded(self, file_path: str | None) -> bool:
        """Return ``True`` when *file_path* matches an ``exclude`` glob.

        Matching is deterministic and offline: each pattern is tested against
        the full path, the basename, and every path segment using
        :func:`fnmatch.fnmatch`. This never touches the filesystem.
        """
        if not file_path:
            return False
        pure = PurePath(file_path)
        candidates = [str(pure), pure.name, *pure.parts]
        for pattern in self.exclude:
            if any(fnmatch(candidate, pattern) for candidate in candidates):
                return True
        return False

    @classmethod
    def from_config(
        cls, config: Mapping[str, object] | None, source: str = _CONFIG_SOURCE
    ) -> LinterLayerConfig:
        """Build from a full ECLI config mapping by reading its ``linter`` table."""
        section = config.get("linter") if isinstance(config, Mapping) else None
        return cls.from_section(section, source)

    @classmethod
    def from_section(
        cls, section: object, source: str = _CONFIG_SOURCE
    ) -> LinterLayerConfig:
        """Build from the ``[linter]`` table itself, validating every field."""
        if section is None:
            return cls()
        diagnostics: list[RegistryDiagnostic] = []
        if not isinstance(section, Mapping):
            diagnostics.append(
                RegistryDiagnostic("warning", source, "linter must be a table")
            )
            return cls(diagnostics=tuple(diagnostics))

        default = cls()
        return cls(
            enabled=_read_bool(
                section, "enabled", default.enabled, source, diagnostics
            ),
            auto_install=_read_bool(
                section, "auto_install", default.auto_install, source, diagnostics
            ),
            exclude=_read_exclude(section, default.exclude, source, diagnostics),
            diagnostics=tuple(diagnostics),
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


def _read_exclude(
    section: Mapping[str, object],
    default: tuple[str, ...],
    source: str,
    diagnostics: list[RegistryDiagnostic],
) -> tuple[str, ...]:
    if "exclude" not in section:
        return default
    value = section["exclude"]
    if not isinstance(value, (list, tuple)):
        diagnostics.append(
            RegistryDiagnostic(
                "warning", source, "exclude must be a list of strings; using defaults"
            )
        )
        return default
    patterns: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            patterns.append(item)
        else:
            diagnostics.append(
                RegistryDiagnostic(
                    "warning",
                    source,
                    f"exclude entries must be strings; ignored: {item!r}",
                )
            )
    return tuple(patterns)
