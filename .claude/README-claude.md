<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/README-claude.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Claude Automation Directory

This directory defines the local Claude Code automation surface for ECLI.

Stage 1 automation is safety-first. It exists to validate, diagnose, and prepare controlled fixes. It must not become a release factory.

## Directory map

- `agents/` — Claude subagents with YAML frontmatter.
- `commands/` — command definitions for bounded workflows.
- `project-context.md` — repository-specific operating context.
- `validation-runbook.md` — validation gate policy.
- `build-runbook.md` — non-publishing build and artifact-contract policy.
- `release-runbook.md` — prepare-only release policy.
- `drift-register.md` — known baseline drift and audit debt.

## Stage 1 policy

Stage 1 allows:

- validation,
- diagnostics,
- log triage,
- isolated runtime smoke checks,
- prepare-only release planning,
- documentation synchronization.

Stage 1 forbids:

- committing,
- pushing,
- tagging,
- publishing to PyPI,
- creating GitHub Releases,
- uploading release assets,
- broad architecture refactors,
- full packaging automation.

## Required reading order

Before any Stage 1 automation, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `.claude/project-context.md`
4. `.claude/validation-runbook.md`
5. `audit-report.md`

For build or release work, also read:

- `.claude/build-runbook.md`
- `.claude/release-runbook.md`
- `.claude/drift-register.md`
