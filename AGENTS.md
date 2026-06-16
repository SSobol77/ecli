<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: AGENTS.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->


# ECLI Agent Instructions

This file is the shared, tool-agnostic instruction set for agents working in the ECLI repository.

It applies to Codex-style agents, Claude Code subagents, Cursor agents, and any automation that reads repository-level agent instructions.

ECLI is a terminal-first engineering operations workbench. Treat the repository as a pre-release stabilization project. Work must be audit-aligned, evidence-first, and conservative.

Do not treat ECLI automation as a release factory. Stage 1 automation exists to validate, diagnose, and prepare controlled fixes.

## 1. Source of truth order

Before changing code, tests, scripts, docs, workflows, packaging, or automation, read the relevant files in this order:

1. `AGENTS.md`
2. tool-specific operating file:
   - `CLAUDE.md` for Claude Code,
   - `CODEX.md` for Codex,
   - `CURSOR.md` for Cursor if present.
3. tool-specific runbooks:
   - `.claude/*` only for Claude Code,
   - `.codex/*` only for Codex.
4. `audit-report.md`
5. `docs/planning/roadmap.md`
6. `docs/adr/0001-single-writer-screen.md`
7. `pyproject.toml`
8. `Makefile`
9. relevant source, test, script, workflow, packaging, or documentation files

If a file is missing, report it honestly and continue with the available evidence.

Do not invent missing contracts.

## 2. Stage model

### Stage 1 — Safety-first automation

Stage 1 is active by default.

Allowed Stage 1 work:

* validation,
* diagnostics,
* failing-test reproduction,
* isolated runtime smoke checks,
* log triage with redaction,
* static gate baseline reporting,
* artifact/version drift reporting,
* prepare-only release checklists,
* documentation synchronization,
* Stage 2 planning.

Forbidden Stage 1 work:

* publishing releases,
* uploading artifacts,
* creating GitHub Releases,
* uploading to PyPI,
* creating git tags,
* pushing commits,
* committing changes,
* triggering GitHub workflows,
* canceling or rerunning GitHub Actions,
* running release targets,
* running publish targets,
* broad architecture rewrites,
* broad rendering rewrites,
* splitting `src/ecli/core/Ecli.py`,
* splitting `src/ecli/ui/panels.py`,
* silently mutating tracked packaging descriptors during build preparation.

### Stage 1b — Narrow gated P0 fix

A narrow gated fix may be allowed only when the maintainer explicitly asks for it.

A Stage 1b fix must:

* be tied to one audit finding or one defect,
* have a failing test or explicit evidence first,
* preserve current user-visible behavior unless the defect requires correction,
* keep the diff minimal,
* run or request validation,
* avoid unrelated cleanup.

### Stage 2 — Rendering stabilization

Stage 2 is locked by default.

Stage 2 may begin only after:

1. AUD-001 is closed or explicitly waived.
2. AUD-002 is closed or explicitly waived.
3. AUD-003 is closed or explicitly waived.
4. The relevant validation baseline is understood.
5. The maintainer explicitly approves the Stage 2 transition.

Until Stage 2 is unlocked, Stage 2-ready agents may only perform planning, inventory, and proposal work.

## 3. Agent ownership model

Agent responsibilities must stay separate.

Do not collapse independent roles into one agent.

### Stage 1 active roles

#### `quality-engineer`

Owns:

* validation gate interpretation,
* ruff/mypy/pytest/runtime import reporting,
* P0-specific signal extraction,
* baseline drift reporting,
* curses-boundary inventory,
* display-geometry inventory,
* tester/log-analyst reconciliation,
* PASS/FAIL verdict under the current Stage 1 policy.

Does not own:

* source-code fixes,
* feature work,
* release execution,
* broad refactors.

#### `tester`

Owns:

* failing reproduction tests,
* behavior tests,
* regression tests,
* targeted P0 tests,
* test-only changes.

Does not own:

* production code,
* harness infrastructure,
* release work,
* build scripts.

#### `log-analyst`

Owns:

* read-only log inspection,
* ERROR/CRITICAL/traceback grouping,
* asyncio warning and task exception detection,
* curses/runtime anomaly detection,
* stable log fingerprints,
* secret/prompt redaction before quoting.

Does not own:

* production code,
* test authoring,
* TUI automation,
* unredacted log reporting.

#### `docs-engineer`

Owns:

* README synchronization,
* install/build docs,
* command docs,
* release-note drafts,
* manpage/docs drift,
* documentation consistency with real commands.

Does not own:

* source-code fixes,
* release execution,
* publishing.

#### `runtime-engineer`

Owns:

* isolated `HOME` startup checks,
* runtime import checks,
* runtime smoke checks,
* log creation path verification,
* installed-artifact smoke checks when explicitly provided.

Does not own:

* real user config writes,
* release execution,
* publishing,
* interactive TUI automation unless explicitly requested.

#### `build-engineer`

Owns:

* build target discovery,
* Makefile/script inspection,
* non-publishing build validation,
* artifact contract reporting,
* packaging drift reporting.

Does not own:

* release upload,
* PyPI upload,
* GitHub Release creation,
* git write operations,
* workflow triggers.

#### `release-engineer`

Owns:

* prepare-only release readiness,
* version consistency reports,
* artifact contract reports,
* changelog drafts,
* release-note drafts,
* manual release runbooks.

Does not own:

* git tag,
* git push,
* GitHub Release creation,
* artifact upload,
* PyPI upload,
* workflow triggers,
* release execution.

### Stage 2-ready locked roles

#### `software-architect`

Owns architecture, contracts, ADRs, invariants, boundaries, and verification strategy.

During Stage 1, it may only produce:

* read-only architecture analysis,
* ADR drafts,
* current-vs-target maps,
* interface proposals,
* verification plans,
* Stage 2 plans.

It must not implement production bodies during Stage 1.

#### `render-stabilizer`

Owns rendering stabilization after Stage 2 approval or explicit narrow approval.

During Stage 1, it may only:

* inventory rendering risks,
* review direct curses calls,
* review display-geometry risks,
* review resize/redraw paths,
* identify async/render interaction risks,
* prepare Stage 2 plans.

It must not perform broad rendering rewrites during Stage 1.

#### `test-harness-builder`

Owns reusable test infrastructure.

During Stage 1, it may only:

* design harness architecture,
* propose fixture layout,
* propose pty/golden snapshot strategy,
* propose Hypothesis generator strategy,
* identify missing harness capabilities.

It must not introduce broad harness infrastructure during Stage 1 unless explicitly approved.

#### `feature-continuation`

Owns new feature implementation only after the base is stable.

It is locked during Stage 1.

Feature work is blocked until:

1. AUD-001 is closed or waived.
2. AUD-002 is closed or waived.
3. AUD-003 is closed or waived.
4. The relevant area has a validation baseline.
5. The maintainer explicitly approves Stage 2 or feature work.

## 4. Audit-aligned P0 scope

Stage 1 must track these P0 findings.

### AUD-001 — Config/runtime validation drift

Do not reduce this to TOML syntax.

The shipped `config.toml` may parse successfully, but the typed configuration service does not validate all runtime sections consumed by the legacy runtime loader.

When touching config behavior, distinguish clearly between:

* shipped `config.toml`,
* typed `ConfigService`,
* legacy `utils.load_config()` path,
* runtime sections such as `colors`, `syntax_highlighting`, `logging`, `theme`, `settings`, `file_icons`,
* syntax highlighting regex compilation.

A valid fix must prove the actual runtime loader path, not only typed service validation.

### AUD-002 — `History.redo()` runtime safety

The redo path for selection-preserving block operations must not access selection fields on the `History` object when those fields belong to the editor.

Tests must exercise the real `History` class, not only `FakeHistory`.

A correct fix must preserve:

* text integrity,
* cursor bounds,
* selection bounds,
* redo/history stack consistency,
* modified state consistency.

### AUD-003 — Release artifact contract drift

Treat `pyproject.toml` as the version source of truth.

Report drift in:

* PyInstaller spec entry behavior,
* package console entry behavior,
* Nix packaging,
* NSIS packaging,
* Arch packaging,
* AppImage metadata,
* release workflows,
* release docs,
* generated manpage or package metadata if present.

Tracked packaging descriptors must not be mutated as a side effect of packaging.

Every active packaging, workflow, script, platform descriptor, Docker helper,
and install/build document is a release-contract surface. Release readiness is
blocked if a surface is missing from the Platform & Packaging Release Contract
Matrix in `docs/release/artifact-contract.md`, the agent contracts, the
build/release runbooks, or validation tests/contract checks. Empty, stale,
decorative, or unused packaging files are forbidden; either wire them into the
contract or remove them from active workflows/scripts.

## 5. Quality baseline policy

Use the canonical validation commands:

```sh
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
uv run pytest -ra -q
uv run python scripts/check_runtime_imports.py
```

Interpret them correctly:

* `pytest` is the primary functional baseline.
* `ruff` failures must be reported exactly.
* `mypy` may have known baseline debt; treat it as baseline/diff unless the task explicitly targets type cleanup.
* P0-related mypy errors, especially in `src/ecli/core/History.py`, must be highlighted separately.
* Do not pretend static gates are clean when they are not clean.

Before build or packaging work, inspect:

```sh
make help
make sysinfo
```

The root `Makefile` is the primary ECLI command surface. `make help` is the
short developer workflow, `make help-full` is the complete target map,
`make list-targets` lists public targets, `make doctor` checks local tools
without building packages, and `make sysinfo` prints configured package
variables. Release/upload Make targets are maintainer-owned and require an
explicit confirmation guard.

`Taskfile.yml` is an optional developer convenience wrapper only. Agents may use
`task` when it delegates to existing `make` targets, but must not replace
Makefile targets with Taskfile-only behavior. Makefile remains the authoritative
build/release contract; CI and release gates continue to rely on the existing
canonical command surfaces. Release/publish tasks must remain guarded, and
packaging scripts must remain Python entrypoints under `scripts/*.py`.

Do not use bare `python` when the repository workflow expects `uv run python`.

Do not use broad commands such as:

```sh
uv run python *
gh run *
make *
```

Use exact commands.

## 6. Stage 2-ready rendering policy

The following rendering rules are accepted as the future stabilization direction, but they are not a license for broad Stage 1 refactoring.

### Single-writer screen invariant

The screen is single-writer.

Exactly one approved terminal/UI writer may own the curses surface.

Async tasks, LSP clients, AI providers, file watchers, background workers, and integration code must not mutate the terminal directly.

The following operations are considered terminal-surface mutations and must be inventoried during Stage 1:

* direct `curses` imports,
* `stdscr.*`,
* `refresh`,
* `noutrefresh`,
* `doupdate`,
* terminal resize side effects,
* direct panel/window redraw from non-writer code.

In Stage 1, existing violations are baseline drift to report. New violations are forbidden.

### Display-width geometry invariant

Column math must move toward terminal display width, not Python character count.

Rendering and cursor logic must treat these as first-class cases:

* tabs,
* CJK wide characters,
* emoji,
* zero-width characters,
* combining marks,
* long lines,
* clipped status bars,
* right-edge drawing.

In Stage 1, `len()`-based column, cursor, width, clipping, wrap, or status-line logic must be inventoried and reported. Stage 1 must not perform a broad rewrite unless explicitly approved.

### Stabilize before features

Feature work must not proceed in rendering-sensitive areas while the base is unstable.

### Tester and harness separation

Tester and test-harness-builder are separate roles.

* `tester` writes failing reproduction tests and behavior tests.
* `test-harness-builder` builds reusable infrastructure such as ScreenBuffer assertions, pty harnesses, snapshot tooling, deterministic fakes, and Hypothesis generators.
* `quality-engineer` verifies gates and baseline drift.
* `render-stabilizer` may fix rendering only after a failing test or explicit evidence exists.

Do not collapse these responsibilities into one agent.

## 7. Runtime and log safety

Runtime checks must not write to the user's real configuration unless explicitly requested.

Use an isolated temporary `HOME` for startup, runtime import, and log triage work:

```sh
tmp_home="$(mktemp -d)"
HOME="$tmp_home" XDG_CONFIG_HOME="$tmp_home/.config" uv run python -m ecli --help
```

Logs may contain secrets or prompt content.

Before quoting logs, redact:

* API keys,
* bearer tokens,
* provider URLs containing credentials,
* prompt-like content,
* raw provider responses,
* local sensitive paths when not required for diagnosis,
* environment variable values that may contain secrets.

## 8. Build and release safety

Build work may inspect and validate local build paths.

Build work must not publish.

Release work is prepare-only unless the user explicitly starts a release phase.

Forbidden commands:

```sh
git commit
git push
git tag
git reset
git clean
twine upload
uv publish
python -m twine upload
gh workflow run
gh run cancel
gh run rerun
gh release create
gh release upload
gh release edit
gh release delete
make release
make release-*
make publish
make publish-*
```

If a requested command may publish, upload, tag, push, or mutate public release state, do not run it. Explain that it is blocked and provide a manual checklist instead.

### Shell-to-Python script migration

Active packaging/build/verification scripts under `scripts/` have been migrated
from shell to Python, preserving the release contract (artifact names, locations,
checksum format, exit-code contracts). The migration is **complete**.

* Active shell wrappers under `scripts/` have been removed. Canonical Python implementations include:
  * `scripts/verify_artifact.py` — artifact SHA256 sidecar verifier (exit codes `0`–`5`).
  * `scripts/sign_checksums.py` — writes basename-only `<artifact>.sha256` sidecars (SHA256 only; not GPG signing).
  * `scripts/check_log_invariant.py` — read-only development log-location invariant.
  * `scripts/verify_runtime.py` — cross-artifact launcher validation.
  * `scripts/build_pyinstaller_linux.py`, `scripts/build_and_package_{deb,rpm,opensuse_rpm,arch,slackware,macos,freebsd}.py`,
    `scripts/package_appimage.py`, `scripts/build_freebsd_pkg.py`,
    `scripts/build_freebsd_port.py`, `scripts/build_docker.py`,
    `scripts/publish_pypi.py` (publish guard; never uploads).
* Do not add active shell wrappers under `scripts/`; release readiness is
  blocked if shell packaging/build/verification logic is reintroduced there.
* `scripts/build-and-package-windows.ps1` is a separate Windows-native packaging
  surface and is not part of this migration.
* `.claude/hooks/block-mutations.sh` is a Claude hook, not a packaging script.
* `tools/freebsd-chroot-build.sh` is a separate FreeBSD chroot helper outside
  this migration.
* the removed FreeBSD package-renaming shell helper was unused and removed during no-shell cleanup.
* Python implementations use only the standard library, explicit `argparse`,
  `pathlib.Path`, and `subprocess.run(..., check=True)` with explicit command
  arrays. They must never publish, upload, sign with external keys, tag, push, or
  trigger workflows.
* The migration contract is enforced by
  `tests/packaging/test_scripts_python_migration_contract.py` and documented in
  `docs/release/artifact-contract.md` under `Shell-to-Python Script Migration`.

## 9. Dirty tree preservation

Before edits, inspect the working tree if command execution is available:

```sh
git status --short
```

Never discard user changes.

Do not run destructive commands such as:

```sh
git reset
git checkout -- .
git clean
```

If the working tree is dirty:

1. Identify files changed by the user.
2. Avoid overwriting them.
3. Prefer patch-style edits.
4. Report conflicts before editing.

The user performs git commits manually. Agents must not commit.

## 10. Code change policy

For Stage 1:

* prefer tests, diagnostics, and reports,
* do not perform broad refactors,
* do not change public behavior unless the task explicitly requests a gated fix,
* keep fixes small and audit-linked,
* name the audit finding or defect addressed by every source change,
* include or update a test when practical,
* do not leave TODO-only or stub implementations,
* do not add empty methods,
* do not hide failing gates.

For a source-code fix, report:

```text
Change summary:
- Finding:
- Files changed:
- Behavior before:
- Behavior after:
- Tests added:
- Commands run:
- Remaining risk:
```

## 11. Documentation policy

Documentation changes must match actual repository commands and scripts.

Do not document commands that do not exist.

When updating docs, check:

* `Makefile`,
* `scripts/`,
* `pyproject.toml`,
* `.github/workflows/`,
* relevant packaging descriptors.

Prefer precise examples over vague prose.

## 12. Expected final response format

For any non-trivial task, finish with:

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
