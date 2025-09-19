#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$PROJECT_ROOT/build/linux/dist/ecli"
VERSION="${1:-0.1.0}"
ARCH="${ARCH:-x86_64}"
OUT="$PROJECT_ROOT/dist"
mkdir -p "$OUT"

fpm -s dir -t rpm \
  -n ecli \
  -v "$VERSION" \
  -a "$ARCH" \
  --description "ECLI — fast terminal code editor." \
  --license "GPL-3.0-or-later" \
  --maintainer "Siergej Sobolewski <s.sobolewski@hotmail.com>" \
  "$BIN=/usr/bin/ecli" \
  --package "$OUT/ecli-${VERSION}.${ARCH}.rpm"

echo "Created: $OUT/ecli-${VERSION}.${ARCH}.rpm"
