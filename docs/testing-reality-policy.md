# ECLI Testing Reality Policy

## Purpose

Automated tests are regression guards. They are not runtime truth for curses UI,
panel rendering, input dispatch, background worker behavior, subprocess
integration, logging, or packaged-artifact execution.

A passing test suite may prove that a narrow contract still holds. It does not
prove that a TUI/runtime bug is fixed unless the fix is also verified with fresh
runtime evidence from the current run.

## Runtime Acceptance Requirements

Runtime, TUI, rendering, panel, input, logging, and extension-layer bug reports
or fixes require all of the following evidence before claiming "fixed":

- Fresh logs produced after `make clean-logs`.
- Exact command used to reproduce or verify the behavior.
- Exact log file inspected.
- Relevant current-run log excerpt, or explicit absence of the previous failure
  marker in the current-run log.
- Manual smoke result for visual/TUI behavior, including visible behavior
  observed.

Stale logs are invalid evidence. Passing tests alone are invalid evidence for a
runtime/TUI fix.

## Valid Mock Usage

Mocks, fakes, and monkeypatching are valid when they preserve the contract being
tested and make a deterministic boundary observable:

- Environment and path precedence tests.
- Parser, registry, package-data, and release-contract tests.
- Deterministic failure injection, including missing tools, bad config, timeout
  results, malformed payloads, and unavailable optional dependencies.
- Queue and thread boundary tests that assert state remains unchanged until the
  UI-side consumer drains a real queue.
- Fake curses windows that capture rendered text, geometry, background painting,
  or state transitions without claiming full terminal acceptance.

## Invalid Mock Usage

A mock-heavy test is invalid when it replaces the behavior being claimed as
correct or only proves that a test double was called:

- Tests that assert only `called`, `assert_called`, or an equivalent flag without
  asserting real output, state, error, file, queue, or log behavior.
- Tests that mock the implementation path under test and then assert the mocked
  result.
- Tests that claim curses/TUI/runtime correctness without a real terminal smoke
  path or current-run logs.
- Source-string tests that duplicate a stronger runtime or API-level contract
  and can pass while dispatch behavior is broken.
- Tests with no meaningful assertion, such as checking a constant created inside
  the test without exercising project code.
- Duplicates with identical setup and assertions.
- Tests for obsolete behavior that no supported runtime path can exercise.

## Keep / Rewrite / Delete Criteria

Keep tests that assert real contracts: pure functions, parser behavior,
registry resolution, path/config precedence, packaging names, release assets,
package-data inclusion, deterministic error handling, queue state, rendered text
captured from a fake window, or real file/log output.

Rewrite tests when the contract is important but the current test over-mocks the
runtime path. Prefer real queue handoff, bounded worker polling, file-backed log
inspection, temp git repositories, subprocess boundary fakes that return real
result objects, or smoke-style checks over call-only assertions.

Delete tests when they are misleading, obsolete, duplicated, or assert no
project behavior. Do not delete a test only because it uses mocks.

## Current Audit Ledger

Inventory command run for this audit:

```bash
grep -R --exclude-dir='**pycache**' --exclude='*.pyc' -nE "MagicMock|Mock\(|patch\(|monkeypatch|capsys|capfd|pytest\.mark|assert .*called|assert_called" tests | sort
```

Initial inventory result:

- 268 matching lines.
- 56 matching test files.
- 80 matching test functions after mapping matching lines to enclosing
  `test_*` functions. Decorator-only and fixture-only matches were reviewed at
  file/group level.

Actions:

| File | Test | Action | Reason | Replacement evidence |
|---|---|---|---|---|
| `tests/ui/test_pysh_console_panel.py` | `test_pysh_console_external_command_flow` | REWRITE | The test replaced `threading.Thread` with an immediate fake, bypassing the async handoff it was meant to guard. | Uses the real background thread, polls `process_queues()` with a bounded deadline, then asserts backend arguments, transcript output, exit status, and `_running_command` cleanup. |
| `tests/ui/test_terminal_panel_reservation.py` | `test_f11_opens_pysh_console_panel_action` | REWRITE | The test inspected `KeyBinder` source strings and could pass even if runtime dispatch broke. | Instantiates `KeyBinder`, dispatches F11 through `handle_input()`, and asserts the editor double's `toggle_terminal_panel()` action ran and set the expected status. |
| `tests/services/test_privileged_action_service.py` | `test_all_test_artifacts_remain_under_logs` | DELETE | No meaningful assertion: it only proved that `(Path.cwd() / "logs").name` is `"logs"` without exercising artifacts, fixtures, or project code. | No replacement needed. Real log-location behavior remains covered by `scripts/check_log_invariant.py` and `tests/packaging/test_check_log_invariant_script.py`. |

The remaining mock/monkeypatch-heavy tests were kept because they assert
observable contracts: env/config precedence, deterministic failure injection,
release/package names, queue isolation, rendered text, file-backed logging, or
static no-execution safety constraints.
