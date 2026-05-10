<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/extensions/diagnostics-model.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Diagnostics Model

## Current vs Target

- Observed current state: Python diagnostics via Ruff LSP; optional external DevOps linter path.
- Target state: unified internal diagnostics schema consumed by UI.

## Canonical Diagnostics Schema

| Field | Type | Required | Meaning | Notes |
|---|---|---:|---|---|
| `source` | string | Yes | origin system (`ruff`, `devops-linter`, etc.) | normalized identifier |
| `severity` | enum | Yes | issue severity | `error` / `warning` / `info` |
| `message` | string | Yes | diagnostic text | user-visible |
| `line` | int | Yes | 1-based line | normalize from source if needed |
| `column` | int | No | 1-based column | optional if unavailable |
| `end_line` | int | No | range end line | optional |
| `end_column` | int | No | range end column | optional |
| `code` | string | No | provider code/id | optional |

## Severity Taxonomy

- `error`: actionable issue likely blocking correctness.
- `warning`: non-fatal issue requiring review.
- `info`: advisory.

## External Source Mapping Table

| External source | Mapping rule | Validation note |
|---|---|---|
| Ruff LSP payload | map `range.start` to line/column (0-based) and convert to 1-based output | ensure 0-based -> 1-based conversion |
| DevOps linter text output | parse line/column/message (1-based) when available | parser robustness validation required; assume 1-based line/column input |

## Normalization Rules

- normalize numeric positions to 1-based display coordinates.
- fill absent optional fields with null/omission.
- reject malformed mandatory fields and emit fallback diagnostic.

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
