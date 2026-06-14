<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/build-matrix.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Build Matrix

## Platform Matrix (Current Observed)

The normative platform/package list is the `Canonical 21-Item Platform &
Packaging Artifact Matrix` (summarized by the `Platform & Packaging Release
Contract Matrix`) in `docs/release/artifact-contract.md`. That canonical matrix
has exactly 21 entries, each mapped to repository source files, an expected
artifact, a related GitHub workflow, a required `tests/packaging/` test file, a
required Claude command, and a required Codex prompt. This file summarizes
build-environment notes only; adding a packaging script, workflow, Docker helper,
Nix descriptor, or platform document without adding it to the normative matrix is
release contract drift.

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

## GitHub Actions Workflow Contract Map

The workflow map is normative in `docs/release/artifact-contract.md`. Build
readiness depends on these CI/release surfaces remaining mapped:

- `.github/workflows/ci.yml`: global quality gate and root `main.py`
  compatibility contract.
- `.github/workflows/freebsd-pkg.yml`: FreeBSD `.pkg` package path, including
  port/chroot package expectations.
- `.github/workflows/macos-dmg.yml`: macOS `.app` / `.dmg` package path.
- `.github/workflows/macos-validate.yml`: macOS package validation.
- `.github/workflows/project-automation.yml`: repository automation,
  non-packaging; it must not be treated as a release artifact workflow.
- `.github/workflows/pypi-validate.yml`: PyPI wheel/sdist validation.
- `.github/workflows/release.yml`: aggregate release artifact matrix.
- `.github/workflows/windows-installer.yml`: Windows portable EXE and NSIS
  installer path.
- `.github/workflows/windows-validate.yml`: Windows package validation.

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
