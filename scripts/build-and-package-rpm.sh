#!/usr/bin/env bash
# ==============================================================================
# Build and package ECLI into a .rpm file (RHEL/AlmaLinux/Rocky/Fedora family)
#
# Notes:
# - Do NOT touch $HOME. The app (utils.py) creates ~/.config/ecli on first run.
# - We embed config.toml into the PyInstaller bundle so utils.py can copy it.
# - We force-bundle aiohttp stack and console deps; prefer using ecli.spec.
# - Final artifact: releases/<version>/ecli-<version>-1.x86_64.rpm
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli"
MAINTAINER="Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE="https://ecli.io"
LICENSE="MIT"
CATEGORY="Applications/Editors"

# IMPORTANT: use python3.11 explicitly (EL9 python3 may be 3.9)
VERSION="$(python3.11 - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
if [[ -z "${VERSION}" ]]; then
  echo "Error: Could not read version from pyproject.toml" >&2
  exit 1
fi

ARCH_RPM="x86_64"
RELEASES_DIR="releases/${VERSION}"
FINAL_RPM_PATH="${RELEASES_DIR}/${PACKAGE_NAME}-${VERSION}-1.${ARCH_RPM}.rpm"
STAGING_DIR="build/rpm_staging"

echo "==> Version: ${VERSION}"
echo "==> Output : ${FINAL_RPM_PATH}"

# ------------------------------------------------------------------------------
# Stage 1: Build onefile executable with PyInstaller
# ------------------------------------------------------------------------------
echo "==> Cleaning previous artifacts"
rm -rf build/ dist/

echo "==> Building executable with PyInstaller"
if [[ -f "ecli.spec" ]]; then
  # ecli.spec already:
  # - adds pathex=src
  # - embeds config.toml
  # - forces aiohttp stack + chardet
  # - attaches runtime hook
  pyinstaller ecli.spec --clean --noconfirm
else
  # Fallback if spec not used
  pyinstaller main.py \
    --name "${PACKAGE_NAME}" \
    --onefile \
    --clean \
    --noconfirm \
    --strip \
    --paths "src" \
    --add-data "config.toml:." \
    --hidden-import=ecli \
    --hidden-import=dotenv       --collect-all=dotenv \
    --hidden-import=toml \
    --hidden-import=aiohttp      --collect-all=aiohttp \
    --hidden-import=aiosignal    --collect-all=aiosignal \
    --hidden-import=yarl         --collect-all=yarl \
    --hidden-import=multidict    --collect-all=multidict \
    --hidden-import=frozenlist   --collect-all=frozenlist \
    --hidden-import=chardet      --collect-all=chardet \
    --hidden-import=pyperclip    --collect-all=pyperclip \
    --hidden-import=wcwidth      --collect-all=wcwidth \
    --hidden-import=pygments     --collect-all=pygments \
    --runtime-hook packaging/pyinstaller/rthooks/force_imports.py
fi

# Detect PyInstaller output (onefile or onedir)
EXECUTABLE=""
if [[ -x "dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "dist/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}"
fi
if [[ -z "${EXECUTABLE}" ]]; then
  echo "Error: PyInstaller output not found in dist/." >&2
  exit 1
fi
echo "==> Built: ${EXECUTABLE}"

# ------------------------------------------------------------------------------
# Stage 2: Prepare staging layout (FHS)
# ------------------------------------------------------------------------------
echo "==> Preparing staging layout"
rm -rf "${STAGING_DIR}"
mkdir -p \
  "${STAGING_DIR}/usr/bin" \
  "${STAGING_DIR}/usr/share/applications" \
  "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps" \
  "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}"
mkdir -p "${RELEASES_DIR}"

# Binary
install -m 755 "${EXECUTABLE}" "${STAGING_DIR}/usr/bin/${PACKAGE_NAME}"

# Desktop entry (use provided or minimal fallback)
if [[ -f "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" ]]; then
  install -m 644 "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" \
    "${STAGING_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop"
else
  cat > "${STAGING_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop" <<EOF
[Desktop Entry]
Name=ECLI
Comment=Fast terminal code editor
Exec=${PACKAGE_NAME}
Icon=${PACKAGE_NAME}
Terminal=true
Type=Application
Categories=Development;TextEditor;
StartupNotify=false
EOF
fi

# Icon
if [[ -f "img/logo_m.png" ]]; then
  install -m 644 "img/logo_m.png" \
    "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
fi

# Docs
[[ -f "LICENSE"   ]] && install -m 644 "LICENSE"   "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"
[[ -f "README.md" ]] && install -m 644 "README.md" "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md"

# ------------------------------------------------------------------------------
# Stage 3: Build .rpm with fpm
# ------------------------------------------------------------------------------
echo "==> Building .rpm with fpm"
fpm -s dir -t rpm \
  -n "${PACKAGE_NAME}" \
  -v "${VERSION}" \
  -a "${ARCH_RPM}" \
  --maintainer "${MAINTAINER}" \
  --description "Ecli — terminal DevOps editor with AI and Git integration" \
  --url "${HOMEPAGE}" \
  --license "${LICENSE}" \
  --category "${CATEGORY}" \
  --depends "glibc" \
  --after-install "packaging/linux/fpm-common/postinst" \
  --before-remove "packaging/linux/fpm-common/prerm" \
  --after-remove  "packaging/linux/fpm-common/postrm" \
  --rpm-os linux \
  --package "${FINAL_RPM_PATH}" \
  -C "${STAGING_DIR}" \
  usr

# ------------------------------------------------------------------------------
# Stage 4: Verify
# ------------------------------------------------------------------------------
echo "==> Verifying package"
rpm -qip "${FINAL_RPM_PATH}" || true
rpm -qlp "${FINAL_RPM_PATH}" | head -20 || true

echo "✅ DONE: ${FINAL_RPM_PATH}"
