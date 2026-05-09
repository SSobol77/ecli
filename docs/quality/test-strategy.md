# Test Strategy

## Objectives

- Prevent regressions in editor correctness.
- Enable safe incremental refactor of monolithic modules.
- Enforce release confidence across packaging and runtime paths.

## Test Pyramid

- Unit tests: pure logic (history, selection normalization, config merge/validation).
- Component tests: module-level flows (key decoding, draw-safe behavior, panel lifecycle).
- Integration tests: editor event flow, queue processing, linter/git adapter boundaries.
- Contract tests: artifact naming and config schema contracts.
- Smoke tests: startup and basic file lifecycle.

## Release-Blocking Minimum Suites

- config parse/validation checks
- undo/redo invariants and replay safety
- keybinding decode regression set
- release artifact contract checks

## Characterization Tests for Refactor

Before extracting services from `Ecli`, snapshot and test current behavior for:
- cursor movement semantics
- selection behavior
- undo/redo sequence outcomes
- panel focus transitions

## Ownership

- Core maintainers own correctness suites.
- Release maintainers own artifact contract checks.
- CI maintainers own gating and failure policy.
