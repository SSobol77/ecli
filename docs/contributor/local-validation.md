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
| `make help` / `make help-full` | Makefile command-surface discovery | repository-local command | Yes | Yes |
| `make doctor` / `make sysinfo` | host/tool inspection without building packages | repository-local command | Optional | Yes |
| `make validate` / `make validate-fast` | safe local validation entrypoint | repository-local command | Yes | Yes |
| `make validate-packaging` / `make validate-release-contract` | packaging/release contract checks | repository-local command | Optional | Yes |
| `task help` / `task validate-packaging` | optional developer convenience wrappers over Makefile targets | repository-local command | Optional | Optional |
| `pytest` | tests baseline check | partial/validation-required if tests absent | Optional | Yes |
| `uv run pytest -q tests/packaging` | canonical 21-item packaging release-contract matrix guard | repository-local static check | Optional | Yes |
| `uv run pytest -q tests/packaging/test_scripts_python_migration_contract.py` | shell-to-Python script migration contract guard | repository-local static check | Optional | Yes |
| `uv run python scripts/check_log_invariant.py` | development log-location invariant (artifacts only under `logs/`) | read-only git check | Optional | Yes |
| `uv run python scripts/verify_artifact.py <artifact>` | artifact checksum verification (exit codes 0-5) | structural/local check | No | Yes (release/packaging roles) |
| platform packaging script | artifact build | environment-dependent | No | Yes (release/packaging roles) |

The packaging guard enforces the `Canonical 21-Item Platform & Packaging
Artifact Matrix` in `docs/release/artifact-contract.md`: every one of the 21
entries must keep a `tests/packaging/` test file, a Claude command mapping, a
Codex prompt mapping, and (where relevant) a mapped GitHub workflow.

Makefile remains the authoritative build/release contract. `Taskfile.yml` is an
optional developer convenience wrapper only; it must delegate to existing
Makefile targets, must not become the sole release contract, and must not bypass
guarded release or publish behavior. CI and release gates continue to rely on
the existing canonical command surfaces.

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

## Script Migration Note

Active shell wrappers under `scripts/` have been removed. Use canonical Python
entrypoints under `scripts/` for validation and packaging checks.
`scripts/build-and-package-windows.ps1` remains the separate Windows PowerShell
packaging surface. `tools/freebsd-chroot-build.sh` is a FreeBSD chroot helper
outside this migration, and the unused FreeBSD package-renaming shell helper
was removed as tracked tooling.

## Evidence Expectations for Doc-Related Changes

- command output snippets or validation note
- file/path references updated consistently
- traceability update in planning docs when validation is partial

## Validation-Required Note

- If tests baseline remains absent/partial, maintainers must compensate with focused runtime and packaging verification evidence.
