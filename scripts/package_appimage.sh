#!/usr/bin/env bash
set -euo pipefail

# This script:
# 1) builds the ecli (PyInstaller) binary for Linux,
# 2) places it in AppDir,
# 3) runs appimage-builder to create an .AppImage

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-0.1.0}"
RAW_ARCH="${2:-$(uname -m 2>/dev/null || echo x86_64)}"
case "$RAW_ARCH" in
  amd64|x86_64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) ARCH="$RAW_ARCH" ;;
esac
OUT_DIR="$PROJECT_ROOT/releases/$VERSION"
APPDIR="$PROJECT_ROOT/packaging/linux/appimage/AppDir"

mkdir -p "$OUT_DIR"
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
  "$PROJECT_ROOT/img/logo_m.png" \
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

# The output file will be in PROJECT_ROOT by default. Rename and move it to
# the canonical release directory.
find "$PROJECT_ROOT" -maxdepth 1 -type f -name "*.AppImage" -print0 | while IFS= read -r -d '' f; do
  NEW="$OUT_DIR/ecli_${VERSION}_linux_${ARCH}.AppImage"
  mv "$f" "$NEW"
  echo "Created AppImage: $NEW"
done

# zsync (optional for AppImageUpdate)
if command -v appimagetool >/dev/null 2>&1; then
  (cd "$OUT_DIR" && appimagetool --sign -v "ecli_${VERSION}_linux_${ARCH}.AppImage" || true)
fi
