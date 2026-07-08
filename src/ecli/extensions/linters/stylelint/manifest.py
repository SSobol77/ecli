# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/stylelint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Stylelint optional CSS specialist microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="stylelint",
    display_name="Stylelint",
    languages=("css", "scss", "less"),
    file_extensions=(".css", ".scss", ".less"),
    executable="stylelint",
    argv_template=("stylelint", "--formatter", "json", "{file}"),
    stdin_mode="optional",
    parser="json_generic",
    config_files=(".stylelintrc",
 ".stylelintrc.json",
 ".stylelintrc.yaml",
 ".stylelintrc.yml",
 "stylelint.config.js",
 "stylelint.config.cjs"),
    capabilities=("lint", "fix"),
    tier="optional",
    install_group="web",
    install_hint="Optional CSS specialist for rule coverage beyond Biome's built-in CSS linting. Install via npm `npm install --save-dev stylelint`.",
    homepage_url="https://stylelint.io/",
    enabled_by_default=False,
    bundled_with_full_install=False,
    package_hints=("stylelint",),
)
