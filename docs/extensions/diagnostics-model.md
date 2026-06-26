<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/extensions/diagnostics-model.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Diagnostics Model

## Current vs Target

- Observed current state: Python diagnostics via Ruff LSP; optional external DevOps linter path.
- Target state: unified internal diagnostics schema consumed by UI.

## Canonical Diagnostics Schema

| Field | Type | Required | Meaning | Notes |
|---|---|---:|---|---|
| `file_path` | string | Yes | file containing the diagnostic | absolute or provider-reported path |
| `source` | string | Yes | origin system (`ruff`, `devops-linter`, etc.) | normalized identifier |
| `severity` | enum | Yes | issue severity | `error` / `warning` / `info` / `hint` |
| `message` | string | Yes | diagnostic text | user-visible |
| `line` | int | Yes | 1-based line | normalize from source if needed |
| `column` | int | Yes | 1-based column | set to `1` when unavailable |
| `end_line` | int | No | range end line | optional |
| `end_column` | int | No | range end column | optional |
| `code` | string/null | No | provider code/id | optional; null provider codes must not drop the diagnostic |
| `fix_hint` | string | No | provider fix description | text only; ECLI must not apply edits automatically in the F4 milestone |
| `suggested_code` | string | No | optional provider-proposed code shape | preview-only; never applied by the F4 milestone |

## Severity Taxonomy

- `error`: actionable issue likely blocking correctness.
- `warning`: non-fatal issue requiring review.
- `info`: advisory.
- `hint`: lowest-severity guidance or optional improvement.

## External Source Mapping Table

| External source | Mapping rule | Validation note |
|---|---|---|
| Ruff LSP payload | map `range.start` to line/column (0-based) and convert to 1-based output | ensure 0-based -> 1-based conversion |
| DevOps linter text output | parse line/column/message (1-based) when available | parser robustness validation required; assume 1-based line/column input |

## Normalization Rules

- normalize numeric positions to 1-based display coordinates.
- fill absent line/column values with 1 for visible, navigable output.
- deterministic UI ordering is severity, file path, line, column, source, code.
- fix data is display-only text; automatic code modification is out of scope for
  the F4 Diagnostics Panel milestone.
- reject malformed mandatory fields and emit fallback diagnostic.

## F4 Panel Display Contract

- main-list rows use short severity, source, project-relative/basename path,
  line, column, and message:
  `<severity-short> <source> <relative-file>:<line>:<column> <message>`.
- absolute paths may remain in the normalized diagnostic model, but the panel
  must not render absolute paths before the message.
- constrained-width rows must preserve severity/source, line/column, and visible
  message text before spending remaining space on path context.
- the right-side panel is the only authoritative diagnostics list.
- `F4` opens/closes the panel and must not start Ruff automatically.
- `r` runs diagnostics for the current file; `R` runs workspace diagnostics.
- a completed clean run displays `Diagnostics: PASS` and `No issues found.`;
  the status bar message is `Diagnostics: PASS — no issues found.` and the
  PASS label uses the success colour role when colour is available.
- `Enter` is navigation-only and must report
  `Jumped to <relative-file>:<line>:<column>` on success.
- `d` or `Space` opens a centered `Diagnostic details` popup for the currently
  selected diagnostic only. The popup may show path, line/column, source, code,
  full message, fix hint, and suggested code shape, and must include
  `Preview only. No changes were applied.`
- the centered popup must never render a second full diagnostics list.
- while the panel is open, the selected diagnostic marks only the matching
  editor line-number/gutter using severity colour (`error`, `warning`,
  `info`/`hint`). Selection changes update the marker without moving the
  cursor; `Enter` remains the only jump action. The marker clears on panel
  close, refresh start, clean/replaced snapshots, stale selections, and file
  switches away from the diagnostic file.

## Malformed Diagnostics Handling

- malformed item: log warning/error, skip item, continue pipeline.
- malformed batch: present generic diagnostics failure message to user.

## Normalization Examples

Example A (Ruff):
- Input: `line=0, character=4, message="x"`
- Output: `line=1, column=5, message="x"`

Example B (text linter):
- Input: `"12:7 Missing key"`
- Output: `line=12, column=7, message="Missing key"`
