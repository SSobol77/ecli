<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: audit-report.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# ECLI Pre-Release Audit Report

Audit mode: read-only source/git audit. Source files were not edited. The only intended audit outputs are this report and `audit-evidence/`.

## 1. Summary

Severity counts:

| severity | count |
|---|---:|
| P0 | 3 |
| P1 | 6 |
| P2 | 3 |

The three suspected P0 blocks are confirmed or constrained as follows:

- P0-A config.toml parsing/validation: confirmed schema/runtime-loader drift. The shipped `config.toml` parses, all 162 syntax regexes compile, and the typed service reports zero diagnostics, but that is the defect: the typed schema does not validate most shipped runtime sections used by the legacy runtime loader.
- P0-B undo/redo runtime safety in `src/ecli/core/History.py`: confirmed runtime defect. Redo of selection-preserving block operations references attributes on `History` instead of `editor`, throws `AttributeError`, and leaves redo state inconsistent.
- P0-C `ecli.spec` / artifact-contract / release-pipeline drift: confirmed release drift risk. Runtime import tests pass, but PyInstaller uses `main.py` while package metadata declares `ecli.__main__:main`, several package descriptors hard-code `0.2.2`, and the AppImage packaging script mutates a tracked YAML file with `sed -i`.

Static gates baseline:

- `uv run ruff check . --output-format=concise`: fail, 7 errors.
- `uv run mypy src/ecli tests`: fail, 263 errors in 31 files.
- `uv run pytest -ra -q`: pass, 262 tests.

## 2. Environment & Toolchain

Evidence: `audit-evidence/00-env.txt`, `audit-evidence/01-buildmap.txt`.

Environment snapshot:

- `uv --version`: `uv 0.11.17`.
- Bare `python --version`: failed, `python: command not found`.
- Initial `uv run ruff --version`: materialized CPython 3.11.15 and reported `ruff 0.15.15`.
- Initial `uv run mypy --version`: failed before dev sync, `Failed to spawn: mypy`.
- Initial `uv run pytest --version`: `pytest 8.3.5`.
- Bare `pyinstaller --version`: failed, `pyinstaller: command not found`.
- `git rev-parse HEAD`: `ab08b130e8f1280c94525e0e3f1562c75ab1e47f`.
- Initial `git status --porcelain`: no output.

`uv sync --extra dev` was run under the audit allowance to materialize declared dev tooling. Post-sync tool versions:

- `uv run ruff --version`: `ruff 0.15.12`.
- `uv run mypy --version`: `mypy 2.0.0`.
- `uv run pytest --version`: `pytest 9.0.3`.
- `uv run pyinstaller --version`: `6.20.0`.

Canonical commands and release targets from Makefile evidence:

- Development/test: `uv run ruff check . --output-format=concise`, `uv run mypy src/ecli tests`, `uv run pytest -ra -q`.
- Makefile help advertises package targets for `.deb`, `.rpm`, AppImage, Snap, FreeBSD `.pkg`, macOS `.dmg`, Windows `.exe`, PyPI wheel/sdist, and archive builds.
- Publishing targets are present: `publish-pypi`, `publish-all`, and per-artifact release targets such as `release-deb`, `release-rpm`, `release-appimage`.
- Gate targets include `validate-runtime-imports`, `validate-version-consistency`, `validate-gate2`, and per-platform artifact contract validation targets.

## 3. Static Gates Baseline

Evidence: `audit-evidence/10-ruff.txt`, `audit-evidence/11-mypy.txt`, `audit-evidence/12-pytest.txt`.

Ruff:

- Command: `uv run ruff check . --output-format=concise`.
- Result: fail, exit code 1.
- Count: 7 errors, 5 fixable.
- Failing file: `packaging/pyinstaller/rthooks/force_imports.py`.
- Error classes: `I001`, `F401`, `Q000`, `E722`.

Mypy:

- Command: `uv run mypy src/ecli tests`.
- Result: fail, exit code 1.
- Count: 263 errors in 31 files.
- Highest error concentrations: `src/ecli/ui/panels.py` 53, `src/ecli/core/Ecli.py` 40, `tests/services/test_plan_validation.py` 19, `tests/ui/test_input_routing.py` 17, `src/ecli/ui/KeyBinder.py` 16, `src/ecli/core/History.py` 12.

Pytest:

- Command: `uv run pytest -ra -q`.
- Result: pass, exit code 0.
- Count: 262 passed in 3.37 seconds.
- Slow tests: no pytest slow-test report was emitted by this command; no per-test timing evidence was captured.

### AUD-011: P1 static quality gates are not release-clean

Affected files:

- `packaging/pyinstaller/rthooks/force_imports.py:20`
- `src/ecli/ui/panels.py`
- `src/ecli/core/Ecli.py`
- `src/ecli/core/History.py`

Evidence:

- `audit-evidence/10-ruff.txt`
- `audit-evidence/11-mypy.txt`

Observed facts:

- Ruff fails on `packaging/pyinstaller/rthooks/force_imports.py` with 7 errors.
- Mypy fails with 263 errors in 31 files.
- The highest mypy concentrations are in UI panels, core editor, key binding, and history code.

Impact:

The release branch lacks a clean static quality baseline. The `History.py` P0 defect is visible to mypy, but the current error volume prevents mypy from functioning as a high-signal release gate.

Recommended fix direction:

Either remediate the current static debt or create an explicit, reviewed baseline so new errors fail CI. The P0 `History.py` errors should not remain hidden inside aggregate mypy debt.

## 4. P0 Findings

### AUD-001: P0 config.toml is not validated against the typed service schema used for Phase 1 configuration

Affected files:

- `config.toml:17`
- `config.toml:372`
- `src/ecli/services/config_service.py:81`
- `src/ecli/services/models/config.py:583`
- `src/ecli/utils/utils.py:219`
- `src/ecli/core/Ecli.py:1679`

Evidence:

- `audit-evidence/20-config.txt`
- `audit-evidence/50-ci.txt`

Observed facts:

- `config.toml` parses successfully.
- Corrected validation command reports `typed_service_has_errors=False diagnostics=0`.
- The shipped top-level keys are `ai`, `colors`, `comments`, `editor`, `file_icons`, `fonts`, `keybindings`, `linter`, `logging`, `settings`, `supported_formats`, `syntax_highlighting`, `theme`.
- The typed service expected top-level set is `ai`, `editor`, `git`, `keybindings`, `lsp`, `safety`, `schema`, `ui`.
- Extra shipped keys relative to typed schema: `colors`, `comments`, `file_icons`, `fonts`, `linter`, `logging`, `settings`, `supported_formats`, `syntax_highlighting`, `theme`.
- Missing shipped keys relative to typed schema: `git`, `lsp`, `safety`, `schema`, `ui`.
- All shipped `[[syntax_highlighting.<lang>.patterns]]` entries compiled: `pattern_count=162 compile_failures=0 slow_probe_over_10ms=0`.

Impact:

The typed service gives a clean diagnostic result while most runtime-relevant shipped configuration sections are outside its schema. The application entry path imports `load_config()` from `src/ecli/utils/utils.py`, which creates/loads `~/.config/ecli/config.toml` and merges into `DEFAULT_CONFIG`; the editor syntax path reads `self.config["syntax_highlighting"]` directly. Therefore a release gate that only exercises `ConfigService.load()` cannot prove the runtime config consumed by `Ecli` is schema-valid.

Recommended fix direction:

Make one configuration contract authoritative. Either move runtime startup to `ConfigService` and extend the typed schema to include current runtime sections, or explicitly split legacy UI/editor config from Phase 1 service config with separate validation and tests. Add a test that loads the shipped `config.toml` through the same path used by `src/ecli/__main__.py` and compiles every syntax pattern.

### AUD-002: P0 History redo crashes for selection-preserving block operations

Affected file:

- `src/ecli/core/History.py:478`

Evidence:

- `audit-evidence/21-history.txt`
- `audit-evidence/11-mypy.txt`

Observed facts:

- `History.redo()` restores `selection_after` via `self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end = selection_state_after_op`.
- Immediately after, it checks `if self.is_selecting and self.selection_end:` on the `History` object, not the editor.
- Minimal trace against the real `History` class logs: `AttributeError: 'History' object has no attribute 'is_selecting'`.
- The redo attempt returns with `stacks_after_redo_attempt 0 1`, meaning the action remains on the redo stack and is not restored to main history.
- Mypy independently reports `src/ecli/core/History.py:478: error: "History" has no attribute "is_selecting"` and `"selection_end"`.

Impact:

Redo of block indent/unindent/comment/uncomment actions that store `selection_after` can fail at runtime after partially applying text changes. This violates undo/redo atomicity and can leave text, modified state, and stack state inconsistent.

Recommended fix direction:

Correct the attribute references to the editor object and make redo transactional: validate all replay preconditions before mutating text, apply the mutation, restore cursor/selection, and move stack state only after successful completion. Add direct unit tests for `History` redo of block operations with active selection.

### AUD-003: P0 release artifact contract has drift-prone entry/version surfaces

Affected files:

- `packaging/pyinstaller/ecli.spec:25`
- `pyproject.toml:97`
- `main.py:15`
- `scripts/package_appimage.sh:79`
- `packaging/linux/appimage/appimage-builder.yml:24`
- `packaging/arch/PKGBUILD:10`
- `packaging/windows/nsis/ecli.nsi:18`
- `packaging/nix/package.nix:12`

Evidence:

- `audit-evidence/22-spec-drift.txt`
- `audit-evidence/50-ci.txt`

Observed facts:

- PyInstaller spec uses `entry_point = project_root / "main.py"`.
- Package metadata declares console script `ecli = "ecli.__main__:main"`.
- `main.py` delegates to packaged `ecli.__main__`, so this is not an observed startup failure.
- Existing runtime import contract tests pass: `10 passed in 0.80s`.
- Bare `python scripts/check_runtime_imports.py` fails because bare `python` is absent; `uv run python scripts/check_runtime_imports.py` emits no failure.
- Hard-coded version surfaces exist in Nix, NSIS, Arch, and AppImage metadata.
- `scripts/package_appimage.sh:79` runs `sed -i` against `packaging/linux/appimage/appimage-builder.yml`, which is a tracked packaging file.

Impact:

Runtime import tests are currently green, but release reproducibility is weaker than the artifact contract implies. Multiple packaging descriptors can drift from `pyproject.toml`, and the AppImage path mutates a tracked source file during packaging. This creates a release-blocking risk for a pre-release stabilization branch because artifact state can depend on prior local build history.

Recommended fix direction:

Make `pyproject.toml` the single version source and render platform descriptors into build directories rather than mutating tracked inputs. Align PyInstaller entry evidence with the installed console entry point or add a contract test proving `main.py` delegation remains intentional. Extend `validate-version-consistency` to cover Nix, NSIS, Arch, AppImage YAML, man-page generation outputs, and release docs.

## 5. Rendering / Curses Instability Findings

### AUD-004: P1 curses access is not confined to `src/ecli/ui/`

Affected files:

- `src/ecli/core/Ecli.py:550`
- `src/ecli/core/Ecli.py:7805`
- `src/ecli/core/Ecli.py:7820`
- `src/ecli/core/Ecli.py:7880`

Evidence:

- `audit-evidence/30-curses.txt`
- `audit-evidence/11-mypy.txt`

Observed facts:

- Curses references appear in `src/ecli/ui/TerminalAppMode.py`, `src/ecli/ui/DrawScreen.py`, `src/ecli/ui/PanelManager.py`, `src/ecli/ui/KeyBinder.py`, `src/ecli/ui/panels.py`, and also `src/ecli/core/Ecli.py`.
- Mypy reports curses API typing defects in `src/ecli/core/Ecli.py` and `src/ecli/ui/TerminalAppMode.py`, including incompatible `curses.meta` and `curses.putp` calls.

Impact:

Core editor logic owns terminal-mode side effects, reducing fault containment. Curses errors in setup/resize/key handling can bypass the intended UI boundary and complicate deterministic testing.

Recommended fix direction:

Move terminal mode, resize, and raw curses primitives behind a UI/terminal adapter with explicit invariants: no direct curses calls from core, all calls return structured status, and resize/key events are replayable in tests.

### AUD-005: P1 rendering geometry mixes `len()` and terminal cells despite a `wcwidth` dependency

Affected files:

- `src/ecli/ui/DrawScreen.py`
- `src/ecli/ui/panels.py`
- `src/ecli/core/Ecli.py`

Evidence:

- `audit-evidence/30-curses.txt`
- `pyproject.toml:46`

Observed facts:

- The project depends on `wcwidth>=0.2.13`.
- Curses inventory shows many column, cursor, width, and status-bar operations using `len()` and fixed slicing around `cursor_x`, window width, `addstr`, `addnstr`, and `chgat`.
- The audit did not observe a completed cell-width abstraction across editor text, panels, status line, and selection highlighting.

Impact:

Unicode wide characters, emoji, combining marks, and ambiguous-width glyphs can desynchronize logical cursor positions from terminal cells. In a curses editor this can manifest as selection corruption, off-by-one drawing, or `curses.error` near the right edge.

Recommended fix direction:

Introduce a terminal-cell geometry layer based on `wcwidth`/`wcswidth` and make cursor, selection, clipping, and status-bar rendering consume that interface. Add fixtures containing wide glyphs, combining marks, and emoji.

### AUD-006: P2 resize handling exists but is not proven by tests

Affected files:

- `src/ecli/ui/KeyBinder.py:756`
- `src/ecli/core/Ecli.py` resize handling references in `audit-evidence/30-curses.txt`

Evidence:

- `audit-evidence/30-curses.txt`

Observed facts:

- `curses.KEY_RESIZE` is routed to `self.editor.handle_resize`.
- The grep inventory did not show a dedicated SIGWINCH test or terminal-resize simulation in the captured evidence.

Impact:

Resize behavior may work manually, but no automated evidence proves deterministic state clamping, redraw invalidation, and panel recreation after terminal size changes.

Recommended fix direction:

Add headless/fake-window resize tests that verify `last_window_size`, cursor clamping, scroll clamping, panel windows, and redraw invalidation.

## 6. Logging Findings for Log-Analyst

### AUD-007: P1 AI provider logging can expose secrets or prompt/response content

Affected files:

- `src/ecli/integrations/AI.py:313`
- `src/ecli/integrations/AI.py:327`
- `src/ecli/integrations/AI.py:537`
- `src/ecli/integrations/AI.py:577`
- `src/ecli/integrations/AI.py:710`

Evidence:

- `audit-evidence/40-logging.txt`

Observed facts:

- Logging setup writes to `~/.config/ecli/logs/editor.log`.
- Format includes timestamp, level, logger name, message, source filename, and line number.
- Rotation: `editor.log` max 2 MiB, backup count 5.
- `config.toml` requests `[logging] file_level = "DEBUG"`, `console_level = "WARNING"`, `log_to_console = false`, `separate_error_log = false`.
- Runtime console logging is forced disabled in code via `log_to_console_enabled = False`.
- Gemini debug logging includes the full request URL, whose template includes `?key={api_key}`.
- Several provider error paths log raw `response_text`; Hugging Face debug logs `data_raw`.

Impact:

At DEBUG level, AI request URLs, provider responses, or model outputs may reach disk logs. Provider error payloads can include prompt echoes, request metadata, or authentication diagnostics. This is a secret and prompt-content leakage risk.

Recommended fix direction:

Centralize AI log redaction before logger calls. Never log URLs containing credentials. Treat provider response bodies as sensitive unless explicitly summarized. Add tests with sentinel API keys and prompt strings proving they do not appear in captured logs.

### AUD-008: P2 live headless logging run was blocked by the audit write boundary

Affected files:

- `src/ecli/utils/logging_config.py:182`
- `src/ecli/utils/utils.py:193`

Evidence:

- `audit-evidence/40-logging.txt`

Observed facts:

- `setup_logging()` creates `~/.config/ecli/logs/editor.log`.
- `load_config()` may create `~/.config/ecli/config.toml` and `~/.config/ecli/.env`.
- The user constrained writes to `audit-report.md` and `audit-evidence/`.

Impact:

This audit did not execute a live curses/headless ECLI session, so live ERROR/CRITICAL, traceback formatting, asyncio warning, and curses-error behavior are not fully proven.

Recommended fix direction:

Run a follow-up log-analyst pass in an isolated temporary `HOME` and collect logs as evidence. That run should include AI-disabled startup, resize/key smoke, and forced error paths.

## 7. CI / Test Baseline Gaps

### AUD-009: P1 CI does not gate mypy and has weak direct coverage for the P0 history/config invariants

Affected files:

- `.github/workflows/ci.yml:73`
- `.github/workflows/ci.yml:89`
- `tests/core/test_open_preserves_indentation.py:72`
- `tests/characterization/test_existing_keybindings.py:26`
- `tests/services/test_config_service.py`
- `tests/services/test_config_migration.py`

Evidence:

- `audit-evidence/50-ci.txt`
- `audit-evidence/21-history.txt`
- `audit-evidence/11-mypy.txt`

Observed facts:

- CI runs ruff lint, ruff format check, pytest with coverage, and Gate 2 contract validation.
- CI evidence did not show a mypy job.
- Existing tests reference `FakeHistory` in characterization/open-preservation tests rather than exercising the real `History` undo/redo implementation.
- Config service tests exist, but the audit evidence did not show a test that loads the shipped `config.toml` through the legacy runtime `load_config()` path and validates the current runtime-only sections.

Impact:

The exact `History.py` defect is statically visible to mypy but not gated by CI. The config bifurcation remains invisible if tests only cover the typed service model.

Recommended fix direction:

Add a CI mypy gate once the current error debt is triaged or baselined. Add focused tests for `History` redo selection replay and shipped config/runtime-loader validation.

### AUD-010: P2 FreeBSD packaging is isolated and pinned, but release workflow still carries out-of-band attachment logic

Affected files:

- `.github/workflows/freebsd-pkg.yml:50`
- `.github/workflows/freebsd-pkg.yml:118`
- `.github/workflows/release.yml:184`
- `.github/workflows/release.yml:466`

Evidence:

- `audit-evidence/50-ci.txt`

Observed facts:

- Standalone FreeBSD workflow is pinned to `vmactions/freebsd-vm@d1e65811565151536c0c894fff74f06351ed26e6` with comment `v1.4.5`.
- Release workflow also has a FreeBSD build leg and later release-note logic indicating FreeBSD may be attached out-of-band.

Impact:

The pin is good, but the release process has two FreeBSD surfaces and an explicit out-of-band path. That increases operational ambiguity for final release evidence.

Recommended fix direction:

Define one authoritative FreeBSD release path: either release workflow artifact inclusion or standalone out-of-band attachment, with a single checksum/contract record.

## 8. Lint/Type-Debt Backlog

Ruff extend-exclude backlog from `pyproject.toml:152`:

- `src/ecli/core/Ecli.py`
- `src/ecli/core/History.py`
- `src/ecli/integrations/AI.py`
- `src/ecli/integrations/GitBridge.py`
- `src/ecli/integrations/LinterBridge.py`
- `src/ecli/integrations/__init__.py`
- `src/ecli/ui/DrawScreen.py`
- `src/ecli/ui/KeyBinder.py`
- `src/ecli/ui/PanelManager.py`
- `src/ecli/ui/TerminalAppMode.py`
- `src/ecli/ui/__init__.py`
- `src/ecli/ui/panels.py`
- `src/ecli/utils/__init__.py`
- `src/ecli/utils/logging_config.py`
- `src/ecli/utils/utils.py`

Mypy error map, derived from `audit-evidence/11-mypy.txt`:

| module | errors |
|---|---:|
| `src/ecli/ui/panels.py` | 53 |
| `src/ecli/core/Ecli.py` | 40 |
| `tests/services/test_plan_validation.py` | 19 |
| `tests/ui/test_input_routing.py` | 17 |
| `src/ecli/ui/KeyBinder.py` | 16 |
| `src/ecli/core/History.py` | 12 |
| `src/ecli/integrations/LinterBridge.py` | 11 |
| `tests/services/test_privileged_action_service.py` | 10 |
| `tests/services/test_audit_log_service.py` | 9 |
| `tests/ui/test_service_panels.py` | 9 |
| `tests/characterization/test_existing_tui_panels.py` | 9 |
| all remaining files | 58 |

## 9. Findings Table

| ID | severity | area | file:line | evidence |
|---|---|---|---|---|
| AUD-001 | P0 | config/runtime validation | `src/ecli/utils/utils.py:219`, `src/ecli/services/config_service.py:81`, `src/ecli/core/Ecli.py:1679`, `config.toml:372` | `audit-evidence/20-config.txt` |
| AUD-002 | P0 | undo/redo runtime safety | `src/ecli/core/History.py:478` | `audit-evidence/21-history.txt`, `audit-evidence/11-mypy.txt` |
| AUD-003 | P0 | release/artifact drift | `packaging/pyinstaller/ecli.spec:25`, `pyproject.toml:97`, `scripts/package_appimage.sh:79` | `audit-evidence/22-spec-drift.txt`, `audit-evidence/50-ci.txt` |
| AUD-004 | P1 | curses containment | `src/ecli/core/Ecli.py:550`, `src/ecli/core/Ecli.py:7805` | `audit-evidence/30-curses.txt`, `audit-evidence/11-mypy.txt` |
| AUD-005 | P1 | rendering geometry | `src/ecli/ui/DrawScreen.py`, `src/ecli/ui/panels.py`, `src/ecli/core/Ecli.py` | `audit-evidence/30-curses.txt` |
| AUD-006 | P2 | resize verification | `src/ecli/ui/KeyBinder.py:756` | `audit-evidence/30-curses.txt` |
| AUD-007 | P1 | logging/secret risk | `src/ecli/integrations/AI.py:313`, `src/ecli/integrations/AI.py:577` | `audit-evidence/40-logging.txt` |
| AUD-008 | P2 | logging validation blocked | `src/ecli/utils/logging_config.py:182`, `src/ecli/utils/utils.py:193` | `audit-evidence/40-logging.txt` |
| AUD-009 | P1 | CI/test coverage | `.github/workflows/ci.yml:73`, `tests/core/test_open_preserves_indentation.py:72` | `audit-evidence/50-ci.txt`, `audit-evidence/21-history.txt` |
| AUD-010 | P2 | FreeBSD release path | `.github/workflows/freebsd-pkg.yml:50`, `.github/workflows/release.yml:466` | `audit-evidence/50-ci.txt` |
| AUD-011 | P1 | static quality gate | `packaging/pyinstaller/rthooks/force_imports.py:20`, `src/ecli/ui/panels.py` | `audit-evidence/10-ruff.txt`, `audit-evidence/11-mypy.txt` |

## 10. Out of Scope / UNVERIFIED

- Live curses/headless ECLI execution: UNVERIFIED. Blocked because normal startup may create `~/.config/ecli/config.toml`, `~/.config/ecli/.env`, and `~/.config/ecli/logs/editor.log`, while the audit allowed writes only to `audit-report.md` and `audit-evidence/`.
- Windows NSIS execution: UNVERIFIED. Environment is Debian/Linux and user explicitly prohibited Windows-only steps.
- macOS DMG validation: UNVERIFIED. Environment is Debian/Linux.
- FreeBSD package build execution: UNVERIFIED. The audit read workflows/scripts but did not run a FreeBSD VM build.
- PyPI/GitHub publishing: out of scope and not attempted.
- Catastrophic regex behavior beyond bounded probes: partially verified only. The audit compiled all 162 patterns and ran short probes; it did not run formal ReDoS analysis.
- Existing repo logs under `logs/`: inspected only as static files with redaction. They are not proof of current live runtime behavior.

## Appendix A: Exact Commands Run

Environment:

```sh
uv --version
python --version
uv run ruff --version
uv run mypy --version
uv run pytest --version
pyinstaller --version
git rev-parse HEAD
git status --porcelain
uv sync --extra dev
uv run ruff --version
uv run mypy --version
uv run pytest --version
uv run pyinstaller --version
```

Build map:

```sh
sed -n '1,260p' pyproject.toml
sed -n '1,520p' Makefile
test -f Taskfile.yml && sed -n '1,260p' Taskfile.yml || true
find scripts -maxdepth 1 -type f -print | sort
find .github/workflows -maxdepth 1 -type f -print | sort
sed -n '1,220p' .github/workflows/freebsd-pkg.yml
make help
make sysinfo
awk '/^[[:alnum:]_.-]+:/ {print $1}' Makefile | sed 's/:$//' | sort -u
```

Static gates:

```sh
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
uv run pytest -ra -q
```

Config audit:

```sh
nl -ba config.toml | sed -n '1,760p'
nl -ba src/ecli/services/config_service.py | sed -n '57,229p'
nl -ba src/ecli/services/models/config.py | sed -n '77,690p'
nl -ba src/ecli/utils/utils.py | sed -n '65,237p'
nl -ba src/ecli/core/Ecli.py | sed -n '1673,1699p'
uv run python - <<'PY'
# validation of config.toml patterns and typed service
PY
uv run python - <<'PY'
# corrected validation of config.toml patterns and typed service
PY
```

History audit:

```sh
nl -ba src/ecli/core/History.py | sed -n '76,545p'
nl -ba src/ecli/utils/text_buffer.py | sed -n '39,104p'
rg -n "undo|redo|History|history" tests/core tests/characterization tests/ui
uv run pytest tests/core -q
uv run python - <<'PY'
# minimal History runtime traces
PY
```

Packaging drift:

```sh
nl -ba packaging/pyinstaller/ecli.spec | sed -n '1,180p'
nl -ba packaging/pyinstaller/rthooks/force_imports.py | sed -n '1,120p'
nl -ba pyproject.toml | sed -n '17,120p'
nl -ba main.py | sed -n '1,120p'
uv run pytest tests/packaging/test_runtime_import_contract.py -q
python scripts/check_runtime_imports.py
uv run python scripts/check_runtime_imports.py
rg -n "0\.2\.2|version|ecli.__main__:main|ecli.png|hiddenimports|datas|ecli-editor|ecli_editor" pyproject.toml packaging scripts .github README.md CHANGELOG.md docs/release docs/contributor docs/INSTALL.md
```

Curses/rendering:

```sh
rg -n "curses|stdscr|\.refresh\(|noutrefresh|doupdate|addstr|addnstr" src/ecli
rg -n "curses|stdscr|\.refresh\(|noutrefresh|doupdate|addstr|addnstr" src/ecli | cut -d: -f1 | sort -u
rg -n "\blen\([^\n]*(cursor|col|column|x|width|w|screen|line)|wcwidth|wcswidth|SIGWINCH|resize|KEY_RESIZE|resizeterm|is_term_resized|getmaxyx|scroll_left|cursor_x" src/ecli
nl -ba src/ecli/core/Ecli.py | sed -n '540,560p;7790,7890p'
nl -ba src/ecli/ui/DrawScreen.py | sed -n '1,220p;430,520p;930,1030p'
nl -ba src/ecli/ui/panels.py | sed -n '250,460p;1430,1510p;2528,2820p'
```

Logging:

```sh
nl -ba src/ecli/utils/logging_config.py | sed -n '116,322p'
nl -ba config.toml | sed -n '17,22p'
nl -ba src/ecli/integrations/AI.py | sed -n '192,248p;297,327p;507,578p;672,710p'
nl -ba src/ecli/core/AsyncEngine.py | sed -n '147,253p;264,281p'
find logs -maxdepth 2 -type f -print | sort
rg -n "ERROR|CRITICAL|Traceback|unawaited|Task exception|curses" logs src/ecli | redacted excerpt
```

CI/test baseline:

```sh
find .github/workflows -maxdepth 1 -type f -print | sort
nl -ba .github/workflows/*.yml | sed -n '1,260p'
rg -n "config|ConfigService|syntax_highlighting|History|undo|redo|runtime_import|pyinstaller|artifact|freebsd|coderabbit|CodeRabbit" tests .github docs/quality docs/release pyproject.toml
```

## Issue #102 addendum — multiline TextMate protection

Implementation:

- ECLI keeps TextMate scopes as the primary token source for extension-backed
  rendering.
- `src/ecli/extensions/ecli_integration/syntax_service.py` now applies a
  deterministic protected-range pass for known stateless multiline gaps:
  Python strings/docstrings, JavaScript/TypeScript block/doc/line comments and
  strings, HTML comments, and CSS block comments/strings.
- Protected comment/string ranges are cached by buffer revision and mapped onto
  viewport lines before `theme_bridge.tokens_to_spans()` flattens TextMate
  output, so protected comment/string style wins over leaked keyword, number,
  operator, tag, selector, property, or value categories.

Real tests:

- `tests/extensions/test_textmate_multiline_protection.py` adds direct
  protected-range tests, TextMate-span rendering tests, and editor-facing
  rendering tests for Python, JavaScript, TypeScript, HTML, and CSS multiline
  fixtures.
- Existing performance coverage remains in
  `tests/extensions/test_textmate_render_performance.py` and
  `tests/extensions/test_textmate_scroll_regression.py` using real repository
  files including `Makefile`, `logs/freebsd-0.2.2-fail.log`,
  `logs/pr-46-body.md`, and `scripts/build_pyinstaller_linux.py`.

Log/artifact analysis:

- The known real artifacts for large-file acceptance remain the repository
  `Makefile`, `logs/freebsd-0.2.2-fail.log`, and `logs/pr-46-body.md`.
- Synthetic fixtures are intentionally used only for exact adversarial
  multiline comment/string bodies that are not guaranteed to exist in repository
  files.

Documentation:

- `docs/architecture/extensions-layer.md` documents TextMate-primary rendering,
  the bounded language-aware protection layer, and the large-file/multiline
  acceptance tests.
- `docs/release/release-checklist.md` includes large-file scroll, multiline
  rendering, no-SQL fallback, and TextMate dependency/fallback checks.

Audit conclusion:

- Imported upstream extension assets remain untouched.
- F11 PySH Console Panel behavior, future F4 linter work, and VMLab/QEMU/QMP
  scope remain untouched.
- The issue #102 rendering gap is constrained to the ECLI-owned adapter layer,
  with focused regression and performance evidence.

## Extensions runtime asset prune addendum

Scope:

- `src/ecli/extensions/` is now treated as a curated runtime asset bundle, not a
  vendored copy of complete VS Code extension source repositories.
- The prune removes non-runtime development, build, test, media, generated, and
  activation/runtime source artifacts from the imported tree.
- The tree is **normalized**: the root contains only `ecli_integration/`,
  `lang/`, `themes/`, and `THIRD_PARTY_NOTICES.md`. Imported language/runtime
  declarative folders moved under `lang/<name>`; theme folders moved under
  `themes/<name>` with the `theme-` prefix dropped (for example
  `theme-defaults` → `themes/defaults`).
- Retained runtime asset categories are package manifests/NLS tables, TextMate
  grammars, themes, snippets, language-configuration metadata, and legal
  attribution files.

Architecture and safety boundaries:

- ECLI still does not execute a VS Code extension host, Node/TypeScript
  activation, `activationEvents`, `package.json` scripts, or Copilot runtime
  code.
- `ecli_integration` discovery scans the curated `lang/` and `themes/` groups
  (`registry.MANIFEST_GROUP_DIRS`); contribution-path resolution,
  grammar/theme/language-detection adapters, TextMate tokenization, and theme
  numbering are otherwise unchanged.
- VS Code UI/runtime-only folders without ECLI-consumed declarative
  language/grammar/snippet/theme assets are removed from the runtime bundle,
  including `references-view`, `notebook-renderers`, the `*-language-features`
  language servers, `git`/`github`, and the manifest-only / tooling-only
  `copilot`, `npm`, `configuration-editing`, and `extension-editing` folders.
- A generated `src-ecli-extensions.txt` inventory file was removed from the
  runtime tree.
- The existing F4 Diagnostics, F7 AI, F11 PySH Console Panel, TextMate
  tokenization/rendering algorithms, startup/render loop, theme numbering, and
  VMLab/QEMU/QMP scopes are not part of this cleanup.

Validation contract:

- `tests/extensions/test_extensions_tree_contract.py` enforces the normalized
  structure: a small root allowlist (`ecli_integration/`, `lang/`, `themes/`,
  `THIRD_PARTY_NOTICES.md`, optional `README.md`), per-group `package.json`
  presence, the curated runtime file allowlist, and rejection of
  source/build/test/media artifacts and flat root folders.
- Manifest, grammar, theme, language-detection, and package-data tests verify
  that package-referenced runtime assets still resolve and still ship in the
  wheel and sdist.
- `docs/architecture/extensions-layer.md`,
  `docs/release/packaging-flows.md`, and
  `docs/release/release-checklist.md` document the active curated asset
  package-data contract.
