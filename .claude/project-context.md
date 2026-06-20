<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/project-context.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Project Context

ECLI is a terminal-first engineering operations workbench implemented in Python.

The current codebase is a modular monolith centered around `src/ecli/core/Ecli.py`, with curses-based UI modules, integrations for AI/Git/linting, and multi-platform packaging ambitions.

## Current Stage 1 focus

Stage 1 is not a feature phase.

Stage 1 focuses on audit-aligned safety automation:

- config/runtime validation drift,
- undo/redo runtime safety,
- artifact/version contract drift,
- static gate baseline reporting,
- isolated runtime/log validation,
- prepare-only release discipline.

## Audit-aligned P0 scope

Stage 1 must track:

- AUD-001 — config/runtime validation drift.
- AUD-002 — `History.redo()` selection-preserving block operation crash.
- AUD-003 — release artifact contract drift.

## Known baseline

The audit baseline reported:

- pytest passes,
- ruff is not clean,
- mypy is not clean,
- release artifact surfaces have drift risk,
- runtime logs may expose sensitive AI provider data.

Do not pretend the static gates are clean. Report them honestly.

## Rendering stabilization hypothesis

The current rendering risk is likely concentrated around two structural problems:

1. Multiple code paths may mutate the curses surface or terminal state.
2. Column geometry may use character count instead of terminal display width.

Treat this as a working hypothesis to verify against the real tree, not as a license for broad refactor.

This hypothesis is consistent with the current audit direction around curses containment and display-width geometry, but Stage 1 must only inventory and report the problem surface.

Stage 1 must inventory and report:

- direct `curses` imports and calls,
- `stdscr.*` usage,
- `refresh`, `noutrefresh`, and `doupdate` usage,
- `len()`-based cursor, column, width, wrap, clipping, and status-line calculations,
- resize and `KEY_RESIZE` handling paths,
- async paths that can influence rendering,
- background workers that may indirectly trigger drawing or terminal updates.

Stage 1 must not perform a broad rendering rewrite.

## Stage 2-ready rendering target

After P0 stabilization is closed for AUD-001, AUD-002, and AUD-003, ECLI may enter a dedicated rendering stabilization phase.

The Stage 2 target architecture may move toward:

- a single terminal writer boundary,
- pure render/state transformation,
- `ScreenBuffer` as the testable render artifact,
- display-width-aware geometry,
- pty/golden snapshot testing,
- Hypothesis property tests for width, wrap, tabs, resize, and Unicode edge cases.

This is a target architecture, not a claim that the current repository already has this structure.

## Stage 2 activation gate

Do not activate render-stabilizer, software-architect, test-harness-builder, or feature-continuation for broad rendering work until all three P0 findings are closed or explicitly waived by the maintainer:

- AUD-001 — config/runtime validation drift,
- AUD-002 — `History.redo()` selection-preserving block operation crash,
- AUD-003 — release artifact contract drift.

Before Stage 2 starts, the maintainer must explicitly approve the transition from Stage 1 safety automation to Stage 2 rendering stabilization.

## Extensions Layer contract (v0.3.0 Foundation)

The ECLI Extensions Layer is defined normatively in
`docs/architecture/extensions-layer.md`. It is the imported, data-only,
VS Code / TextMate-compatible asset tree plus deterministic adapter code.
Issue #97 is architecture/documentation only — no assets are imported and no
runtime is implemented.

- `src/ecli/extensions/` is the only approved location for imported extension
  assets. Do not invent `vendor/`, `third_party/`, or `src/ecli/syntax/assets/`.
- Imported/upstream files are read-only; add behavior through deterministic
  adapter code, never by editing upstream files.
- No VS Code extension host, no Node activation, no `activationEvents` execution,
  no `package.json` scripts, no Copilot runtime, no network/auth side effects,
  no hidden command execution through extension metadata.
- Preserve F11 as the PySH Console Panel; no generic PTY terminal emulator.
- VMLab moved to v0.3.5 and is blocked until the v0.3.0 Extensions Foundation is
  complete.

## Operating constraints

- Preserve user changes.
- Do not commit.
- Do not push.
- Do not tag.
- Do not publish.
- Do not run release targets.
- Do not write to the real user configuration during runtime checks.
- Use isolated `HOME` for startup/log triage.
