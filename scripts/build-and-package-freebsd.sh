#!/bin/sh
# ==============================================================================
# Build and package ECLI into a native FreeBSD .pkg (FreeBSD 14.x)
#
# This script is intended to run INSIDE a FreeBSD 14 VM/container.
# It:
#   1) Installs build deps (Python 3.11, PyInstaller, etc.)
#   2) Builds a one-file binary via PyInstaller (using ecli.spec if present)
#   3) Stages files under /usr/local/... (FHS for FreeBSD)
#   4) Creates a native .pkg with `pkg create`
#
# Output: releases/<version>/ecli-<version>.pkg
# Updated: September 26, 2025 for Python 3.11 and TTY-friendly output.
# ==============================================================================

set -eu

# TTY Compatibility: Add green color to ==> messages if stdout is tty
if [ -t 1 ]; then
  GREEN="\033[32m"
  RESET="\033[0m"
else
  GREEN=""
  RESET=""
fi

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

PACKAGE_NAME="ecli"
MAINTAINER="Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE="https://ecli.io"
LICENSE="Apache-2.0"
COMMENT="Terminal DevOps editor with AI and Git integration"
CATEGORY="editors"  # FreeBSD manifest 'categories'

# ------------------------------------------------------------------------------
# 0) System prerequisites (FreeBSD 14)
# ------------------------------------------------------------------------------
echo "${GREEN}==> Installing base build dependencies (FreeBSD 14)...${RESET}"
# fetch/curl:to install uv; ca_root_nss: TLS certs
pkg install -y \
  python311 py311-pip py311-setuptools py311-wheel py311-pyinstaller \
  git gmake pkgconf ca_root_nss curl py311-uv

# ------------------------------------------------------------------------------
# 1) Userland package manager: uv
# ------------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "${GREEN}==> Installing uv...${RESET}"
  # FreeBSD имеет fetch в базе; используем его (можно и curl)
  fetch -o - https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
# Let's make sure that the UV is picked up
export PATH="$HOME/.local/bin:$PATH"

# ------------------------------------------------------------------------------
# 2) Python deps needed at analysis time for PyInstaller to bundle
# (similar to deb/rpm: aiohttp stack + console libs)
# ------------------------------------------------------------------------------
echo "${GREEN}==> Installing runtime Python deps via uv (system site, Python 3.11)...${RESET}"
uv pip install --system --python python3.11 \
  aiohttp aiosignal yarl multidict frozenlist \
  python-dotenv toml chardet \
  pyperclip wcwidth pygments tato

# ------------------------------------------------------------------------------
# 3) Determine version from pyproject.toml (use stdlib tomllib on 3.11)
# ------------------------------------------------------------------------------
echo "${GREEN}==> Reading version from pyproject.toml...${RESET}"
VERSION="$(python3.11 - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
if [ -z "$VERSION" ]; then
  echo "ERROR: Could not read version from pyproject.toml" >&2
  exit 1
fi
echo "${GREEN}==> Version: $VERSION${RESET}"

RELEASES_DIR="releases/$VERSION"
STAGING_ROOT="build/freebsd_pkg_staging"
META_DIR="build/freebsd_pkg_meta"
BIN_NAME="$PACKAGE_NAME"
EXECUTABLE=""  # will detect below

# ------------------------------------------------------------------------------
# 4) Build one-file executable with PyInstaller
# ------------------------------------------------------------------------------
echo "${GREEN}==> Cleaning previous artifacts${RESET}"
rm -rf build/ dist/

echo "${GREEN}==> Building executable with PyInstaller...${RESET}"
if [ -f "ecli.spec" ]; then
  # spec should already:
  # - add pathex=src
  # - embed config.toml
  # - force aiohttp stack + chardet
  # - include runtime hook packaging/pyinstaller/rthooks/force_imports.py
  pyinstaller ecli.spec --clean --noconfirm
else
  # Backup route: we strictly collect everything we need
  pyinstaller main.py \
    --name "$PACKAGE_NAME" \
    --onefile --clean --noconfirm --strip \
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

# Detect onefile result
if [ -x "dist/$PACKAGE_NAME/$PACKAGE_NAME" ]; then
  EXECUTABLE="dist/$PACKAGE_NAME/$PACKAGE_NAME"
elif [ -x "dist/$PACKAGE_NAME" ]; then
  EXECUTABLE="dist/$PACKAGE_NAME"
fi
if [ -z "$EXECUTABLE" ]; then
  echo "ERROR: PyInstaller output not found in dist/." >&2
  exit 1
fi
echo "${GREEN}==> Built: $EXECUTABLE${RESET}"

# ------------------------------------------------------------------------------
# 5) Stage files under /usr/local for FreeBSD packaging
# ------------------------------------------------------------------------------
echo "${GREEN}==> Preparing staging layout under $STAGING_ROOT ...${RESET}"
rm -rf "$STAGING_ROOT" "$META_DIR"
mkdir -p \
  "$STAGING_ROOT/usr/local/bin" \
  "$STAGING_ROOT/usr/local/share/applications" \
  "$STAGING_ROOT/usr/local/share/icons/hicolor/256x256/apps" \
  "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME" \
  "$STAGING_ROOT/usr/local/man/man1" \
  "$RELEASES_DIR" \
  "$META_DIR"

# Binary
install -m 755 "$EXECUTABLE" "$STAGING_ROOT/usr/local/bin/$BIN_NAME"

# Desktop entry (XDG .desktop correctly under /usr/local/share)
if [ -f "packaging/linux/fpm-common/$PACKAGE_NAME.desktop" ]; then
  install -m 644 "packaging/linux/fpm-common/$PACKAGE_NAME.desktop" \
    "$STAGING_ROOT/usr/local/share/applications/$PACKAGE_NAME.desktop"
else
  cat > "$STAGING_ROOT/usr/local/share/applications/$PACKAGE_NAME.desktop" <<EOF
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
if [ -f "img/logo_m.png" ]; then
  install -m 644 "img/logo_m.png" \
    "$STAGING_ROOT/usr/local/share/icons/hicolor/256x256/apps/$PACKAGE_NAME.png"
fi

# Docs
[ -f "LICENSE"   ] && install -m 644 "LICENSE"   "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME/LICENSE"
[ -f "README.md" ] && install -m 644 "README.md" "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME/README.md"

# Man page
if [ ! -f "man/$PACKAGE_NAME.1" ]; then
  MANFILE="$STAGING_ROOT/usr/local/man/man1/$PACKAGE_NAME.1"
  DATE_STR="$(date +"%B %Y")"
  cat > "$MANFILE" <<EOF
.TH ${PACKAGE_NAME} 1 "${DATE_STR}" "${PACKAGE_NAME} ${VERSION}" "User Commands"
.SH NAME
${PACKAGE_NAME} - Terminal code editor
.SH SYNOPSIS
.B ${PACKAGE_NAME}
[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]
.SH DESCRIPTION
${PACKAGE_NAME} is a fast terminal code editor.
.SH OPTIONS
\\fB--help\\fR     Show help
\\fB--version\\fR  Show version
.SH AUTHOR
${MAINTAINER}
.SH HOMEPAGE
${HOMEPAGE}
EOF
  gzip -f "$MANFILE"
else
  install -m 644 "man/$PACKAGE_NAME.1" "$STAGING_ROOT/usr/local/man/man1/$PACKAGE_NAME.1"
  gzip -f "$STAGING_ROOT/usr/local/man/man1/$PACKAGE_NAME.1"
fi

# ------------------------------------------------------------------------------
# 6) Create +MANIFEST for pkg(8) and build .pkg
# ------------------------------------------------------------------------------
ABI="$(pkg config ABI 2>/dev/null || echo 'FreeBSD:14:amd64')"

MANIFEST_FILE="$META_DIR/+MANIFEST"
cat > "$MANIFEST_FILE" <<EOF
name: ${PACKAGE_NAME}
version: ${VERSION}
origin: ${CATEGORY}/${PACKAGE_NAME}
comment: ${COMMENT}
desc: |
  ${COMMENT}
maintainer: ${MAINTAINER}
www: ${HOMEPAGE}
abi: ${ABI}
prefix: /
categories:
  - ${CATEGORY}
licenses:
  - ${LICENSE}
licenselogic: single
EOF

echo "${GREEN}==> Creating .pkg with pkg create...${RESET}"
# pkg create will take all files from the staging root, metadata from +MANIFEST
pkg create -M "$MANIFEST_FILE" -r "$STAGING_ROOT" -o "$RELEASES_DIR"

PKG_PATH="$(ls -1 "$RELEASES_DIR/${PACKAGE_NAME}-${VERSION}"*.pkg 2>/dev/null || true)"
if [ -z "$PKG_PATH" ]; then
  echo "ERROR: pkg create did not produce a .pkg file" >&2
  exit 1
fi

# Generate SHA256 checksum for verification
sha256sum "$PKG_PATH" > "$PKG_PATH.sha256" || shasum -a 256 "$PKG_PATH" > "$PKG_PATH.sha256"

echo "${GREEN}✅ DONE: $PKG_PATH${RESET}"
echo "${GREEN}✅ Checksum: $PKG_PATH.sha256${RESET}"
# Optional: list contents
pkg info -F "$PKG_PATH" || true
