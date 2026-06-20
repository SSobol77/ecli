<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/release-checklist.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Release Checklist

- [ ] Version in `pyproject.toml` is correct.
- [ ] Every official ECLI release publishes exactly 21 physical GitHub Release
      assets, one per canonical matrix entry; release publication is blocked
      unless the exact 21 assets are present and verified.
- [ ] `docs/release/artifact-contract.md` lists all 21 entries in the
      `Canonical 21-Item Platform & Packaging Artifact Matrix`, and every active
      platform/package surface in the `Platform & Packaging Release Contract
      Matrix`.
- [ ] Each of the 21 canonical entries has a `tests/packaging/` test file, a
      Claude command mapping, a Codex prompt mapping, and (where relevant) a
      mapped GitHub workflow; `uv run pytest -q tests/packaging` passes.
- [ ] Every active platform/package surface is represented in docs, Codex and
      Claude agent contracts, build/release runbooks, and validation tests or
      contract checks.
- [ ] Empty, stale, decorative, or unused packaging files have been removed from
      active workflows/scripts or wired into the matrix.
- [ ] Artifact contract names are configured and validated.
- [ ] `make help`, `make help-full`, `make list-targets`, `make doctor`, and
      `make sysinfo` match current package surfaces and canonical Python
      scripts.
- [ ] `make validate-gate2` passes before any publish step.
- [ ] `make validate-release-assets` passes against `releases/<version>/`.
- [ ] Required packaging scripts exist and are executable.
- [ ] Active shell wrappers under `scripts/` are absent; Python entrypoints under
      `scripts/` are canonical. Windows PowerShell packaging
      (`scripts/build-and-package-windows.ps1`), the Claude hook
      (`.claude/hooks/block-mutations.sh`), and the FreeBSD chroot helper
      (`tools/freebsd-chroot-build.sh`) are classified separately.
- [ ] Confirm the removed FreeBSD package-renaming shell helper remains absent unless a future
      dedicated tools migration restores equivalent Python tooling.
- [ ] Workflow references are valid (no missing files such as packaging specs).
- [ ] Checksums are generated for all release artifacts under
      `releases/<version>/.checksums/`; `.sha256` sidecars are verification
      evidence, not GitHub Release assets.
- [ ] Contributor docs match actual release/build commands.
- [ ] FreeBSD governance policy reviewed for artifact handling.
- [ ] Release notes include known limitations and degraded flows.
- [ ] AppImage, openSUSE, Arch, Slackware, FreeBSD `.pkg`,
      FreeBSD ports/chroot evidence, macOS app evidence, Nix flake evidence,
      NixOS package evidence, Docker helper evidence, and workflow contract
      evidence are present in the canonical 21-asset set.
- [ ] FreeBSD may be built by native, VM, chroot, or ports route, but the
      official release remains blocked until both required FreeBSD assets are
      present in the exact 21-asset set.
- [ ] Confirm vmactions/freebsd-vm is still pinned to a known-good commit SHA
      in both `release.yml` and `freebsd-pkg.yml`.

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
