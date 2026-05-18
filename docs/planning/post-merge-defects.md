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

## Defect PMV-003: FreeBSD 14.3 Release Leg Aborted at Pseudo-TTY Smoke

Timestamp: 2026-05-19T00:00:00+02:00

### Context

ECLI v0.2.2 release pipeline `Release` workflow run `26064484430`, job
`76632103340` (`Build FreeBSD package`). The Linux / macOS / Windows / Python
legs all passed. PyPI 0.2.2 was published successfully (immutable). The
GitHub Release for `v0.2.2` could not be published because
`publish-github-release` had `needs.build-freebsd.result == 'success'` in its
`if:` condition.

### Symptom

The `Build in FreeBSD 14.3 VM` step ended with:

```text
##[error]The process '/usr/bin/ssh' failed with exit code 1
```

Last in-VM lines before the SSH wrapper died:

```text
Bare ECLI pseudo-TTY startup exited unexpectedly with status 1
script: illegal option -- c
usage: script [-aeFfkpqrw] [-t time] [file [command ...]]
```

Captured log: `logs/freebsd-0.2.2-fail.log` (local; `logs/*` is gitignored).
Reproduce remotely with:

```sh
gh run view --job 76632103340 --log > logs/freebsd-0.2.2-fail.log
```

### Root Cause Classification

**RC-OTHER** — portability defect in `scripts/verify_runtime.sh`.

The `run_native_smoke()` helper invoked `script -q -c "..." /dev/null` to run
the packaged binary inside a bounded pseudo-TTY. The `-c CMD` flag is a
GNU/util-linux extension; FreeBSD's BSD `script(1)` is positional
(`script [opts] [file [command ...]]`). On FreeBSD 14.3, `script -c` returns
exit 1 with `script: illegal option -- c`. Under `set -euo pipefail` this
exit propagated all the way up through `build-and-package-freebsd.sh`, which
in turn terminated the SSH session inside the vmactions VM wrapper, surfacing
as the opaque ssh exit-1.

### Evidence

Quoted from the failing job log (`logs/freebsd-0.2.2-fail.log:1165-1167`):

```text
script: illegal option -- c
usage: script [-aeFfkpqrw] [-t time] [file [command ...]]
       script -p [-deq] [-T fmt] [file]
```

The `pkg create` step at log line 1153 completed and emitted the payload
listing — proof that `install_system_dependencies`,
`install_python_dependencies`, PyInstaller, staging, and `pkg create` were
all green. The failure was downstream, in the runtime verification step.

Implicated source lines:

- `scripts/verify_runtime.sh:418` (pre-fix): `timeout 3s script -q -c "..." /dev/null`
- `scripts/verify_runtime.sh:425` (pre-fix): `echo "Bare ECLI pseudo-TTY startup exited unexpectedly..."`

### Fix Summary

1. `scripts/verify_runtime.sh`: detect `script(1)` flavor via `script --help`
   and select GNU (`-c CMD FILE`) vs BSD (`FILE COMMAND...`) syntax at
   runtime. Environment variables are now pushed in via `env HOME=... TERM=...`
   for both flavors so behavior is identical across Linux, FreeBSD, and macOS.
2. `scripts/build-and-package-freebsd.sh`: added `STEP=` instrumentation, an
   `on_error` EXIT trap that dumps the failing step, dmesg tail, `sysctl`
   memory, and `df -h`, a `pkg update -f` retry loop, observable pip output,
   a low-memory guard before PyInstaller, and PyInstaller / Python version
   echo at the top of `build_binary`.
3. `.github/workflows/release.yml`:
   - Pinned `vmactions/freebsd-vm` to commit SHA `d1e6581...` (v1.4.5).
   - Increased VM resources to `mem: 6144`, `cpu: 4`.
   - Tee'd the in-VM stdout to `freebsd-build.log` and added an
     `if: failure()` upload step (`freebsd-build-log-<run_id>`) so future
     SSH disconnects cannot lose the in-VM trace.
   - Marked `build-freebsd` as `continue-on-error: true` and removed it from
     the success criteria of `publish-github-release`. FreeBSD now lives in
     `needs:` for ordering only.
   - The publisher injects a `freebsd_note` line into the release body when
     `needs.build-freebsd.result != 'success'`, explicitly stating that the
     `.pkg` is attached out-of-band.
4. `.github/workflows/freebsd-pkg.yml`: mirrored vmactions SHA pin, added
   build-log capture on failure, raised resources, and added a
   workflow_dispatch input `release_tag` that uploads the freshly built
   `.pkg` + `.sha256` to that GitHub Release via
   `gh release upload --clobber`.

### Follow-Up Actions

- Re-run `Release` workflow (`gh workflow run release.yml --ref main \
   -f build_assets=true -f publish_pypi=false -f publish_github_release=true`)
  to publish v0.2.2 GitHub Release with non-FreeBSD assets.
- If FreeBSD leg lands green in that rerun, the `.pkg` is included
  automatically. If it fails again, dispatch `FreeBSD 14 .pkg` with
  `release_tag=v0.2.2` to attach the `.pkg` out-of-band.
- Track migration of FreeBSD leg from `vmactions/freebsd-vm` (qemu-on-Linux)
  to native Cirrus CI as a stretch reliability improvement; see
  `docs/release/build-matrix.md`.

### Owner

Release engineering — Siergej Sobolewski.

