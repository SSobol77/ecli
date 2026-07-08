# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/taplo/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Taplo TOML linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="taplo",
    display_name="Taplo",
    languages=("toml",),
    file_extensions=(".toml",),
    executable="taplo",
    argv_template=("taplo", "lint", "{file}"),
    stdin_mode="unsupported",
    parser="text_lines",
    config_files=("taplo.toml", ".taplo.toml"),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="core",
    install_hint="Install via `cargo install taplo-cli --locked`. See https://taplo.tamasfe.dev/cli/installation/.",
    homepage_url="https://taplo.tamasfe.dev/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("taplo-cli",),
)
