#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build-and-package-deb.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# ==============================================================================
# ECLI — Build and Package into a .deb (runs inside Debian/Ubuntu container or locally)
#
# This script:
#   1) Enters the project root deterministically.
#   2) Reads the version from pyproject.toml (Python 3.11 tomllib; 3.10 tomli fallback if needed).
#   3) Builds a standalone executable via PyInstaller (uses packaging/pyinstaller/ecli.spec if present; otherwise a safe fallback).
#   4) Stages a minimal FHS payload for Debian (/usr/bin, /usr/share/{applications,icons,doc,man}).
#   5) Produces a .deb with FPM and places artifacts under releases/<version>/.
#   6) Optionally generates a .sha256 checksum next to the .deb (if checksum step is enabled below).
#
# Build-time requirements expected in the environment:
#   - python3.11 + pip, pyinstaller
#   - ruby + fpm
#   - dpkg-dev utils (for validation) — optional
#
# Runtime dependencies declared in the package (via FPM):
#   - libncurses6, libncursesw6, libtinfo6, ncurses-term
#   - libyaml-0-2
#   - xclip | xsel (clipboard integration; may be set as Recommends if desired)
#
# Notes:
#   - Do NOT modify $HOME; the app will create ~/.config/ecli on first run.
#   - Desktop entry and icon are included when available.
#   - All outputs are written to releases/<version>/ to keep the repo clean.
# ==============================================================================


set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli"
MAINTAINER="Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE="https://ecli.io"
LICENSE="GPL-2.0-only"
CATEGORY="editors"
PYTHON_BIN="${PYTHON:-python3}"

VERSION="$("${PYTHON_BIN}" - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
[ -n "${VERSION}" ] || { echo "Cannot read version from pyproject.toml"; exit 1; }

echo "==> Checking production runtime imports"
"${PYTHON_BIN}" scripts/check_runtime_imports.py

ARCH_DEB="amd64"
RAW_ARCH="$(uname -m 2>/dev/null || echo x86_64)"
case "${RAW_ARCH}" in
  amd64|x86_64) FILENAME_ARCH="x86_64" ;;
  aarch64|arm64) FILENAME_ARCH="arm64" ;;
  *) FILENAME_ARCH="${RAW_ARCH}" ;;
esac
RELEASES_DIR="releases/${VERSION}"
FINAL_DEB_PATH="${RELEASES_DIR}/${PACKAGE_NAME}_${VERSION}_linux_${FILENAME_ARCH}.deb"
STAGING_DIR="build/deb_staging"

echo "==> Version: ${VERSION}"
rm -rf build/ dist/
rm -f "${FINAL_DEB_PATH}" "${FINAL_DEB_PATH}.sha256"

echo "==> Building executable with PyInstaller"
if [[ -f "packaging/pyinstaller/ecli.spec" ]]; then
  pyinstaller packaging/pyinstaller/ecli.spec --clean --noconfirm
else
  # Fallback: force src layout and critical deps
  pyinstaller main.py \
    --name "${PACKAGE_NAME}" \
    --onefile --clean --noconfirm --strip \
    --paths "src" \
    --add-data "config.toml:." \
    --add-data "pyproject.toml:." \
    --hidden-import=ecli \
    --hidden-import=dotenv --collect-all=dotenv \
    --hidden-import=toml \
    --hidden-import=aiohttp     --collect-all=aiohttp \
    --hidden-import=aiosignal   --collect-all=aiosignal \
    --hidden-import=yarl        --collect-all=yarl \
    --hidden-import=multidict   --collect-all=multidict \
    --hidden-import=frozenlist  --collect-all=frozenlist \
    --hidden-import=chardet     --collect-all=chardet \
    --runtime-hook packaging/pyinstaller/rthooks/force_imports.py
fi

# Detect PyInstaller output
EXECUTABLE=""
if [[ -x "dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "dist/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}"
fi
[ -n "${EXECUTABLE}" ] || { echo "PyInstaller output not found"; exit 1; }

echo "==> Preparing staging (FHS)"
rm -rf "${STAGING_DIR}"
mkdir -p \
  "${STAGING_DIR}/usr/bin" \
  "${STAGING_DIR}/usr/share/applications" \
  "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps" \
  "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}" \
  "${STAGING_DIR}/usr/share/man/man1" \
  "${RELEASES_DIR}"
printf 'LINUX_ARCH := %s\n' "${FILENAME_ARCH}" > "${RELEASES_DIR}/.linux.env"

install -m 755 "${EXECUTABLE}" "${STAGING_DIR}/usr/bin/${PACKAGE_NAME}"

# Desktop entry
if [[ -f "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" ]]; then
  install -m 644 "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" \
    "${STAGING_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop"
else
  cat > "${STAGING_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ECLI
Comment=Terminal-first engineering operations workbench
Exec=${PACKAGE_NAME}
Icon=${PACKAGE_NAME}
Terminal=true
Categories=Development;IDE;Utility;
StartupNotify=false
EOF
fi

# Icon
if [[ -f "src/ecli/assets/ecli.png" ]]; then
  install -m 644 "src/ecli/assets/ecli.png" \
    "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
fi

# Docs
[[ -f "LICENSE"   ]] && install -m 644 "LICENSE"   "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"
[[ -f "README.md" ]] && install -m 644 "README.md" "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md"
[[ -f "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md" ]] && gzip -9fn "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md" || true
[[ -f "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"   ]] && gzip -9fn "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"   || true

# Minimal man page, if missing
if [[ ! -f "man/${PACKAGE_NAME}.1" ]]; then
  cat > "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1" <<EOF
.TH ${PACKAGE_NAME^^} 1 "$(date +"%B %Y")" "${PACKAGE_NAME} ${VERSION}" "User Commands"
.SH NAME
${PACKAGE_NAME} - Terminal code editor
.SH SYNOPSIS
.B ${PACKAGE_NAME}
[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]
.SH DESCRIPTION
${PACKAGE_NAME^^} is a fast terminal code editor.
.SH OPTIONS
\\fB--help\\fR     Show help
\\fB--version\\fR  Show version
.SH AUTHOR
${MAINTAINER%% <*}
.SH REPORTING BUGS
${HOMEPAGE}
EOF
  gzip -f "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1"
else
  install -m 644 "man/${PACKAGE_NAME}.1" "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1"
  gzip -f "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1"
fi

echo "==> Building .deb with FPM"
fpm -s dir -t deb \
  -n "${PACKAGE_NAME}" \
  -v "${VERSION}" \
  -a "amd64" \
  --maintainer "${MAINTAINER}" \
  --description "Ecli — terminal DevOps editor with AI and Git integration" \
  --url "${HOMEPAGE}" \
  --license "${LICENSE}" \
  --category "${CATEGORY}" \
  --deb-priority optional \
  --deb-compression xz \
  --depends "libncurses6" \
  --depends "libncursesw6" \
  --depends "libtinfo6" \
  --depends "ncurses-term" \
  --depends "libyaml-0-2" \
  --depends "xclip | xsel" \
  --after-install "packaging/linux/fpm-common/postinst" \
  --before-remove "packaging/linux/fpm-common/prerm" \
  --after-remove  "packaging/linux/fpm-common/postrm" \
  --package "${FINAL_DEB_PATH}" \
  -C "${STAGING_DIR}" usr

echo "==> Verify"
dpkg-deb --info "${FINAL_DEB_PATH}" >/dev/null || true
dpkg-deb --contents "${FINAL_DEB_PATH}" | head -20 || true
scripts/verify_runtime.sh "${FINAL_DEB_PATH}"

echo "==> Generating SHA-256 checksum"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "${RELEASES_DIR}" && sha256sum "$(basename "${FINAL_DEB_PATH}")" > "$(basename "${FINAL_DEB_PATH}").sha256")
elif command -v shasum >/dev/null 2>&1; then
  (cd "${RELEASES_DIR}" && shasum -a 256 "$(basename "${FINAL_DEB_PATH}")" > "$(basename "${FINAL_DEB_PATH}").sha256")
else
  echo "WARNING: no sha256 tool found (sha256sum/shasum). Skipping checksum." >&2
fi

# instant validation
if command -v sha256sum >/dev/null 2>&1; then
  (cd "${RELEASES_DIR}" && sha256sum -c "$(basename "${FINAL_DEB_PATH}").sha256") || true
elif command -v shasum >/dev/null 2>&1; then
  (cd "${RELEASES_DIR}" && shasum -a 256 -c "$(basename "${FINAL_DEB_PATH}").sha256") || true
fi

echo "✅ DONE: ${FINAL_DEB_PATH}"
