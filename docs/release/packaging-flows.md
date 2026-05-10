<!--
Filename: docs/release/packaging-flows.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Packaging Flows

## Linux

- DEB flow: `scripts/build-and-package-deb.sh`
- RPM flow: `scripts/build-and-package-rpm.sh`
- AppImage flow: `scripts/package_appimage.sh`

## FreeBSD

Supported paths:
- native host/VM: `scripts/build-and-package-freebsd.sh`
- chroot-based: `tools/freebsd-chroot-build.sh` (via make target)
- port-oriented build path: `scripts/build_freebsd_port.sh`
- CI VM path: `.github/workflows/freebsd-pkg.yml`

Governance rule:
- FreeBSD outputs must be treated as release artifacts, not source-history payload by default.

## macOS

- DMG flow: `scripts/build-and-package-macos.sh`

## Windows

- Portable EXE and installer flow: `scripts/build-and-package-windows.ps1`
- NSIS script: `packaging/windows/nsis/ecli.nsi`
