# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_spotbugs/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the SpotBugs Java bytecode-analysis microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="spotbugs",
    display_name="SpotBugs",
    languages=("java",),
    file_extensions=(".java", ".class"),
    executable="spotbugs",
    argv_template=("spotbugs", "-textui", "-xml", "{file}"),
    stdin_mode="unsupported",
    parser="xml_generic",
    config_files=("spotbugs-exclude.xml", "spotbugs.xml"),
    capabilities=("lint",),
    tier="recommended",
    install_group="language",
    install_hint="Install SpotBugs from https://spotbugs.github.io/ (standalone distribution or via Maven/Gradle plugin). Requires compiled Java classes; skipped for isolated source files without build output.",
    homepage_url="https://spotbugs.github.io/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("spotbugs",),
)
