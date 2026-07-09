# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_checkstyle/package_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Package delivery contract skeleton for the Checkstyle microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import PackageContract


PACKAGE_CONTRACT = PackageContract(
    service_name="checkstyle",
    mandatory_for_full_install=True,
    bundled_with_full_install=True,
    binary_names=("checkstyle",),
    version_probe=("checkstyle", "--version"),
    delivery_notes="Standalone jar or Maven/Gradle plugin; bundled with ECLI Full where platform packaging allows.",
    allowed_install_mechanisms=(
        "jar-shim",
        "os-package-manager",
        "ecli-managed-tools",
        "verified-upstream-download",
        "nix-derivation",
    ),
    source_url="https://checkstyle.org/",
)
