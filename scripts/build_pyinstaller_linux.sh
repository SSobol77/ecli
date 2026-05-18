#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: scripts/build_pyinstaller_linux.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

# Build Ecli binary with PyInstaller (Linux)
# Prefers packaging/pyinstaller/ecli.spec; falls back to main.py onefile.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli"
MAIN_SCRIPT="main.py"
SPEC_FILE="packaging/pyinstaller/ecli.spec"

echo "==> Checking prerequisites"
command -v python3 >/dev/null
command -v pyinstaller >/dev/null
python3 scripts/check_runtime_imports.py

echo "==> Cleaning previous artifacts"
rm -rf build/ dist/

echo "==> Building with PyInstaller"
PYI_ARGS=(--onefile --clean --noconfirm --strip)

# Bundle optional configs if present
[[ -f "config.toml" ]] && PYI_ARGS+=(--add-data "config.toml:.")
[[ -f "pyproject.toml" ]] && PYI_ARGS+=(--add-data "pyproject.toml:.")
[[ -d "config" ]] && PYI_ARGS+=(--add-data "config:config")

if [[ -f "${SPEC_FILE}" ]]; then
  pyinstaller "${SPEC_FILE}" --clean --noconfirm
else
  pyinstaller "${MAIN_SCRIPT}" --name "${PACKAGE_NAME}" "${PYI_ARGS[@]}"
fi

# Sanity check
if [[ -x "dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  echo "==> OK: dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
  ./scripts/verify_runtime.sh --allow-nonrelease "dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "dist/${PACKAGE_NAME}" ]]; then
  echo "==> OK: dist/${PACKAGE_NAME}"
  ./scripts/verify_runtime.sh --allow-nonrelease "dist/${PACKAGE_NAME}"
else
  echo "Build output not found in dist/. Aborting." >&2
  exit 1
fi
