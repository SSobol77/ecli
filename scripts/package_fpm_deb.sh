#!/bin/bash
# ==============================================================================
# scripts/package_fpm_deb.sh
#
# Creates a standalone .deb package and places it in the 'releases/' directory.
# This script first builds an executable with PyInstaller, then packages it.
# ==============================================================================

set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_ROOT=$(cd -- "${SCRIPT_DIR}/.." &> /dev/null && pwd)
cd "${PROJECT_ROOT}"

# --- Dependency Check ---
if ! command -v fpm &> /dev/null || ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: 'fpm' or 'pyinstaller' not found." >&2
    echo "Please ensure both are installed and in your PATH." >&2
    exit 1
fi

# --- Configuration ---
PACKAGE_VERSION=$(grep "^version =" pyproject.toml | cut -d '"' -f 2)
PACKAGE_NAME="ecli"
BUILD_DIR="build"
STAGING_DIR="${BUILD_DIR}/deb_staging_standalone"
RELEASES_DIR="releases/${PACKAGE_VERSION}"

echo "--- Starting standalone .deb package build for ${PACKAGE_NAME} v${PACKAGE_VERSION} ---"

# --- Step 1: Build the Standalone Executable with PyInstaller ---
echo "--> Step 1: Running PyInstaller to create the executable..."
pyinstaller main.py \
    --name "${PACKAGE_NAME}" \
    --onefile \
    --clean \
    --noconfirm \
    --add-data "config.toml:."

# --- Step 2: Cleanup and Preparation for Packaging ---
echo "--> Step 2: Cleaning up and preparing staging directory..."
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}/usr/bin"
mkdir -p "${STAGING_DIR}/usr/share/applications"
mkdir -p "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}"
mkdir -p "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps"

# --- Step 3: Copy Build Artifacts to Staging Directory ---
echo "--> Step 3: Copying artifacts into the staging directory..."
cp "dist/${PACKAGE_NAME}" "${STAGING_DIR}/usr/bin/"
cp "img/logo_m.png" "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps/ecli.png"
cp "packaging/linux/fpm-common/ecli.desktop" "${STAGING_DIR}/usr/share/applications/"
cp "README.md" "LICENSE" "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/"

# --- Step 4: Build the Final Package with FPM ---
echo "--> Step 4: Invoking FPM to create the final .deb package..."
fpm \
    -s dir \
    -t deb \
    -n "${PACKAGE_NAME}" \
    -v "${PACKAGE_VERSION}" \
    --architecture "amd64" \
    --maintainer "Siergej Sobolewski <s.sobolewski@hotmail.com>" \
    --description "A fast, modern, and extensible terminal-based code editor (standalone)." \
    --url "https://ecli.io" \
    --license "Apache-2.0" \
    --category "editors" \
    --deb-priority "optional" \
    --depends libc6 \
    --after-install "packaging/linux/fpm-common/postinst" \
    --after-remove "packaging/linux/fpm-common/postrm" \
    -C "${STAGING_DIR}" \
    .

# --- Step 5: Organize Release Artifacts ---
echo "--> Step 5: Moving package to the releases directory..."
mkdir -p "${RELEASES_DIR}"
PACKAGE_FILENAME="${PACKAGE_NAME}_${PACKAGE_VERSION}_amd64.deb"
mv "${PACKAGE_FILENAME}" "${RELEASES_DIR}/"

# --- Completion ---
echo ""
echo "--- Standalone .deb package build completed successfully! ---"
echo "Package saved to: ${RELEASES_DIR}/${PACKAGE_FILENAME}"
echo ""

exit 0
