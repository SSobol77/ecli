<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/artifact-contract.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Artifact Contract (Normative)

## Contract Scope

Defines canonical artifact names, locations, and verification expectations for release outputs.

Every active packaging, workflow, script, documentation, or platform descriptor
is a release-contract surface. Empty, stale, decorative, or unused packaging files are forbidden.
A platform/package surface must be represented in:

- product and release documentation;
- Codex and Claude agent contracts;
- build, validation, and release runbooks;
- repository-local validation tests or contract checks.

Release readiness is blocked when an active platform/package surface is missing
from any of those four evidence classes. Stage 1 automation may report and
prepare fixes for this drift, but release execution remains maintainer-owned.

## Canonical Output Location

- All release artifacts must be emitted under `releases/<version>/`.

## Canonical 21-Item Platform & Packaging Artifact Matrix

This is the normative, complete list of active ECLI release-contract artifacts.
It contains exactly 21 entries. Coverage in tests under `tests/packaging/`,
Claude commands under `.claude/commands/`, Codex prompts under `.codex/prompts/`,
and GitHub workflows under `.github/workflows/` must never be smaller than this
matrix. If an artifact exists here but lacks a test, a Claude command mapping, a
Codex prompt mapping, or (where relevant) a workflow mapping, release readiness
is blocked. Do not add a packaging file, workflow, script, or platform descriptor
unless it is wired into this matrix, agent contracts, build/release runbooks, and
validation tests. Do not invent unsupported package types.

| # | Package / artifact | Platform / system | Repository source files | Expected artifact / output | Related GitHub workflow | Required test file | Required Claude command coverage | Required Codex prompt coverage | Release-readiness condition |
|---|---|---|---|---|---|---|---|---|---|
| 1 | PyPI wheel | PyPI / Python | `pyproject.toml`; `scripts/publish_pypi.py` | `ecli_editor-<version>-py3-none-any.whl` | `.github/workflows/pypi-validate.yml` | `tests/packaging/test_packaging_pypi_wheel_contract.py` | `.claude/commands/package-pypi.md` | `.codex/prompts/package-pypi.md` | Wheel builds, `twine check --strict` passes, checksum sidecar present |
| 2 | PyPI source distribution | PyPI / Python | `pyproject.toml`; `scripts/publish_pypi.py` | `ecli_editor-<version>.tar.gz` | `.github/workflows/pypi-validate.yml` | `tests/packaging/test_packaging_pypi_sdist_contract.py` | `.claude/commands/package-pypi.md` | `.codex/prompts/package-pypi.md` | Sdist builds, `twine check --strict` passes, checksum sidecar present |
| 3 | Linux generic PyInstaller executable | Linux | `packaging/pyinstaller/ecli.spec`; `packaging/pyinstaller/rthooks/force_imports.py`; `scripts/build_pyinstaller_linux.py`; root `main.py` compatibility shim | `dist/ecli` PyInstaller binary | `.github/workflows/release.yml` | `tests/packaging/test_packaging_linux_pyinstaller_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | Runtime import check passes; spec uses root `main.py`; binary smoke-runs |
| 4 | Linux release tarball | Linux | `scripts/build_pyinstaller_linux.py`; `scripts/verify_runtime.py`; `Makefile` targets `package-tar-linux`, `validate-tar-linux-contract` | `ecli_<version>_linux_<arch>.tar.gz` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_linux_tarball_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | Tarball artifact and SHA256 sidecar validated; runtime smoke check passes |
| 5 | Debian / Ubuntu `.deb` | Linux (Debian/Ubuntu) | `scripts/build_and_package_deb.py`; `docker/build-linux-deb.Dockerfile`; `Makefile` target `package-deb` | `ecli_<version>_linux_<arch>.deb` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_deb_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | DEB artifact naming and SHA256 checks pass; package metadata inspected when toolchain present |
| 6 | generic RPM `.rpm` | Linux (RPM family) | `scripts/build_and_package_rpm.py`; `docker/build-linux-rpm.Dockerfile`; `Makefile` target `package-rpm` | `ecli_<version>_linux_<arch>.rpm` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_rpm_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | RPM artifact naming and SHA256 checks pass; FPM/RPM metadata inspected when toolchain present |
| 7 | openSUSE / SUSE RPM | Linux (openSUSE/SUSE) | `scripts/build_and_package_opensuse_rpm.py`; shared RPM flow | `ecli_<version>_opensuse_<arch>.rpm` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_opensuse_rpm_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | openSUSE/SUSE artifact naming and SHA256 checks pass through the shared RPM contract |
| 8 | Arch Linux `PKGBUILD` | Linux (Arch) | `packaging/arch/PKGBUILD` (never root `PKGBUILD`); `scripts/build_and_package_arch.py` | `ecli_<version>_arch_<arch>.pkg.tar.zst` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_arch_pkgbuild_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | Raw `makepkg` output normalized; SHA256 sidecar present; no active root `PKGBUILD` alias |
| 9 | Slackware `.txz` | Linux (Slackware) | `scripts/build_and_package_slackware.py`; Linux PyInstaller helper | `ecli_<version>_slackware_<arch>.txz` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_slackware_txz_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | Slackware `.txz` artifact naming and SHA256 checks pass |
| 10 | AppImage | Linux (cross-distro) | `packaging/linux/appimage/appimage-builder.yml`; `scripts/package_appimage.py`; `Makefile` target `package-appimage` | `ecli_<version>_linux_<arch>.AppImage` | `.github/workflows/release.yml` | `tests/packaging/test_packaging_appimage_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | AppImage artifact naming and SHA256 checks pass; descriptor mutation is AUD-003 drift |
| 11 | FreeBSD `.pkg` | FreeBSD | `scripts/build_and_package_freebsd.py`; `scripts/build_freebsd_pkg.py`; `.github/workflows/freebsd-pkg.yml` | `ecli_<version>_freebsd_<arch>.pkg` | `.github/workflows/freebsd-pkg.yml` | `tests/packaging/test_packaging_freebsd_pkg_contract.py` | `.claude/commands/package-freebsd.md` | `.codex/prompts/package-freebsd.md` | Native/VM `.pkg` naming and SHA256 checks pass; vmactions log and checksum evidence captured |
| 12 | FreeBSD ports/chroot build path | FreeBSD | `scripts/build_freebsd_port.py`; `tools/freebsd-chroot-build.sh`; `Makefile` targets `package-freebsd-port`, `package-freebsd-chroot` | Native `.pkg` from local `package-freebsd-port` / `package-freebsd-chroot` paths | `.github/workflows/freebsd-pkg.yml` | `tests/packaging/test_packaging_freebsd_ports_chroot_contract.py` | `.claude/commands/package-freebsd.md` | `.codex/prompts/package-freebsd.md` | Local port and chroot paths produce a normalized `.pkg`; not source-history payload by default |
| 13 | macOS `.app` | macOS | `scripts/build_and_package_macos.py`; `packaging/pyinstaller/ecli.spec`; root `main.py` compatibility shim | `ECLI.app` bundle | `.github/workflows/macos-dmg.yml` | `tests/packaging/test_packaging_macos_app_contract.py` | `.claude/commands/package-macos.md` | `.codex/prompts/package-macos.md` | `.app` bundle built from shared PyInstaller spec using root `main.py`; Universal2 layout |
| 14 | macOS `.dmg` | macOS | `scripts/build_and_package_macos.py`; `.github/workflows/macos-dmg.yml`; `.github/workflows/macos-validate.yml`; `docs/install/macos.md` | `ecli_<version>_macos_universal2.dmg` | `.github/workflows/macos-dmg.yml` | `tests/packaging/test_packaging_macos_dmg_contract.py` | `.claude/commands/package-macos.md` | `.codex/prompts/package-macos.md` | macOS Contract Validate passes; DMG artifact and SHA256 structural validation |
| 15 | Windows portable `.exe` | Windows | `scripts/build-and-package-windows.ps1`; `packaging/pyinstaller/ecli.spec`; root `main.py` compatibility shim | `ecli_<version>_win_<arch>.exe` | `.github/workflows/windows-installer.yml` | `tests/packaging/test_packaging_windows_portable_exe_contract.py` | `.claude/commands/package-windows.md` | `.codex/prompts/package-windows.md` | Portable EXE help/version smoke passes; checksum sidecar present |
| 16 | Windows NSIS installer `.exe` | Windows | `packaging/windows/nsis/ecli.nsi`; `scripts/build-and-package-windows.ps1`; `.github/workflows/windows-installer.yml`; `.github/workflows/windows-validate.yml`; `docs/install/windows.md` | `ecli_<version>_win_<arch>_setup.exe` | `.github/workflows/windows-installer.yml` | `tests/packaging/test_packaging_windows_nsis_installer_contract.py` | `.claude/commands/package-windows.md` | `.codex/prompts/package-windows.md` | Windows Contract Validate passes; NSIS installer and checksum validation |
| 17 | Nix flake | Nix / NixOS | `flake.nix` | `nix run .` app / `nix build .` package | _local build path; no release workflow_ | `tests/packaging/test_packaging_nix_flake_contract.py` | `.claude/commands/package-nix.md` | `.codex/prompts/package-nix.md` | Flake exposes default package/app for declared systems; version drift reported against `pyproject.toml` |
| 18 | Nix/NixOS package expression | Nix / NixOS | `packaging/nix/package.nix` | `result/bin/ecli` derivation output | _local build path; no release workflow_ | `tests/packaging/test_packaging_nixos_package_contract.py` | `.claude/commands/package-nix.md` | `.codex/prompts/package-nix.md` | Package expression builds `ecli` with `mainProgram`; hard-coded version/license drift (e.g. `asl20`) reported against `pyproject.toml` |
| 19 | Docker DEB build helper | Linux build helper | `docker/build-linux-deb.Dockerfile`; `Makefile` targets `package-deb-docker`, `package-docker` | Containerized `.deb` build helper image (not itself a release artifact) | _build helper; no release workflow_ | `tests/packaging/test_packaging_docker_deb_helper_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | Helper builds the DEB inside a container and must not publish or upload artifacts |
| 20 | Docker RPM build helper | Linux build helper | `docker/build-linux-rpm.Dockerfile`; `Makefile` targets `package-rpm-docker`, `package-docker` | Containerized `.rpm` build helper image (not itself a release artifact) | _build helper; no release workflow_ | `tests/packaging/test_packaging_docker_rpm_helper_contract.py` | `.claude/commands/package-linux.md` | `.codex/prompts/package-linux.md` | Helper builds the RPM inside a container and must not publish or upload artifacts |
| 21 | GitHub Actions release/workflow contract map | CI / release automation | `.github/workflows/release.yml`; `.github/workflows/ci.yml`; the GitHub Actions Workflow Contract Map below | Aggregate release artifact matrix orchestration | `.github/workflows/release.yml` | `tests/packaging/test_packaging_workflows_contract.py` | `.claude/commands/release.md` | `.codex/prompts/release.md` | Every workflow on disk is documented and mapped; aggregate release matrix gated by `validate-gate2` |

## Platform & Packaging Release Contract Matrix

This matrix is normative for active ECLI release-contract surfaces and is the
summary view of the canonical 21-item matrix above. Do not add a
packaging file, workflow, script, or platform descriptor unless it is wired into
this matrix, agent contracts, build/release runbooks, and validation tests.

| Surface | Artifacts / package form | Contract files and active paths | Validation / contract evidence |
|---|---|---|---|
| PyPI | wheel `.whl`; source distribution `.tar.gz` | `pyproject.toml`; `scripts/publish_pypi.py`; `.github/workflows/pypi-validate.yml`; `Makefile` targets `package-pypi`, `validate-pypi-contract` | PyPI contract workflow; wheel/sdist checksum checks; `twine check --strict`; `pyproject.toml` is the version source of truth |
| Linux generic | PyInstaller executable; release `.tar.gz` | `packaging/pyinstaller/ecli.spec`; root `main.py` compatibility shim; `scripts/build_pyinstaller_linux.py`; `Makefile` targets `package-tar-linux`, `validate-tar-linux-contract` | Runtime import check; PyInstaller spec entry check; tarball artifact and SHA256 sidecar validation |
| Debian / Ubuntu | `.deb` | `scripts/build_and_package_deb.py`; `build/deb_staging/`; Docker helper `docker/build-linux-deb.Dockerfile`; `Makefile` target `package-deb` | Debian artifact naming and SHA256 checks; package-manager metadata inspection when toolchain is present |
| RPM generic | `.rpm` | `scripts/build_and_package_rpm.py`; Docker helper `docker/build-linux-rpm.Dockerfile`; `Makefile` target `package-rpm` | RPM artifact naming and SHA256 checks; FPM/RPM metadata inspection when toolchain is present |
| openSUSE / SUSE | RPM package path | `scripts/build_and_package_opensuse_rpm.py`; shared RPM flow; `Makefile` RPM contract target with `opensuse` platform label | openSUSE/SUSE artifact naming and SHA256 checks through the shared RPM package contract |
| Arch | `PKGBUILD`; normalized `.pkg.tar.zst` | root `PKGBUILD` if restored; `packaging/arch/PKGBUILD`; `scripts/build_and_package_arch.py` | Raw `makepkg` output must be normalized to `ecli_<version>_arch_<arch>.pkg.tar.zst` with SHA256 sidecar; a missing active root `PKGBUILD` alias is release-contract drift |
| Slackware | `.txz` | `scripts/build_and_package_slackware.py`; Linux PyInstaller helper | Slackware `.txz` artifact naming and SHA256 checks |
| AppImage | `.AppImage` | `packaging/linux/appimage/appimage-builder.yml`; `scripts/package_appimage.py`; `Makefile` target `package-appimage` | AppImage artifact naming and SHA256 checks; tracked descriptor mutation is AUD-003 drift until removed |
| FreeBSD | `.pkg`; local port/chroot path | `scripts/build_and_package_freebsd.py`; `scripts/build_freebsd_pkg.py`; `scripts/build_freebsd_port.py`; `tools/freebsd-chroot-build.sh`; `.github/workflows/freebsd-pkg.yml` | Native/VM/chroot `.pkg` naming and SHA256 checks; vmactions workflow log and checksum evidence |
| macOS | `.app`; `.dmg`; universal2 / x86_64 / arm64 packaging path | `scripts/build_and_package_macos.py`; `.github/workflows/macos-dmg.yml`; `.github/workflows/macos-validate.yml`; `docs/install/macos.md`; `packaging/pyinstaller/ecli.spec`; root `main.py` compatibility shim | macOS Contract Validate; Universal2 binary creation; DMG artifact and SHA256 structural validation |
| Windows | portable `.exe`; NSIS installer `.exe` | `scripts/build-and-package-windows.ps1`; `packaging/windows/nsis/ecli.nsi`; `.github/workflows/windows-installer.yml`; `.github/workflows/windows-validate.yml`; `docs/install/windows.md`; `packaging/pyinstaller/ecli.spec`; root `main.py` compatibility shim | Windows Contract Validate; portable help/version smoke; NSIS installer and checksum validation |
| Nix / NixOS | flake app/package; Nix derivation | `flake.nix`; `packaging/nix/package.nix`; Codex/Claude Nix package prompts | Nix package inspection contract; hard-coded version/license drift must be reported against `pyproject.toml` |
| Docker build helpers | containerized Linux `.deb` and `.rpm` helper images | `docker/build-linux-deb.Dockerfile`; `docker/build-linux-rpm.Dockerfile`; `Makefile` targets `package-deb-docker`, `package-rpm-docker`, `package-docker` | Docker helper paths remain build helpers for Linux package contracts and must not publish or upload artifacts |

## GitHub Actions Workflow Contract Map

Every workflow under `.github/workflows/` is a CI/release contract surface and
must be listed here. Adding a workflow without documenting its role is
release-contract drift. Packaging workflows must map back to a package surface,
agent contract, release documentation, and repository-local packaging test.

| Workflow | Classification | Contract role |
|---|---|---|
| `.github/workflows/ci.yml` | Global quality gate | Runs the global CI quality gate and `validate-gate2`; keeps root `main.py` compatibility in the CI path filters. |
| `.github/workflows/freebsd-pkg.yml` | Packaging workflow | FreeBSD `.pkg` package path covering native package, port, chroot, checksum, artifact upload, and out-of-band attach mechanics. |
| `.github/workflows/macos-dmg.yml` | Packaging workflow | macOS `.app` / `.dmg` package path using the shared PyInstaller spec and DMG artifact contract. |
| `.github/workflows/macos-validate.yml` | Packaging validation workflow | macOS package validation for the `.app` / `.dmg` contract. |
| `.github/workflows/project-automation.yml` | Repository automation, non-packaging | Moves issues and pull requests between project columns. It is not a release artifact workflow and must not be counted as package coverage. |
| `.github/workflows/pypi-validate.yml` | Packaging validation workflow | PyPI wheel and source distribution validation for `ecli-editor`. |
| `.github/workflows/release.yml` | Aggregate release workflow | Builds and publishes the aggregate release artifact matrix after maintainer-controlled release triggers. |
| `.github/workflows/windows-installer.yml` | Packaging workflow | Windows portable EXE and NSIS installer package path. |
| `.github/workflows/windows-validate.yml` | Packaging validation workflow | Windows package validation for portable EXE and NSIS installer contracts. |

## Canonical Naming Rules

Final GitHub Release artifact names must use this normalized ECLI schema:

`ecli_<version>_<platform>_<arch>.<extension>`

Short form: `ecli_<v>_<platform>_<arch>.<extension>`

Windows installer artifacts use this installer-specific extension of the same schema:

`ecli_<version>_win_<arch>_setup.exe`

Short form: `ecli_<v>_win_<arch>_setup.exe`

Allowed `<platform>` tokens:

- `linux`
- `opensuse`
- `arch`
- `slackware`
- `freebsd`
- `macos`
- `win`

Allowed `<arch>` tokens:

- `x86_64`
- `arm64`
- `universal2` (macOS DMG only)

Current artifact forms:

- DEB: `ecli_<version>_linux_<arch>.deb`
- Generic RPM: `ecli_<version>_linux_<arch>.rpm`
- openSUSE/SUSE RPM: `ecli_<version>_opensuse_<arch>.rpm`
- Arch Linux package: `ecli_<version>_arch_<arch>.pkg.tar.zst`
- Slackware package: `ecli_<version>_slackware_<arch>.txz`
- AppImage: `ecli_<version>_linux_<arch>.AppImage`
- Linux tarball: `ecli_<version>_linux_<arch>.tar.gz`
- Snap: `ecli_<version>_linux_<arch>.snap`
- FreeBSD: `ecli_<version>_freebsd_<arch>.pkg`
- Windows portable EXE: `ecli_<version>_win_<arch>.exe`
- Windows NSIS installer EXE: `ecli_<version>_win_<arch>_setup.exe`
- macOS: `ecli_<version>_macos_universal2.dmg`

The DEB internal `Architecture` field remains package-manager native
(`amd64` on x86_64). Only the final release filename uses the canonical architecture token.

Current normalized Linux x86_64 package names:

- `ecli_<version>_linux_x86_64.deb`
- `ecli_<version>_linux_x86_64.rpm`
- `ecli_<version>_opensuse_x86_64.rpm`
- `ecli_<version>_arch_x86_64.pkg.tar.zst`
- `ecli_<version>_slackware_x86_64.txz`
- `ecli_<version>_linux_x86_64.AppImage`

Arch Linux packaging has two valid filename domains. `PKGBUILD` and raw `makepkg` output may use the native Arch filename
`ecli-editor-<version>-1-<arch>.pkg.tar.zst`.

The ECLI release script must normalize that package to `ecli_<version>_arch_<arch>.pkg.tar.zst` before it is
published as a GitHub Release artifact.

Slackware packages use the traditional `.txz` format. The ECLI GitHub Release artifact must be named `ecli_<version>_slackware_<arch>.txz`.

For each artifact, a checksum file must exist:

- `<artifact>.sha256`

Checksum sidecars use coreutils-compatible format:

```text
<64 lowercase hex characters>  <artifact basename>
```

The artifact basename must not include a directory component.

## SBOM Artifacts

Release builds emit a CycloneDX SBOM alongside the Python distribution artifacts. SBOM filenames follow the PyPI distribution naming convention (hyphens, no platform/arch tokens) because they describe the Python distribution, not a native platform package:

- `releases/<version>/ecli-editor-<version>.cdx.json`
- `releases/<version>/ecli-editor-<version>.cdx.json.sha256`

This is intentional inconsistency with native release artifacts (which use `ecli_<v>_<platform>_<arch>.<ext>` underscore convention). SBOMs apply to the Python wheel and sdist, both of which use PEP 427 / PEP 625 hyphen naming. The SBOM tracks the same convention.

The SBOM and its SHA256 sidecar are attached to the GitHub Release
alongside the wheel and sdist. They are NOT uploaded to PyPI (PyPI does not accept arbitrary attachments).

Format requirements:

- CycloneDX schema version 1.5.

- JSON encoding (not XML).

- Generated by `python3 -m cyclonedx_py environment --validate`
  (failure on malformed output blocks the release).

- SHA256 sidecar in coreutils format: `<hex>  <basename>` (LF-terminated).

See `docs/release/release-process.md` "SBOM" section for generation
procedure.

## Forbidden Variants

- Mixed hyphen/underscore variants for final released names are forbidden.

- Artifacts outside `releases/<version>/` are non-contract outputs.

## Build Entrypoints

Canonical script entrypoints are those referenced by `Makefile` and active workflows under `.github/workflows/`.

Current-state note:

- `packaging/pyinstaller/ecli.spec` is the single source of truth for
  PyInstaller builds across all platforms.

- deterministic release parity depends on keeping the canonical PyInstaller spec, Makefile targets, workflows, and packaging scripts aligned on the canonical output names.

## Non-Contract and Legacy Helpers

These packaging-adjacent scripts exist in the tree but are not active members of
the canonical 21-item matrix. They are documented here so that no packaging
script is undocumented:

- `scripts/build_docker.py` — legacy
  single-image DEB helper. It is superseded by the canonical Docker DEB/RPM build
  helpers (`docker/build-linux-deb.Dockerfile`, `docker/build-linux-rpm.Dockerfile`)
  and the `make package-docker` target. It still references
  `docker/build-linux.Dockerfile`, which no longer exists, so it is reported drift
  and is slated for cleanup. It must not be wired into release automation.

## Shell-to-Python Script Migration

ECLI has completed the migration of active packaging/build/verification scripts
under `scripts/` from shell to Python. The migration must never change the
release contract: artifact names, locations, checksum format, and the documented
exit-code contracts are preserved.

Migration rules (normative):

- Each migrated script has a canonical Python implementation using only the
  standard library, explicit `argparse`, `pathlib.Path`, and (where it shells
  out) `subprocess.run(..., check=True)` with explicit command arrays.
- Active shell wrappers under `scripts/` are removed. Business logic must not be
  reintroduced in shell under `scripts/`.
- Exit-code semantics, artifact naming, and contract-relevant environment
  variables are preserved.
- A migrated script must never publish, upload, sign with external keys, tag,
  push, or trigger workflows.
- Migration status is enforced by
  `tests/packaging/test_scripts_python_migration_contract.py`.

Migration status: **complete**. The Python module is the only canonical
implementation for migrated active scripts under `scripts/`; no active shell
wrapper remains there. The `Makefile`, GitHub Actions workflows, and `.cirrus.yml`
call the Python entrypoints directly. Release readiness is blocked if any active
shell wrapper is reintroduced under `scripts/`; the migration is enforced by
`tests/packaging/test_scripts_python_migration_contract.py`.

`scripts/build-and-package-windows.ps1` is a separate Windows-native packaging
surface (PowerShell), not part of the shell-to-Python migration. The external
`tools/freebsd-chroot-build.sh` chroot helper is out of scope for this batch and
tracked as a future dedicated tools migration follow-up.
`.claude/hooks/block-mutations.sh` is a Claude hook, not a packaging/build script.
The unused tracked helper the removed FreeBSD package-renaming shell helper was removed during the
no-shell cleanup; FreeBSD package naming is covered by the canonical Python
scripts and release contract tests.

| Canonical Python implementation | Notes |
|---|---|
| `scripts/sign_checksums.py` | Writes coreutils basename-only `<artifact>.sha256` sidecars (SHA256 only; not GPG signing) |
| `scripts/check_log_invariant.py` | Read-only `git ls-files` log-location invariant |
| `scripts/verify_artifact.py` | Structural SHA256 sidecar verifier; exit-code contract `0`-`5` preserved |
| `scripts/verify_runtime.py` | Cross-artifact launcher validation; exit codes (`0`/`2`/`3`/`4`/`5`/`6`) preserved |
| `scripts/build_pyinstaller_linux.py` | Linux PyInstaller build; prefers `packaging/pyinstaller/ecli.spec` |
| `scripts/build_and_package_deb.py` | `ecli_<version>_linux_<arch>.deb` via FPM; dependency set preserved |
| `scripts/build_and_package_rpm.py` | `ecli_<version>_<platform>_<arch>.rpm`; `RPM_PLATFORM_LABEL`/`RPM_DEPENDS` env preserved |
| `scripts/build_and_package_opensuse_rpm.py` | Delegates to the shared RPM flow with the openSUSE label/deps |
| `scripts/build_and_package_arch.py` | `ecli_<version>_arch_<arch>.pkg.tar.zst` via `makepkg` (exit `5` on missing tool) |
| `scripts/build_and_package_slackware.py` | `ecli_<version>_slackware_<arch>.txz` via `makepkg` (exit `5` on missing tool) |
| `scripts/package_appimage.py` | `ecli_<version>_linux_<arch>.AppImage` via `appimage-builder` |
| `scripts/build_and_package_macos.py` | `ecli_<version>_macos_universal2.dmg`; ad-hoc codesign only |
| `scripts/build_and_package_freebsd.py` | Native/VM `ecli_<version>_freebsd_<arch>.pkg` via `pkg create` |
| `scripts/build_freebsd_pkg.py` | Local FreeBSD `.pkg` (root; UCL/YAML manifests) |
| `scripts/build_freebsd_port.py` | Local FreeBSD ports skeleton -> normalized `.pkg` |
| `scripts/build_docker.py` | Legacy single-image DEB helper (documented drift; not wired into release automation) |
| `scripts/publish_pypi.py` | Maintainer-owned publish guard; never uploads; supports `--dry-run` |

## Naming Migration Notes

Gate 2 Phase 0 replaces legacy platform-specific filename conventions with one cross-platform schema.

The removed legacy forms include:

- `ecli_<version>_amd64.deb`
- `ecli_<version>_amd64.rpm`
- `ecli_<version>_amd64.pkg`
- `ecli_<version>_linux_x86_64.AppImage`
- `ecli_<version>_Linux_x86_64.tar.gz`
- `ecli_<version>_win_x64.exe`

The migration makes artifact discovery deterministic for CI and release automation while preserving package-manager metadata inside each artifact.

## CI Validation Requirements

- release workflow must validate expected artifact names and checksums before publish.

- missing contract artifact must fail the pipeline.

- macOS DMG package builds must perform one native mounted-DMG runtime smoke
  during `scripts/build_and_package_macos.py`. Follow-up assertions in the same
  build job may use structural/checksum-only validation to avoid redundant
  immediate `hdiutil attach` calls against the same image.
