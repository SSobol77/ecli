<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/release/build-matrix.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Build Matrix

## Platform Matrix (Current Observed)

- Linux: DEB/RPM/openSUSE RPM/Arch/Slackware/AppImage scripts and workflows

- NixOS/Nix: local flake/package expression

- FreeBSD: native `.pkg` via script and VM workflow

- macOS: DMG build workflow and script

- Windows: portable EXE plus NSIS installer workflow and script

## Build Environment Notes

- Linux packaging relies on FPM and platform-specific dependencies.

- openSUSE/SUSE RPM builds require `python3`, `python3-pip`,
  `python3-devel`, `gcc`, `make`, and `rpm-build`; runtime packages include  `ncurses6`, `libyaml-0-2`, and optional clipboard tools `xclip` or `xsel`.

- Arch packaging requires `makepkg`; raw package names are normalized by the ECLI release script.

- Slackware packaging requires Slackware `makepkg`, `tar`, `xz`, `python3`, PyInstaller, and project Python build dependencies. Runtime packages include `ncurses`, `libyaml`, and `xclip` or `xsel` when available for the target release.

- Nix packaging requires flakes and nixpkgs inputs.

- FreeBSD packaging requires native FreeBSD runtime context (host/VM/chroot pattern).

- Windows installer path requires Python 3.11+, Git, PowerShell 7, and NSIS (`makensis`). Visual Studio Build Tools are required only when native dependencies or build tooling need local compilation.

- macOS DMG path relies on `hdiutil` and Python tooling.

## Validation State

- Actual flow support is bounded by current CI behavior and script/workflow drift.

- Any platform marked release-ready must satisfy artifact contract checks.
