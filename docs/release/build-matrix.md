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

## FreeBSD Reliability Plan

The FreeBSD `.pkg` leg currently runs inside `vmactions/freebsd-vm` (a
qemu-on-Linux VM action on the `ubuntu-latest` GitHub-hosted runner). This
adds a non-trivial flake surface that other platforms do not have, because
the build observes a Linux kernel under qemu before crossing the SSH bridge
into a FreeBSD guest. Treat this as a near-term mitigation, not a long-term
architectural answer:

- Short term (mitigated 2026-05-19): pin vmactions by commit SHA, raise
  guest memory to 6 GiB, tee the in-VM stdout to a workflow artifact, and
  mark `build-freebsd` as best-effort in `release.yml` so a flake cannot
  block a GitHub Release.

- Medium term (proposed): migrate the FreeBSD leg to **Cirrus CI** with a
  native FreeBSD task. Cirrus CI provides first-class FreeBSD compute on
  bare-metal hypervisors, removes the qemu-in-Linux indirection, and gives
  the same level of observability the other legs have today. Required
  scope: a `.cirrus.yml` definition plus a small bridge that copies the
  built `.pkg` + `.sha256` back to the GitHub Release via
  `gh release upload --clobber` when invoked under a release tag. This is
  a stretch goal — track separately from v0.2.x release work.
