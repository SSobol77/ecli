# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_checkstyle/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Checkstyle Java style linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="checkstyle",
    display_name="Checkstyle",
    languages=("java",),
    file_extensions=(".java",),
    executable="checkstyle",
    argv_template=("checkstyle", "-f", "xml", "-c", "{config}", "{file}"),
    stdin_mode="unsupported",
    parser="xml_generic",
    config_files=("checkstyle.xml", "config/checkstyle/checkstyle.xml"),
    capabilities=("lint",),
    tier="recommended",
    install_group="language",
    install_hint="Install Checkstyle from https://checkstyle.org/ (standalone jar or via Maven/Gradle plugin).",
    homepage_url="https://checkstyle.org/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("checkstyle",),
)
