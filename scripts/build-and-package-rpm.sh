#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: scripts/build-and-package-rpm.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

# ==============================================================================
# ECLI — Build and Package into an .rpm (runs inside AlmaLinux/RHEL container or locally)
#
# This script:
#   1) Enters project root deterministically.
#   2) Reads version from pyproject.toml (Python 3.11 tomllib; 3.10 tomli fallback).
#   3) Builds a standalone binary via PyInstaller (uses packaging/pyinstaller/ecli.spec if present).
#   4) Stages a minimal FHS payload for RPM.
#   5) Builds .rpm with FPM, places artifacts under releases/<version>/.
#   6) Normalizes file name to ecli_<version>_linux_<arch>.rpm and generates .sha256.
#
# Requirements in the build environment:
#   - python3.11 + pip, pyinstaller
#   - ruby + fpm
#   - rpm-build, redhat-rpm-config, rpmdevtools
#   - runtime libs are declared as Requires in the RPM (ncurses-libs, libyaml).
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Enter project root and export for child processes
# ------------------------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"
export PROJECT_ROOT

# ------------------------------------------------------------------------------
# Project metadata
# ------------------------------------------------------------------------------
PACKAGE_NAME="${PACKAGE_NAME:-ecli}"
MAINTAINER="${MAINTAINER:-Siergej Sobolewski <s.sobolewski@hotmail.com>}"
HOMEPAGE="${HOMEPAGE:-https://ecli.io}"
LICENSE="${LICENSE:-Apache-2.0}"
CATEGORY="${CATEGORY:-editors}"  # shows as "Group" in some RPM tools

# CPU arch label used in the normalized filename.
RAW_ARCH="$(uname -m 2>/dev/null || echo x86_64)"
case "${RAW_ARCH}" in
  amd64|x86_64) NORMALIZED_ARCH="x86_64" ;;
  aarch64|arm64) NORMALIZED_ARCH="arm64" ;;
  *) NORMALIZED_ARCH="${RAW_ARCH}" ;;
esac

# ------------------------------------------------------------------------------
# Read version from pyproject.toml (works on Py 3.10/3.11)
# ------------------------------------------------------------------------------
read_version() {
  python3.11 - <<'PY'
import os
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib

root = os.environ.get("PROJECT_ROOT", ".")
with open(os.path.join(root, "pyproject.toml"), "rb") as f:
    data = tomllib.load(f)
print(data["project"]["version"])
PY
}

VERSION="$(read_version || true)"
if [[ -z "${VERSION}" ]]; then
  echo "ERROR: Cannot read version from pyproject.toml" >&2
  exit 1
fi
export VERSION
echo "==> Version: ${VERSION}"

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
BUILD_DIR="${BUILD_DIR:-build/rpm}"
STAGING_DIR="${STAGING_DIR:-${BUILD_DIR}/staging}"
DOC_DIR="${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}"
MAN_DIR="${STAGING_DIR}/usr/share/man/man1"
BIN_DIR="${STAGING_DIR}/usr/bin"
APPS_DIR="${STAGING_DIR}/usr/share/applications"
ICON_DIR="${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps"

RELEASES_DIR="${RELEASES_DIR:-releases/${VERSION}}"
mkdir -p "${RELEASES_DIR}"
printf 'LINUX_ARCH := %s\n' "${NORMALIZED_ARCH}" > "${RELEASES_DIR}/.linux.env"

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required tool: $1"
}

# ------------------------------------------------------------------------------
# Check build-time tools
# ------------------------------------------------------------------------------
echo "==> Checking build tools"
need python3.11
need pyinstaller
need fpm
need rpmbuild    # provided by rpm-build
need gzip

# ------------------------------------------------------------------------------
# Build binary with PyInstaller
# ------------------------------------------------------------------------------
echo "==> Building executable with PyInstaller"
rm -rf "${BUILD_DIR}"
mkdir -p "${STAGING_DIR}" "${DOC_DIR}" "${MAN_DIR}" "${BIN_DIR}" "${APPS_DIR}" "${ICON_DIR}"

if [[ -f "packaging/pyinstaller/ecli.spec" ]]; then
  pyinstaller packaging/pyinstaller/ecli.spec --clean --noconfirm
else
  # Fallback: single-file CLI with common dynamic deps collected
  pyinstaller main.py \
    --name "${PACKAGE_NAME}" \
    --onefile --clean --noconfirm --strip \
    --paths "src" \
    --add-data "config.toml:." \
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

EXECUTABLE=""
if [[ -x "dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "dist/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}"
fi
[[ -n "${EXECUTABLE}" ]] || die "PyInstaller output not found in dist/"

# ------------------------------------------------------------------------------
# Stage FHS payload
# ------------------------------------------------------------------------------
echo "==> Staging payload (FHS)"
install -m 0755 "${EXECUTABLE}" "${BIN_DIR}/${PACKAGE_NAME}"

# Desktop file
if [[ -f "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" ]]; then
  install -m 0644 "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" \
    "${APPS_DIR}/${PACKAGE_NAME}.desktop"
else
  cat > "${APPS_DIR}/${PACKAGE_NAME}.desktop" <<EOF
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

# Icon (optional)
if [[ -f "src/ecli/assets/ecli.png" ]]; then
  install -m 0644 "src/ecli/assets/ecli.png" "${ICON_DIR}/${PACKAGE_NAME}.png"
fi

# Docs (gzip README/LICENSE if present)
[[ -f "LICENSE"   ]] && install -m 0644 "LICENSE"   "${DOC_DIR}/LICENSE"
[[ -f "README.md" ]] && install -m 0644 "README.md" "${DOC_DIR}/README.md"
[[ -f "${DOC_DIR}/README.md" ]] && gzip -9fn "${DOC_DIR}/README.md" || true
[[ -f "${DOC_DIR}/LICENSE"   ]] && gzip -9fn "${DOC_DIR}/LICENSE"   || true

# Man page (generate minimal if missing)
if [[ ! -f "man/${PACKAGE_NAME}.1" ]]; then
  MANFILE="${MAN_DIR}/${PACKAGE_NAME}.1"
  cat > "${MANFILE}" <<EOF
.TH ${PACKAGE_NAME^^} 1 "$(date +"%B %Y")" "${PACKAGE_NAME} ${VERSION}" "User Commands"
.SH NAME
${PACKAGE_NAME} - Terminal code editor
.SH SYNOPSIS
.B ${PACKAGE_NAME}
[\fIOPTIONS\fR] [\fIFILE\fR...]
.SH DESCRIPTION
${PACKAGE_NAME^^} is a fast terminal code editor with AI and Git integration.
.SH OPTIONS
\fB--help\fR     Show help
\fB--version\fR  Show version
.SH AUTHOR
${MAINTAINER%% <*}
.SH HOMEPAGE
${HOMEPAGE}
EOF
  gzip -f "${MANFILE}"
else
  install -m 0644 "man/${PACKAGE_NAME}.1" "${MAN_DIR}/${PACKAGE_NAME}.1"
  gzip -f "${MAN_DIR}/${PACKAGE_NAME}.1"
fi

# ------------------------------------------------------------------------------
# Build RPM with FPM
# ------------------------------------------------------------------------------
# Note: On EL9, libtinfo is provided by ncurses-libs.
# We declare runtime deps close to what the Debian package uses.
echo "==> Building .rpm with FPM"
TMP_RPM_OUT="${RELEASES_DIR}/${PACKAGE_NAME}-${VERSION}.rpm"  # FPM will override naming; we just set an output path

fpm -s dir -t rpm \
  -n "${PACKAGE_NAME}" \
  -v "${VERSION}" \
  --maintainer "${MAINTAINER}" \
  --description "Ecli — terminal DevOps editor with AI and Git integration" \
  --url "${HOMEPAGE}" \
  --license "${LICENSE}" \
  --category "${CATEGORY}" \
  --rpm-os linux \
  --rpm-summary "Terminal DevOps editor with AI and Git integration" \
  --depends "ncurses-libs" \
  --depends "libyaml" \
  --rpm-auto-add-directories \
  --after-install "packaging/linux/fpm-common/postinst" \
  --before-remove "packaging/linux/fpm-common/prerm" \
  --after-remove  "packaging/linux/fpm-common/postrm" \
  --package "${TMP_RPM_OUT}" \
  -C "${STAGING_DIR}" usr

# Find the actual rpm file produced (FPM may add dist/release suffixes)
echo "==> Locating final RPM"
ACTUAL_RPM="$(ls -1 "${RELEASES_DIR}"/${PACKAGE_NAME}-*.rpm 2>/dev/null | head -1 || true)"
[[ -n "${ACTUAL_RPM}" && -f "${ACTUAL_RPM}" ]] || die "RPM not found under ${RELEASES_DIR}"

# ------------------------------------------------------------------------------
# Normalize file name and generate SHA256
# ------------------------------------------------------------------------------
NORMALIZED_RPM="${RELEASES_DIR}/${PACKAGE_NAME}_${VERSION}_linux_${NORMALIZED_ARCH}.rpm"
if [[ "${ACTUAL_RPM}" != "${NORMALIZED_RPM}" ]]; then
  cp -f "${ACTUAL_RPM}" "${NORMALIZED_RPM}"
fi

echo "==> Generating SHA-256 checksum"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "${RELEASES_DIR}" && sha256sum "$(basename "${NORMALIZED_RPM}")" > "$(basename "${NORMALIZED_RPM}").sha256")
elif command -v shasum >/dev/null 2>&1; then
  (cd "${RELEASES_DIR}" && shasum -a 256 "$(basename "${NORMALIZED_RPM}")" > "$(basename "${NORMALIZED_RPM}").sha256")
else
  echo "WARNING: no sha256 tool found (sha256sum/shasum). Skipping checksum." >&2
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo "✅ DONE"
echo "RPM (actual): ${ACTUAL_RPM}"
echo "RPM (normalized): ${NORMALIZED_RPM}"
[[ -f "${NORMALIZED_RPM}.sha256" ]] && echo "SHA256: ${NORMALIZED_RPM}.sha256"

# Optional quick metadata check (does not fail the build)
if command -v rpm >/dev/null 2>&1; then
  echo "==> RPM metadata (quick peek):"
  rpm -qpi "${ACTUAL_RPM}" | sed -n '1,20p' || true
fi
