# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/ruff/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Ruff linter microservice.

Ruff is the F4 linter microservices reference implementation: it is the
only provider that is fully implemented in this migration
(``ruff/provider.py``), and it is bundled internally with ECLI rather than
shelled out to as an external tool (``provider_kind="internal"``).
"""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="ruff",
    display_name="Ruff",
    languages=("python",),
    file_extensions=(".py", ".pyi"),
    executable="ruff",
    argv_template=("ruff", "check", "--output-format=json", "{file}"),
    stdin_mode="optional",
    parser="json_generic",
    config_files=("pyproject.toml", "ruff.toml", ".ruff.toml"),
    capabilities=("lint", "fix"),
    tier="core",
    install_group="core",
    install_hint="Bundled with ECLI; no separate installation required.",
    homepage_url="https://docs.astral.sh/ruff/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    provider_kind="internal",
    package_hints=("ruff",),
)
