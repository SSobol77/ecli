# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/biome/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Biome web linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="biome",
    display_name="Biome",
    languages=("javascript",
 "javascriptreact",
 "typescript",
 "typescriptreact",
 "json",
 "jsonc",
 "css",
 "graphql"),
    file_extensions=(".js",
 ".jsx",
 ".mjs",
 ".cjs",
 ".ts",
 ".tsx",
 ".json",
 ".jsonc",
 ".css",
 ".graphql"),
    executable="biome",
    argv_template=("biome", "lint", "--reporter=json", "{file}"),
    stdin_mode="optional",
    parser="biome_json",
    config_files=("biome.json", "biome.jsonc"),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="web",
    install_hint="Install via npm: `npm install --save-dev --save-exact @biomejs/biome`, or download a standalone binary from https://biomejs.dev/guides/getting-started/.",
    homepage_url="https://biomejs.dev/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("@biomejs/biome",),
    supersedes=("eslint", "stylelint"),
)
