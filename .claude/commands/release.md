---
description: Prepare-only ECLI release readiness review. Generates checklist, version/artifact drift report, and manual runbook without committing, tagging, publishing, or uploading.
argument-hint: "[optional version or focus: preflight|version|artifacts|notes|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/release.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /release — ECLI Prepare-Only Release Readiness

Prepare release evidence and a manual release checklist.

Argument: `$ARGUMENTS`

## Purpose

This command does not publish a release.

It produces release readiness evidence only.

## Covered canonical artifact entries

This command owns the aggregate release surface, covering this entry from the
`Canonical 21-Item Platform & Packaging Artifact Matrix` in
`docs/release/artifact-contract.md`:

- GitHub Actions release/workflow contract map

Stage 1 `/release` is prepare-only and must never:

- commit,
- push,
- tag,
- upload to PyPI,
- create GitHub Releases,
- upload GitHub Release artifacts,
- trigger release workflows.

## Required reading

Before release readiness work, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/release-runbook.md`
5. `.claude/build-runbook.md`
6. `.claude/validation-runbook.md`
7. `.claude/drift-register.md`
8. `audit-report.md`
9. `pyproject.toml`
10. `Makefile`
11. `.github/workflows/`
12. `CHANGELOG.md` if present
13. release docs if present

## Delegate to

Use or follow the policy of:

- `release-engineer`
- `quality-engineer`
- `build-engineer`
- `runtime-engineer`

## Preflight checks

Inspect or run only non-publishing commands allowed by `.claude/settings.local.json`:

```sh
make help
make sysinfo
uv run pytest -ra -q
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
uv run python scripts/check_runtime_imports.py
```

Do not run release or publish targets.

## Forbidden commands

Never run:

```sh
git commit
git push
git tag
git reset
git clean
twine upload
uv publish
python -m twine upload
gh workflow run
gh run cancel
gh run rerun
gh release create
gh release upload
gh release edit
gh release delete
make release
make release-*
make publish
make publish-*
```

## Release readiness report

Produce:

```text
Release readiness report

Requested focus:
Version source:
Declared version:
Git write actions attempted: no
Publishing attempted: no

Validation:
- Pytest:
- Ruff:
- Mypy:
- Runtime imports:

Artifact contract:
- Linux:
- FreeBSD:
- PyPI:
- Windows:
- macOS:
- Checksums:

Drift:
- Version drift:
- Artifact naming drift:
- Workflow drift:
- Documentation drift:

Blocked commands:
- ...

Manual release actions still required:
- ...

Recommended next step:
```

## AUD-003 rule

Do not treat release as ready if version surfaces drift from `pyproject.toml`.

Do not treat tracked packaging descriptor mutation as acceptable release behavior.

## AUD-010 rule

If FreeBSD has more than one release path, report the ambiguity.

Do not silently choose the standalone workflow or release workflow.

## Output format

Finish with:

```text
Prepare-only release summary:
- Requested focus:
- Version source:
- Validation status:
- Artifact status:
- Drift status:
- Publishing commands blocked:
- Manual actions required:
- Recommended next step:
```
