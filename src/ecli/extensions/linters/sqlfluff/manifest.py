# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/sqlfluff/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the SQLFluff SQL linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="sqlfluff",
    display_name="SQLFluff",
    languages=("sql",),
    file_extensions=(".sql",),
    executable="sqlfluff",
    argv_template=("sqlfluff", "lint", "--format", "json", "{file}"),
    stdin_mode="optional",
    parser="json_generic",
    config_files=(".sqlfluff", "pyproject.toml"),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="data",
    install_hint="Install via pip: `pip install sqlfluff`. See https://docs.sqlfluff.com/en/stable/gettingstarted.html.",
    homepage_url="https://sqlfluff.com/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("sqlfluff",),
)
