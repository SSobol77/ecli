#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: .claude/hooks/block-mutations.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# PreToolUse(Bash) guard: hard-block maintainer-owned mutations in agent runs.
# Exit 2 blocks the tool call; stderr is fed back to the model.
set -euo pipefail
input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"
[ -z "$cmd" ] && exit 0
deny_re='(^|[;&|[:space:]])(git[[:space:]]+(add|commit|push|tag)|gh[[:space:]]+(pr[[:space:]]+create|issue[[:space:]]+(edit|close|comment|reopen)|release|workflow[[:space:]]+run|run[[:space:]]+(rerun|cancel))|twine[[:space:]]+upload|make[[:space:]]+(release|publish))'
if printf '%s' "$cmd" | grep -Eq "$deny_re"; then
  echo "BLOCKED by .claude/hooks/block-mutations.sh: '$cmd' is a maintainer-owned action (prepare-only Stage 1). Run it yourself." >&2
  exit 2
fi
exit 0
