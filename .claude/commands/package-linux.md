---
description: Prepare-only Linux packaging inspection for ECLI. Checks build targets, scripts, artifact names, and drift without publishing or uploading.
argument-hint: "[optional target: deb|rpm|appimage|snap|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/package-linux.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /package-linux — ECLI Linux Packaging Prepare-Only Check

Inspect Linux packaging readiness without publishing.

Argument: `$ARGUMENTS`

## Purpose

Prepare and validate the Linux packaging plan for ECLI.

This command is Stage 1 prepare-only. It must not publish or upload artifacts.

## Covered canonical artifact entries

This command covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- Linux generic PyInstaller executable
- Linux release tarball
- Debian / Ubuntu `.deb`
- generic RPM `.rpm`
- openSUSE / SUSE RPM
- Arch Linux `PKGBUILD`
- Slackware `.txz`
- AppImage
- Docker DEB build helper
- Docker RPM build helper

## Required reading

Before any packaging-related action, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/build-runbook.md`
5. `.claude/release-runbook.md`
6. `.claude/drift-register.md`
7. `audit-report.md`
8. `pyproject.toml`
9. `Makefile`

Inspect:

```text
scripts/
packaging/
.github/workflows/
docs/INSTALL.md
docs/BUILD_FROM_SOURCE.md
```

## Delegate to

Use or follow the policy of:

* `build-engineer`
* `release-engineer` in prepare-only mode
* `quality-engineer` for validation interpretation

## Allowed Stage 1 work

You may:

* inspect Linux packaging targets,
* inspect packaging scripts,
* inspect artifact naming conventions,
* inspect version surfaces,
* run `make help` and `make sysinfo` if allowed,
* run `sh -n scripts/*` and `bash -n scripts/*` if allowed,
* prepare a packaging checklist,
* report artifact-contract drift.

## Forbidden Stage 1 work

Do not run packaging targets that create release assets unless the user explicitly promotes the task out of Stage 1.

Do not run:

```sh
make release
make release-*
make publish
make publish-*
twine upload
gh release create
gh release upload
git commit
git push
git tag
```

## Artifact contract inspection

Report:

```text
Linux packaging contract report

Requested target:
Version source:
Expected artifacts:
Known scripts:
Known Makefile targets:
Tracked descriptors:
Hard-coded versions:
Mutates tracked files:
Checksums expected:
Publishing attempted: no
Drift:
Recommended next step:
```

## AUD-003 rule

Treat `pyproject.toml` as the version source of truth.

Any hard-coded Linux packaging version surface must be reported.

Any script that mutates tracked packaging descriptors must be reported as release-risk drift.

## Output format

Finish with:

```text
Linux packaging prepare-only summary:
- Requested target:
- Targets found:
- Scripts found:
- Version drift:
- Artifact naming drift:
- Tracked-file mutation risk:
- Publishing commands blocked:
- Recommended next step:
```
