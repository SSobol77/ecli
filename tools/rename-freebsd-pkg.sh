#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tools/rename-freebsd-pkg.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

set -eu

ver="${1:-0.1.0}"
outdir="releases/$ver"
src_pkg="$outdir/ecli-${ver}.pkg"
dst_pkg="$outdir/ecli_${ver}_amd64.pkg"

if [ ! -f "$src_pkg" ]; then
  echo "Source pkg not found: $src_pkg" >&2
  exit 1
fi

mv -f "$src_pkg" "$dst_pkg"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$dst_pkg" > "${dst_pkg}.sha256"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$dst_pkg" > "${dst_pkg}.sha256"
elif command -v sha256 >/dev/null 2>&1; then
  sha256 -q "$dst_pkg" > "${dst_pkg}.sha256"
else
  echo "No checksum tool found (sha256sum/shasum/sha256)" >&2
  exit 1
fi

rm -f "$outdir/ecli-${ver}.pkg.sha256" 2>/dev/null || true
echo "Renamed to: $dst_pkg"
ls -la "$outdir"
