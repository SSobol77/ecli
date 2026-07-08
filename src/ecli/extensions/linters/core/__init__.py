# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Shared diagnostics service, models, and registry types for F4 linters."""

from ecli.extensions.linters.core.display import diagnostic_display_path
from ecli.extensions.linters.core.models import (
    Diagnostic,
    DiagnosticRequest,
    DiagnosticResult,
    DiagnosticsSnapshot,
    ProviderState,
)
from ecli.extensions.linters.core.service import DiagnosticsService


__all__ = [
    "Diagnostic",
    "DiagnosticRequest",
    "DiagnosticResult",
    "DiagnosticsService",
    "DiagnosticsSnapshot",
    "ProviderState",
    "diagnostic_display_path",
]
