# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_pmd/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the PMD Java static-rules linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="pmd",
    display_name="PMD",
    languages=("java",),
    file_extensions=(".java",),
    executable="pmd",
    argv_template=("pmd",
 "check",
 "--format",
 "json",
 "--dir",
 "{file}",
 "--rulesets",
 "{ruleset}"),
    stdin_mode="unsupported",
    parser="json_generic",
    config_files=("pmd.xml", "ruleset.xml"),
    capabilities=("lint",),
    tier="recommended",
    install_group="language",
    install_hint="Install PMD from https://pmd.github.io/ (standalone distribution or via Maven/Gradle plugin).",
    homepage_url="https://pmd.github.io/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("pmd",),
)
