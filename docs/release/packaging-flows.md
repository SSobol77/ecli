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

- openSUSE/SUSE RPM flow: `scripts/build-and-package-opensuse-rpm.sh`
  - build prerequisites: `python3`, `python3-pip`, `python3-devel`, `gcc`, `make`, `rpm-build`; runtime packages include `ncurses6`, `libyaml-0-2`, and optional clipboard tools `xclip` or `xsel`.

- Arch Linux package flow: `scripts/build-and-package-arch.sh`

- Slackware package flow: `scripts/build-and-package-slackware.sh`
  - build prerequisites: Slackware `makepkg`, `tar`, `xz`, `python3`,
    PyInstaller, and project Python build dependencies.

- Nix package flow: `flake.nix` / `packaging/nix/package.nix`

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
  - build prerequisites: Python 3.11+, Git, PowerShell 7, NSIS for installer builds, and Visual Studio Build Tools only when native compilation is required.

- NSIS script: `packaging/windows/nsis/ecli.nsi`
