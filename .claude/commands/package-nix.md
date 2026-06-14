---
description: Prepare-only Nix packaging inspection for ECLI. Reviews flake and package expression coverage, version/license metadata, and local Nix contract drift without building or publishing.
argument-hint: "[optional focus: flake|package|metadata|docs|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/package-nix.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /package-nix - ECLI Nix Packaging Prepare-Only Check

Inspect Nix packaging readiness without building, publishing, uploading, tagging, pushing, or triggering workflows.

Argument: `$ARGUMENTS`

## Purpose

Validate the Nix flake and package expression contract in prepare-only mode.

This command covers local Nix packaging support only. It does not imply nixpkgs publication.

## Covered canonical artifact entries

This command covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- Nix flake
- Nix/NixOS package expression

## Required reading

Before Nix packaging analysis, read:

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
flake.nix
packaging/nix/package.nix
docs/INSTALL.md
docs/contributor/install.md
docs/contributor/build-from-source.md
docs/release/packaging-flows.md
README.md
```

## Delegate to

Use or follow the policy of:

* `build-engineer`
* `release-engineer` in prepare-only mode
* `docs-engineer` when docs drift is found

## Allowed Stage 1 work

You may:

* inspect `flake.nix`,
* inspect `packaging/nix/package.nix`,
* inspect Nix install/build documentation,
* inspect version surfaces,
* inspect license metadata,
* prepare a Nix packaging checklist,
* report drift from `pyproject.toml`.

You may run only non-publishing local inspection commands allowed by `.claude/settings.local.json`, such as:

```sh
make help
make sysinfo
```

## Forbidden Stage 1 work

Do not run Nix packaging builds unless the user explicitly promotes the task out of Stage 1.

Do not run:

```sh
nix build .
nix run .
nix profile install .
gh workflow run
gh run cancel
gh run rerun
gh release create
gh release upload
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

Do not create, upload, or modify release assets.

## Nix packaging contract report

Use this format:

```text
Nix packaging contract report

Requested focus:
Authoritative version source:
Declared version:
Flake path:
Package expression path:
Main program:
License metadata:
Supported systems:
Hard-coded version surfaces:
Publishing attempted: no
Drift:
Recommended next step:
```

## AUD-003 rule

Treat `pyproject.toml` as the version source of truth.

If `flake.nix` or `packaging/nix/package.nix` hard-codes a version, report it as drift unless it is generated from the canonical source.

## Output format

Finish with:

```text
Nix prepare-only summary:
- Requested focus:
- Flake/package coverage:
- Version consistency:
- License metadata:
- Docs drift:
- Publishing commands blocked:
- Recommended next step:
```
