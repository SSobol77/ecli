#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build-and-package-slackware.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# Build a traditional Slackware .txz package from the PyInstaller binary.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli"
VERSION="$(awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $2; exit}' pyproject.toml)"
[[ -n "${VERSION}" ]] || {
  echo "ERROR: Cannot read version from pyproject.toml" >&2
  exit 1
}
python3 scripts/check_runtime_imports.py

RAW_ARCH="$(uname -m 2>/dev/null || echo x86_64)"
case "${RAW_ARCH}" in
  amd64|x86_64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="aarch64" ;;
  *) ARCH="${RAW_ARCH}" ;;
esac

command -v makepkg >/dev/null 2>&1 || {
  echo "Slackware makepkg is required to build .txz packages." >&2
  exit 5
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "sha256sum is required to write package checksums." >&2
  exit 5
}

RELEASES_DIR="releases/${VERSION}"
BUILD_ROOT="build/slackware"
STAGING_ROOT="${BUILD_ROOT}/pkg"
FINAL_TXZ="${PROJECT_ROOT}/${RELEASES_DIR}/${PACKAGE_NAME}_${VERSION}_slackware_${ARCH}.txz"

echo "==> Building ECLI PyInstaller binary"
bash "${PROJECT_ROOT}/scripts/build_pyinstaller_linux.sh"

EXECUTABLE=""
if [[ -x "${PROJECT_ROOT}/dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="${PROJECT_ROOT}/dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "${PROJECT_ROOT}/dist/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="${PROJECT_ROOT}/dist/${PACKAGE_NAME}"
fi
[[ -n "${EXECUTABLE}" ]] || {
  echo "ERROR: PyInstaller output not found under dist/." >&2
  exit 1
}

echo "==> Staging Slackware package"
rm -rf "${BUILD_ROOT}"
mkdir -p \
  "${STAGING_ROOT}/usr/bin" \
  "${STAGING_ROOT}/usr/share/applications" \
  "${STAGING_ROOT}/usr/share/icons/hicolor/256x256/apps" \
  "${STAGING_ROOT}/usr/doc/${PACKAGE_NAME}-${VERSION}" \
  "${STAGING_ROOT}/install" \
  "${RELEASES_DIR}"

install -m 0755 "${EXECUTABLE}" "${STAGING_ROOT}/usr/bin/${PACKAGE_NAME}"
install -m 0644 "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" \
  "${STAGING_ROOT}/usr/share/applications/${PACKAGE_NAME}.desktop"
install -m 0644 "src/ecli/assets/ecli.png" \
  "${STAGING_ROOT}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
[[ -f "LICENSE" ]] && install -m 0644 "LICENSE" "${STAGING_ROOT}/usr/doc/${PACKAGE_NAME}-${VERSION}/LICENSE"
[[ -f "README.md" ]] && install -m 0644 "README.md" "${STAGING_ROOT}/usr/doc/${PACKAGE_NAME}-${VERSION}/README.md"

cat > "${STAGING_ROOT}/install/slack-desc" <<EOF
${PACKAGE_NAME}: ${PACKAGE_NAME} (terminal-first engineering operations workbench)
${PACKAGE_NAME}:
${PACKAGE_NAME}: ECLI is a terminal-first engineering operations workbench.
${PACKAGE_NAME}: It combines a curses editor with operational diagnostics,
${PACKAGE_NAME}: command-plan previews, Git visibility, and service panels.
${PACKAGE_NAME}:
${PACKAGE_NAME}: Homepage: https://www.ecli.io
${PACKAGE_NAME}: Repository: https://github.com/SSobol77/ecli
${PACKAGE_NAME}:
${PACKAGE_NAME}: License: GPL-2.0-only
${PACKAGE_NAME}:
EOF

echo "==> Building Slackware package"
rm -f "${FINAL_TXZ}" "${FINAL_TXZ}.sha256"
(cd "${STAGING_ROOT}" && makepkg -l y -c n "${FINAL_TXZ}")

echo "==> Writing checksum"
(cd "${RELEASES_DIR}" && sha256sum "$(basename "${FINAL_TXZ}")" > "$(basename "${FINAL_TXZ}").sha256")
scripts/verify_runtime.sh "${FINAL_TXZ}"

echo "DONE: ${FINAL_TXZ}"
