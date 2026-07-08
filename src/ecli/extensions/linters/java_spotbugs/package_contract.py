# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/java_spotbugs/package_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Package delivery contract skeleton for the SpotBugs microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import PackageContract


PACKAGE_CONTRACT = PackageContract(
    service_name="spotbugs",
    mandatory_for_full_install=True,
    bundled_with_full_install=True,
    binary_names=("spotbugs",),
    version_probe=("spotbugs", "-version"),
    delivery_notes="Standalone distribution or Maven/Gradle plugin; workspace/project-scoped, requires compiled classes (design doc section 12.3).",
)
