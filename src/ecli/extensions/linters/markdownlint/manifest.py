# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/markdownlint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the markdownlint-cli2 Markdown linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="markdownlint-cli2",
    display_name="markdownlint-cli2",
    languages=("markdown",),
    file_extensions=(".md", ".markdown"),
    executable="markdownlint-cli2",
    argv_template=("markdownlint-cli2", "{file}"),
    stdin_mode="unsupported",
    parser="text_lines",
    config_files=(".markdownlint-cli2.jsonc",
 ".markdownlint-cli2.yaml",
 ".markdownlint-cli2.cjs",
 ".markdownlintrc"),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="core",
    install_hint="Install via npm: `npm install --save-dev markdownlint-cli2`. See https://github.com/DavidAnson/markdownlint-cli2.",
    homepage_url="https://github.com/DavidAnson/markdownlint-cli2",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("markdownlint-cli2",),
)
