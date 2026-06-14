<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/drift-register.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Drift Register

This file records known Stage 1 baseline drift.

It is not a defect tracker for every bug. It records automation-relevant drift that affects validation, build, runtime, or release safety.

## Current baseline drift

| ID | Area | Status | Notes |
|---|---|---|---|
| DRIFT-001 | Static gate / ruff | Known baseline debt | Ruff may be red; report exact files and rules. |
| DRIFT-002 | Static gate / mypy | Known baseline debt | Treat mypy as baseline/diff unless full type cleanup is explicitly requested. |
| DRIFT-003 | Config validation | P0 | Runtime config sections are not fully covered by typed config service validation. |
| DRIFT-004 | History redo | P0 | `History.redo()` selection-preserving block operations require targeted test/fix. |
| DRIFT-005 | Artifact contract | P0 | Version and packaging descriptors may drift from `pyproject.toml`. |
| DRIFT-006 | Runtime logs | P1 | AI provider logging may expose secrets or prompt/response content. |
| DRIFT-007 | Curses boundary | P1 | Direct curses usage outside `src/ecli/ui/` exists and is baseline debt. |

## Update policy

When adding an entry, include:

```text
ID:
Area:
Severity:
First observed:
Evidence:
Current status:
Owner:
Recommended next step:
```

Do not remove a drift entry unless the validation evidence proving closure is available.
