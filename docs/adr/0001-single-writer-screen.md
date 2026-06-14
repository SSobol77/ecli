<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/adr/0001-single-writer-screen.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->

# ADR 0001 — Single-writer screen with a pure renderer

- Status: Proposed / Stage 2 locked
- Date: 2026-06-14
- Owners: software-architect role
- Activation gate: blocked until AUD-001, AUD-002, and AUD-003 are closed or explicitly waived
- Supersedes: none

## Context

ECLI is a curses + asyncio terminal editor (Pygments highlighting, optional LSP and AI
providers). The reported instability — flicker, "garbage" cells, cursor landing in the wrong
column, corruption after resize — is consistent with two structural causes, not many unrelated
bugs:

1. The curses surface is mutated from more than one place. Async edges (LSP diagnostics, AI
   provider responses, file-watch callbacks) reach the screen outside the main draw path.
   curses is not re-entrant and has global hidden state; concurrent or interleaved
   `refresh`/`doupdate` from different tasks corrupts output and desynchronises the cursor.
2. Column geometry is computed from character count (`len`) rather than display width. Tabs,
   CJK wide characters, and zero-width / combining characters then misalign every downstream
   calculation (wrapping, cursor, scroll region).

A secondary consequence is that rendering is effectively untestable: drawing logic is fused
with terminal IO, so there is no pure value to assert against.

## Decision

Adopt one rendering architecture with four coupled facets (they are not independent and are
recorded as a single decision):

1. **Single-writer screen.** Exactly one component — `src/ecli/term/` — owns the curses surface
   and is the only code permitted to import `curses` or call `stdscr.*` / `*refresh` /
   `noutrefresh` / `doupdate`. This is an enforced invariant, audited in CI.
2. **Pure renderer.** `render(state, viewport) -> ScreenBuffer` is a pure, deterministic
   function: no IO, no global reads, no curses. It maps editor state to an in-memory grid of
   cells.
3. **ScreenBuffer as the testable boundary.** The `ScreenBuffer` is an immutable value
   (rows x cols of `Cell`). All rendering correctness is asserted at this level without a real
   terminal. The terminal writer's only job is to diff two ScreenBuffers and emit the minimal
   byte sequence.
4. **Render-intent queue.** Async edges never touch the screen. They post `RenderIntent`
   messages to a queue owned by the app loop. The loop folds intents into editor state,
   re-runs `render`, and hands the new ScreenBuffer to the single writer.

This ADR records the Stage 2 target architecture. It does not authorize broad Stage 1 source refactoring.

## Invariants (each must be mechanically testable)

- INV-1  Only `src/ecli/term/` references `curses` / `stdscr` / `*refresh` / `doupdate`.
- INV-2  `render(state, viewport)` performs no IO and reads no module-level mutable state;
         identical inputs yield an identical ScreenBuffer.
- INV-3  For every produced row, the sum of cell widths equals `viewport.width`.
- INV-4  Wrapping is a partition of the logical line: concatenating wrapped segments
         reconstructs the original logical line exactly.
- INV-5  Cursor screen position is derived from display width, never character index.
- INV-6  A resize is handled by recomputing the viewport and re-rendering, never by mutating
         the previous ScreenBuffer in place.
- INV-7  The writer is the single consumer of ScreenBuffers; no other component emits to the
         terminal.

## Failure modes addressed

- Interleaved curses writes from async tasks (root cause of corruption/flicker) -> structurally
  impossible: async edges can only post intents (INV-1, INV-7).
- Misaligned wide/zero-width/tab geometry -> caught by INV-3/INV-4/INV-5 property tests.
- Resize corruption -> INV-6.
- Silent regression of any of the above -> CI audit + property suite.

## Verification strategy

- INV-1, INV-7: static audit (grep gate in regression-guard / CI) for forbidden curses usage
  outside `src/ecli/term/`.
- INV-2: property test — call `render` twice on the same inputs, assert identical ScreenBuffer;
  assert no IO via fakes that fail if touched.
- INV-3, INV-4, INV-5: Hypothesis properties over generated buffers and viewports.
- Terminal writer: pty golden-snapshot tests (the only tests that touch a real terminal, via a
  pseudo-terminal, marked `@pytest.mark.render`).

## Alternatives considered

- **Keep direct curses drawing, add locking.** Rejected: a lock serialises writers but leaves
  rendering fused with IO (still untestable) and is fragile under asyncio (lock held across
  awaits stalls the loop). Does not address geometry bugs.
- **Use curses pads/panels as the abstraction.** Rejected as the primary boundary: still couples
  correctness to curses semantics and a live terminal; poor testability.
- **Adopt a third-party TUI framework (Textual / urwid).** Out of scope for stabilisation: a
  large rewrite, new runtime model, and dependency risk. The ScreenBuffer boundary keeps the
  option open later without blocking the current fix.

## Consequences

Positive: rendering becomes deterministic and unit-testable; async edges cannot corrupt the
screen; geometry bugs become property-checkable; the terminal layer shrinks to a diff+emit.
Negative: a one-time refactor to route all drawing through `render` + writer; a diffing writer
must be written and tuned; intent plumbing adds indirection for async edges.

## Reconciliation tasks (current-vs-target — do before implementing)

The target layering in AGENTS.md is not assumed to exist yet. Before coding, map the real tree:

1. Inventory every `import curses` / `stdscr` / `*refresh` / `doupdate` site and record which
   module each lives in (this is the migration worklist toward INV-1).
2. Identify the current "god" draw routine(s) and what editor state they read — that state set
   defines the `EditorState` protocol the renderer needs.
3. Identify where async LSP/AI/file-watch results currently reach the screen — each becomes a
   `RenderIntent`.
4. Confirm actual package names/paths; adjust `src/ecli/{model,render,term,io,app}` to match or
   record the rename as part of this ADR before merge.
