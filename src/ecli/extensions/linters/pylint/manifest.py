# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/pylint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Pylint optional deep-lint Python microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="pylint",
    display_name="Pylint",
    languages=("python",),
    file_extensions=(".py", ".pyi"),
    executable="pylint",
    argv_template=("pylint", "--output-format=json", "{file}"),
    stdin_mode="unsupported",
    parser="json_generic",
    config_files=(".pylintrc", "pylintrc", "pyproject.toml", "setup.cfg"),
    capabilities=("lint",),
    tier="optional",
    install_group="language",
    install_hint="Optional deep-lint for Python, complementary to Ruff (not a replacement). Install via pip `pip install pylint`.",
    homepage_url="https://pylint.readthedocs.io/",
    enabled_by_default=False,
    bundled_with_full_install=False,
    package_hints=("pylint",),
)
