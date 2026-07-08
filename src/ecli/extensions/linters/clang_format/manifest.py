# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/clang_format/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Clang-Format C/C++ formatting-check microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="clang-format",
    display_name="Clang-Format",
    languages=("c", "cpp"),
    file_extensions=(".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"),
    executable="clang-format",
    argv_template=("clang-format", "--dry-run", "--Werror", "{file}"),
    stdin_mode="unsupported",
    parser="text_lines",
    config_files=(".clang-format",),
    capabilities=("lint",),
    tier="recommended",
    install_group="systems",
    install_hint="Install Clang-Format via LLVM tooling: your OS package manager (e.g. `apt install clang-format`, `brew install clang-format`) or https://clang.llvm.org/docs/ClangFormat.html.",
    homepage_url="https://clang.llvm.org/docs/ClangFormat.html",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("clang-format",),
)
