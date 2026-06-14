<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/runbooks/render-inventory.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex rendering inventory runbook

## Purpose

Stage 1 read-only rendering inventory for ECLI.

This runbook inventories terminal-surface mutation, resize behavior, display-width risks, and async redraw triggers. It does not authorize production rendering edits in Stage 1.

Git, GitHub, workflow, release, publication, and artifact-upload actions are maintainer-owned.

## Codex read-only execution pattern

Use Codex in read-only mode and let shell redirection write the report:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT" > logs/render-inventory-codex.md
```

Codex prints Markdown only. The shell redirection, not Codex file editing, creates or updates the report file.

## Inventory targets

Inspect:

* direct `curses` imports;
* `stdscr.*`;
* `refresh`, `noutrefresh`, `doupdate`;
* `KEY_RESIZE`, `SIGWINCH`, and resize paths;
* `len()`-based display geometry;
* async redraw triggers.

Use static inspection:

```sh
rg -n "import curses|from curses|stdscr\\.|refresh\\(|noutrefresh\\(|doupdate\\(" src/ecli tests
rg -n "KEY_RESIZE|SIGWINCH|resize|resizeterm" src/ecli tests
rg -n "len\\(|wcwidth|wcswidth|column|cursor|wrap|clip|viewport|status" src/ecli tests
rg -n "async|await|create_task|call_soon|redraw|draw|render|refresh" src/ecli tests
```

## Classification

Use:

* `baseline` — existing current architecture or known drift;
* `new-drift` — newly introduced in the current work;
* `needs-review` — requires deeper source inspection or maintainer decision;
* `candidate-Stage2-fix` — valid only after AUD-001, AUD-002, and AUD-003 are closed or explicitly waived and the maintainer approves Stage 2.

## Stage 1 rules

Codex must not:

* edit production rendering code in Stage 1;
* perform broad rendering rewrites;
* split `src/ecli/core/Ecli.py`;
* split `src/ecli/ui/panels.py`;
* introduce new terminal writers;
* normalize violations silently.

Existing violations are drift to report. New violations are forbidden.

Stage 2 requires explicit maintainer approval and AUD gate closure or waiver.

## Forbidden actions

Codex must not run:

* `git commit`, `git push`, `git tag`;
* `gh pr create`, `gh issue edit`, `gh issue close`, `gh issue comment`;
* `gh workflow run`, `gh run rerun`, `gh run cancel`;
* `gh release`;
* `twine upload`, `uv publish`, or `python -m twine upload`;
* `make release`, `make release-*`, `make publish`, or `make publish-*`.

## Output

Finish with:

```text
Result:
- What was inspected:
- Evidence:
- Commands run:
- Commands blocked:
- Files touched:
- Remaining risks:
- Recommended next step:
```
