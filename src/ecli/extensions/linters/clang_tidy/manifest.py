# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/clang_tidy/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Clang-Tidy C/C++ linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="clang-tidy",
    display_name="Clang-Tidy",
    languages=("c", "cpp"),
    file_extensions=(".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"),
    executable="clang-tidy",
    argv_template=("clang-tidy", "{file}", "--quiet", "--export-fixes=-"),
    stdin_mode="unsupported",
    parser="text_lines",
    config_files=("compile_commands.json", ".clang-tidy"),
    capabilities=("lint",),
    tier="recommended",
    install_group="systems",
    install_hint="Install Clang-Tidy via LLVM tooling: your OS package manager (e.g. `apt install clang-tidy`, `brew install llvm`) or https://clang.llvm.org/extra/clang-tidy/.",
    homepage_url="https://clang.llvm.org/extra/clang-tidy/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("clang-tidy",),
)
