# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/golangci_lint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the golangci-lint Go linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="golangci-lint",
    display_name="golangci-lint",
    languages=("go",),
    file_extensions=(".go",),
    executable="golangci-lint",
    argv_template=("golangci-lint", "run", "--out-format=json"),
    stdin_mode="unsupported",
    parser="json_generic",
    config_files=(".golangci.yml", ".golangci.yaml", ".golangci.toml", ".golangci.json"),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="language",
    install_hint="Install golangci-lint from https://golangci-lint.run/usage/install/ (script, `go install`, or your OS package manager).",
    homepage_url="https://golangci-lint.run/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("golangci-lint",),
)
