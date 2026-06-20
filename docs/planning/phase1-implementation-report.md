<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/planning/phase1-implementation-report.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Gate 2 Phase 1 Implementation Report

Date: 2026-05-10

Base state: `main` at `cc30717`.

Phase 1 is complete for workstreams A, B, and C. Workstream D was deferred by
maintainer decision; the Phase 0 FreeBSD package flow remains functional but is
not Gate 2 polished. PR #17 was accepted as a separate hygiene addition to
close long-standing GPL-2.0-only metadata drift before v0.1.0 release operations.

No real PyPI publish, production tag push, or production GitHub Release was
performed during Phase 1 implementation.

## Workstream Summary

| Workstream | PR | Merge commit | Files | Line delta | CI status | Result |
|---|---:|---|---:|---:|---|---|
| A - macOS Universal2 ad-hoc signed DMG | [#14](https://github.com/SSobol77/ecli/pull/14) | `46868b0` | 20 | +903 / -1340 | Passed: PyPI Contract Validate, Windows Contract Validate, macOS Contract Validate, SonarCloud | Complete |
| B - PyPI token publish + CycloneDX SBOM | [#15](https://github.com/SSobol77/ecli/pull/15) | `73b4914` | 6 | +567 / -6 | Passed: CI, PyPI Contract Validate, Windows Contract Validate, macOS Contract Validate, SonarCloud | Complete |
| C - Windows portable EXE + NSIS installer | [#16](https://github.com/SSobol77/ecli/pull/16) | `68ec4b6` | 15 | +754 / -423 | Passed: PyPI Contract Validate, Windows Contract Validate, macOS Contract Validate, SonarCloud | Complete |
| Out-of-band - GPL-2.0-only license normalization | [#17](https://github.com/SSobol77/ecli/pull/17) | `cc30717` | 135 | +1677 / -411 | Passed: CI, PyPI Contract Validate, Windows Contract Validate, macOS Contract Validate, SonarCloud | Complete |

Line deltas and file counts are from merged PR metadata.

## Acceptance Status

### Workstream A - macOS Universal2 DMG

Status: complete.

- [x] Canonical PyInstaller spec retained at `packaging/pyinstaller/ecli.spec`.
- [x] Root-level stale `ecli.spec` path removed from the implementation path.
- [x] `scripts/build_and_package_macos.py` builds a Universal2 artifact by
  combining arm64 and x86_64 legs on `macos-14`.
- [x] DMG output follows canonical naming:
  `ecli_<version>_macos_universal2.dmg`.
- [x] `.sha256` sidecar uses basename-only coreutils-compatible format.
- [x] CI mounts the DMG, locates the binary, checks `lipo -info` for both
  `x86_64` and `arm64`, and runs `codesign --verify --verbose`.
- [x] User-facing macOS install documentation explains first-launch Gatekeeper
  behavior honestly.
- [x] Notarization, hardened runtime, Developer ID signing, and stapling are
  deferred to Phase 2.

### Workstream B - PyPI Tag Publish and SBOM

Status: complete.

- [x] PyPI distribution name is `ecli-editor`; import package and CLI remain
  `ecli`.
- [x] Tag-triggered `release.yml` publishes through
  `pypa/gh-action-pypi-publish` using static `secrets.PYPI_API_TOKEN`.
- [x] PyPI Trusted Publishers / OIDC migration is explicitly deferred to v0.2.
- [x] Release path runs `python3 -m build` and `twine check --strict`.
- [x] CycloneDX SBOM is generated in JSON schema version 1.5 with validation.
- [x] SBOM artifact names are:
  `dist/ecli-editor-<version>.cdx.json` and `.sha256`.
- [x] Historical v0.1.0 SBOM handling recorded. Superseded by Issue #92:
  SBOM files are verification evidence only and are not GitHub Release assets.
- [x] SBOM is not uploaded to PyPI.

### Workstream C - Windows Portable EXE and NSIS Installer

Status: complete.

- [x] `scripts/build-and-package-windows.ps1` is the only Windows packaging
  script remaining under `scripts/`.
- [x] Duplicate `scripts/build_pyinstaller_windows.ps1` was audited, superior
  root/build-dir/strict-output behavior was merged, and the duplicate was
  deleted.
- [x] Portable EXE output:
  `ecli_<version>_win_x86_64.exe`.
- [x] NSIS installer output:
  `ecli_<version>_win_x86_64_setup.exe`.
- [x] Both EXEs receive `.sha256` sidecars in ASCII, LF-terminated,
  basename-only coreutils format.
- [x] `releases/<version>/.win.env` records `WIN_ARCH`, portable filename, and
  installer filename.
- [x] `validate-windows-contract` was extended through
  `package-windows-assert` to validate both Windows artifacts.
- [x] Windows CI proves both EXEs are well-formed without running the curses
  application.
- [x] Windows CI verifies NSIS Programs & Features registration through silent
  install/uninstall and registry assertions.
- [x] User-facing Windows documentation explains SmartScreen warnings and the
  unsigned v0.1.0 status.
- [x] Windows code signing, MSI/WiX, and ARM64 Windows are deferred to Phase 2.

### Workstream D - FreeBSD Polish

Status: deferred.

- [ ] FreeBSD `.pkg` manifest polish is not included in Phase 1.
- [ ] Canonical naming audit for the FreeBSD package internals is deferred.
- [x] Existing Phase 0 FreeBSD packaging remains functional through
  `scripts/build_and_package_freebsd.py` and the release workflow's FreeBSD VM
  job.

### Out-of-Band Scope - License Normalization

Status: complete.

- [x] GPL-2.0-only SPDX headers normalized across project-owned source, script,
  documentation, and config files.
- [x] Project-owned MIT metadata was replaced with GPL-2.0-only.
- [x] Generated/cache/binary artifacts were not given fake headers.
- [x] `.gitignore` was tightened for release outputs, runtime logs, and
  generated AppImage staging content.

## v0.1.0 Release Readiness Checklist

- [x] macOS Universal2 DMG (ad-hoc signed) builds and verifies in CI.
- [x] PyPI publish workflow is tag-triggered using static `PYPI_API_TOKEN`.
- [x] CycloneDX SBOM (schema 1.5) generation recorded. Superseded by Issue #92:
  SBOM files are verification evidence only and are not GitHub Release assets.
- [x] Windows portable EXE + NSIS installer build, both unsigned.
- [x] User documentation (macOS, Windows) explains first-launch warnings
  honestly.
- [x] License headers are GPL-2.0-only across all source files.
- [x] All Phase 0 contracts (naming, sidecars, exit codes) honored.
- [x] No real PyPI publish or production release performed.

## Phase 2 / v0.2 Follow-Up Items

- Apple Developer Program enrollment.
- macOS Developer ID signing, hardened runtime, notarization, and stapling.
- PyPI Trusted Publishers / OIDC migration to remove the static token
  requirement.
- Windows code signing through Azure Trusted Signing or EV certificate.
- MSI/WiX installer alternative.
- ARM64 Windows binary.
- Workstream D: FreeBSD `.pkg` manifest polish and canonical naming audit.
  Current FreeBSD packaging remains functional but is not Gate 2 polished.

## v0.1.0 Maintainer Tag-Push Procedure

Only the maintainer should execute this procedure. It intentionally creates the
first production tag-triggered publish path for v0.1.0.

### Pre-Flight Verification

```sh
git switch main
git fetch --prune --tags origin
git status --short --branch
git log --oneline -5
git tag -l v0.1.0
```

Expected:

- `main` is clean and aligned with `origin/main`.
- `cc30717` or a later approved commit is at the top of `main`.
- `git tag -l v0.1.0` prints nothing.

Run local static checks:

```sh
python3 -m compileall -q src main.py
python3 - <<'PY'
import tomllib
from pathlib import Path

for path in [Path("pyproject.toml"), Path("config.toml")]:
    with path.open("rb") as f:
        tomllib.load(f)
    print(f"OK: {path}")
PY
python3 -m pytest tests/test_smoke.py -v
git diff --check
```

Verify PyPI publish secret presence:

```sh
gh secret list --repo SSobol77/ecli | grep '^PYPI_API_TOKEN'
```

Optional dry-run orientation:

```sh
make -n validate-gate2
gh workflow list
```

Do not run local publish targets. The tag push is the release trigger.

### Tag Creation

```sh
git tag -a v0.1.0 -m "ECLI v0.1.0"
```

### Tag Push

```sh
git push origin v0.1.0
```

### Post-Push Monitoring

The tag push starts `.github/workflows/release.yml` (`Release`). Monitor it:

```sh
gh run list --workflow Release --limit 5
gh run watch <run-id>
```

Expected release workflow jobs:

- `Build Python distributions`
- `Build Linux packages`
- `Build FreeBSD package`
- `Build macOS DMG`
- `Build Windows artifacts`
- `Publish to PyPI`
- `Publish GitHub release`

Expected GitHub Release assets for `v0.1.0`:

- Python: wheel and source distribution.
- SBOM: `ecli-editor-0.1.0.cdx.json` and `.sha256`.
- Linux: `.deb`, `.rpm`, `.tar.gz`, and `.sha256` sidecars.
- FreeBSD: `.pkg` and `.sha256`.
- macOS: `ecli_0.1.0_macos_universal2.dmg` and `.sha256`.
- Windows: `ecli_0.1.0_win_x86_64.exe`,
  `ecli_0.1.0_win_x86_64_setup.exe`, and both `.sha256` sidecars.

Post-publish inspection:

```sh
gh release view v0.1.0 --web
python3 -m pip index versions ecli-editor
```

If `Publish to PyPI` fails after artifacts build successfully, do not re-tag.
Fix the secret or workflow issue and rerun the failed workflow job from GitHub
Actions when the failure mode is safe to retry.

## Residual Risks

- Static `PYPI_API_TOKEN` is sufficient for v0.1.0 but remains a secret
  exposure risk until PyPI Trusted Publishers is enabled.
- macOS ad-hoc signing verifies binary integrity in CI but does not provide
  notarized first-launch trust. Users will still see Gatekeeper friction.
- Windows artifacts are unsigned, so SmartScreen friction is expected.
- FreeBSD remains operational but lacks the deferred manifest polish and
  canonical naming audit.
- `scripts/build_freebsd_port.sh` has a pre-existing Bash parse failure around a
  Python heredoc fallback. It is not the canonical FreeBSD package flow used by
  Phase 1 release CI, but should be repaired in the FreeBSD polish workstream.
