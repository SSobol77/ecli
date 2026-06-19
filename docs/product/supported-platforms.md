<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/product/supported-platforms.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Supported Platforms

## Runtime Platforms (Current State)

- Linux (primary)
- FreeBSD
- macOS
- Windows

## Packaging Targets (Current Tooling)

- PyPI: wheel and source distribution
- Linux: PyInstaller executable, release tarball, DEB, RPM, openSUSE/SUSE RPM,
  Arch package, Slackware package, AppImage
- FreeBSD: `.pkg`
- macOS: `.app` / `.dmg`
- Windows: portable `.exe` and NSIS installer `.exe`
- Nix / NixOS: flake package and app
- Docker build helpers: Debian and RPM build containers

## Canonical 21-Item Artifact Coverage

The normative artifact list is the `Canonical 21-Item Platform & Packaging
Artifact Matrix` in `docs/release/artifact-contract.md`. Every official ECLI
release publishes exactly 21 physical GitHub Release assets, one per canonical
matrix entry. Release publication is blocked unless `scripts/verify_release_assets.py`
verifies the exact top-level asset set under `releases/<version>/`. Checksum
sidecars are verification evidence, not GitHub Release assets.

Every entry below must remain covered by tests under `tests/packaging/`, by
`.claude/commands/`, by `.codex/prompts/`, and (where relevant) by a GitHub
workflow:

1. PyPI wheel
2. PyPI source distribution
3. Linux generic PyInstaller executable
4. Linux release tarball
5. Debian / Ubuntu `.deb`
6. generic RPM `.rpm`
7. openSUSE / SUSE RPM
8. Arch Linux `PKGBUILD`
9. Slackware `.txz`
10. AppImage
11. FreeBSD `.pkg`
12. FreeBSD ports/chroot build path
13. macOS `.app`
14. macOS `.dmg`
15. Windows portable `.exe`
16. Windows NSIS installer `.exe`
17. Nix flake
18. Nix/NixOS package expression
19. Docker DEB build helper
20. Docker RPM build helper
21. GitHub Actions release/workflow contract map

Mandatory GitHub Release asset names for each `<version>`:

```text
01_pypi_wheel__ecli_editor-<version>-py3-none-any.whl
02_pypi_sdist__ecli_editor-<version>.tar.gz
03_linux_pyinstaller__ecli_<version>_linux_x86_64.bin
04_linux_tarball__ecli_<version>_linux_x86_64.tar.gz
05_debian__ecli_<version>_linux_x86_64.deb
06_rpm__ecli_<version>_linux_x86_64.rpm
07_opensuse__ecli_<version>_opensuse_x86_64.rpm
08_arch__ecli_<version>_arch_x86_64.pkg.tar.zst
09_slackware__ecli_<version>_slackware_x86_64.txz
10_appimage__ecli_<version>_linux_x86_64.AppImage
11_freebsd_pkg__ecli_<version>_freebsd_x86_64.pkg
12_freebsd_ports_chroot__ecli_<version>_freebsd_ports_chroot_evidence.tar.gz
13_macos_app__ecli_<version>_macos_universal2_app_evidence.tar.gz
14_macos_dmg__ecli_<version>_macos_universal2.dmg
15_windows_portable__ecli_<version>_win_x86_64.exe
16_windows_nsis__ecli_<version>_win_x86_64_setup.exe
17_nix_flake__ecli_<version>_nix_flake_evidence.tar.gz
18_nixos_package__ecli_<version>_nixos_package_evidence.tar.gz
19_docker_deb_helper__ecli_<version>_docker_deb_helper_evidence.tar.gz
20_docker_rpm_helper__ecli_<version>_docker_rpm_helper_evidence.tar.gz
21_workflow_contract__ecli_<version>_workflow_contract_evidence.tar.gz
```

## Support Stance

- Current state indicates cross-platform packaging intent.
- Support quality is bounded by CI/workflow coverage and artifact contract compliance.
- The normative release-contract surface list lives in
  `docs/release/artifact-contract.md`. A platform/package surface is not
  release-ready unless it is represented in product/release docs, agent
  contracts, runbooks, and validation tests or contract checks.

### Support Status Definitions

- **Fully supported**: CI workflow passes, artifacts are produced and verified, and platform is recommended for production use.
- **Failing or unverified**: Build failures, test failures, or absence of CI workflow coverage; artifact may not be available or tested; not recommended for release.
- **Degraded**: limited support with known issues or limited testing; not recommended for production until issues are resolved.

### Platform Status and Incident Management

- Live platform status: check CI dashboard and release notes for current status of each platform.
- Incident triage: degraded platforms are reviewed with each release cycle; maintainers assess whether to restore, drop, or stabilize the platform.
- Expected communication: major changes to platform status (removal, restoration, degradation) are noted in release documentation.

## Script Migration Note

Active shell wrappers under `scripts/` have been removed; canonical package and
verification implementations are Python entrypoints under `scripts/`. Windows
PowerShell packaging remains separate at `scripts/build-and-package-windows.ps1`.
`.claude/hooks/block-mutations.sh` is a Claude hook, not product packaging.
`tools/freebsd-chroot-build.sh` remains a FreeBSD chroot helper outside the
script migration, and the removed FreeBSD package-renaming shell helper was removed as unused
tracked tooling.
