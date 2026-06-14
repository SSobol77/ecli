<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/contributor/local-validation.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Local Validation

## Command Matrix (Verified vs Provisional)

| Command | Purpose | Verified status | Required for contributor? | Required for maintainer? |
|---|---|---|---:|---:|
| `ruff check src` | lint baseline | verified in CI pattern | Yes | Yes |
| `ruff format --check src` | formatting gate | verified in CI pattern | Yes | Yes |
| `python main.py` | runtime sanity | repository-observed entrypoint | Yes | Yes |
| `pytest` | tests baseline check | partial/validation-required if tests absent | Optional | Yes |
| `uv run pytest -q tests/packaging` | canonical 21-item packaging release-contract matrix guard | repository-local static check | Optional | Yes |
| platform packaging script | artifact build | environment-dependent | No | Yes (release/packaging roles) |

The packaging guard enforces the `Canonical 21-Item Platform & Packaging
Artifact Matrix` in `docs/release/artifact-contract.md`: every one of the 21
entries must keep a `tests/packaging/` test file, a Claude command mapping, a
Codex prompt mapping, and (where relevant) a mapped GitHub workflow.

## Minimum Validation Path (Contributor)

1. lint
2. format check
3. runtime launch sanity

## Full Validation Path (Maintainer)

1. minimum path
2. test path (`pytest`) if test baseline exists
3. packaging release-contract matrix guard
4. packaging path for affected artifact(s)
5. artifact contract and checksum verification

## Drift Handling Rule

- If documented command fails due to repository/tooling drift:
  1. capture error evidence,
  2. record drift in planning/risk docs,
  3. update docs and/or scripts in same governance cycle.

## Evidence Expectations for Doc-Related Changes

- command output snippets or validation note
- file/path references updated consistently
- traceability update in planning docs when validation is partial

## Validation-Required Note

- If tests baseline remains absent/partial, maintainers must compensate with focused runtime and packaging verification evidence.
