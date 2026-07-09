# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/clang_tidy/package_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Package delivery contract skeleton for the Clang-Tidy microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import PackageContract


PACKAGE_CONTRACT = PackageContract(
    service_name="clang-tidy",
    mandatory_for_full_install=True,
    bundled_with_full_install=True,
    binary_names=("clang-tidy",),
    version_probe=("clang-tidy", "--version"),
    delivery_notes="OS package dependency (LLVM tooling) or bundled binary; requires compile_commands.json / CMake context for full analysis, see the design doc section 11.1.",
    allowed_install_mechanisms=(
        "os-package-manager",
        "ecli-managed-tools",
        "bundled-binary",
        "nix-derivation",
    ),
    source_url="https://clang.llvm.org/extra/clang-tidy/",
)
