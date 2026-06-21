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
defines exactly 21 physical GitHub Release assets, each mapped to repository
source files, an expected artifact, a related GitHub workflow, a required
`tests/packaging/` test file, a required Claude command, and a required Codex
prompt. This file summarizes build-environment notes only; adding a packaging
script, workflow, Docker helper, Nix descriptor, or platform document without
adding it to the normative matrix is release contract drift.

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. Release publication is blocked unless the exact
21 assets are present and verified by `scripts/verify_release_assets.py`.

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

- macOS DMG path relies on `hdiutil`, Python tooling, Homebrew `oniguruma`, and
  `pkg-config`; the build script validates native Oniguruma headers/libs before
  pip can source-build `onigurumacffi`.

## GitHub Actions Workflow Contract Map

The workflow map is normative in `docs/release/artifact-contract.md`. Build
readiness depends on these CI/release surfaces remaining mapped:

- `.github/workflows/ci.yml`: global quality gate, release contract tests, and
  root `main.py` compatibility contract.
- `.github/workflows/freebsd-pkg.yml`: FreeBSD `.pkg` package path, including
  port/chroot package expectations.
- `.github/workflows/macos-dmg.yml`: macOS `.app` / `.dmg` package path.
- `.github/workflows/macos-validate.yml`: macOS package validation.
- `.github/workflows/project-automation.yml`: repository automation,
  non-packaging; it must not be treated as a release artifact workflow.
- `.github/workflows/pypi-validate.yml`: PyPI wheel/sdist validation.
- `.github/workflows/release.yml`: aggregate exact 21-asset release matrix.
- `.github/workflows/windows-installer.yml`: Windows portable EXE and NSIS
  installer path.
- `.github/workflows/windows-validate.yml`: Windows package validation.

## Future Extensions Layer Package-Data Impact (planned, #98/#99)

The ECLI Extensions Layer (`docs/architecture/extensions-layer.md`) does not yet
exist on disk and does not change this matrix in issue #97. When the imported
asset tree lands under `src/ecli/extensions/` (issue #98) and is covered by
package-data tests (issue #99):

- The 21-asset count is unchanged. Extension assets ship **inside** the existing
  PyPI wheel/sdist and downstream artifacts, not as new top-level GitHub Release
  assets.
- Non-`.py` extension data files (`*.json`, `*.tmLanguage`,
  `*.code-snippets`, `schemas/*.json`, etc.) require explicit wheel
  `force-include` and sdist `include` coverage in `pyproject.toml`.
- Every active platform/package contract above must remain green after the asset
  tree is added; a `tests/packaging/` test must assert extension data inclusion
  in the wheel and sdist.

## Validation State

- Actual flow support is bounded by current CI behavior and script/workflow drift.

- Any platform marked release-ready must satisfy artifact contract checks.

- `make validate-release-assets` must pass before official GitHub Release
  publication.

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

## Script Migration Contract

- Active shell wrappers under `scripts/` have been removed; Python entrypoints
  under `scripts/` are canonical.
- `scripts/build-and-package-windows.ps1` remains the separate Windows
  PowerShell packaging surface.
- `.claude/hooks/block-mutations.sh` is a Claude hook, not packaging.
- `tools/freebsd-chroot-build.sh` remains a FreeBSD chroot helper outside this
  migration.
- the removed FreeBSD package-renaming shell helper was unused tracked tooling and has been removed.

## FreeBSD Reliability Plan

The FreeBSD `.pkg` leg currently runs inside `vmactions/freebsd-vm` (a
qemu-on-Linux VM action on the `ubuntu-latest` GitHub-hosted runner). This
adds a non-trivial flake surface that other platforms do not have, because
the build observes a Linux kernel under qemu before crossing the SSH bridge
into a FreeBSD guest. Treat this as a near-term mitigation, not a long-term
architectural answer:

- Short term: pin vmactions by commit SHA, raise guest memory to 6 GiB, and
  tee the in-VM stdout to a workflow artifact. A FreeBSD failure blocks official
  GitHub Release publication until the required FreeBSD package and
  ports/chroot evidence assets are present.

- Medium term (proposed): migrate the FreeBSD leg to **Cirrus CI** with a
  native FreeBSD task. Cirrus CI provides first-class FreeBSD compute on
  bare-metal hypervisors, removes the qemu-in-Linux indirection, and gives
  the same level of observability the other legs have today. Required
  scope: a `.cirrus.yml` definition plus a controlled evidence bridge back into
  the aggregate release workflow before `scripts/verify_release_assets.py`
  runs. This is a stretch goal; track separately from v0.2.x release work.
