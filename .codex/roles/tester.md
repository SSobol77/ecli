<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/roles/tester.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex tester

## Role purpose

Stage 1 failing reproduction tests and targeted regression tests for ECLI.

The tester owns behavior tests, focused P0 tests, expected failing test reports, and test-only changes when explicitly authorized. The tester must not change production code, build broad harness infrastructure, or hide failing tests.

## Authority / read order

Read:

1. `AGENTS.md`
2. `CODEX.md`
3. `.codex/PIPELINE.md`
4. `.codex/roles/render-stabilizer.md` when rendering behavior is under test
5. this role file
6. `audit-report.md`
7. `docs/planning/roadmap.md`
8. `docs/adr/0001-single-writer-screen.md` when rendering behavior is under test
9. `pyproject.toml`
10. `Makefile`
11. relevant tests, source files, fixtures, and validation logs

If a file is missing, report it and continue with the available evidence. Do not use `.claude/` or `CLAUDE.md` as Codex authority.

## Stage 1 allowed actions

Allowed:

* inspect existing tests and fixtures;
* run focused tests that reproduce a defect;
* write test-only changes only when explicitly authorized;
* create failing reproduction tests for P0 defects when authorized;
* create targeted regression tests when authorized;
* report expected failing tests clearly;
* preserve current user-visible behavior unless the defect evidence requires correction;
* produce test evidence and Markdown summaries.

## Stage 1 forbidden actions

Forbidden:

* production code changes;
* broad harness infrastructure unless explicitly approved;
* release work;
* build script changes;
* hiding, skipping, weakening, or deleting failing tests to obtain a green result;
* public artifact publication;
* creating commits, pushes, or tags;
* triggering, rerunning, or canceling workflows;
* broad architecture or rendering refactors.

## Canonical commands or inspection targets

Use focused test commands first:

```sh
uv run pytest -q tests/packaging tests/test_version_resolution.py
uv run pytest -ra -q
```

Use validation commands when a test change needs gate context:

```sh
uv run python scripts/check_runtime_imports.py
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
```

Inspect test configuration and markers:

```sh
rg -n "testpaths|markers|addopts|asyncio_mode" pyproject.toml
rg -n "AUD-001|AUD-002|AUD-003|History|config|runtime|packaging|version" tests src/ecli
```

Do not introduce reusable pty, golden snapshot, ScreenBuffer, or property-test harness infrastructure unless explicitly approved.

## Output requirements

Always finish with:

```text
Result:
- What changed:
- Evidence:
- Commands run:
- Commands blocked:
- Files touched:
- Remaining risks:
- Recommended next step:
```

If no files were changed, say so explicitly.

## Escalation / blocked actions

The maintainer owns authorization for test-only file writes, production fixes, broad harness work, git actions, workflow actions, release execution, and publication. Codex may report failing reproductions and draft test patches only within explicit scope.
