#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Project: ECLI
# File: scripts/check-log-invariant.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# Author: Siergej Sobolewski
# License: Apache License, Version 2.0
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

failed=0

check_untracked_generated_artifacts() {
  local path

  while IFS= read -r path; do
    case "$path" in
      logs/*)
        continue
        ;;
      *.log|*.log.*|*.trace|*.dump|*.tmp|*.pid|*.sock|dry-run-*|test-evidence-*|smoke-output-*|agent-debug-*)
        printf 'ERROR: untracked generated artifact outside logs/: %s\n' "$path" >&2
        failed=1
        ;;
    esac
  done < <(git ls-files --others --exclude-standard)
}

check_tracked_generated_artifacts() {
  local path

  while IFS= read -r path; do
    case "$path" in
      logs/.gitkeep|logs/README.md)
        continue
        ;;
      logs/*)
        continue
        ;;
      *.log|*.log.*|*.trace|*.dump|*.tmp|*.pid|*.sock)
        printf 'ERROR: tracked generated artifact outside logs/: %s\n' "$path" >&2
        failed=1
        ;;
    esac
  done < <(git ls-files)
}

check_forbidden_runtime_dirs() {
  local path

  while IFS= read -r path; do
    case "$path" in
      .ecli/*|.ecli/vmlab/*|tmp/*|.tmp/*|.cache/*)
        printf 'ERROR: generated/runtime artifact in forbidden location: %s\n' "$path" >&2
        failed=1
        ;;
    esac
  done < <(git ls-files --others --exclude-standard)
}

check_untracked_generated_artifacts
check_tracked_generated_artifacts
check_forbidden_runtime_dirs

if [ "$failed" -ne 0 ]; then
  printf '\nDevelopment artifacts must be written only under logs/.\n' >&2
  exit 1
fi

printf 'OK: development log invariant satisfied.\n'
