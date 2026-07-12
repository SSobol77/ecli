#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: packaging/debian/verify_deb_minimal_install.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# ==============================================================================
# Minimal .deb-only Debian 13 install proof.
#
# This is deliberately the SMALLEST possible clean-room test and must run
# BEFORE the full two-stage installer integration test. It proves the ECLI
# .deb is self-sufficient on a stock Debian 13 image:
#
#   * does NOT run scripts/install_ecli_linters.py;
#   * does NOT preinstall Python (the base debian:trixie image has none);
#   * does NOT preinstall any F4 linter/toolchain package;
#   * installs ONLY the local .deb through APT;
#   * runs `ecli --version`;
#   * proves APT resolved every ELF NEEDED entry (via `ldd`), i.e. that the
#     declared Depends: field is complete and the binary is not missing a
#     runtime library such as libz.so.1/zlib1g.
#
# Usage (inside a clean debian:trixie container, as root):
#   sh packaging/debian/verify_deb_minimal_install.sh /path/to/ecli_*.deb
# ==============================================================================

set -eu

DEB="${1:?usage: verify_deb_minimal_install.sh <path-to-ecli.deb>}"

step() { printf '\n===== [%s] =====\n' "$1"; }

step "identity: Debian 13 amd64, no Python, no linter toolchain preinstalled"
. /etc/os-release
[ "$ID" = "debian" ] || { echo "FAIL: not Debian ($ID)"; exit 1; }
[ "${VERSION_ID%%.*}" = "13" ] || { echo "FAIL: not Debian 13 ($VERSION_ID)"; exit 1; }
[ "$(dpkg --print-architecture)" = "amd64" ] || { echo "FAIL: not amd64"; exit 1; }
if command -v python3 >/dev/null 2>&1; then
    echo "FAIL: python3 is present; this must be a minimal image"
    exit 1
fi
for tool in ruff biome zig hadolint taplo actionlint pmd spotbugs \
            golangci-lint tflint markdownlint-cli2 yamllint shellcheck \
            clang-tidy cppcheck clang-format checkstyle cargo sqlfluff; do
    if command -v "$tool" >/dev/null 2>&1; then
        echo "FAIL: linter toolchain tool '$tool' is present; must be absent"
        exit 1
    fi
done
echo "OK: Debian 13 amd64, no python3, no F4 linter/toolchain present"

step "install ONLY the local .deb through APT (no other package selected)"
apt-get update -qq
apt-get install -y "$DEB"

step "ecli --version"
VERSION_OUTPUT=$(ecli --version)
echo "$VERSION_OUTPUT"
case "$VERSION_OUTPUT" in
    "ecli "*) ;;
    *) echo "FAIL: unexpected ecli --version output: $VERSION_OUTPUT"; exit 1 ;;
esac

step "prove APT resolved every ELF NEEDED entry (ldd: no 'not found')"
LDD_OUTPUT=$(ldd /usr/bin/ecli)
echo "$LDD_OUTPUT"
if echo "$LDD_OUTPUT" | grep -q "not found"; then
    echo "FAIL: /usr/bin/ecli has an unresolved runtime dependency"
    exit 1
fi
echo "OK: every NEEDED shared library resolved (Depends: is complete)"

printf '\n===== MINIMAL DEB-ONLY INSTALL: PASS =====\n'
