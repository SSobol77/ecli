# Changelog

## 0.2.1 - Release Hardening and Packaging

ECLI v0.2.1 is a release-hardening update for source editing correctness,
Python package assets, Linux desktop integration, and Linux package coverage.

### Fixed

- Packaged the application icon in PyPI wheel and source distributions.
- Added deterministic package-resource lookup for the ECLI icon.
- Preserved source-file indentation and whitespace when opening and saving text
  files.
- Preferred strict UTF-8 decoding before detector fallback, preventing valid
  UTF-8 Cyrillic source files from being misidentified as MacRoman.

### Added

- `ecli-install-desktop-entry` for explicit user-level Linux desktop launcher
  and icon registration after `pip`/`pipx` installs.
- SUSE/openSUSE RPM release support.
- Slackware `.txz` package support.
- Arch Linux `PKGBUILD` support with normalized ECLI release artifact names.
- Nix/NixOS flake and package expression support.
- Normalized release artifact naming contract for Linux package outputs.

### Changed

- Project package version is `0.2.1`.
- Installation documentation now covers `pipx`, virtual environments,
  Debian/Ubuntu externally managed Python environments, Linux desktop launcher
  registration, and the added Linux package families.

## 0.2.0 - Services Foundation

ECLI v0.2.0 prepares the Services Foundation release. The editor remains the
default launch surface, and the new service capabilities are exposed through
right-side TUI panels plus a minimal read-only CLI.

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
- Friendly AI configuration error handling when a selected provider is missing
  its user-provided API key.

### Changed

- Project package version is `0.2.0`.
- PyPI-facing README now describes the terminal-first workbench model, current
  panel keybindings, service CLI, and v0.2.0 safety boundaries.
- AI provider selection and API-key storage guidance is documented explicitly:
  provider selection belongs in `config.toml`; API keys belong in
  `~/.config/ecli/.env`.

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
