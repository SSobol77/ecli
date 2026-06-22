# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/providers/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Diagnostics provider catalog: one active adapter (Ruff) and planned metadata.

ECLI integrates existing professional tools through safe ECLI-owned adapters and
ships no custom lint rules. Only :class:`RuffDiagnosticsProvider` executes in
this build; everything else is planned metadata in :mod:`.planned`.
"""

from __future__ import annotations

from .planned import (
    FILENAME_LANGUAGE,
    LANGUAGE_LABELS,
    PLANNED_NOTE_OVERRIDES,
    PLANNED_PROVIDERS,
    SONARQUBE_PROVIDER,
)
from .ruff import RUFF_METADATA, RuffDiagnosticsProvider


__all__ = [
    "FILENAME_LANGUAGE",
    "LANGUAGE_LABELS",
    "PLANNED_NOTE_OVERRIDES",
    "PLANNED_PROVIDERS",
    "RUFF_METADATA",
    "SONARQUBE_PROVIDER",
    "RuffDiagnosticsProvider",
]
