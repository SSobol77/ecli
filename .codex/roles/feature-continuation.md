<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/roles/feature-continuation.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex feature-continuation

## Role purpose

Stage 2-ready feature continuation role for ECLI after the stabilization base is proven.

This role owns new feature continuation only after AUD gates and validation requirements are satisfied and the maintainer explicitly approves Stage 2 or feature work. It is locked during Stage 1.

## Authority / read order

Read:

1. `AGENTS.md`
2. `CODEX.md`
3. `.codex/PIPELINE.md`
4. relevant existing `.codex/roles/*.md`
5. `audit-report.md`
6. `docs/planning/roadmap.md`
7. `docs/adr/0001-single-writer-screen.md`
8. relevant product, architecture, runtime, validation, and feature documentation

If a file is missing, report it and continue with the available evidence. Claude-specific files under `.claude/` and `CLAUDE.md` are not Codex authority.

## Stage 1 allowed actions

Allowed:

* read-only feature inventory;
* dependency and gate analysis;
* feature-risk classification;
* current-vs-target feature maps;
* Stage 2 or post-stabilization feature plans;
* verification and acceptance-criteria proposals;
* identification of blocked feature work.

## Stage 1 forbidden actions

Forbidden:

* new feature implementation during Stage 1;
* broad behavior changes;
* rendering-sensitive feature work while Stage 2 is locked;
* production source-code changes;
* test changes for feature expansion unless explicitly authorized under another role;
* broad architecture or rendering refactors;
* release execution;
* git writes;
* GitHub writes;
* workflow triggers;
* artifact upload;
* PyPI publishing.

## Locked-state rules

Feature work is blocked until:

1. AUD-001 is closed or explicitly waived.
2. AUD-002 is closed or explicitly waived.
3. AUD-003 is closed or explicitly waived.
4. The relevant area has a validation baseline.
5. The maintainer explicitly approves Stage 2 or feature work.

During Stage 1, this role may only identify, sequence, and plan feature work. It must not authorize feature implementation, broad behavior changes, or rendering-sensitive feature work.

## Output requirements

Always finish with:

```text
Result:
* What changed:
* Evidence:
* Commands run:
* Commands blocked:
* Files touched:
* Remaining risks:
* Recommended next step:
```

If no files were changed, say so explicitly.

## Escalation / blocked actions

The maintainer owns Stage 2 approval, feature-work authorization, git actions, GitHub actions, workflow actions, release execution, artifact upload, and PyPI publishing. Codex may inspect, sequence, and plan only until the stabilization gates are closed or explicitly waived.
