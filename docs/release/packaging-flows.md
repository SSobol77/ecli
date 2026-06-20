<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/packaging-flows.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Packaging Flows

The active platform/package set is contract-bound by
`docs/release/artifact-contract.md` under the `Canonical 21-Item Platform &
Packaging Artifact Matrix` (summarized by the `Platform & Packaging Release
Contract Matrix`). That canonical matrix defines exactly 21 physical GitHub
Release assets. Every official ECLI release publishes exactly those 21 assets,
one per canonical matrix entry; release publication is blocked unless
`scripts/verify_release_assets.py` verifies the exact set under
`releases/<version>/`. Release readiness is blocked if any active packaging
surface is absent from docs, agent contracts, build/release runbooks, or
validation tests under `tests/packaging/`. Empty, stale, decorative, or unused
packaging files are forbidden.

Checksum sidecars are mandatory verification evidence under
`releases/<version>/.checksums/` or workflow validation artifacts, not GitHub
Release assets.

## Mandatory GitHub Release Assets

```text
ecli_editor-<version>-py3-none-any.whl
ecli_editor-<version>.tar.gz
ecli_<version>_linux_x86_64.bin
ecli_<version>_linux_x86_64.tar.gz
ecli_<version>_linux_x86_64.deb
ecli_<version>_linux_x86_64.rpm
ecli_<version>_opensuse_x86_64.rpm
ecli_<version>_arch_x86_64.pkg.tar.zst
ecli_<version>_slackware_x86_64.txz
ecli_<version>_linux_x86_64.AppImage
ecli_<version>_freebsd_x86_64.pkg
ecli_<version>_freebsd_ports_chroot_evidence.tar.gz
ecli_<version>_macos_universal2_app_evidence.tar.gz
ecli_<version>_macos_universal2.dmg
ecli_<version>_win_x86_64.exe
ecli_<version>_win_x86_64_setup.exe
ecli_<version>_nix_flake_evidence.tar.gz
ecli_<version>_nixos_package_evidence.tar.gz
ecli_<version>_docker_deb_helper_evidence.tar.gz
ecli_<version>_docker_rpm_helper_evidence.tar.gz
ecli_<version>_workflow_contract_evidence.tar.gz
```

## Shell-to-Python Script Migration

Active packaging/build/verification scripts under `scripts/` have been migrated
from shell to Python without changing the release contract. The normative rules
live in `docs/release/artifact-contract.md` under
`Shell-to-Python Script Migration`, and the migration is enforced by
`tests/packaging/test_scripts_python_migration_contract.py`.

Migration status: **complete**. Python modules are the only canonical
implementations for migrated active scripts under `scripts/`; no active shell
wrapper remains there. The `Makefile`, GitHub Actions workflows, and
`.cirrus.yml` call the Python entrypoints directly. The canonical Python target
list and migration rules live in `docs/release/artifact-contract.md` under
`Shell-to-Python Script Migration`.

Canonical Python entrypoints include `scripts/sign_checksums.py`,
`scripts/check_log_invariant.py`, `scripts/verify_artifact.py`,
`scripts/verify_release_assets.py`, `scripts/verify_runtime.py`,
`scripts/build_pyinstaller_linux.py`, `scripts/build_and_package_deb.py`,
`scripts/build_and_package_rpm.py`,
`scripts/build_and_package_opensuse_rpm.py`, `scripts/build_and_package_arch.py`,
`scripts/build_and_package_slackware.py`, `scripts/package_appimage.py`,
`scripts/build_and_package_macos.py`, `scripts/build_and_package_freebsd.py`,
`scripts/build_freebsd_pkg.py`, `scripts/build_freebsd_port.py`,
`scripts/build_docker.py`, and `scripts/publish_pypi.py`.

`scripts/build-and-package-windows.ps1` is a separate Windows-native packaging
surface (PowerShell), not part of the shell-to-Python migration.
`.claude/hooks/block-mutations.sh` is a Claude hook, not a packaging script.
`tools/freebsd-chroot-build.sh` is a separate FreeBSD chroot helper outside the
script migration. The unused FreeBSD package-renaming shell helper was removed
during no-shell cleanup. Release readiness is blocked if active shell is
reintroduced under `scripts/`.

## Makefile Command Surface

The root `Makefile` is the primary developer and maintainer command surface.
Use `make help` for the short workflow, `make help-full` for the complete target
map, `make list-targets` for public target discovery, `make doctor` for local
tool availability, and `make sysinfo` for configured package variables.
Maintainer-owned release/upload targets require `ECLI_ALLOW_RELEASE=1`.
Legacy per-platform `release-*` targets fail closed because partial GitHub
Release uploads are incompatible with the exact 21-asset contract. The aggregate
`publish-all` target is the guarded GitHub Release asset publisher and must run
the exact asset verifier first.

`Taskfile.yml` is an optional developer convenience wrapper. It may expose
developer-friendly commands such as `task help`, `task validate-packaging`, and
`task package-linux`, but those commands must delegate to existing Makefile
targets. Makefile remains the authoritative build/release contract; CI and
release gates continue to rely on Makefile, canonical Python scripts under
`scripts/*.py`, and workflow-defined gates. Taskfile tasks must not redefine
artifact names, bypass guarded release/publish targets, or call removed shell
wrappers.

## Linux

- DEB flow: `scripts/build_and_package_deb.py`

- RPM flow: `scripts/build_and_package_rpm.py`

- openSUSE/SUSE RPM flow: `scripts/build_and_package_opensuse_rpm.py`
  - build prerequisites: `python3`, `python3-pip`, `python3-devel`, `gcc`, `make`, `rpm-build`; runtime packages include `ncurses6`, `libyaml-0-2`, and optional clipboard tools `xclip` or `xsel`.

- Arch Linux package flow: `scripts/build_and_package_arch.py`

- Slackware package flow: `scripts/build_and_package_slackware.py`
  - build prerequisites: Slackware `makepkg`, `tar`, `xz`, `python3`,
    PyInstaller, and project Python build dependencies.

- Nix package flow: `flake.nix` / `packaging/nix/package.nix`

- AppImage flow: `scripts/package_appimage.py`

## FreeBSD

Supported paths:

- native host/VM: `scripts/build_and_package_freebsd.py`; local builder `scripts/build_freebsd_pkg.py`

- chroot-based: `tools/freebsd-chroot-build.sh` (via make target; not yet migrated)

- port-oriented build path: `scripts/build_freebsd_port.py`

- CI VM path: `.github/workflows/freebsd-pkg.yml`

Governance rule:

- FreeBSD outputs must be treated as release artifacts, not source-history payload by default.
- Official release publication is blocked until the FreeBSD `.pkg` asset and
  FreeBSD ports/chroot evidence asset are present in the exact 21-asset set.

## macOS

- DMG flow: `scripts/build_and_package_macos.py`

## Windows

- Portable EXE and installer flow: `scripts/build-and-package-windows.ps1`
  - build prerequisites: Python 3.11+, Git, PowerShell 7, NSIS for installer builds, and Visual Studio Build Tools only when native compilation is required.

- NSIS script: `packaging/windows/nsis/ecli.nsi`
