# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/eslint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the ESLint legacy/optional web linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="eslint",
    display_name="ESLint",
    languages=("javascript", "javascriptreact", "typescript", "typescriptreact"),
    file_extensions=(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"),
    executable="eslint",
    argv_template=("eslint", "--format", "json", "--no-color", "{file}"),
    stdin_mode="optional",
    parser="eslint_json",
    config_files=(".eslintrc",
 ".eslintrc.js",
 ".eslintrc.cjs",
 ".eslintrc.json",
 ".eslintrc.yml",
 ".eslintrc.yaml",
 "eslint.config.js",
 "eslint.config.mjs",
 "eslint.config.cjs",
 "package.json"),
    capabilities=("lint", "fix"),
    tier="legacy",
    install_group="web",
    install_hint="Legacy/optional fallback, superseded by Biome as the default web linter. Install via npm `npm install --save-dev eslint` only if you need an ESLint-specific rule set Biome does not cover.",
    homepage_url="https://eslint.org/",
    enabled_by_default=False,
    bundled_with_full_install=False,
    package_hints=("eslint",),
)
