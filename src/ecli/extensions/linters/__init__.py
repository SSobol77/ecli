# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""The ECLI F4 Linter Microservices package.

Each supported linter is an independent microservice directory under this
package (``ruff/``, ``biome/``, ``zig/``, ...), following
``docs/architecture/ecli-f4-linter-microservices-design.md``. This
top-level package aggregates every microservice's declarative
``manifest.MANIFEST`` into the ``LINTER_CATALOG`` tuple and exposes the
same catalog-lookup API the retired ``ecli.diagnostics.linter_catalog``
module used to provide.

This module is **data only**: it does not execute any linter binary, does
not parse any linter output, and does not wire anything into
``DiagnosticsService`` or F4. Only ``ruff`` has a working ``provider.py``
in this migration; every other microservice is a manifest/package-contract
skeleton. See ``docs/extensions/diagnostics-linter-layer.md``.
"""

from __future__ import annotations

from ecli.extensions.linters import (
    actionlint,
    biome,
    cargo_clippy,
    clang_format,
    clang_tidy,
    cppcheck,
    eslint,
    golangci_lint,
    hadolint,
    java_checkstyle,
    java_pmd,
    java_spotbugs,
    markdownlint,
    oxlint,
    pylint,
    ruff,
    shellcheck,
    sqlfluff,
    stylelint,
    taplo,
    tflint,
    yamllint,
    zig,
)
from ecli.extensions.linters.core.registry import (
    LinterDefinition,
    get_linter as _get_linter,
    iter_linters as _iter_linters,
    linters_for_language as _linters_for_language,
)


# Declaration order follows the recommended provider registration order in
# docs/architecture/ecli-f4-linter-microservices-design.md section 9, with
# legacy/optional entries (not part of the first-class base profiles)
# appended after their superseding/recommended counterparts.
LINTER_CATALOG: tuple[LinterDefinition, ...] = (
    ruff.manifest.MANIFEST,
    biome.manifest.MANIFEST,
    oxlint.manifest.MANIFEST,
    eslint.manifest.MANIFEST,
    stylelint.manifest.MANIFEST,
    zig.manifest.MANIFEST,
    clang_tidy.manifest.MANIFEST,
    cppcheck.manifest.MANIFEST,
    clang_format.manifest.MANIFEST,
    java_checkstyle.manifest.MANIFEST,
    java_pmd.manifest.MANIFEST,
    java_spotbugs.manifest.MANIFEST,
    shellcheck.manifest.MANIFEST,
    markdownlint.manifest.MANIFEST,
    yamllint.manifest.MANIFEST,
    actionlint.manifest.MANIFEST,
    hadolint.manifest.MANIFEST,
    taplo.manifest.MANIFEST,
    cargo_clippy.manifest.MANIFEST,
    golangci_lint.manifest.MANIFEST,
    sqlfluff.manifest.MANIFEST,
    tflint.manifest.MANIFEST,
    pylint.manifest.MANIFEST,
)


def get_linter(name: str) -> LinterDefinition:
    """Return the catalog entry for ``name``.

    Raises:
        KeyError: if no catalog entry is registered under ``name``.
    """
    return _get_linter(LINTER_CATALOG, name)


def iter_linters() -> tuple[LinterDefinition, ...]:
    """Return every catalog entry, in declaration order."""
    return _iter_linters(LINTER_CATALOG)


def linters_for_language(language: str) -> tuple[LinterDefinition, ...]:
    """Return catalog entries that declare support for ``language``."""
    return _linters_for_language(LINTER_CATALOG, language)


__all__ = [
    "LINTER_CATALOG",
    "LinterDefinition",
    "get_linter",
    "iter_linters",
    "linters_for_language",
]
