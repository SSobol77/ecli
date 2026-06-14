#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build-and-package-macos.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# ==============================================================================
# ECLI - macOS Universal2 packaging (PyInstaller x86_64 + arm64 -> DMG)
#
# Strict outputs:
#   releases/<version>/ecli_<version>_macos_universal2.dmg
#   releases/<version>/ecli_<version>_macos_universal2.dmg.sha256
#
# Requirements:
#   - macOS 14 Apple Silicon runner or host with Rosetta available
#   - Python 3.11+
#   - PyInstaller
#   - Xcode command line tools: arch, lipo, codesign, hdiutil
#
# Phase 1 policy:
#   - ad-hoc codesign only
#   - no Apple Developer ID
#   - no notarization
#   - no stapling
#
# Icon policy:
#   - The canonical PNG is packaged at src/ecli/assets/ecli.png.
#   - A macOS .app bundle requires .icns; this script uses img/logo_m.icns when
#     present and otherwise leaves the bundle icon unset rather than adding a
#     non-deterministic conversion dependency.
# ==============================================================================

set -euo pipefail

log() { printf "\033[1;36m==>\033[0m %s\n" "$*"; }
ok() { printf "\033[32mOK\033[0m  %s\n" "$*"; }
err() { printf "\033[31mERR\033[0m %s\n" "$*" >&2; }

require_tool() {
  command -v "$1" >/dev/null 2>&1 || {
    err "Missing required tool: $1"
    exit 5
  }
}

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ "$(uname -s)" != "Darwin" ]; then
  err "macOS packaging must run on Darwin."
  exit 1
fi

PYTHON_BIN="${PYTHON:-python3}"
SPEC_FILE="${PROJECT_ROOT}/packaging/pyinstaller/ecli.spec"
APP_NAME="ECLI"
MACOS_ARCH="universal2"

require_tool arch
require_tool lipo
require_tool codesign
require_tool hdiutil
require_tool shasum
command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  err "Missing Python interpreter: $PYTHON_BIN"
  exit 5
}

log "Reading version from pyproject.toml..."
VERSION="$("$PYTHON_BIN" - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
[ -n "${VERSION:-}" ] || {
  err "Cannot read [project].version"
  exit 1
}
ok "Version: ${VERSION}"

log "Checking production runtime imports..."
"$PYTHON_BIN" scripts/check_runtime_imports.py

RELEASES_DIR="releases/${VERSION}"
PKG_NAME_BASE="ecli_${VERSION}_macos_${MACOS_ARCH}"
DMG_PATH="${RELEASES_DIR}/${PKG_NAME_BASE}.dmg"
SHA_PATH="${DMG_PATH}.sha256"
UNIVERSAL_DIR="build/macos_universal2"
UNIVERSAL_BIN="${UNIVERSAL_DIR}/ecli"

log "Checking Python architecture support..."
arch -x86_64 "$PYTHON_BIN" -c 'import platform; print("python-x86_64", platform.machine())'
arch -arm64 "$PYTHON_BIN" -c 'import platform; print("python-arm64", platform.machine())'

build_arch() {
  local arch_name="$1"
  local arch_flag="$2"
  local venv_dir="build/macos_venv_${arch_name}"
  local build_dir="build/macos_${arch_name}"
  local dist_dir="dist/macos_${arch_name}"
  local output="${dist_dir}/ecli"

  log "Preparing ${arch_name} Python environment..."
  rm -rf "$venv_dir"
  "$PYTHON_BIN" -m venv "$venv_dir"
  arch "$arch_flag" "$venv_dir/bin/python" -m pip install --upgrade pip wheel setuptools
  arch "$arch_flag" "$venv_dir/bin/python" -m pip install --upgrade -e ".[dev]"

  log "Building ${arch_name} PyInstaller binary..."
  rm -rf "$build_dir" "$dist_dir"
  ECLI_REPO_ROOT="$PROJECT_ROOT" \
  ECLI_PYINSTALLER_ONEDIR=0 \
  ECLI_BUILD_MACOS_APP=0 \
    arch "$arch_flag" "$venv_dir/bin/python" -m PyInstaller \
      "$SPEC_FILE" \
      --clean \
      --noconfirm \
      --workpath "$build_dir" \
      --distpath "$dist_dir"

  [ -x "$output" ] || {
    err "PyInstaller output missing: $output"
    exit 1
  }
  lipo -info "$output"
  ok "Built ${arch_name}: $output"
}

log "Cleaning previous macOS build artifacts..."
rm -rf \
  build/macos_venv_x86_64 \
  build/macos_venv_arm64 \
  build/macos_x86_64 \
  build/macos_arm64 \
  "$UNIVERSAL_DIR" \
  dist/macos_x86_64 \
  dist/macos_arm64

build_arch "x86_64" "-x86_64"
build_arch "arm64" "-arm64"

log "Merging binaries into Universal2 executable..."
mkdir -p "$UNIVERSAL_DIR"
lipo -create "dist/macos_x86_64/ecli" "dist/macos_arm64/ecli" -output "$UNIVERSAL_BIN"
chmod 755 "$UNIVERSAL_BIN"
LIPO_INFO="$(lipo -info "$UNIVERSAL_BIN")"
printf '%s\n' "$LIPO_INFO"
case "$LIPO_INFO" in
  *x86_64*arm64*|*arm64*x86_64*) ;;
  *)
    err "Universal2 binary does not contain both x86_64 and arm64."
    exit 1
    ;;
esac
ok "Universal2 binary: $UNIVERSAL_BIN"

log "Applying ad-hoc codesign..."
# No --options runtime: Phase 1 explicitly defers hardened runtime and notarization.
codesign --sign - --force "$UNIVERSAL_BIN"
codesign --verify --verbose "$UNIVERSAL_BIN"
ok "Ad-hoc signature verified."

log "Creating DMG staging tree..."
mkdir -p "$RELEASES_DIR"
printf 'MACOS_ARCH=universal2\n' > "$RELEASES_DIR/.macos.env"

DMG_STAGING="build/macos_dmg"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"

if [ "${ECLI_BUILD_MACOS_APP:-0}" = "1" ]; then
  APP_DIR="${DMG_STAGING}/${APP_NAME}.app"
  CONTENTS="${APP_DIR}/Contents"
  MACOS_DIR="${CONTENTS}/MacOS"
  RES_DIR="${CONTENTS}/Resources"
  mkdir -p "$MACOS_DIR" "$RES_DIR"
  install -m 755 "$UNIVERSAL_BIN" "${MACOS_DIR}/ecli"
  if [ -f "img/logo_m.icns" ]; then
    install -m 644 "img/logo_m.icns" "${RES_DIR}/AppIcon.icns"
    ICON_PLIST_ENTRY='  <key>CFBundleIconFile</key><string>AppIcon</string>'
  else
    ICON_PLIST_ENTRY=''
    err "No deterministic .icns asset found; macOS app icon is not set."
  fi
  cat > "${CONTENTS}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>io.ecli.editor</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleExecutable</key><string>ecli</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
${ICON_PLIST_ENTRY}
</dict>
</plist>
EOF
  codesign --sign - --force --deep "$APP_DIR"
  codesign --verify --verbose "$APP_DIR"
  ln -s /Applications "$DMG_STAGING/Applications"
else
  install -m 755 "$UNIVERSAL_BIN" "$DMG_STAGING/ecli"
fi

log "Creating compressed DMG..."
rm -f "$DMG_PATH" "$SHA_PATH"
VOL_NAME="ECLI-${VERSION}"
DMG_TMP="${DMG_PATH%.dmg}-tmp.dmg"
rm -f "$DMG_TMP"
hdiutil create -volname "$VOL_NAME" -srcfolder "$DMG_STAGING" -ov -fs HFS+ -format UDRW "$DMG_TMP"
hdiutil convert "$DMG_TMP" -format UDZO -imagekey zlib-level=9 -o "$DMG_PATH"
rm -f "$DMG_TMP"

log "Writing SHA256 sidecar..."
(cd "$RELEASES_DIR" && shasum -a 256 "$(basename "$DMG_PATH")" > "$(basename "$DMG_PATH").sha256")

[ -f "$DMG_PATH" ] || {
  err "Missing $DMG_PATH"
  exit 2
}
[ -f "$SHA_PATH" ] || {
  err "Missing $SHA_PATH"
  exit 3
}

ok "DMG: $DMG_PATH"
ok "SHA: $SHA_PATH"
./scripts/verify_runtime.sh "$DMG_PATH"
log "Done."
