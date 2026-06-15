---
description: Prepare-only FreeBSD packaging inspection for ECLI. Reviews FreeBSD .pkg paths, VM/chroot/ports scripts, artifact naming, and release-path drift without publishing.
argument-hint: "[optional target: native|chroot|ports|ci|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/package-freebsd.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /package-freebsd — ECLI FreeBSD Packaging Prepare-Only Check

Inspect FreeBSD packaging readiness without publishing.

Argument: `$ARGUMENTS`

## Purpose

Validate the FreeBSD packaging plan and artifact contract in prepare-only mode.

This command must not publish, upload, tag, push, commit, or trigger release workflows.

## Covered canonical artifact entries

This command covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- FreeBSD `.pkg`
- FreeBSD ports/chroot build path

## Required reading

Before FreeBSD packaging analysis, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/build-runbook.md`
5. `.claude/release-runbook.md`
6. `.claude/drift-register.md`
7. `audit-report.md`
8. `freebsd-pkg-build-scripts-list.md` if present
9. `pyproject.toml`
10. `Makefile`

Inspect:

```text
scripts/build_and_package_freebsd.py   # canonical Python entrypoint
scripts/build_freebsd_pkg.py           # canonical Python entrypoint
scripts/build_freebsd_port.py          # canonical Python entrypoint
tools/freebsd-chroot-build.sh          # chroot helper (not yet migrated)
.github/workflows/freebsd-pkg.yml
.github/workflows/release.yml
```

## Delegate to

Use or follow the policy of:

* `build-engineer`
* `runtime-engineer` for isolated smoke checks
* `release-engineer` in prepare-only mode

## Allowed Stage 1 work

You may:

* inspect FreeBSD scripts and workflows,
* run script syntax checks if allowed,
* inspect artifact naming,
* inspect checksum policy,
* report release-path ambiguity,
* report whether FreeBSD release is standalone, workflow-attached, or out-of-band.

## Forbidden Stage 1 work

Do not trigger FreeBSD CI.

Do not run:

```sh
gh workflow run
gh run cancel
gh run rerun
make package-freebsd-ci
make release-freebsd
make release
make release-*
make publish
make publish-*
git commit
git push
git tag
```

Do not create or upload `.pkg` release assets unless the user explicitly starts a packaging phase outside Stage 1.

## FreeBSD contract report

Use:

```text
FreeBSD packaging contract report

Requested target:
Authoritative path:
Native path:
Chroot path:
Ports path:
CI path:
Release workflow path:
Expected artifact:
Expected checksum:
Version source:
Out-of-band release risk:
Publishing attempted: no
Drift:
Recommended next step:
```

## AUD-010 rule

If both standalone FreeBSD workflow and release workflow contain FreeBSD logic, report the ambiguity.

Do not choose one silently.

## Output format

Finish with:

```text
FreeBSD packaging prepare-only summary:
- Requested target:
- Paths inspected:
- Artifact contract:
- Checksum contract:
- Release path ambiguity:
- Commands blocked:
- Recommended next step:
```
