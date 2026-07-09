# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/markdownlint/package_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Package delivery contract skeleton for the markdownlint-cli2 microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import PackageContract


PACKAGE_CONTRACT = PackageContract(
    service_name="markdownlint-cli2",
    mandatory_for_full_install=True,
    bundled_with_full_install=True,
    binary_names=("markdownlint-cli2",),
    version_probe=("markdownlint-cli2", "--version"),
    delivery_notes="npm package; bundled with ECLI Full where platform packaging allows.",
    allowed_install_mechanisms=(
        "language-package-manager",
        "ecli-managed-tools",
        "bundled-binary",
        "nix-derivation",
    ),
    source_url="https://github.com/DavidAnson/markdownlint-cli2",
)
