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
- [ ] Every official ECLI release uploads exactly 21 ECLI-owned physical GitHub
      Release assets, one per canonical matrix entry; release publication is
      blocked unless the exact 21 ECLI-owned assets are present and verified.
- [ ] If the GitHub UI shows **Assets 23**, confirm the extra two entries are
      GitHub-generated `Source code (zip)` and `Source code (tar.gz)` archives.
      They are not ECLI-owned uploaded artifacts and are not part of the
      canonical 21 artifact contract entries.
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
- [ ] `make validate-gate2` passes as source and structural contract
      validation; it does not inspect ignored historical release artifacts.
- [ ] `make validate-official-evidence-drift` passes; this invokes
      `scripts/f4_linter_linux_provisioning.py --check-official-evidence-drift`
      and blocks release readiness if the Linux official distro evidence
      registry drifts from generated evidence.
- [ ] The canonical `Release` workflow `validate-built-artifacts` job downloads
      all build outputs, assembles `releases/<version>/`, generates adjacent
      `.sha256` sidecars, runs `make validate-built-artifacts`, and is required
      by both GitHub Release and PyPI publication jobs.
- [ ] `make validate-release-assets` passes against `releases/<version>/` after
      checksum sidecars are staged under `.checksums/`.
- [ ] Required packaging scripts exist and are executable.
- [ ] Active shell wrappers under `scripts/` are absent; Python entrypoints under
      `scripts/` are canonical. Windows PowerShell packaging
      (`scripts/build-and-package-windows.ps1`) and the FreeBSD chroot helper
      (`tools/freebsd-chroot-build.sh`) are classified separately.
- [ ] Confirm the removed FreeBSD package-renaming shell helper remains absent unless a future
      dedicated tools migration restores equivalent Python tooling.
- [ ] Workflow references are valid (no missing files such as packaging specs).
- [ ] Checksums are generated for all release artifacts under
      `releases/<version>/.checksums/`; `.sha256` sidecars are CI/release
      verification evidence, not uploaded GitHub Release assets.
- [ ] Contributor docs match actual release/build commands.
- [ ] FreeBSD governance policy reviewed for artifact handling.
- [ ] Release notes include known limitations and degraded flows.
- [ ] AppImage, openSUSE, Arch, Slackware, FreeBSD `.pkg`,
      FreeBSD ports/chroot evidence, macOS app evidence, Nix flake evidence,
      NixOS package evidence, Docker helper evidence, and workflow contract
      evidence are present in the canonical 21 ECLI-owned asset set.
- [ ] FreeBSD may be built by native, VM, chroot, or ports route, but the
      official release remains blocked until both required FreeBSD assets are
      present in the exact 21 ECLI-owned asset set.
- [ ] Confirm vmactions/freebsd-vm is still pinned to a known-good commit SHA
      in both `release.yml` and `freebsd-pkg.yml`.
- [ ] Extensions Layer: confirm the curated runtime asset bundle under
      `src/ecli/extensions/` is normalized — the root holds only
      `ecli_integration/`, `lang/`, `themes/`, and `THIRD_PARTY_NOTICES.md`, with
      imported assets under `lang/<name>` and `themes/<name>` containing only
      manifests/NLS, grammars, themes, snippets, language-configuration metadata,
      and legal attribution files; confirm non-`.py` extension data files are
      present in the built wheel and sdist via `tests/extensions/`; confirm
      enforcement tests reject source/build/test/media artifacts, flat root
      folders, and VS Code UI/runtime-only folders; and confirm all 21 canonical
      assets remain green. See `docs/architecture/extensions-layer.md`.
- [ ] F4 linter provisioning: every ECLI Full artifact maps provisioning to
      exactly 21 artifact contract entries, detects OS/artifact context first,
      detects already-installed required tools before installing missing tools,
      verifies executable availability and version probes, and includes
      deterministic provisioning evidence.
- [ ] `scripts/provision_f4_linters.py --all-artifacts --mode dry-run` writes
      21 deterministic `f4-linter-provisioning-<artifact-entry-id>.json`
      evidence files, and
      `scripts/verify_f4_linter_provisioning.py --all-artifacts` verifies them.
- [ ] Linux official distro evidence drift audit remains clean:
      `uv run python scripts/f4_linter_linux_provisioning.py --check-official-evidence-drift`
      prints
      `PASS: Linux official distro evidence drift audit clean` and exits `0`;
      exit `2` is release-blocking drift.
- [ ] F4 linter package-manager dependencies: package metadata asserts the
      dependency relationship and post-install executable availability for each
      required linter/toolchain dependency it delegates to the OS package
      manager.
- [ ] F4 linter bundled/upstream tools: every bundled or GitHub/upstream
      downloaded binary, JAR, or tarball has explicit source URL, pinned
      version, checksum/provenance evidence, executable permission handling, and
      no silent unverified execution.
- [ ] Missing required F4 linter after ECLI Full install is treated as a release
      blocker unless the artifact is explicitly documented as minimal or
      constrained before release.
- [ ] PyPI wheel/sdist limitations are documented honestly: plain Python
      package metadata cannot reliably provision Node, Rust, Go, Zig, Java, or
      system binaries, so complete F4 linter provisioning belongs to Full
      platform artifacts.

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

## TextMate engine dependency check

- [ ] `pyproject.toml` declares `python-textmate` (pulls `onigurumacffi`).
- [ ] Wheel/PyInstaller/AppImage/DMG/Windows artifacts include
      `python-textmate` + `onigurumacffi`, or start and fall back to the legacy
      highlighter without crashing when absent.
- [ ] macOS workflows install Homebrew `oniguruma` and `pkg-config` before
      package installation, and `scripts/build_and_package_macos.py` exports
      `CPPFLAGS`, `CFLAGS`, `LDFLAGS`, and `PKG_CONFIG_PATH` for pip subprocesses.
- [ ] Source-build platforms (FreeBSD ports/pkg, Nix from source) provide the
      **Oniguruma** dev headers/library, or document the legacy-fallback policy.
- [ ] Startup log shows `textmate_tokenizer_available=True` on a reference build.
- [ ] Real large-file scroll smoke passes on `Makefile` and
      `logs/freebsd-0.2.2-fail.log` without repaint freezes.
- [ ] Multiline comment/string rendering checks pass for Python triple strings,
      JavaScript block/doc comments, TypeScript block/doc comments, HTML
      comments, and CSS block comments.
- [ ] Words, numbers, operators, tags, selectors, properties, and values inside
      protected multiline comments/strings render as comment/string, while code
      after the protected region still highlights as code.
- [ ] `.log` files and `.gitignore` are not detected as SQL/Transact-SQL.
- [ ] TextMate dependency/fallback checks pass when `python-textmate` or
      Oniguruma is unavailable.

## Theme numbering migration check

- [ ] Shipped `config.toml` defaults to `theme = 207` (`Dark+`).
- [ ] Theme numbering policy is present in `config.toml`,
      `docs/architecture/extensions-layer.md`, and config docs:
      `1`-`8` deprecated aliases, `100`-`199` light, `200`-`299` dark,
      `300`-`399` high contrast, `800`-`899` reserved.
- [ ] Old pre-extension `theme = 1`-`8` configs migrate to the matching
      compatibility ids in the `18x`/`28x`/`38x` ranges.
- [ ] Transitional previous-implementation ids migrate as `1`-`10` -> `101`-`110`,
      `11`-`25` -> `201`-`215`, and `26`-`29` -> `301`-`304`.
- [ ] Migration writes
      `~/.config/ecli/config.toml.pre-extension-theme-numbering.bak` and emits a
      visible ECLI warning.
- [ ] Missing/invalid theme numbers are not mapped to unrelated themes; ECLI
      keeps the current valid theme when available.
