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

- Arch packaging requires `makepkg`; raw package names are normalized by the ECLI release script.

- Slackware packaging requires Slackware `makepkg` and emits normalized ECLI `.txz` release names.

- Nix packaging requires flakes and nixpkgs inputs.

- FreeBSD packaging requires native FreeBSD runtime context (host/VM/chroot pattern).

- Windows installer path requires NSIS (`makensis`).

- macOS DMG path relies on `hdiutil` and Python tooling.

## Validation State

- Actual flow support is bounded by current CI behavior and script/workflow drift.

- Any platform marked release-ready must satisfy artifact contract checks.
