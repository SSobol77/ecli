#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build-and-package-opensuse-rpm.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# Build an openSUSE/SUSE-oriented RPM using the shared RPM packaging flow.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RPM_PLATFORM_LABEL="${RPM_PLATFORM_LABEL:-opensuse}" \
RPM_DEPENDS="${RPM_DEPENDS:-libncurses6;libyaml-0-2}" \
  "${PROJECT_ROOT}/scripts/build-and-package-rpm.sh"
