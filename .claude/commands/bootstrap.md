---
description: Bootstrap the ECLI development environment safely and report repository readiness without modifying release state.
argument-hint: "[optional focus: deps|sysinfo|tools|all]"
allowed-tools: Read, Grep, Glob, Bash
---

<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/commands/bootstrap.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# /bootstrap — ECLI Safe Development Bootstrap

Bootstrap the ECLI development environment in read-mostly, non-release mode.

Argument: `$ARGUMENTS`

## Purpose

Prepare or inspect the local development environment for ECLI without publishing, tagging, committing, or changing release state.

This command is safe to run before `/validate`.

## Required reading

Before running commands, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/README.md`
4. `.claude/project-context.md`
5. `.claude/validation-runbook.md`
6. `pyproject.toml`
7. `Makefile`

## Allowed command intent

You may run, if permitted by `.claude/settings.local.json`:

```sh
make help
make sysinfo
uv sync
````

You may inspect:

```sh
pyproject.toml
uv.lock
Makefile
scripts/
.claude/settings.local.json
```

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
gh release create
gh release upload
make release
make release-*
make publish
make publish-*
```

## Bootstrap procedure

1. Report the requested focus from `$ARGUMENTS`.
2. Inspect `pyproject.toml` and identify the Python/package/build backend.
3. Inspect `Makefile` and summarize available non-publishing targets.
4. Run `make help` if allowed.
5. Run `make sysinfo` if allowed.
6. Run `uv sync` only when dependency materialization is explicitly needed or requested.
7. Do not run packaging or release targets.
8. Report blocked actions honestly.

## Output format

Finish with:

```text
Bootstrap summary:
- Focus:
- Project metadata:
- Toolchain status:
- Makefile targets inspected:
- Dependency sync:
- Blocked actions:
- Risks:
- Recommended next step:
```