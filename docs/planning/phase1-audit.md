<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/planning/phase1-audit.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Gate 2 Phase 1 Readiness Audit

Date: 2026-05-09

Branch: `docs/phase1-audit`

Scope:

- Workstream A: macOS Phase 1, issue #5.
- Workstream B: PyPI Phase 1, issue #6.
- Workstream C: Windows Phase 1, issue #7.
- Coordination remains issue #8.

No Phase 1 implementation was started.

## Summary

Phase 0 artifact-contract work is present: platform validation targets exist,
checksum sidecars use basename-only SHA256 format, PyPI namespace
`ecli-editor` is reserved, and direct checksum verification is now available via
`scripts/verify-artifact.sh` for CI consumers that need granular exit codes.

Phase 1 is not implementation-ready until maintainer decisions are made for
paid/external services and signing credentials: Apple Developer Program,
notarization secrets, PyPI Trusted Publishers, and Windows code-signing path.

## Workstream A: macOS Phase 1 (#5)

### Existing Repo State

- `make package-macos` calls `scripts/build-and-package-macos.sh`.
- `scripts/build-and-package-macos.sh` builds a PyInstaller app bundle, creates a
  DMG with `hdiutil`, writes `releases/<version>/.macos.env`, and emits
  `ecli_<version>_macos_<arch>.dmg` plus `.sha256`.
- `.github/workflows/macos-dmg.yml` builds a DMG on `macos-13` and uploads it as
  a workflow artifact.
- `.github/workflows/macos-validate.yml` runs the dry-run contract validation on
  `macos-14`.
- `make validate-macos-contract` validates the built DMG and SHA256 sidecar.

### Gaps Versus Phase 1 Acceptance

- Universal2 is not implemented. The current script derives `MAC_ARCH` from
  `uname -m` and produces one host-architecture DMG, not a single x86_64+arm64
  binary.
- The script explicitly states that it does not sign or notarize. There is no
  hardened-runtime `codesign` step, Developer ID certificate import, entitlement
  file, `notarytool submit`, notarization polling, or `stapler staple`.
- There is no verification evidence for execution on both Intel and Apple
  Silicon macOS. CI currently builds on one runner architecture at a time.
- DMG distribution readiness is incomplete: no stapling verification, no
  `spctl`/Gatekeeper assessment, and no quarantine-path smoke test.
- Secret injection for Apple credentials is undefined.

### Maintainer Decisions Still Required

- Whether the maintainer has Apple Developer Program membership.
- If notarization is available, how Apple ID credentials, Team ID, app-specific
  password, and the Developer ID certificate/private key are injected.
- Whether Phase 1 should halt macOS at an ad-hoc signed DMG if notarization
  credentials are unavailable.

## Workstream B: PyPI Phase 1 (#6)

### Existing Repo State

- `pyproject.toml` distribution name is `ecli-editor`; import package and console
  script remain `ecli`.
- `make package-pypi` builds wheel and sdist using `python3 -m build`, validates
  metadata with `twine check --strict`, and emits SHA256 sidecars.
- `.github/workflows/pypi-validate.yml` performs dry-run package validation and
  verifies PyPI namespace ownership.
- `.github/workflows/release.yml` is tag-triggered and contains a `publish-pypi`
  job using `pypa/gh-action-pypi-publish` with `id-token: write`; the job now
  verifies that the reserved namespace is `ecli-editor` before publishing.
- `docs/release/release-process.md` documents namespace pre-reservation and the
  current static-token-to-OIDC migration direction.
- `scripts/publish_pypi.sh` is a placeholder and is not a usable publish path.

### Gaps Versus Phase 1 Acceptance

- Trusted Publishers configuration in the PyPI project settings cannot be
  verified from the repository. The current release job assumes OIDC publishing,
  but PyPI-side trust binding must be configured by the maintainer.
- `.github/workflows/release.yml` currently binds `publish-pypi` to GitHub
  environment `pypi`. The Phase 1 decision text says the PyPI Trusted Publisher
  environment should be left empty per Phase 0 Q4; this must be reconciled before
  tag publishing is treated as production-ready.
- The release workflow build step uses `python -m build`; issue #6 proposed
  `uv build`. The project needs one authoritative build command for release CI.
- The release workflow does not run `twine check --strict` in `build-python`.
  Validation exists in `make package-pypi` and `pypi-validate.yml`, but the
  tag-triggered release path should carry its own pre-publish metadata gate.
- SBOM emission is not implemented. There is no CycloneDX generation,
  artifact naming convention, checksum sidecar, or upload step for SBOM output.
- User-facing install language must use `pip install ecli-editor`, not
  `pip install ecli`, because Q5 chose the PyPI distribution name
  `ecli-editor`.

### Maintainer Decisions Still Required

- Whether PyPI Trusted Publishers is already configured for
  `SSobol77/ecli` and the selected workflow filename.
- Whether to keep the current OIDC publish path, temporarily use a scoped
  `PYPI_API_TOKEN`, or block tag publishing until Trusted Publishers is
  configured.
- Whether to standardize Phase 1 release builds on `uv build` or the current
  `python3 -m build` path.
- SBOM policy: CycloneDX format variant, package scope, and whether SBOMs are
  attached only to GitHub Releases or also published as PyPI attestations later.

## Workstream C: Windows Phase 1 (#7)

### Existing Repo State

- `make package-windows` calls `pwsh -File ./scripts/build-and-package-windows.ps1`.
- `scripts/build-and-package-windows.ps1` builds with PyInstaller and invokes
  NSIS, emitting `ecli_<version>_win_x86_64.exe` plus `.sha256`.
- `scripts/build_pyinstaller_windows.ps1` is a second Windows packager with
  richer comments and `uv sync --frozen`; current Makefile wiring does not call
  it.
- `packaging/windows/nsis/ecli.nsi` installs to Program Files, writes uninstall
  registry keys under `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`,
  creates a Start Menu shortcut, writes an uninstaller, and removes those entries
  on uninstall.
- `.github/workflows/windows-installer.yml` and
  `.github/workflows/windows-validate.yml` install NSIS and run the Windows build
  or validation path on `windows-latest`.
- `make validate-windows-contract` validates the current Windows artifact and
  checksum sidecar.

### Gaps Versus Phase 1 Acceptance

- Portable EXE and installer outputs are not separated. The current strict
  artifact name is a single `.exe`, and the Phase 1 contract needs both a
  PyInstaller `--onefile` portable EXE and an NSIS installer artifact.
- The original issue mentions MSI, while Phase 1 scope prefers NSIS. MSI/WiX must
  be explicitly deferred or added as a separate flow.
- Code signing is not implemented. There is no Authenticode `signtool` step,
  Azure Trusted Signing integration, EV certificate path, timestamp server, or
  verification with `Get-AuthenticodeSignature`.
- NSIS registration exists, but Phase 1 still needs install/uninstall validation
  on Windows 10 and Windows 11 runners or test hosts, including Programs &
  Features registration evidence.
- The two Windows packaging scripts overlap. Phase 1 should choose one canonical
  script before adding signing and dual-artifact semantics.
- ARM64 Windows support remains optional and is not implemented.

### Maintainer Decisions Still Required

- Whether Windows Phase 1 is unsigned by default or requires Azure Trusted
  Signing / EV certificate integration.
- Whether NSIS-only is authoritative for Phase 1, or MSI/WiX must be added.
- Which Windows packaging script is canonical:
  `scripts/build-and-package-windows.ps1` or
  `scripts/build_pyinstaller_windows.ps1`.

## Coordination Notes (#8)

- Issue #8 should remain open for Phase 1 sequencing and cross-workstream
  status.
- The workstreams are externally coupled by credentials and release semantics:
  notarization, PyPI OIDC, Windows signing, SBOM naming, and GitHub Release asset
  policy should be decided before code changes begin.
- No real PyPI publish or GitHub Release creation should occur during Phase 1
  implementation validation. Use workflow dry-runs, draft releases, or local
  artifact checks until maintainer approval.

## Maintainer Decisions Required

Q-P1-A1. Does the maintainer hold an Apple Developer Program membership
(US$99/yr)? Required for notarization. If NO, Workstream A halts at
"ad-hoc signed DMG" and notarization is deferred to Phase 2.

Q-P1-A2. If YES on A1, what is the preferred secret-injection path for
`APPLE_ID`, `APPLE_TEAM_ID`, `APP_SPECIFIC_PASSWORD`, and the .p12 signing
certificate?

- GitHub Actions secrets (simple, recommended)
- 1Password Connect / external secret manager
- GitHub Environments (declined per Q4 of Phase 0)

Q-P1-B1. Has the maintainer configured Trusted Publishers under
pypi.org/manage/project/ecli-editor/settings/publishing/ with:

```text
owner       = SSobol77
repository  = ecli
workflow    = <workflow-filename>.yml
environment = (leave empty per Q4 of Phase 0)
```

If NO: Workstream B halts on the OIDC migration step but can proceed with
static-token publish in the meantime.

Q-P1-C1. Code signing for Windows EXE — choose path:

- (a) Unsigned (Phase 1 default; SmartScreen warns).
- (b) Azure Trusted Signing (newer, low cost, requires Azure subscription).
- (c) EV cert from CA (high cost, immediate SmartScreen trust).

If (b) or (c), provide credential injection path.

Q-P1-C2. MSI installer scope — confirm:

- (a) NSIS-only for Phase 1 (recommended).
- (b) NSIS + WiX MSI dual-flow (defers Phase 1 by approximately 2 weeks).

## Stop Gate

Stop here. Do not begin Phase 1 implementation until the maintainer decisions
above are answered.
