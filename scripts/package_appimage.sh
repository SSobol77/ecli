#!/usr/bin/env bash
set -euo pipefail

# This script:
# 1) builds the ecli (PyInstaller) binary for Linux,
# 2) places it in AppDir,
# 3) runs appimage-builder to create an .AppImage

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-0.1.0}"
OUT_DIR="$PROJECT_ROOT/dist"
APPDIR="$PROJECT_ROOT/packaging/linux/appimage/AppDir"

mkdir -p "$OUT_DIR"
# 1) Build the PyInstaller binary (if it hasn't been built yet)
bash "$PROJECT_ROOT/scripts/build_pyinstaller_linux.sh"

# 2) Place the binary in AppDir/usr/bin/ecli
install -Dm755 "$PROJECT_ROOT/build/linux/dist/ecli" "$APPDIR/usr/bin/ecli"

# 3) Update the version in appimage-builder.yml (on the fly)
sed -i "s/version: \".*\"/version: \"${VERSION}\"/" "$PROJECT_ROOT/packaging/linux/appimage/appimage-builder.yml"

# 4) Install appimage-builder locally if not (for CI, do it in a job)
if ! command -v appimage-builder >/dev/null 2>&1; then
  python3 -m pip install --user appimage-builder
  export PATH="$HOME/.local/bin:$PATH"
fi

#5) Build AppImage
pushd "$PROJECT_ROOT"
appimage-builder --recipe packaging/linux/appimage/appimage-builder.yml --skip-test
popd

# The output file will be in PROJECT_ROOT (by default, appimage-builder places it next to it)
# Rename and move to dist
find "$PROJECT_ROOT" -maxdepth 1 -type f -name "*.AppImage" -print0 | while IFS= read -r -d '' f; do
  NEW="$OUT_DIR/ECLI-${VERSION}-x86_64.AppImage"
  mv "$f" "$NEW"
  echo "Created AppImage: $NEW"
done

# zsync (optional for AppImageUpdate)
if command -v appimagetool >/dev/null 2>&1; then
  (cd "$OUT_DIR" && appimagetool --sign -v ECLI-${VERSION}-x86_64.AppImage || true)
fi
