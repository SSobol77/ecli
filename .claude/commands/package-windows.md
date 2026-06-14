---
description: Prepare-only Windows packaging inspection for ECLI. Reviews PyInstaller/NSIS workflow, Windows artifact naming, version drift, and release risks without building, uploading, or triggering workflows.
argument-hint: "[optional focus: nsis|pyinstaller|workflow|version|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/package-windows.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /package-windows — ECLI Windows Packaging Prepare-Only Check

Inspect Windows packaging readiness without building, publishing, uploading, tagging, pushing, or triggering workflows.

Argument: `$ARGUMENTS`

## Purpose

Validate the Windows packaging plan and artifact contract in prepare-only mode.

This command exists for release-matrix completeness. It must not execute Windows-only build steps from a non-Windows environment and must not trigger remote release workflows.

## Covered canonical artifact entries

This command covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- Windows portable `.exe`
- Windows NSIS installer `.exe`

## Required reading

Before Windows packaging analysis, read:

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
packaging/windows/
packaging/windows/nsis/
packaging/windows/nsis/ecli.nsi
packaging/pyinstaller/
packaging/pyinstaller/ecli.spec
.github/workflows/windows-installer.yml
.github/workflows/release.yml
scripts/
docs/INSTALL.md
docs/BUILD_FROM_SOURCE.md
```

## Delegate to

Use or follow the policy of:

* `build-engineer`
* `release-engineer` in prepare-only mode
* `quality-engineer`

## Allowed Stage 1 work

You may:

* inspect Windows packaging descriptors,
* inspect NSIS scripts,
* inspect PyInstaller configuration,
* inspect GitHub Actions Windows workflow,
* inspect artifact naming conventions,
* inspect version surfaces,
* report hard-coded version drift,
* prepare a Windows packaging checklist,
* report missing checksums or artifact-contract gaps.

You may run only non-publishing local inspection commands allowed by `.claude/settings.local.json`, such as:

```sh
make help
make sysinfo
```

You may inspect files with read-only tools.

## Forbidden Stage 1 work

Do not run Windows packaging builds unless the user explicitly promotes the task out of Stage 1.

Do not run:

```sh
gh workflow run
gh run cancel
gh run rerun
gh release create
gh release upload
gh release edit
gh release delete
make package-windows
make release-windows
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

Do not create, upload, or modify `.exe`, `.msi`, `.zip`, installer, or release assets.

Do not mutate tracked NSIS, PyInstaller, or workflow files as part of a build.

## Windows packaging contract report

Use this format:

```text
Windows packaging contract report

Requested focus:
Authoritative version source:
Declared version:
PyInstaller spec:
NSIS descriptor:
Workflow path:
Expected installer artifact:
Expected checksum:
Hard-coded version surfaces:
Tracked-file mutation risk:
Workflow trigger required:
Publishing attempted: no
Drift:
Recommended next step:
```

## AUD-003 rule

Treat `pyproject.toml` as the version source of truth.

If `packaging/windows/nsis/ecli.nsi` or any Windows workflow hard-codes a version, report it as drift unless it is generated from the canonical source.

If PyInstaller uses a different entry surface than the installed console script, report whether a test proves the delegation path.

## Release safety rule

This command must never decide that Windows packaging is release-ready by itself.

It may only produce a prepare-only readiness report. Final Windows build and publishing actions require explicit human approval and must remain outside Stage 1 automation.

## Output format

Finish with:

```text
Windows packaging prepare-only summary:
- Requested focus:
- Paths inspected:
- Version drift:
- PyInstaller status:
- NSIS status:
- Workflow status:
- Artifact contract:
- Checksum contract:
- Publishing commands blocked:
- Recommended next step:
```
