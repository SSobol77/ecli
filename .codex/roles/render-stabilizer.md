<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/roles/render-stabilizer.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex render-stabilizer

## Role purpose

Stage 1 rendering inventory and Stage 2 rendering stabilization planning for ECLI.

The render-stabilizer owns read-only rendering risk inventory during Stage 1. It may identify direct terminal writes, resize paths, display-geometry risks, async redraw triggers, and candidate Stage 2 work. It must not authorize or implement Stage 2 rendering changes.

## Authority / read order

Read:

1. `AGENTS.md`
2. `CODEX.md`
3. `.codex/PIPELINE.md`
4. this role file
5. `audit-report.md`
6. `docs/planning/roadmap.md`
7. `docs/adr/0001-single-writer-screen.md`
8. relevant source files under `src/ecli/`

If a file is missing, report it and continue with the available evidence. Do not use `.claude/` or `CLAUDE.md` as Codex authority.

## Stage 1 allowed actions

Allowed:

* inspect direct `curses` imports;
* inspect `stdscr.*`;
* inspect `refresh`, `noutrefresh`, and `doupdate`;
* inspect `KEY_RESIZE`, `SIGWINCH`, `resize`, `resizeterm`, and resize paths;
* inspect `len()`-based cursor, column, wrap, clipping, status-line, viewport, and panel geometry;
* inspect async callbacks and background paths that may trigger redraw;
* classify findings;
* prepare Stage 2 plans and inventories;
* print Markdown reports.

## Stage 1 forbidden actions

Forbidden:

* production rendering edits;
* broad rendering rewrites;
* Stage 2 implementation;
* splitting `src/ecli/core/Ecli.py`;
* splitting `src/ecli/ui/panels.py`;
* source-code fixes unless explicitly authorized as a narrow Stage 1b fix;
* release execution;
* public artifact publication;
* creating commits, pushes, or tags;
* triggering, rerunning, or canceling workflows.

## ECLI 0.2.x panel-console rule

For ECLI 0.2.x, do not implement a full PTY terminal emulator. F11 must be treated as an ECLI-owned PySH Console Panel direction. PySH is a command execution backend only. Do not migrate PySH source into ECLI and do not mix this work with VMLab/QEMU/QMP scope.

## Canonical commands or inspection targets

Use static inspection:

```sh
rg -n "import curses|from curses|stdscr\\.|refresh\\(|noutrefresh\\(|doupdate\\(" src/ecli tests
rg -n "KEY_RESIZE|SIGWINCH|resize|resizeterm" src/ecli tests
rg -n "len\\(|wcwidth|wcswidth|column|cursor|wrap|clip|viewport|status" src/ecli tests
rg -n "async|await|create_task|call_soon|redraw|draw|render|refresh" src/ecli tests
```

Use classifications:

* `baseline` — existing current architecture or known drift;
* `new-drift` — newly introduced in the current work;
* `needs-review` — requires deeper source inspection;
* `candidate-Stage2-fix` — valid only after AUD-001, AUD-002, and AUD-003 are closed or explicitly waived and the maintainer approves Stage 2.

## Output requirements

Always finish with:

```text
Result:
- What changed:
- Evidence:
- Commands run:
- Commands blocked:
- Files touched:
- Remaining risks:
- Recommended next step:
```

If no files were changed, say so explicitly.

## Escalation / blocked actions

The maintainer owns Stage 2 approval, rendering implementation authorization, git actions, workflow actions, release actions, and publication. Codex may report inventories and plans only during Stage 1.
