# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/yamllint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the yamllint YAML linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="yamllint",
    display_name="yamllint",
    languages=("yaml",),
    file_extensions=(".yml", ".yaml"),
    executable="yamllint",
    argv_template=("yamllint", "--format", "parsable", "{file}"),
    stdin_mode="optional",
    parser="text_lines",
    config_files=(".yamllint", ".yamllint.yaml", ".yamllint.yml"),
    capabilities=("lint",),
    tier="recommended",
    install_group="core",
    install_hint="Install via pip: `pip install yamllint`. See https://yamllint.readthedocs.io/.",
    homepage_url="https://yamllint.readthedocs.io/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("yamllint",),
)
