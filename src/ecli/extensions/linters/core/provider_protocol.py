# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/provider_protocol.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""The provider protocol every linter microservice provider implements.

See ``docs/architecture/ecli-f4-linter-microservices-design.md`` section 7
("Provider Interface"). Every registered provider must implement
``supports(request)`` so ``DiagnosticsService`` only runs providers that are
actually applicable to the current request -- this is what stops Ruff (or
any other single-language provider) from producing an irrelevant skip
message for a file type it does not handle.
"""

from __future__ import annotations

from typing import Protocol

from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult


class DiagnosticProvider(Protocol):
    """Protocol implemented by diagnostics providers."""

    name: str
    enabled: bool

    def supports(self, request: DiagnosticRequest) -> bool:
        """Return True if this provider is applicable to ``request``."""

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        """Run diagnostics for the given request."""
