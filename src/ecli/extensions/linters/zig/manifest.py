# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/zig/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Zig systems-language linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="zig",
    display_name="Zig",
    languages=("zig",),
    file_extensions=(".zig",),
    executable="zig",
    argv_template=("zig", "fmt", "--check", "--ast-check", "{file}"),
    stdin_mode="unsupported",
    parser="zig_text",
    config_files=(),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="systems",
    install_hint="Install the Zig toolchain from https://ziglang.org/download/ or your OS package manager.",
    homepage_url="https://ziglang.org/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("zig",),
)
