# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/golangci_lint/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""golangci-lint linter microservice (manifest/package-contract skeleton only).

No provider.py in this migration: only Ruff has a fully working
provider. This microservice is metadata-only until a future stage
implements its runtime provider. See
docs/architecture/ecli-f4-linter-microservices-design.md.
"""

from ecli.extensions.linters.golangci_lint import (
    manifest,
    package_contract,
)


__all__ = [
    "manifest",
    "package_contract",
]
