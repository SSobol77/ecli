<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/release/packaging-flows.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
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
