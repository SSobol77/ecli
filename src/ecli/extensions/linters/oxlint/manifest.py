# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/oxlint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Oxlint optional secondary web linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="oxlint",
    display_name="Oxlint",
    languages=("javascript", "javascriptreact", "typescript", "typescriptreact"),
    file_extensions=(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"),
    executable="oxlint",
    argv_template=("oxlint", "--format=json", "{file}"),
    stdin_mode="unsupported",
    parser="json_generic",
    config_files=(".oxlintrc.json",),
    capabilities=("lint", "fix"),
    tier="optional",
    install_group="web",
    install_hint="Optional high-performance secondary linter: install via npm `npm install --save-dev oxlint`. See https://oxc.rs/docs/guide/usage/linter.html.",
    homepage_url="https://oxc.rs/",
    enabled_by_default=False,
    bundled_with_full_install=False,
    package_hints=("oxlint",),
)
