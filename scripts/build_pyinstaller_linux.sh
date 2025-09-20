#!/usr/bin/env bash
set -euo pipefail
# Build self-contained binary with PyInstaller (Linux)
# Requires: uv, pyinstaller
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/build/linux"
mkdir -p "$OUT_DIR"

uv sync --frozen
uv run pyinstaller \
  --name ecli \
  --onefile \
  --console \
  --clean \
  --distpath "$OUT_DIR/dist" \
  --workpath "$OUT_DIR/work" \
  --paths "$PROJECT_ROOT/src" \
  "$PROJECT_ROOT/src/ecli/__main__.py"

echo "Built binary: $OUT_DIR/dist/ecli"
