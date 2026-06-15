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

## Shell-to-Python script migration

The shell-to-Python migration is **complete**: active shell wrappers under
`scripts/` have been removed. Use the Python entrypoints when inspecting Linux
packaging flows:

- `python3 scripts/verify_artifact.py <artifact>` — SHA256 sidecar verifier (exit codes `0`–`5`).
- `python3 scripts/sign_checksums.py <artifact> [...]` — writes `<artifact>.sha256` sidecars.
- `python3 scripts/check_log_invariant.py` — development log-location invariant.
- `python3 scripts/build_pyinstaller_linux.py`, `scripts/build_and_package_deb.py`,
  `scripts/build_and_package_rpm.py`, `scripts/build_and_package_opensuse_rpm.py`,
  `scripts/build_and_package_arch.py`, `scripts/build_and_package_slackware.py`,
  `scripts/package_appimage.py`, `scripts/build_docker.py`, and
  `scripts/verify_runtime.py`.

The migration contract is defined in
`docs/release/artifact-contract.md` under `Shell-to-Python Script Migration` and
enforced by `tests/packaging/test_scripts_python_migration_contract.py`. Report
any active shell logic reintroduced under `scripts/` as release-blocking drift.

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
