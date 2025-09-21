#!/bin/bash
# ==============================================================================
# scripts/build_pyinstaller_linux.sh
#
# Builds a standalone executable for Linux using PyInstaller.
# The output will be a single file in the 'dist/' directory.
# ==============================================================================

set -euo pipefail
PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &> /dev/null && pwd)
cd "${PROJECT_ROOT}"

echo "--- Building standalone Linux executable with PyInstaller ---"

# Clean up previous builds
rm -rf build/ dist/

# Get the package name from main.spec or pyproject.toml
# We'll assume the main entry point is main.py for this example.
PACKAGE_NAME="ecli"

pyinstaller main.py \
    --name "${PACKAGE_NAME}" \
    --onefile \
    --clean \
    --noconfirm \
    --additional-hooks-dir=./hooks # Optional: for complex libraries

echo "--- Executable created at: dist/${PACKAGE_NAME} ---"
