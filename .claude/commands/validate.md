---
description: Run the Stage 1 ECLI validation gate with pytest/ruff/mypy/runtime-import reporting and baseline-aware interpretation.
argument-hint: "[optional focus: all|pytest|ruff|mypy|runtime|config|artifact|logs]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/validate.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /validate — ECLI Stage 1 Validation Gate

Run the ECLI Stage 1 validation gate.

Argument: `$ARGUMENTS`

## Purpose

Validate the repository using audit-aligned, baseline-aware gates.

This command does not fix code automatically. It reports evidence and recommends the next step.

## Required reading

Before running validation, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/validation-runbook.md`
5. `.claude/drift-register.md`
6. `audit-report.md`
7. `pyproject.toml`
8. `Makefile`

## Delegate to

Use or follow the policy of:

- `quality-engineer`
- `tester`
- `runtime-engineer`
- `log-analyst` when logs are involved
- `release-engineer` only for prepare-only artifact/version drift interpretation

## Canonical validation commands

Run only when allowed by `.claude/settings.local.json`:

```sh
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
uv run pytest -ra -q
uv run python scripts/check_runtime_imports.py
```

Optional non-publishing discovery:

```sh
make help
make sysinfo
make test
make lint
```

Packaging script-migration and log-invariant checks (read-only, non-publishing):

```sh
uv run pytest -q tests/packaging/test_scripts_python_migration_contract.py
uv run python scripts/check_log_invariant.py
```

## Gate interpretation

### Pytest

Treat pytest as the primary functional baseline.

If pytest fails, report it as a direct validation failure.

### Ruff

Report exact files and rule codes.

Do not claim ruff is clean unless the command exits cleanly.

### Mypy

Mypy may have known baseline debt. Treat it as baseline/diff unless the task explicitly targets full type cleanup.

Always highlight P0-related mypy errors separately, especially `src/ecli/core/History.py`.

### Runtime imports

Use:

```sh
uv run python scripts/check_runtime_imports.py
```

Do not use bare `python`.

### Config/runtime validation

For AUD-001, distinguish between:

* typed `ConfigService` validation,
* legacy runtime `utils.load_config()` path,
* shipped `config.toml`,
* `syntax_highlighting` regex compilation.

Do not reduce AUD-001 to TOML syntax parsing.

### Artifact contract

For AUD-003, report version and artifact drift in prepare-only mode.

Do not run release or publish targets.

### Curses boundary

For AUD-004, report current baseline. Do not hard-fail on existing baseline unless a growth baseline exists.

## Forbidden actions

Do not run:

```sh
git commit
git push
git tag
git reset
git clean
twine upload
gh workflow run
gh run cancel
gh run rerun
gh release create
gh release upload
make release
make release-*
make publish
make publish-*
```

## Output format

Finish with:

```text
Validation summary:
- Focus:
- Pytest:
- Ruff:
- Mypy:
- Runtime imports:
- Config/runtime validation:
- Artifact contract:
- Curses boundary:
- Logging risk:
- Baseline drift:
- Blocked actions:
- Recommended next step:
```
