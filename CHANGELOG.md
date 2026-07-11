<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: CHANGELOG.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Changelog

## 0.2.4 - Extensions, Diagnostics, and Release Gate Hardening

ECLI v0.2.4 adds the Extensions Foundation, extension-backed syntax and theme
integration, F4 diagnostics/linter architecture, OS/artifact-aware provisioning
evidence, Linux official distro evidence audits, and release gate hardening.

### Added

- Added the curated Extensions Layer under `src/ecli/extensions/` with
  data-only language, grammar, snippet, configuration, and theme assets.

- Added extension manifest registry, package-data contract coverage, and
  source-tree tests that reject raw VS Code runtime/source artifacts,
  generated outputs, media/test assets, and misplaced extension roots.

- Added extension-backed language detection, TextMate grammar catalog lookup,
  syntax rendering, and multiline comment/string protection for editor text.

- Added theme registry and theme bridge support for extension-backed themes,
  including numbered theme migration coverage for the current configuration
  model.

- Added the F4 Diagnostics/Linter architecture with normalized diagnostics
  models, provider registry, provider utilities, Ruff reference provider,
  linter microservice metadata, parser coverage, and service/provider
  selection tests.

- Added OS/artifact-aware F4 linter provisioning contracts, provisioning
  evidence generation/verification scripts, packaging hooks, and exact
  21-artifact evidence coverage.

- Added Linux F4 provisioning policy manifests, distro provenance catalog,
  distro mapping evidence, official Debian evidence promotion, and official
  evidence drift audit gates.

### Changed

- Project package version is `0.2.4`.

- README now presents v0.2.4 as the current release and describes the
  Extensions Layer, F4 Diagnostics/Linter architecture, provisioning evidence
  gates, and current safety boundaries.

- Release validation is separated into source/structural Gate 2, explicit
  fail-closed built-artifact validation, and exact final GitHub Release asset
  verification.

- PyPI and GitHub Release publication ordering now requires successful built
  artifact validation before publication jobs may run.

- Release documentation now preserves the exact 21 ECLI-owned uploaded asset
  contract, treats GitHub-generated source archives as outside that contract,
  and keeps checksum sidecars as non-uploaded verification evidence.

### Fixed

- Removed agent-workspace files from the tracked repository and release
  contract surface.

- Stabilized v0.2.3 runtime/UX edge cases before adding the F4 and extension
  layers.

- Simplified CLI preload document handling while preserving editor open/create
  semantics.

- Prevented logging rollover errors from corrupting the TUI.

### Safety Boundaries

- Imported extension assets are data only; ECLI does not execute VS Code
  extension runtime code.

- F4 provisioning evidence gates are packaging/release contracts and do not
  redesign the F4 panel UI.

- Clean-machine Debian 13 installer validation has not yet been completed.
  Repository tests and CI evidence do not replace that physical installation
  test.

## 0.2.3 - Panel Console Stabilization

ECLI v0.2.3 is a Panel Console Stabilization release on top of the Services
Foundation. It keeps the existing editor behavior intact, rejects full
PTY/VT terminal emulator scope for ECLI 0.2.x, and replaces the fragile F11
terminal experiment with an ECLI-owned PySH Console Panel.

### Added

- Added the F11 PySH Console Panel as the supported command-console panel
  surface.

- Added F12 focus switching between the editor and right-side panels.

- Added deterministic PySH backend diagnostics and console builtins for `cd`,
  `pwd`, `clear`, and `exit`.

- Added command cancellation coverage for the console backend path.

### Changed

- PySH is used as a subprocess argv backend only; command execution uses safe
  argv construction rather than shell interpolation.

- The release explicitly rejects full PTY terminal emulation, VT parsing,
  xterm behavior, fullscreen terminal application scope, PySH source migration,
  and PySH monorepo conversion.

- The official GitHub Release asset contract is exactly 21 clean public asset
  names. Numeric public prefixes were documented as a v0.2.3 staging mistake
  and are rejected by the release asset verifier after repair.

### Fixed

- Stabilized F11 panel open/focus behavior and F12 editor/panel focus routing.

- Preserved service-panel safety boundaries: System Doctor remains read-only,
  Command Plan output remains draft/preview-only, and privileged remediation is
  not enabled.

### Safety Boundaries

- No full PTY/VT terminal emulator is included.

- No VMLab, QEMU, QMP, or privileged remediation runtime scope is included.

## 0.2.2 - Packaged Runtime Startup Fixes

### Fixed

- Fixed packaged/frozen runtime startup failure caused by a test-only
  `unittest.mock` dependency leaking into production code.

- Added visible stderr diagnostics for critical pre-curses startup failures.

- Added cross-package runtime smoke validation for packaged ECLI launchers.

- Fixed Git Panel status command getting stuck at
  `Running: git status ...` without rendering command results.

- Fixed Git Panel repository detection and working-directory handling.

- Fixed Git Panel BUSY state reset after command completion, errors, timeout,
  or cancellation.

- Fixed Git Panel cancellation/output messages rendering outside the output
  pane.

- Fixed global Help shortcut being blocked by active panels.

- Fixed AI Code Assistant shortcut crashing when invoked while File Manager is
  active.

- Made F7 AI Code Assistant close File Manager automatically and continue with
  the normal editor AI flow.

- Hardened editor selection handling so invalid panel/editor state cannot raise
  `IndexError`.

- Prevented selection warnings/log records from being printed into the curses
  editor canvas.

- Prevented input handler tracebacks from corrupting the curses screen.

- Preserved global Help behavior across active panels.

### Packaging

- Hardened release builds with production import guards.

- Ensured packaged `ecli --help` and `ecli --version` can run without curses
  initialization.

- Enforced artifact output under the current project version directory.

## 0.2.1 - Release Hardening and Packaging

ECLI v0.2.1 is a release-hardening update for source editing correctness, Python package assets, Linux desktop integration, and Linux package coverage.

### Fixed

- Packaged the application icon in PyPI wheel and source distributions.

- Added deterministic package-resource lookup for the ECLI icon.

- Preserved source-file indentation and whitespace when opening and saving text
  files.

- Preferred strict UTF-8 decoding before detector fallback, preventing valid UTF-8 Cyrillic source files from being misidentified as MacRoman.

### Added

- `ecli-install-desktop-entry` for explicit user-level Linux desktop launcher and icon registration after `pip`/`pipx` installs.

- SUSE/openSUSE RPM release support.

- Slackware `.txz` package support.

- Arch Linux `PKGBUILD` support with normalized ECLI release artifact names.

- Nix/NixOS flake and package expression support.

- Normalized release artifact naming contract for Linux package outputs.

### Changed

- Project package version is `0.2.1`.

- Installation documentation now covers `pipx`, virtual environments, Debian/Ubuntu externally managed Python environments, Linux desktop launcher registration, and the added Linux package families.

## 0.2.0 - Services Foundation

ECLI v0.2.0 prepares the Services Foundation release. The editor remains the default launch surface, and the new service capabilities are exposed through right-side TUI panels plus a minimal read-only CLI.

### Added

- Right-side System Doctor panel on `F8` for read-only diagnostic findings.

- Right-side Services status view for the Phase 1 composition root.

- Command Plan preview flow for eligible System Doctor findings.

- Minimal service CLI:
  - `python3 -m ecli --services`
  - `python3 -m ecli --doctor`
  - `python3 -m ecli --plan-preview`

- Typed service foundation:
  - `ConfigService`
  - `ProjectService`
  - `CommandPlanService`
  - `BuiltInPolicyEngine`
  - `AuditLogService`
  - `PrivilegedActionService` refusal-only skeleton
  - `SystemDoctor` read-only skeleton
  - `ServiceRegistry` composition root

- Friendly AI configuration error handling when a selected provider is missing its user-provided API key.

### Changed

- Project package version is `0.2.0`.

- PyPI-facing README now describes the terminal-first workbench model, current panel keybindings, service CLI, and v0.2.0 safety boundaries.

- AI provider selection and API-key storage guidance is documented explicitly:
  - provider selection belongs in `config.toml`;
  - API keys belong in `~/.config/ecli/.env`.

### Safety Boundaries

- SystemDoctor is read-only.

- CommandPlan output is draft/preview-only.

- PrivilegedActionService is refusal-only in this release.

- Service panels do not execute remediation.

- No VMLab runtime behavior is included.

- No real privileged execution path is enabled.

### Expected Release Artifacts

- PyPI wheel and source distribution.

- Linux `.deb`.

- Linux `.rpm`.

- Linux `.tar.gz`.

- Windows portable `.exe`.

- Windows setup `.exe`.

- macOS universal2 `.dmg`.

- FreeBSD `.pkg`.

- CycloneDX SBOM.

- SHA256 sidecars.
