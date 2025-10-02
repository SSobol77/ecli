#!/bin/sh
# ==============================================================================
# ECLI — FreeBSD 14.x Native Package Builder (.pkg)
# ==============================================================================
# SYNOPSIS
#   Build and package ECLI into a native FreeBSD .pkg on FreeBSD 14.x.
#
#   This script MUST run INSIDE a real FreeBSD 14.x environment (host or VM).
#   Docker on Linux will NOT work (wrong kernel/ABI). In CI, use a FreeBSD VM
#   action such as `vmactions/freebsd-vm@v1`.
#
# WHAT THE SCRIPT DOES
#   1) Installs exact system build dependencies via `pkg`:
#      - python311 toolchain and PyInstaller (py311-*)
#      - py311-ruff (ships Ruff for linting)
#      - ncurses (wide curses + terminfo)
#      - libyaml (C-accelerated YAML, optional at runtime but included)
#   2) Installs required Python packages for bundling with:
#        python3.11 -m pip install \
#          aiohttp aiosignal yarl multidict frozenlist \
#          python-dotenv toml chardet pyperclip wcwidth pygments tato PyYAML
#   3) Builds a single-file ECLI binary using PyInstaller (uses ecli.spec if present).
#   4) Stages files under /usr/local/... following FreeBSD conventions
#      (bin/, share/{applications,icons,doc}, man/).
#   5) Generates +MANIFEST and creates a native .pkg via `pkg create`.
#   6) Renames the artifact to a strict name and writes a checksum:
#      releases/<version>/ecli_<version>_amd64.pkg
#      releases/<version>/ecli_<version>_amd64.pkg.sha256
#
# PRODUCED ARTIFACTS
#   - Directory: releases/<version>/
#   - Files:
#       ecli_<version>_amd64.pkg
#       ecli_<version>_amd64.pkg.sha256
#
# VERSIONING
#   - The <version> is read from `pyproject.toml` → [project].version.
#
# PREREQUISITES
#   - FreeBSD 14.x host or VM with Internet access to pkg(8) repos.
#   - Git installed (the script installs it if missing).
#   - `pyproject.toml` and `main.py` present at repo root.
#   - Optional: `ecli.spec` for a fine-tuned PyInstaller build.
#
# USAGE (LOCAL, INSIDE FREEBSD 14.x)
#   $ sh scripts/build-and-package-freebsd.sh
#
#   After a successful run, check:
#   $ ls -l releases/*/ecli_*.pkg
#   $ cat releases/*/ecli_*.pkg.sha256
#
# USAGE (MAKE)
#   Add (or use) the Make target:
#     .PHONY: package-freebsd
#     package-freebsd: clean
#     	sh ./scripts/build-and-package-freebsd.sh
#   Then:
#     $ make package-freebsd
#
# USAGE (GITHUB ACTIONS — FREEBSD VM)
#   - Runner: ubuntu-latest
#   - Step:
#       - uses: vmactions/freebsd-vm@v1
#         with:
#           release: "14.3"
#           usesh: true
#           run: |
#             sh ./scripts/build-and-package-freebsd.sh
#   - Next steps can upload/commit:
#       releases/<version>/ecli_<version>_amd64.pkg
#       releases/<version>/ecli_<version>_amd64.pkg.sha256
#
# QUICK VERIFICATION
#   # Inspect package metadata:
#   $ pkg info -F releases/<version>/ecli_<version>_amd64.pkg
#
#   # Inspect archive contents (structure under /usr/local):
#   $ tar -tf releases/<version>/ecli_<version>_amd64.pkg | head
#
#   # Verify checksum:
#   $ sha256 -q releases/<version>/ecli_<version>_amd64.pkg
#   # Compare against contents of the .sha256 file.
#
# TROUBLESHOOTING
#   - "pkg create did not produce a .pkg file":
#       Ensure the build finished and staging tree exists under build/freebsd_pkg_staging.
#   - "PyInstaller output not found in dist/":
#       Check PyInstaller logs. Ensure `main.py` (or `ecli.spec`) is correct and
#       required Python deps are installed.
#   - Missing system packages:
#       The script runs `pkg update -f` and installs exact FreeBSD 14.x package names.
#       If a repo mirror is unavailable, retry or switch mirrors.
#   - Running on Linux Docker:
#       Not supported. Use a FreeBSD VM (local hypervisor, Cirrus CI, or GA VM action).
#
# EXIT CODES
#   0   Success.
#   1   Generic failure (e.g., missing artifacts, dependency installation error).
#   2+  Other non-zero statuses indicate step-specific failures.
#
# COPYRIGHT / LICENSE
#   - Maintainer: Siergej Sobolewski <s.sobolewski@hotmail.com>
#   - License: Apache-2.0 (package ships LICENSE if present)
#
# LAST UPDATED
#   2025-10-02 — Strict artifact naming; expanded dependencies and usage.
# ==============================================================================


set -eu

# -------- Pretty printing ------------------------------------------------------
print_header() { printf "\033[1;36m==> %s\033[0m\n" "$*"; }
print_step()   { printf "\033[32m  -> %s\033[0m\n" "$*"; }
print_warn()   { printf "\033[33mWARN:\033[0m %s\n" "$*"; }
print_error()  { printf "\033[31mERROR:\033[0m %s\n" "$*"; }

# -------- Paths & meta --------------------------------------------------------
PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

PACKAGE_NAME="ecli"
MAINTAINER="Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE="https://ecli.io"
LICENSE="Apache-2.0"
COMMENT="Terminal DevOps editor with AI and Git integration"
CATEGORY="editors"  # FreeBSD manifest 'categories'

# -------- System deps (exact list as requested) --------------------------------
install_system_dependencies() {
  print_header "ECLI FreeBSD Package Builder"
  print_step "Installing system build dependencies..."

  # Exact pkg names for FreeBSD 14:
  # - python311 / py311-* for Python 3.11 toolchain
  # - py311-pyinstaller — system PyInstaller package
  # - py311-ruff — ship Ruff as part of default tooling
  # - ncurses — required on 14.x (wide curses / terminfo tools)
  # - libyaml — OPTIONAL: C-accelerated YAML (we'll install as requested)
  packages="
    ca_root_nss
    curl
    git
    gmake
    pkgconf
    python311
    py311-pip
    py311-pyinstaller
    py311-setuptools
    py311-wheel
    py311-ruff
    ncurses
    libyaml
  "

  # Non-interactive pkg mode
  env ASSUME_ALWAYS_YES=yes pkg update -f || true
  if ! env ASSUME_ALWAYS_YES=yes pkg install -y $packages; then
    print_error "Failed to install system packages"
    return 1
  fi

  # Sanity: ensure pyinstaller & ruff exist
  command -v pyinstaller >/dev/null 2>&1 || {
    print_error "pyinstaller is not in PATH (expected from py311-pyinstaller)"
    return 1
  }
  command -v ruff >/dev/null 2>&1 || {
    print_warn "py311-ruff installed but binary not found in PATH"
  }
}

# -------- Python deps (exact list as requested) --------------------------------
install_python_dependencies() {
  print_step "Installing Python (pip) dependencies for Python 3.11..."

  # aiohttp stack, TUI bits, etc. (exact list requested)
  pip_packages="aiohttp aiosignal yarl multidict frozenlist python-dotenv toml chardet pyperclip wcwidth pygments tato PyYAML"

  # Upgrade pip tooling lightly (safe)
  python3.11 -m pip install --upgrade pip wheel setuptools >/dev/null 2>&1 || true

  if ! python3.11 -m pip install $pip_packages; then
    print_error "Failed to install Python dependencies"
    return 1
  fi
}

# -------- Read version from pyproject.toml ------------------------------------
read_version() {
  print_step "Reading version from pyproject.toml..."
  VERSION="$(python3.11 - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
  if [ -z "${VERSION:-}" ]; then
    print_error "Cannot read [project].version from pyproject.toml"
    return 1
  fi
  echo "$VERSION"
}

# -------- Build binary with PyInstaller ---------------------------------------
build_binary() {
  print_step "Cleaning previous artifacts (build/, dist/)..."
  rm -rf build/ dist/

  print_step "Building one-file binary with PyInstaller..."
  if [ -f "ecli.spec" ]; then
    pyinstaller ecli.spec --clean --noconfirm
  else
    # Fallback specless build (collect all required hidden imports)
    pyinstaller main.py \
      --name "$PACKAGE_NAME" \
      --onefile --clean --noconfirm --strip \
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

  if [ -x "dist/$PACKAGE_NAME/$PACKAGE_NAME" ]; then
    echo "dist/$PACKAGE_NAME/$PACKAGE_NAME"
  elif [ -x "dist/$PACKAGE_NAME" ]; then
    echo "dist/$PACKAGE_NAME"
  else
    print_error "PyInstaller output not found in dist/"
    return 1
  fi
}

# -------- Stage filesystem tree ------------------------------------------------
stage_files() {
  EXECUTABLE="$1"
  VERSION="$2"

  STAGING_ROOT="build/freebsd_pkg_staging"
  META_DIR="build/freebsd_pkg_meta"

  print_step "Staging filesystem under $STAGING_ROOT ..."
  rm -rf "$STAGING_ROOT" "$META_DIR"
  mkdir -p \
    "$STAGING_ROOT/usr/local/bin" \
    "$STAGING_ROOT/usr/local/share/applications" \
    "$STAGING_ROOT/usr/local/share/icons/hicolor/256x256/apps" \
    "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME" \
    "$STAGING_ROOT/usr/local/man/man1" \
    "$META_DIR"

  install -m 755 "$EXECUTABLE" "$STAGING_ROOT/usr/local/bin/$PACKAGE_NAME"

  # .desktop
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
  [ -f "img/logo_m.png" ] && install -m 644 "img/logo_m.png" \
    "$STAGING_ROOT/usr/local/share/icons/hicolor/256x256/apps/$PACKAGE_NAME.png"

  # Docs
  [ -f "LICENSE"   ] && install -m 644 "LICENSE"   "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME/LICENSE"
  [ -f "README.md" ] && install -m 644 "README.md" "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME/README.md"

  # Man
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

  echo "$STAGING_ROOT"
}

# -------- Create +MANIFEST and build .pkg -------------------------------------
make_pkg() {
  STAGING_ROOT="$1"
  VERSION="$2"

  META_DIR="build/freebsd_pkg_meta"
  ABI="$(pkg config ABI 2>/dev/null || echo 'FreeBSD:14:amd64')"

  mkdir -p "$META_DIR"

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
prefix: /usr/local
categories:
  - ${CATEGORY}
licenses:
  - ${LICENSE}
licenselogic: single
EOF

  RELEASES_DIR="releases/$VERSION"
  mkdir -p "$RELEASES_DIR"

  print_step "Creating .pkg with pkg create..."
  pkg create -M "$MANIFEST_FILE" -r "$STAGING_ROOT" -o "$RELEASES_DIR"

  # Normalize arch for filename
  RAW_ARCH="$(uname -m 2>/dev/null || echo amd64)"
  case "$RAW_ARCH" in
    amd64|x86_64) ARCH="amd64" ;;
    *) ARCH="${RAW_ARCH}" ;;
  esac

  ORIG_PKG="$(ls -1 "$RELEASES_DIR/${PACKAGE_NAME}-${VERSION}"*.pkg 2>/dev/null | head -n1 || true)"
  [ -n "$ORIG_PKG" ] || { print_error "pkg create did not produce a .pkg file"; return 1; }

  DEST_PKG="${RELEASES_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH}.pkg"
  [ "$ORIG_PKG" != "$DEST_PKG" ] && mv -f "$ORIG_PKG" "$DEST_PKG"

  # SHA256 sidecar
  if command -v sha256 >/dev/null 2>&1; then
    sha256 -q "$DEST_PKG" > "${DEST_PKG}.sha256"
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$DEST_PKG" | awk '{print $1}' > "${DEST_PKG}.sha256"
  else
    print_warn "No sha256/shasum available; skipping checksum."
  fi

  echo "$DEST_PKG"
}

# ============================== MAIN ==========================================
install_system_dependencies
install_python_dependencies

VERSION="$(read_version)"
print_step "Version detected: $VERSION"

EXECUTABLE="$(build_binary)"
print_step "Executable: $EXECUTABLE"

STAGING_ROOT="$(stage_files "$EXECUTABLE" "$VERSION")"
PKG_PATH="$(make_pkg "$STAGING_ROOT" "$VERSION")"

print_header "DONE"
print_step "Package:   $PKG_PATH"
print_step "Checksum:  ${PKG_PATH}.sha256"
# Show meta if available
pkg info -F "$PKG_PATH" || true
