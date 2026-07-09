# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/eslint/package_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Package delivery contract skeleton for the ESLint microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import PackageContract


PACKAGE_CONTRACT = PackageContract(
    service_name="eslint",
    mandatory_for_full_install=False,
    bundled_with_full_install=False,
    binary_names=("eslint",),
    version_probe=("eslint", "--version"),
    delivery_notes="Optional npm package; legacy fallback, not part of the default ECLI Full bundle.",
    allowed_install_mechanisms=(
        "language-package-manager",
        "ecli-managed-tools",
        "nix-derivation",
    ),
    source_url="https://eslint.org/",
)
