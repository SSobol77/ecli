# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/tflint/manifest.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Product/runtime metadata for the TFLint Terraform linter microservice."""

from __future__ import annotations

from ecli.extensions.linters.core.registry import LinterDefinition


MANIFEST = LinterDefinition(
    name="tflint",
    display_name="TFLint",
    languages=("terraform",),
    file_extensions=(".tf", ".tfvars"),
    executable="tflint",
    argv_template=("tflint", "--format=json"),
    stdin_mode="unsupported",
    parser="json_generic",
    config_files=(".tflint.hcl",),
    capabilities=("lint",),
    tier="recommended",
    install_group="infra",
    install_hint="Install TFLint from https://github.com/terraform-linters/tflint#installation.",
    homepage_url="https://github.com/terraform-linters/tflint",
    enabled_by_default=True,
    bundled_with_full_install=True,
    package_hints=("tflint",),
)
