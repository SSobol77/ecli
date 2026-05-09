<!--
Path: docs/contributor/local-validation.md
File: local-validation.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Local Validation

## Command Matrix (Verified vs Provisional)

| Command | Purpose | Verified status | Required for contributor? | Required for maintainer? |
|---|---|---|---:|---:|
| `ruff check src` | lint baseline | verified in CI pattern | Yes | Yes |
| `ruff format --check src` | formatting gate | verified in CI pattern | Yes | Yes |
| `python main.py` | runtime sanity | repository-observed entrypoint | Yes | Yes |
| `pytest` | tests baseline check | partial/validation-required if tests absent | Optional | Yes |
| platform packaging script | artifact build | environment-dependent | No | Yes (release/packaging roles) |

## Minimum Validation Path (Contributor)

1. lint
2. format check
3. runtime launch sanity

## Full Validation Path (Maintainer)

1. minimum path
2. test path (`pytest`) if test baseline exists
3. packaging path for affected artifact(s)
4. artifact contract and checksum verification

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
