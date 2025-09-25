#!/usr/bin/env bash
# Build Ecli binary with PyInstaller (Linux)
# Prefers ecli.spec; falls back to main.py onefile.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli"
MAIN_SCRIPT="main.py"
SPEC_FILE="ecli.spec"

echo "==> Checking prerequisites"
command -v python3 >/dev/null
command -v pyinstaller >/dev/null

echo "==> Cleaning previous artifacts"
rm -rf build/ dist/

echo "==> Building with PyInstaller"
PYI_ARGS=(--onefile --clean --noconfirm --strip)

# Bundle optional configs if present
[[ -f "config.toml" ]] && PYI_ARGS+=(--add-data "config.toml:.")
[[ -d "config" ]] && PYI_ARGS+=(--add-data "config:config")

if [[ -f "${SPEC_FILE}" ]]; then
  pyinstaller "${SPEC_FILE}" --clean --noconfirm
else
  pyinstaller "${MAIN_SCRIPT}" --name "${PACKAGE_NAME}" "${PYI_ARGS[@]}"
fi

# Sanity check
if [[ -x "dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  echo "==> OK: dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "dist/${PACKAGE_NAME}" ]]; then
  echo "==> OK: dist/${PACKAGE_NAME}"
else
  echo "Build output not found in dist/. Aborting." >&2
  exit 1
fi
