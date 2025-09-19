#!/usr/bin/env bash
set -euo pipefail
# Package .deb from built binary using fpm
# Requires: ruby, fpm, dpkg, fakeroot
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$PROJECT_ROOT/build/linux/dist/ecli"
VERSION="${1:-0.1.0}"
ARCH="${ARCH:-amd64}"
OUT="$PROJECT_ROOT/dist"
mkdir -p "$OUT"

fpm -s dir -t deb \
  -n ecli \
  -v "$VERSION" \
  -a "$ARCH" \
  --description "ECLI — fast terminal code editor." \
  --license "GPL-3.0-or-later" \
  --maintainer "Siergej Sobolewski <s.sobolewski@hotmail.com>" \
  --after-install "$PROJECT_ROOT/packaging/linux/fpm-common/postinst" \
  --before-remove "$PROJECT_ROOT/packaging/linux/fpm-common/prerm" \
  --deb-no-default-config-files \
  "$BIN=/usr/bin/ecli" \
  "$PROJECT_ROOT/packaging/linux/fpm-common/ecli.desktop=/usr/share/applications/ecli.desktop" \
  --package "$OUT/ecli_${VERSION}_${ARCH}.deb"

echo "Created: $OUT/ecli_${VERSION}_${ARCH}.deb"
