---
description: Prepare-only PyPI packaging inspection for ECLI. Checks Python package metadata, wheel/sdist readiness, version consistency, and upload blockers without publishing.
argument-hint: "[optional focus: metadata|sdist|wheel|version|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/package-pypi.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /package-pypi — ECLI PyPI Package Prepare-Only Check

Inspect PyPI packaging readiness without publishing.

Argument: `$ARGUMENTS`

## Purpose

Check Python package metadata and distribution readiness.

This command must not upload to PyPI.

## Covered canonical artifact entries

This command covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- PyPI wheel
- PyPI source distribution

## Exact official release asset gate

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. No reduced or subset official release is
allowed. The PyPI wheel and source distribution are two required entries in the
same exact asset set.

Release readiness is blocked unless `scripts/verify_release_assets.py` verifies
the exact top-level asset set under `releases/<version>/`. Checksum sidecars are
verification evidence under `.checksums/` or workflow artifacts; they are not
GitHub Release assets.

## Required reading

Before PyPI packaging analysis, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/build-runbook.md`
5. `.claude/release-runbook.md`
6. `.claude/drift-register.md`
7. `audit-report.md`
8. `pyproject.toml`
9. `README.md`
10. `CHANGELOG.md` if present

Inspect:

```text
src/ecli/
pyproject.toml
uv.lock
scripts/
.github/workflows/
```

## Delegate to

Use or follow the policy of:

* `build-engineer`
* `release-engineer` in prepare-only mode
* `quality-engineer`

## Allowed Stage 1 work

You may:

* inspect `pyproject.toml`,
* inspect package metadata,
* inspect console script entry,
* inspect version surfaces,
* inspect packaging workflow,
* prepare a PyPI readiness checklist,
* report missing metadata,
* report drift from `pyproject.toml`.

## Conditional build rule

Do not run distribution build commands unless the user explicitly asks for a local build and the command is allowed by `.claude/settings.local.json`.

If allowed in a later phase, local build may use:

```sh
uv build
```

But Stage 1 default is inspect/report only.

## Forbidden work

Do not run:

```sh
twine upload
uv publish
python -m twine upload
gh release create
gh release upload
git commit
git push
git tag
make publish-pypi
make publish
make publish-*
make release
make release-*
```

## Metadata report

Use:

```text
PyPI package readiness report

Package name:
Version source:
Declared version:
Build backend:
Console scripts:
Required Python:
Dependencies:
Optional dependencies:
README metadata:
License metadata:
Distribution build run: no
Upload attempted: no
Drift:
Recommended next step:
```

## AUD-003 rule

If console entry metadata and PyInstaller/main entry behavior differ, report it as intentional only when a test proves the delegation path.

## Output format

Finish with:

```text
PyPI prepare-only summary:
- Package metadata:
- Version consistency:
- Entry points:
- Build readiness:
- Upload blocked:
- Drift:
- Recommended next step:
```
