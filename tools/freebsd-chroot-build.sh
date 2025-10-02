#!/bin/sh
# ==============================================================================
# ECLI — Reproducible "Docker-like" FreeBSD Build via chroot (14.3-RELEASE)
# ==============================================================================
# SYNOPSIS
#   Build a native FreeBSD .pkg in a clean, isolated chroot that mimics a
#   containerized build (like Docker, but the FreeBSD way).
#
# WHAT THIS SCRIPT DOES
#   1) Creates a clean FreeBSD 14.3 rootfs from the official base.txz.
#   2) Bootstraps pkg(8) and installs EXACT system build deps:
#        ca_root_nss curl git gmake pkgconf
#        python311 py311-pip py311-pyinstaller py311-setuptools py311-wheel
#        py311-ruff ncurses libyaml
#   3) Installs Python deps (Python 3.11) via pip:
#        aiohttp aiosignal yarl multidict frozenlist
#        python-dotenv toml chardet pyperclip wcwidth pygments tato PyYAML
#   4) Copies the repository into /ecli inside the chroot.
#   5) Runs your canonical packager:
#        sh /ecli/scripts/build-and-package-freebsd.sh
#      which MUST produce STRICT artifacts:
#        /ecli/releases/<version>/ecli_<version>_amd64.pkg
#        /ecli/releases/<version>/ecli_<version>_amd64.pkg.sha256
#   6) Copies the /ecli/releases/ tree back to the host ./releases/ and verifies
#      the exact file names/locations exist (assert).
#
# PRODUCED ARTIFACTS (STRICT)
#   - releases/<version>/ecli_<version>_amd64.pkg
#   - releases/<version>/ecli_<version>_amd64.pkg.sha256
#
# VERSION SOURCE
#   - Read from pyproject.toml → [project].version (via Python 3.11 tomllib).
#
# REQUIREMENTS
#   - Run on a FreeBSD 14.3 host with root privileges (sudo is fine).
#   - Internet connectivity to fetch base.txz and packages.
#   - Repo layout must include:
#       pyproject.toml, scripts/build-and-package-freebsd.sh, main.py, src/...
#
# USAGE
#   $ chmod +x tools/freebsd-chroot-build.sh
#   $ sudo tools/freebsd-chroot-build.sh
#   # Inspect artifacts:
#   $ ls -l releases/*/ecli_*_amd64.pkg*
#
# CLEANUP
#   - The chroot is created under ${CHROOT_DIR} (default: /tmp/ecli-chroot-14_3).
#   - This script unmounts devfs/procfs automatically; remove the directory if
#     you want to reclaim space:
#       # rm -rf /tmp/ecli-chroot-14_3
#
# EXIT CODES
#   0  Success
#   1+ Failure at a specific step (message printed to stderr)
#
# LAST UPDATED
#   2025-10-02 — aligned with packaging scripts; strict artifact naming verified.
# ==============================================================================

set -eu

# ----------------------------- Configuration ----------------------------------
# Override via env if desired:
CHROOT_DIR="${CHROOT_DIR:-/tmp/ecli-chroot-14_3}"
# Official mirror for base.txz (14.3-RELEASE, amd64). Override MIRROR to pin.
MIRROR="${MIRROR:-https://download.freebsd.org/releases/amd64/amd64/14.3-RELEASE}"
BASE_TGZ="base.txz"

# ------------------------------- Pretty logs ----------------------------------
info(){ printf "\033[1;36m==>\033[0m %s\n" "$*"; }
ok(){   printf "\033[32mOK\033[0m  %s\n" "$*"; }
warn(){ printf "\033[33mWARN\033[0m %s\n" "$*"; }
err(){  printf "\033[31mERR\033[0m %s\n" "$*" >&2; }

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    err "Run as root (use sudo)."
    exit 1
  fi
}

# ------------------------------- Utilities ------------------------------------
read_version() {
  # Reads [project].version from pyproject.toml using Python 3.11 tomllib.
  python3.11 - <<'PY'
import tomllib, sys
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
}

fetch_rootfs() {
  info "Preparing clean rootfs: ${CHROOT_DIR}"
  rm -rf "$CHROOT_DIR"
  mkdir -p "$CHROOT_DIR"
  info "Fetching base.txz from ${MIRROR} ..."
  fetch -o "$CHROOT_DIR/$BASE_TGZ" "${MIRROR}/${BASE_TGZ}"
  info "Extracting base.txz ..."
  tar -xpf "$CHROOT_DIR/$BASE_TGZ" -C "$CHROOT_DIR"
  rm -f "$CHROOT_DIR/$BASE_TGZ"
  ok "Rootfs extracted"
}

mount_fs() {
  info "Mounting devfs/procfs into chroot ..."
  mount -t devfs devfs "$CHROOT_DIR/dev"
  [ -d "$CHROOT_DIR/proc" ] || mkdir -p "$CHROOT_DIR/proc"
  mount -t procfs proc "$CHROOT_DIR/proc"
  ok "Mounts ready"
}

umount_fs() {
  info "Unmounting chroot filesystems ..."
  umount -f "$CHROOT_DIR/proc" 2>/dev/null || true
  umount -f "$CHROOT_DIR/dev"  2>/dev/null || true
  ok "Unmounted"
}

bootstrap_pkg() {
  info "Bootstrapping pkg(8) in chroot ..."
  chroot "$CHROOT_DIR" /bin/sh -c "env ASSUME_ALWAYS_YES=yes pkg bootstrap -f"
  chroot "$CHROOT_DIR" /bin/sh -c "env ASSUME_ALWAYS_YES=yes pkg update -f"
  ok "pkg ready"
}

install_system_deps() {
  info "Installing exact system dependencies (build toolchain) ..."
  chroot "$CHROOT_DIR" /bin/sh -c '
    set -eu
    env ASSUME_ALWAYS_YES=yes pkg install -y \
      ca_root_nss \
      curl \
      git \
      gmake \
      pkgconf \
      python311 \
      py311-pip \
      py311-pyinstaller \
      py311-setuptools \
      py311-wheel \
      py311-ruff \
      ncurses \
      libyaml
  '
  ok "System deps installed"
}

install_python_deps() {
  info "Installing Python (pip) deps for Python 3.11 ..."
  chroot "$CHROOT_DIR" /bin/sh -c '
    set -eu
    python3.11 -m pip install --upgrade pip wheel setuptools >/dev/null 2>&1 || true
    python3.11 -m pip install \
      aiohttp aiosignal yarl multidict frozenlist \
      python-dotenv toml chardet \
      pyperclip wcwidth pygments tato PyYAML
  '
  ok "Python deps installed"
}

copy_project_in() {
  info "Copying repository into chroot:/ecli ..."
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude ".git" ./ "$CHROOT_DIR/ecli/"
  else
    (cd . && tar -cpf - --exclude .git .) | (cd "$CHROOT_DIR" && mkdir -p ecli && tar -xpf - -C ecli)
  fi
  ok "Project copied"
}

run_packager() {
  info "Running canonical packager inside chroot ..."
  chroot "$CHROOT_DIR" /bin/sh -c '
    set -eu
    cd /ecli
    sh ./scripts/build-and-package-freebsd.sh
  '
  ok "Packaging finished"
}

copy_artifacts_back() {
  info "Copying releases/ back to host ..."
  mkdir -p ./releases
  if [ -d "$CHROOT_DIR/ecli/releases" ]; then
    if command -v rsync >/dev/null 2>&1; then
      rsync -a "$CHROOT_DIR/ecli/releases/" "./releases/"
    else
      (cd "$CHROOT_DIR/ecli/releases" && tar -cpf - .) | (cd ./releases && tar -xpf -)
    fi
  fi
  ok "Artifacts copied to ./releases/"
}

assert_strict_artifacts() {
  # Validate strict paths/names:
  info "Asserting strict artifact naming & location ..."
  VERSION="$(read_version)"
  [ -n "$VERSION" ] || { err "Unable to read version from pyproject.toml"; exit 1; }

  ARCH="amd64"  # we normalize to amd64 (as in the rest of the toolchain)
  PKG="releases/${VERSION}/ecli_${VERSION}_${ARCH}.pkg"
  SHA="${PKG}.sha256"

  if [ ! -f "$PKG" ]; then
    err "Missing artifact: $PKG"
    ls -R releases || true
    exit 2
  fi
  if [ ! -f "$SHA" ]; then
    err "Missing checksum: $SHA"
    ls -R releases || true
    exit 3
  fi
  ok "Found: $PKG"
  ok "Found: $SHA"
}

cleanup() {
  umount_fs
  info "If desired, remove chroot dir: rm -rf ${CHROOT_DIR}"
}

# ---------------------------------- Main --------------------------------------
main() {
  [ "$(uname -s)" = "FreeBSD" ] || { err "Host must be FreeBSD."; exit 1; }
  require_root

  fetch_rootfs
  mount_fs
  trap cleanup EXIT INT TERM

  bootstrap_pkg
  install_system_deps
  copy_project_in
  install_python_deps
  run_packager
  copy_artifacts_back
  assert_strict_artifacts

  info "Done. Strict artifacts are in ./releases/<version>/"
}

main "$@"
