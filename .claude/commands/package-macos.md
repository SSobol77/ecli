---
description: Prepare-only macOS packaging inspection for ECLI. Reviews DMG workflow, PyInstaller entry contract, artifact naming, and release risks without building, uploading, or triggering workflows.
argument-hint: "[optional focus: pyinstaller|dmg|workflow|version|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/package-macos.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /package-macos - ECLI macOS Packaging Prepare-Only Check

Inspect macOS packaging readiness without building, publishing, uploading, tagging, pushing, or triggering workflows.

Argument: `$ARGUMENTS`

## Purpose

Validate the macOS packaging plan and artifact contract in prepare-only mode.

This command exists for release-matrix completeness. It must not execute macOS-only build steps from a non-macOS environment and must not trigger remote release workflows.

## Covered canonical artifact entries

This command covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- macOS `.app`
- macOS `.dmg`

## Exact official release asset gate

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. No reduced or subset official release is
allowed. macOS app evidence and the macOS DMG are mandatory entries in the exact
asset set.

Release readiness is blocked unless `scripts/verify_release_assets.py` verifies
the exact top-level asset set under `releases/<version>/`. Checksum sidecars are
verification evidence under `.checksums/` or workflow artifacts; they are not
GitHub Release assets.

## Required reading

Before macOS packaging analysis, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/build-runbook.md`
5. `.claude/release-runbook.md`
6. `.claude/drift-register.md`
7. `audit-report.md`
8. `pyproject.toml`
9. `Makefile`

Inspect when present:

```text
main.py
scripts/build_and_package_macos.py   # canonical Python entrypoint
packaging/pyinstaller/ecli.spec
.github/workflows/macos-dmg.yml
.github/workflows/macos-validate.yml
docs/install/macos.md
docs/release/artifact-contract.md
docs/release/packaging-flows.md
```

## Delegate to

Use or follow the policy of:

* `build-engineer`
* `release-engineer` in prepare-only mode
* `quality-engineer`

## Allowed Stage 1 work

You may:

* inspect macOS packaging scripts,
* inspect PyInstaller configuration,
* inspect GitHub Actions macOS workflows,
* inspect artifact naming conventions,
* inspect version surfaces,
* inspect the root `main.py` compatibility shim,
* prepare a macOS packaging checklist,
* report artifact-contract drift.

You may run only non-publishing local inspection commands allowed by `.claude/settings.local.json`, such as:

```sh
make help
make sysinfo
```

## Forbidden Stage 1 work

Do not run macOS packaging builds unless the user explicitly promotes the task out of Stage 1.

Do not run:

```sh
gh workflow run
gh run cancel
gh run rerun
gh release create
gh release upload
gh release edit
gh release delete
make package-macos
make release-macos
make release
make release-*
make publish
make publish-*
twine upload
uv publish
git commit
git push
git tag
git reset
git clean
```

Do not create, upload, or modify `.dmg`, `.app`, checksum, installer, or release assets.

## macOS packaging contract report

Use this format:

```text
macOS packaging contract report

Requested focus:
Authoritative version source:
Declared version:
Compatibility launcher:
PyInstaller spec:
Workflow paths:
Expected DMG artifact:
Expected checksum:
Hard-coded version surfaces:
Workflow trigger required:
Publishing attempted: no
Drift:
Recommended next step:
```

## AUD-003 rule

Treat `pyproject.toml` as the version source of truth.

If PyInstaller uses a different entry surface than the installed console script, report whether the root `main.py` shim delegates to `ecli.__main__.main`.

## Output format

Finish with:

```text
macOS prepare-only summary:
- Requested focus:
- Compatibility launcher:
- Artifact contract:
- Version consistency:
- Workflow risks:
- Publishing commands blocked:
- Recommended next step:
```
