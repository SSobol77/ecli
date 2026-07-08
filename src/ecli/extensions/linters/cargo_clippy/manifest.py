# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/cargo_clippy/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the Cargo Clippy Rust linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="cargo-clippy",
    display_name="Cargo Clippy",
    languages=("rust",),
    file_extensions=(".rs",),
    executable="cargo",
    argv_template=("cargo", "clippy", "--message-format=json"),
    stdin_mode="unsupported",
    parser="cargo_json",
    config_files=("Cargo.toml", "clippy.toml", ".clippy.toml"),
    capabilities=("lint", "fix"),
    tier="recommended",
    install_group="systems",
    install_hint="Included with the Rust toolchain: run `rustup component add clippy`.",
    homepage_url="https://doc.rust-lang.org/clippy/",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("clippy",),
)
