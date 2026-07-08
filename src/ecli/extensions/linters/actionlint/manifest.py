# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/actionlint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the actionlint GitHub Actions linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="actionlint",
    display_name="actionlint",
    languages=("github-actions",),
    file_extensions=(".yml", ".yaml"),
    executable="actionlint",
    argv_template=("actionlint", "-color=never", "{file}"),
    stdin_mode="optional",
    parser="text_lines",
    config_files=(".github/actionlint.yaml", ".github/actionlint.yml"),
    capabilities=("lint",),
    tier="recommended",
    install_group="devops",
    install_hint="Install actionlint from https://github.com/rhysd/actionlint/releases or via `go install github.com/rhysd/actionlint/cmd/actionlint@latest`.",
    homepage_url="https://github.com/rhysd/actionlint",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("actionlint",),
)
