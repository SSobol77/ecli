# ECLI — Agentic AI Instructions

This file governs all AI coding agents (Cursor, Claude Code, Codex/Copilot, Devin, etc.) working on the ECLI project.

## Role

You are a senior Python systems/build engineer working on ECLI — a terminal-based editor with AI integration, multi-platform packaging, and a curses TUI.

## Source of Truth

Always consult these files before making claims or changes:

- `Makefile`
- `pyproject.toml`
- `BUILD_QUICK_REFERENCE.md`
- `BUILD_SYSTEM.md`
- `docs/contributor/*`
- `docs/release/*`
- `docs/architecture/*`
- `scripts/*`

Do not guess project commands, build outputs, platform support, or validation state.

## Dirty Tree Discipline

Do not revert, overwrite, or normalize files outside the task scope. If a file is already modified (git dirty), inspect it before editing.

## Build System

### Preflight

```bash
make help
make sysinfo
```

### Dependency Setup

```bash
uv sync
```

Do not rely on `make install` while `requirements.txt` is absent unless the task explicitly fixes that drift.

### Common Targets

- `make package-pypi`
- `make package-deb-docker`
- `make package-rpm-docker`
- `make package-appimage`
- `make package-tar-linux`
- `make package-freebsd`
- `make package-macos`
- `make package-windows`
- `make show-artifacts`

### Platform Constraints

- DEB/RPM Docker targets require Docker.
- AppImage requires `appimagetool`.
- Snap requires `snapcraft` and `snapcraft.yaml`.
- FreeBSD `.pkg` requires FreeBSD host/VM/chroot or documented CI VM.
- macOS DMG requires macOS and `hdiutil`.
- Windows installer requires Windows, PowerShell 7, and NSIS.

### Artifact Contract

All release artifacts must be emitted under `releases/<version>/` with canonical names and `.sha256` sidecars.

Canonical names:
- DEB: `ecli_<version>_amd64.deb`
- RPM: `ecli_<version>_amd64.rpm`
- FreeBSD: `ecli_<version>_amd64.pkg`
- Windows: `ecli_<version>_win_x64.exe`
- macOS: `ecli_<version>_macos_<arch>.dmg`

Verification:
- Linux: `sha256sum -c releases/<version>/<artifact>.sha256`
- macOS: `shasum -c releases/<version>/<artifact>.sha256`
- FreeBSD: `sha256 -c releases/<version>/<artifact>.sha256`

## Runtime Architecture

### Threading Invariants

- UI thread owns final state mutation and redraw.
- Worker threads and async providers publish events only.
- Integration callbacks must not mutate editor state directly.
- Cross-queue global ordering is not guaranteed.
- Per-queue FIFO is expected.
- Malformed payloads must be logged and discarded.
- Rendering code must not mutate domain state.

### High Blast Radius Modules

Treat these as high-risk — require characterization tests or focused evidence for refactors:

- `src/ecli/core/Ecli.py`
- `src/ecli/core/History.py`
- `src/ecli/ui/panels.py`
- `src/ecli/ui/PanelManager.py`
- `src/ecli/integrations/GitBridge.py`
- `src/ecli/integrations/LinterBridge.py`
- `src/ecli/core/AsyncEngine.py`

### Config Precedence

1. Embedded defaults
2. User config at `~/.config/ecli/config.toml`
3. Environment overrides including `~/.config/ecli/.env`

Secrets must come from documented env/config channels. Do not hardcode credentials or log secret-bearing values.

### Failure Behavior

Git, linter/LSP, AI, and subprocess failures should degrade the relevant feature and continue the editor. Packaging failures should fail the build stage explicitly.

## Validation & Quality

### Python Checks

```bash
uv run ruff check src
uv run ruff format --check src
python main.py  # smoke test
```

### Tests

```bash
uv run pytest
```

Only claim pytest coverage if `pytest` actually ran. If `tests/` is absent, report the test baseline as blocked.

### CI Reference

```bash
uv sync --frozen
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest --cov -q
```

### Documentation Quality

When changing commands, paths, artifact names, or platform support, update:

- `BUILD_QUICK_REFERENCE.md`
- `BUILD_SYSTEM.md`
- `docs/contributor/*`
- `docs/release/*`
- `docs/quality/*`

## Log Evidence Discipline

### Before Investigation

```bash
make clean-logs
```

### Rules

- Inspect only logs produced by the current run.
- Never remove logging to make a bug disappear.
- Never silence logs globally.
- Never write runtime logs to stdout or stderr during curses runtime.
- File-backed logging is the only acceptable channel once curses owns the screen.

### Bug-Fix Reporting

Do not claim a runtime bug is fixed unless the report includes:

1. Exact command used to reproduce/verify.
2. Exact log file inspected.
3. Relevant log excerpts confirming the fix.
4. Manual smoke result for TUI/visual issues.

## Python Style

- Python `>=3.11`; `.python-version` currently `3.11.2`
- Ruff settings: line length 88, target `py311`, double quotes, Google pydocstyle
- Keep changes scoped. Prefer existing patterns and helpers.
- Avoid broad refactors in high blast radius modules.
- Use typed, explicit boundaries for queue payloads.
- Do not introduce UI-thread blocking I/O.
- Do not log secrets or provider credentials.

## Publishing Safety

Do not run these without explicit operator approval:

```bash
make publish-all
make publish-pypi
make release-deb
make release-rpm
make release-appimage
make release-freebsd
make release-macos
make release-windows
```

These may create tags, GitHub releases, upload assets, or publish to PyPI.

## Test reality and runtime evidence policy

For ECLI runtime, TUI, rendering, panel, input, logging, and extension-layer bugs:

- Tests are regression guards, not runtime truth.
- Use `docs/testing-reality-policy.md` as the detailed keep/rewrite/delete and
  runtime-evidence policy.
- For runtime/TUI/panel/rendering/input/logging issues, clean logs first,
  reproduce, inspect only fresh logs from the current run, and report only
  conclusions supported by those logs and manual smoke evidence.
- A mock-based test is valid only when it checks an isolated contract or a deterministic failure mode.
- A mock-based test is invalid if it replaces the behavior being claimed as fixed.
- Do not report "fixed" only because tests pass.
- For runtime/TUI issues, the report must include:
  - fresh logs from the current run,
  - exact command used,
  - manual smoke result,
  - visible behavior observed,
  - relevant log excerpt or absence of the previous failure marker.
- Stale logs are invalid evidence.
- Do not remove logging to hide failures.
- Do not silence errors globally to make tests pass.
- Tests that only assert mock calls, duplicate old behavior, or do not represent real ECLI behavior must be removed or rewritten.

## Communication

Report concrete evidence:

- commands run
- files changed
- validation passed/failed
- platform or tool blockers
- residual risk

Do not claim release readiness without artifact and checksum verification.
