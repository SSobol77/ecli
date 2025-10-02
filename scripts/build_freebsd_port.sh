#!/bin/sh
# ==============================================================================
# ECLI — Build via FreeBSD Ports (local port skeleton)
# ==============================================================================
# SYNOPSIS
#   Build ECLI as a local FreeBSD port and produce a native .pkg on FreeBSD 14.3.
#
# WHAT THIS SCRIPT DOES
#   1) Reads version from pyproject.toml ([project].version).
#   2) Archives the current repo into /tmp/ecli-<version>.tar.gz.
#   3) Creates a local port skeleton: /usr/ports/editors/ecli_local
#      - MASTER_SITES=file:///tmp
#      - DISTFILES=ecli-<version>.tar.gz
#      - do-build runs your PyInstaller build (inside WRKSRC)
#      - do-install installs staged files into ${STAGEDIR}
#   4) Runs `make -C /usr/ports/editors/ecli_local makesum package`.
#   5) Copies & renames the resulting package to:
#         releases/<version>/ecli_<version>_amd64.pkg
#         releases/<version>/ecli_<version>_amd64.pkg.sha256
#
# REQUIREMENTS
#   - Run on FreeBSD 14.x (root privileges required).
#   - /usr/ports tree present (if нет — подскажет команду portsnap fetch extract).
#   - Internet for pkg(8) repositories (to install build deps if не хватает).
#
# USAGE
#   $ sudo sh scripts/build_freebsd_port.sh
#
# EXIT CODES
#   0 success, non-zero on failure.
#
# LAST UPDATED
#   2025-10-02
# ==============================================================================

set -eu

# --- Pretty logs --------------------------------------------------------------
info(){ printf "\033[1;36m==>\033[0m %s\n" "$*"; }
ok(){   printf "\033[32mOK\033[0m  %s\n" "$*"; }
warn(){ printf "\033[33mWARN\033[0m %s\n" "$*"; }
err(){  printf "\033[31mERR\033[0m %s\n" "$*" >&2; }

# --- Root / OS checks ---------------------------------------------------------
[ "$(uname -s)" = "FreeBSD" ] || { err "Run on FreeBSD."; exit 1; }
[ "$(id -u)" -eq 0 ] || { err "Run as root (sudo)."; exit 1; }

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# --- Read version from pyproject.toml -----------------------------------------
info "Reading version from pyproject.toml..."
VERSION="$(/usr/local/bin/python3.11 - <<'PY' 2>/dev/null || python3.11 - <<'PY'
import tomllib, sys
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
[ -n "${VERSION:-}" ] || { err "Cannot read [project].version"; exit 1; }
ok "Version: $VERSION"

PORT_CAT="editors"
PORT_NAME="ecli_local"            # локальное имя порта, без конфликтов
PORTDIR="/usr/ports/${PORT_CAT}/${PORT_NAME}"
DISTDIR="/tmp"
DISTFILE="ecli-${VERSION}.tar.gz"
DISTPATH="${DISTDIR}/${DISTFILE}"

RAW_ARCH="$(uname -m 2>/dev/null || echo amd64)"
case "$RAW_ARCH" in
  amd64|x86_64) ARCH="amd64" ;;
  *) ARCH="${RAW_ARCH}" ;;
esac

# --- Ensure /usr/ports exists -------------------------------------------------
if [ ! -d /usr/ports ]; then
  warn "/usr/ports not found. Install ports tree, e.g.:"
  warn "  # portsnap fetch extract"
  err  "Ports tree is required."
  exit 1
fi

# --- Create source tarball ----------------------------------------------------
info "Creating source tarball: ${DISTPATH}"
rm -f "$DISTPATH"
# архивируем весь проект, исключая .git и сборочные артефакты
( cd "$PROJECT_ROOT" && \
  tar --exclude .git --exclude build --exclude dist --exclude .pytest_cache \
      --exclude .ruff_cache --exclude .mypy_cache \
      -czf "$DISTPATH" . )
ok "Tarball ready"

# --- Create local port skeleton ----------------------------------------------
info "Creating local port skeleton at: ${PORTDIR}"
rm -rf "$PORTDIR"
mkdir -p "$PORTDIR"

# Makefile ---------------------------------------------------------------------
cat > "${PORTDIR}/Makefile" <<'EOF_MK'
PORTNAME=       ecli
# DISTVERSION is substituted by the script to actual version
DISTVERSION=    __ECLI_VERSION__
CATEGORIES=     editors

MAINTAINER=     Siergej Sobolewski <s.sobolewski@hotmail.com>
COMMENT=        Terminal DevOps editor with AI and Git integration
WWW=            https://ecli.io

LICENSE=        APACHE20
LICENSE_FILE=   ${WRKSRC}/LICENSE

ONLY_FOR_ARCHS= amd64

# We fetch from a local tarball prepared by the script
MASTER_SITES=   file:///tmp/
DISTFILES=      ecli-${DISTVERSION}.tar.gz

# Extracted tree lives here
WRKSRC=         ${WRKDIR}/ecli-${DISTVERSION}

# We rely on system Python toolchain and utilities
USES=           python:3.11+ gmake

# Build-time system deps (install via pkg if needed)
BUILD_DEPENDS=  py311-pyinstaller>0:devel/py-pyinstaller@py311 \
                git:devel/git \
                gmake:devel/gmake

# Runtime deps are embedded into PyInstaller binary. Man/desktop/icons are plain files.

# --- Build phase: call project's script inside WRKSRC -------------------------
do-build:
	@cd ${WRKSRC} && env ASSUME_ALWAYS_YES=yes pkg update -f || true
	@cd ${WRKSRC} && sh ./scripts/build-and-package-freebsd.sh

# --- Install phase: copy staged tree into ${STAGEDIR} -------------------------
# The build script stages under build/freebsd_pkg_staging/usr/local/...
do-install:
	@${ECHO_MSG} ">> Installing staged files to ${STAGEDIR}/usr/local ..."
	@cd ${WRKSRC}/build/freebsd_pkg_staging && \
		${FIND} usr -type d -exec ${MKDIR} ${STAGEDIR}/{} \; && \
		${FIND} usr -type f -exec ${INSTALL} -m 644 {} ${STAGEDIR}/{} \;

# The binary must be executable
	@${CHMOD} 755 ${STAGEDIR}/usr/local/bin/ecli || true

# --- Packaging list -----------------------------------------------------------
# Keep plist simple and stable. Matches what build script stages.
PLIST_FILES= \
	bin/ecli \
	share/applications/ecli.desktop \
	share/icons/hicolor/256x256/apps/ecli.png \
	share/doc/ecli/LICENSE \
	share/doc/ecli/README.md \
	man/man1/ecli.1.gz
EOF_MK

# Подставим версию
sed -i '' -e "s/__ECLI_VERSION__/${VERSION}/g" "${PORTDIR}/Makefile"

# pkg-descr --------------------------------------------------------------------
cat > "${PORTDIR}/pkg-descr" <<'EOF_DESCR'
ECLI is a fast terminal-first code editor tailored for DevOps workflows:
- Git integration
- AI-assisted code features
- TUI optimized for terminals
- First-class support for DevOps config formats

This local port builds a native, single-file binary via PyInstaller and
installs it under /usr/local.
EOF_DESCR

# distinfo будет сгенерирован `make makesum`

# --- Ensure system deps for the build script (once per host) ------------------
info "Ensuring base system build deps (host) ..."
env ASSUME_ALWAYS_YES=yes pkg install -y \
  ca_root_nss curl git gmake pkgconf \
  python311 py311-pip py311-pyinstaller py311-setuptools py311-wheel py311-ruff \
  ncurses libyaml >/dev/null || true
ok "Host deps ok"

# --- Generate distinfo --------------------------------------------------------
info "Generating distinfo (makesum) ..."
make -C "$PORTDIR" makesum || { err "makesum failed"; exit 1; }
ok "distinfo ready"

# --- Build package via ports --------------------------------------------------
info "Building package with ports (this may take a while) ..."
make -C "$PORTDIR" clean package || { err "make package failed"; exit 1; }
ok "Ports build finished"

# --- Locate produced pkg and rename/copy to releases/<ver> --------------------
info "Locating produced package ..."
PKG_FROM_PORTS="$(make -C "$PORTDIR" -V PKGFILE || true)"
if [ -z "$PKG_FROM_PORTS" ] || [ ! -f "$PKG_FROM_PORTS" ]; then
  # Fallback: try common packages path
  CAND="$(ls -1 /usr/ports/packages/All/ecli-*.pkg 2>/dev/null | tail -n1 || true)"
  [ -n "$CAND" ] && PKG_FROM_PORTS="$CAND"
fi

[ -n "$PKG_FROM_PORTS" ] && [ -f "$PKG_FROM_PORTS" ] || {
  err "Cannot find produced .pkg; looked at PKGFILE and /usr/ports/packages/All"
  exit 1
}
ok "Found: $PKG_FROM_PORTS"

RELEASES_DIR="${PROJECT_ROOT}/releases/${VERSION}"
DEST_PKG="${RELEASES_DIR}/ecli_${VERSION}_${ARCH}.pkg"
DEST_SHA="${DEST_PKG}.sha256"

mkdir -p "$RELEASES_DIR"
cp -f "$PKG_FROM_PORTS" "$DEST_PKG"

# checksum рядом
if command -v sha256 >/dev/null 2>&1; then
  sha256 -q "$DEST_PKG" > "$DEST_SHA"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$DEST_PKG" | awk '{print $1}' > "$DEST_SHA"
else
  warn "No sha256/shasum available; skipping checksum."
fi

ok "Copied & renamed -> $DEST_PKG"
[ -f "$DEST_SHA" ] && ok "Checksum      -> $DEST_SHA"

# --- Final info ---------------------------------------------------------------
info "pkg info -F ${DEST_PKG}"
pkg info -F "$DEST_PKG" || true

info "Done."
exit 0
