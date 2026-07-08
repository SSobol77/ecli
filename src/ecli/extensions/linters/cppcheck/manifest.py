# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/cppcheck/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Cppcheck C/C++ secondary static analysis microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="cppcheck",
    display_name="Cppcheck",
    languages=("c", "cpp"),
    file_extensions=(".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"),
    executable="cppcheck",
    argv_template=("cppcheck",
 "--enable=warning,style,performance,portability",
 "--template=json",
 "{file}"),
    stdin_mode="unsupported",
    parser="text_lines",
    config_files=(".cppcheck", "cppcheck.cfg"),
    capabilities=("lint",),
    tier="recommended",
    install_group="systems",
    install_hint="Install Cppcheck via your OS package manager (e.g. `apt install cppcheck`, `brew install cppcheck`) or https://cppcheck.sourceforge.io/.",
    homepage_url="https://cppcheck.sourceforge.io/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("cppcheck",),
)
