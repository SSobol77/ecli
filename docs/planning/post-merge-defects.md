<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/planning/post-merge-defects.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Gate 2 Post-Merge Defects

Timestamp: 2026-05-09T22:55:40+02:00

Branch: `chore/gate2-postmerge-verification`

## Stop Condition

Part A halted during A.2.1 before proceeding to A.3, per the execution rule:

> Any A.2.x verification fails -> halt, defect report, do not proceed to A.3.

## Defect PMV-001: Required `python` Invocation Is Unavailable

### Verification Step

A.2.1 Smoke tests run:

```sh
cd $(git rev-parse --show-toplevel)
python -m pip install --user -e ".[dev]" --quiet
python -m pytest tests/test_smoke.py -v
```

### Transcript

```text
bash: line 1: python: command not found
```

### Impact

The post-merge verification command specified for Gate 2 cannot execute in this
environment because `python` is not present on `PATH`. The smoke tests were not
collected or executed, and editable-install entry point verification was not
started.

This is a verification contract failure, not evidence that `tests/test_smoke.py`,
`src/ecli/__init__.py`, or `src/ecli/__main__.py` are defective. The prescribed
command path cannot establish those properties until the `python` interpreter
alias issue is resolved or the verification contract is amended to use
`python3`.

### Required Maintainer Triage

Choose one of:

- Provide a `python` command on the verification runner PATH and rerun Part A.2
  from A.2.1.
- Amend the Gate 2 post-merge verification contract to use `python3` for A.2.1,
  A.2.2, and other Python invocations where the repository requires explicit
  Python 3 semantics.

No fix-forward was applied because Gate 2 sign-off depends on preserving the
actual verification evidence.

### Resolution

Resolved by prompt amendment 2026-05-09T23:02:33+02:00. Verification contract
uses python3 explicitly. No repository changes required.

## Defect PMV-002: Editable Entry Point Does Not Print Version

Timestamp: 2026-05-09T23:03:35+02:00

### Verification Step

A.2.3 Editable install entry point, using the amendment's absolute-path form
because `pip install --user` placed scripts under `~/.local/bin`, which is not
on `PATH` in this workstation shell:

```sh
ls -la ~/.local/bin/ecli && ~/.local/bin/ecli --version 2>&1 | head -3 || \
    echo "ENTRY POINT NOT INSTALLED"
```

### Transcript

```text
-rwxrwxr-x 1 ssb ssb 212 May  9 23:03 /home/ssb/.local/bin/ecli
Could not parse user config '/home/ssb/.config/ecli/config.toml': Unbalanced quotes (line 18 column 34 char 258). Using defaults.
[?1h=CRITICAL - ecli         - Unhandled exception at the top level.
Traceback (most recent call last):
ENTRY POINT NOT INSTALLED
```

### Impact

The editable install created the `ecli` console script, so the project script
entry point is linked. However, `ecli --version` does not satisfy the Phase 0
post-merge acceptance expectation that the command prints a version string. The
command appears to enter the normal application path, emits terminal-control
bytes, logs a top-level critical exception, and returns nonzero.

This prevents completing A.2.3 and therefore blocks Gate 2 Part A sign-off.

### Required Maintainer Triage

Determine whether `ecli --version` is intended to be a supported noninteractive
CLI contract for Phase 0. If yes, the entry point should handle `--version`
before loading user configuration or launching the terminal UI. If no, amend the
post-merge verification contract to check an actually supported version surface,
for example `python3 -c 'import ecli; print(ecli.__version__)'`.

### Resolution

Resolved by prompt amendment 2026-05-09T23:12:56+02:00. Root cause: A.2.3
invoked `ecli --version`, but ECLI's CLI does not implement a non-TTY
`--version` handler. When piped through `head`, curses.initscr() fails on
no-TTY, producing the observed top-level exception. This is curses behavior, not
a code defect.

A.2.3 amended to verify entry-point linkage via filesystem check + module
import, without invoking the CLI binary. The CLI `--version`/`--help` work is
tracked separately as a Phase 1 follow-up.

No repository changes required for Gate 2 sign-off.
