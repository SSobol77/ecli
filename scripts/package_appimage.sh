#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/package_appimage.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

set -euo pipefail

# This script:
# 1) builds the ecli (PyInstaller) binary for Linux,
# 2) places it in AppDir,
# 3) runs appimage-builder to create an .AppImage

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_VERSION="$(python3 - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
VERSION="${1:-$PROJECT_VERSION}"
if [[ "$VERSION" != "$PROJECT_VERSION" ]]; then
  echo "Requested AppImage version ${VERSION} does not match pyproject.toml version ${PROJECT_VERSION}." >&2
  exit 2
fi
RAW_ARCH="${2:-$(uname -m 2>/dev/null || echo x86_64)}"
case "$RAW_ARCH" in
  amd64|x86_64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) ARCH="$RAW_ARCH" ;;
esac
OUT_DIR="$PROJECT_ROOT/releases/$VERSION"
APPDIR="$PROJECT_ROOT/packaging/linux/appimage/AppDir"

mkdir -p "$OUT_DIR"
printf 'LINUX_ARCH := %s\n' "$ARCH" > "$OUT_DIR/.linux.env"
python3 "$PROJECT_ROOT/scripts/check_runtime_imports.py"
# 1) Build the PyInstaller binary (if it hasn't been built yet)
bash "$PROJECT_ROOT/scripts/build_pyinstaller_linux.sh"

# 2) Prepare AppDir and place the payload under deterministic paths.
rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps"

EXECUTABLE=""
if [[ -x "$PROJECT_ROOT/build/linux/dist/ecli" ]]; then
  EXECUTABLE="$PROJECT_ROOT/build/linux/dist/ecli"
elif [[ -x "$PROJECT_ROOT/dist/ecli/ecli" ]]; then
  EXECUTABLE="$PROJECT_ROOT/dist/ecli/ecli"
elif [[ -x "$PROJECT_ROOT/dist/ecli" ]]; then
  EXECUTABLE="$PROJECT_ROOT/dist/ecli"
fi

[[ -n "$EXECUTABLE" ]] || {
  echo "PyInstaller output not found for AppImage staging." >&2
  exit 1
}

install -Dm755 "$EXECUTABLE" "$APPDIR/usr/bin/ecli"
install -Dm644 \
  "$PROJECT_ROOT/packaging/linux/fpm-common/ecli.desktop" \
  "$APPDIR/usr/share/applications/ecli.desktop"
install -Dm644 \
  "$PROJECT_ROOT/src/ecli/assets/ecli.png" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps/ecli.png"

# 3) Update the version in appimage-builder.yml (on the fly)
sed -i "s/version: \".*\"/version: \"${VERSION}\"/" "$PROJECT_ROOT/packaging/linux/appimage/appimage-builder.yml"

# 4) Install appimage-builder locally if not (for CI, do it in a job)
if ! command -v appimage-builder >/dev/null 2>&1; then
  python3 -m pip install --user appimage-builder
  export PATH="$HOME/.local/bin:$PATH"
fi

#5) Build AppImage
pushd "$PROJECT_ROOT"
appimage-builder \
  --recipe packaging/linux/appimage/appimage-builder.yml \
  --appdir "$APPDIR" \
  --skip-test
popd

APPIMAGE_FILE="$OUT_DIR/ecli_${VERSION}_linux_${ARCH}.AppImage"
found_appimage=0

# The output file will be in PROJECT_ROOT by default. Rename and move it to
# the canonical release directory.
while IFS= read -r -d '' f; do
  found_appimage=1
  rm -f "$APPIMAGE_FILE" "$APPIMAGE_FILE.sha256"
  mv "$f" "$APPIMAGE_FILE"
  echo "Created AppImage: $APPIMAGE_FILE"
done < <(find "$PROJECT_ROOT" -maxdepth 1 -type f -name "*.AppImage" -print0)

if [[ "$found_appimage" -eq 0 || ! -f "$APPIMAGE_FILE" ]]; then
  echo "AppImage build did not produce ${APPIMAGE_FILE}." >&2
  exit 1
fi

# zsync (optional for AppImageUpdate)
if command -v appimagetool >/dev/null 2>&1; then
  (cd "$OUT_DIR" && appimagetool --sign -v "$(basename "$APPIMAGE_FILE")" || true)
fi

(cd "$OUT_DIR" && sha256sum "$(basename "$APPIMAGE_FILE")" > "$(basename "$APPIMAGE_FILE").sha256")
"$PROJECT_ROOT/scripts/verify_runtime.sh" "$APPIMAGE_FILE"
