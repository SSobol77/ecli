#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/clean_logs.sh
#
# Clean volatile local runtime logs before manual smoke/debug sessions.

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"

mkdir -p "$LOG_DIR"

find "$LOG_DIR" -mindepth 1 -type f \
  ! -name ".gitkeep" \
  ! -name "README.md" \
  -delete

: > "$LOG_DIR/editor.log"

printf 'Cleaned runtime logs in %s\n' "$LOG_DIR"