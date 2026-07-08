# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/hadolint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Hadolint Dockerfile linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="hadolint",
    display_name="Hadolint",
    languages=("dockerfile",),
    file_extensions=("Dockerfile", ".dockerfile"),
    executable="hadolint",
    argv_template=("hadolint", "--format", "json", "{file}"),
    stdin_mode="optional",
    parser="json_generic",
    config_files=(".hadolint.yaml", ".hadolint.yml"),
    capabilities=("lint",),
    tier="recommended",
    install_group="devops",
    install_hint="Install Hadolint from https://github.com/hadolint/hadolint/releases or your OS package manager.",
    homepage_url="https://github.com/hadolint/hadolint",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("hadolint",),
)
