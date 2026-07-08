# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/shellcheck/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the ShellCheck shell-script linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="shellcheck",
    display_name="ShellCheck",
    languages=("shellscript",),
    file_extensions=(".sh", ".bash", ".ksh", ".zsh"),
    executable="shellcheck",
    argv_template=("shellcheck", "--format=json", "{file}"),
    stdin_mode="optional",
    parser="json_generic",
    config_files=(".shellcheckrc",),
    capabilities=("lint",),
    tier="recommended",
    install_group="devops",
    install_hint="Install ShellCheck from https://www.shellcheck.net/ or your OS package manager (e.g. `apt install shellcheck`, `brew install shellcheck`).",
    homepage_url="https://www.shellcheck.net/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("shellcheck",),
)
