#!/usr/bin/env bash
# ==============================================================================
# ECLI — macOS packaging (PyInstaller .app → .dmg) for x86_64 / arm64
# Strict outputs:
#   releases/<version>/ecli_<version>_macos_<arch>.dmg
#   releases/<version>/ecli_<version>_macos_<arch>.dmg.sha256
#
# Requirements (local):
#   - macOS 12+ with Python 3.11 and Xcode CLT
#   - hdiutil (stock), codesign (stock), optional: create-dmg
#   - If running locally: ensure `python3.11` is available (via pyenv or brew)
#
# In CI (GitHub Actions macos-13/macos-14), install deps in workflow:
#   - python@3.11 (or actions/setup-python)
#   - pip: aiohttp stack, PyInstaller, etc. (see below)
#
# NOTE: This script does NOT sign/notarize. Add codesign/notarize steps if needed.
# ==============================================================================

set -euo pipefail

log() { printf "\033[1;36m==>\033[0m %s\n" "$*"; }
ok()  { printf "\033[32mOK\033[0m  %s\n" "$*"; }
err(){ printf "\033[31mERR\033[0m %s\n" "$*" >&2; }

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64)  MAC_ARCH="x86_64" ;;
  arm64)   MAC_ARCH="arm64"  ;;
  *)       MAC_ARCH="$ARCH_RAW" ;;
esac

# --- Read version from pyproject.toml -----------------------------------------
log "Reading version from pyproject.toml..."
VERSION="$(python3.11 - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
[ -n "${VERSION:-}" ] || { err "Cannot read [project].version"; exit 1; }
ok "Version: ${VERSION}"

RELEASES_DIR="releases/${VERSION}"
APP_NAME="ECLI"
PKG_NAME_BASE="ecli_${VERSION}_macos_${MAC_ARCH}"
DMG_PATH="${RELEASES_DIR}/${PKG_NAME_BASE}.dmg"
SHA_PATH="${DMG_PATH}.sha256"

# --- Python deps (optional locally; in CI ставим до запуска) ------------------
log "Ensuring Python deps present (PyInstaller + runtime stack)..."
python3.11 -m pip install --upgrade pip wheel setuptools >/dev/null 2>&1 || true
python3.11 -m pip install \
  pyinstaller \
  aiohttp aiosignal yarl multidict frozenlist \
  python-dotenv toml chardet pyperclip wcwidth pygments tato PyYAML

# --- PyInstaller build ---------------------------------------------------------
log "Cleaning previous artifacts..."
rm -rf build/ dist/

log "Building PyInstaller app..."
if [ -f "ecli.spec" ]; then
  pyinstaller ecli.spec --clean --noconfirm
else
  pyinstaller main.py \
    --name ecli \
    --onefile --clean --noconfirm \
    --paths "src" \
    --add-data "config.toml:." \
    --hidden-import=ecli \
    --hidden-import=dotenv       --collect-all=dotenv \
    --hidden-import=toml \
    --hidden-import=PyYAML       --collect-all=PyYAML \
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

# dist/ecli/ecli (onefile)
EXECUTABLE=""
if [ -x "dist/ecli/ecli" ]; then
  EXECUTABLE="dist/ecli/ecli"
elif [ -x "dist/ecli" ]; then
  EXECUTABLE="dist/ecli"
fi
[ -n "$EXECUTABLE" ] || { err "PyInstaller output not found in dist/"; exit 1; }
ok "Executable: $EXECUTABLE"

# --- Create .app bundle (minimal) ---------------------------------------------
# Layout:
#   build/macos_app/ECLI.app/Contents/{MacOS/ (binary), Info.plist, Resources/...}
APP_DIR="build/macos_app/${APP_NAME}.app"
CONTENTS="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS}/MacOS"
RES_DIR="${CONTENTS}/Resources"

log "Assembling minimal .app bundle..."
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR"

# Binary
install -m 755 "$EXECUTABLE" "${MACOS_DIR}/ECLI"

# Icon (optional)
[ -f "img/logo_m.icns" ] && install -m 644 "img/logo_m.icns" "${RES_DIR}/AppIcon.icns"

# Info.plist
cat > "${CONTENTS}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>                <string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key>         <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>          <string>io.ecli.app</string>
  <key>CFBundleVersion</key>             <string>${VERSION}</string>
  <key>CFBundleShortVersionString</key>  <string>${VERSION}</string>
  <key>CFBundleExecutable</key>          <string>ECLI</string>
  <key>CFBundlePackageType</key>         <string>APPL</string>
  <key>LSMinimumSystemVersion</key>      <string>12.0</string>
  <key>NSHighResolutionCapable</key>     <true/>
  <key>CFBundleIconFile</key>            <string>AppIcon</string>
</dict>
</plist>
EOF

# --- Create DMG with drag-to-Applications layout ------------------------------
log "Creating DMG image..."
mkdir -p "$RELEASES_DIR"

# Staging for DMG
DMG_STAGING="build/macos_dmg"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$APP_DIR" "$DMG_STAGING/"

# Create Applications symlink
ln -s /Applications "$DMG_STAGING/Applications"

VOL_NAME="ECLI-${VERSION}"
DMG_TMP="${DMG_PATH%.dmg}-tmp.dmg"

# Create read-write DMG, set up layout, then convert to compressed
hdiutil create -volname "$VOL_NAME" -srcfolder "$DMG_STAGING" -ov -fs HFS+ -format UDRW "$DMG_TMP"
# (Optional) Customize Finder window via AppleScript — опускаем для простоты.
hdiutil convert "$DMG_TMP" -format UDZO -imagekey zlib-level=9 -o "$DMG_PATH"
rm -f "$DMG_TMP"

# Checksum
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$DMG_PATH" | awk '{print $1}' > "$SHA_PATH"
else
  /usr/bin/openssl dgst -sha256 "$DMG_PATH" | awk '{print $2}' > "$SHA_PATH"
fi

ok "DMG: $DMG_PATH"
ok "SHA: $SHA_PATH"

# --- Assert strict names -------------------------------------------------------
[ -f "$DMG_PATH" ] || { err "Missing $DMG_PATH"; exit 2; }
[ -f "$SHA_PATH" ] || { err "Missing $SHA_PATH"; exit 3; }
log "Done."
