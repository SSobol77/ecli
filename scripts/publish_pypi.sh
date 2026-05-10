#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: scripts/publish_pypi.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

# ECLI PyPI publish — placeholder.
#
# Actual PyPI publishing is performed by:
#   .github/workflows/release.yml  (job: publish-pypi)
#   via OIDC + PyPI Trusted Publishers, on tag push.
#
# Local maintainer publish from a clean workstation should be done
# explicitly with the documented procedure:
#
#   python3 -m build
#   python3 -m twine check --strict dist/*
#   python3 -m twine upload dist/*
#
# See docs/release/release-process.md for the full procedure including
# PyPI namespace pre-reservation and token rotation.
#
# This script intentionally exits non-zero to prevent accidental local
# publishes from automated chains (e.g. Makefile recipes, CI hooks).

set -euo pipefail

cat >&2 <<'MSG'
ERROR: scripts/publish_pypi.sh is not implemented.

PyPI publishing for ECLI is performed by .github/workflows/release.yml
on tag push. For maintainer-side local publish, follow the explicit
procedure in docs/release/release-process.md.
MSG

exit 1
