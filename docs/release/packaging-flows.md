<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/packaging-flows.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Packaging Flows

The active platform/package set is contract-bound by
`docs/release/artifact-contract.md` under the `Canonical 21-Item Platform &
Packaging Artifact Matrix` (summarized by the `Platform & Packaging Release
Contract Matrix`). That canonical matrix defines exactly 21 physical GitHub
Release assets. Every official ECLI release publishes exactly those 21 assets,
one per canonical matrix entry; release publication is blocked unless
`scripts/verify_release_assets.py` verifies the exact set under
`releases/<version>/`. Release readiness is blocked if any active packaging
surface is absent from docs, agent contracts, build/release runbooks, or
validation tests under `tests/packaging/`. Empty, stale, decorative, or unused
packaging files are forbidden.

Checksum sidecars are mandatory verification evidence under
`releases/<version>/.checksums/` or workflow validation artifacts, not GitHub
Release assets.

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

## Future Extensions Layer Package-Data (planned, #98/#99)

The ECLI Extensions Layer (`docs/architecture/extensions-layer.md`) is an
architecture contract only in issue #97 and changes no packaging flow here. When
the imported, data-only asset tree lands under `src/ecli/extensions/` (issue #98)
and is covered by tests (issue #99), the following packaging rules apply:

- Extension assets must be included in the **PyPI wheel and sdist**. The wheel
  target already includes the `src/ecli` package, but non-`.py` data files
  (`package.json`, `*.tmLanguage`/`*.tmLanguage.json`, `*.code-snippets`,
  `language-configuration.json`, `schemas/*.json`, `themes/*.json`,
  `package.nls.json`, `cgmanifest.json`) require explicit
  `[tool.hatch.build.targets.wheel.force-include]` and
  `[tool.hatch.build.targets.sdist] include` entries, mirroring how
  `src/ecli/assets/ecli.png` is shipped.
- **Package-data coverage must be tested** under `tests/packaging/`, asserting the
  imported extension data files are present in the built wheel and sdist.
- Imported assets are read-only; packaging must ship them unchanged. Packaging
  scripts must not mutate, reformat, or regenerate imported extension files.
- The exact 21-asset GitHub Release contract is unchanged: extension assets ride
  inside the wheel/sdist and downstream platform artifacts, not as new
  top-level release assets.

## Shell-to-Python Script Migration

Active packaging/build/verification scripts under `scripts/` have been migrated
from shell to Python without changing the release contract. The normative rules
live in `docs/release/artifact-contract.md` under
`Shell-to-Python Script Migration`, and the migration is enforced by
`tests/packaging/test_scripts_python_migration_contract.py`.

Migration status: **complete**. Python modules are the only canonical
implementations for migrated active scripts under `scripts/`; no active shell
wrapper remains there. The `Makefile`, GitHub Actions workflows, and
`.cirrus.yml` call the Python entrypoints directly. The canonical Python target
list and migration rules live in `docs/release/artifact-contract.md` under
`Shell-to-Python Script Migration`.

Canonical Python entrypoints include `scripts/sign_checksums.py`,
`scripts/check_log_invariant.py`, `scripts/verify_artifact.py`,
`scripts/verify_release_assets.py`, `scripts/verify_runtime.py`,
`scripts/build_pyinstaller_linux.py`, `scripts/build_and_package_deb.py`,
`scripts/build_and_package_rpm.py`,
`scripts/build_and_package_opensuse_rpm.py`, `scripts/build_and_package_arch.py`,
`scripts/build_and_package_slackware.py`, `scripts/package_appimage.py`,
`scripts/build_and_package_macos.py`, `scripts/build_and_package_freebsd.py`,
`scripts/build_freebsd_pkg.py`, `scripts/build_freebsd_port.py`,
`scripts/build_docker.py`, and `scripts/publish_pypi.py`.

`scripts/build-and-package-windows.ps1` is a separate Windows-native packaging
surface (PowerShell), not part of the shell-to-Python migration.
`.claude/hooks/block-mutations.sh` is a Claude hook, not a packaging script.
`tools/freebsd-chroot-build.sh` is a separate FreeBSD chroot helper outside the
script migration. The unused FreeBSD package-renaming shell helper was removed
during no-shell cleanup. Release readiness is blocked if active shell is
reintroduced under `scripts/`.

## Makefile Command Surface

The root `Makefile` is the primary developer and maintainer command surface.
Use `make help` for the short workflow, `make help-full` for the complete target
map, `make list-targets` for public target discovery, `make doctor` for local
tool availability, and `make sysinfo` for configured package variables.
Maintainer-owned release/upload targets require `ECLI_ALLOW_RELEASE=1`.
Legacy per-platform `release-*` targets fail closed because partial GitHub
Release uploads are incompatible with the exact 21-asset contract. The aggregate
`publish-all` target is the guarded GitHub Release asset publisher and must run
the exact asset verifier first.

`Taskfile.yml` is an optional developer convenience wrapper. It may expose
developer-friendly commands such as `task help`, `task validate-packaging`, and
`task package-linux`, but those commands must delegate to existing Makefile
targets. Makefile remains the authoritative build/release contract; CI and
release gates continue to rely on Makefile, canonical Python scripts under
`scripts/*.py`, and workflow-defined gates. Taskfile tasks must not redefine
artifact names, bypass guarded release/publish targets, or call removed shell
wrappers.

## Linux

- DEB flow: `scripts/build_and_package_deb.py`

- RPM flow: `scripts/build_and_package_rpm.py`

- openSUSE/SUSE RPM flow: `scripts/build_and_package_opensuse_rpm.py`
  - build prerequisites: `python3`, `python3-pip`, `python3-devel`, `gcc`, `make`, `rpm-build`; runtime packages include `ncurses6`, `libyaml-0-2`, and optional clipboard tools `xclip` or `xsel`.

- Arch Linux package flow: `scripts/build_and_package_arch.py`

- Slackware package flow: `scripts/build_and_package_slackware.py`
  - build prerequisites: Slackware `makepkg`, `tar`, `xz`, `python3`,
    PyInstaller, and project Python build dependencies.

- Nix package flow: `flake.nix` / `packaging/nix/package.nix`

- AppImage flow: `scripts/package_appimage.py`

## FreeBSD

Supported paths:

- native host/VM: `scripts/build_and_package_freebsd.py`; local builder `scripts/build_freebsd_pkg.py`

- chroot-based: `tools/freebsd-chroot-build.sh` (via make target; not yet migrated)

- port-oriented build path: `scripts/build_freebsd_port.py`

- CI VM path: `.github/workflows/freebsd-pkg.yml`

Governance rule:

- FreeBSD outputs must be treated as release artifacts, not source-history payload by default.
- Official release publication is blocked until the FreeBSD `.pkg` asset and
  FreeBSD ports/chroot evidence asset are present in the exact 21-asset set.

## macOS

- DMG flow: `scripts/build_and_package_macos.py`

## Windows

- Portable EXE and installer flow: `scripts/build-and-package-windows.ps1`
  - build prerequisites: Python 3.11+, Git, PowerShell 7, NSIS for installer builds, and Visual Studio Build Tools only when native compilation is required.

- NSIS script: `packaging/windows/nsis/ecli.nsi`

## TextMate syntax engine dependency (Oniguruma)

ECLI's default syntax engine (`[extensions].syntax_engine = "extension"`) tokenizes
with the imported TextMate grammars via the `python-textmate` dependency, which
pulls `onigurumacffi` (CFFI bindings to the **Oniguruma** regex library).

- **Wheel/sdist, Linux/macOS/Windows PyInstaller, AppImage, Docker helpers:**
  `onigurumacffi` ships binary wheels for manylinux/musllinux, macOS
  (universal2), and Windows — no system library is required. PyInstaller/AppImage
  bundles must include `python-textmate` and `onigurumacffi`; verify the app
  starts and, if the tokenizer is absent, falls back to the legacy highlighter
  without crashing.
- **Source builds (FreeBSD ports/pkg, Nix from source, musl edge cases):** the
  **Oniguruma** development headers/library must be available at build time
  (`devel/oniguruma` on FreeBSD, `oniguruma`/`libonig-dev` on Debian/Ubuntu,
  `oniguruma` on Arch and in nixpkgs). Declare/install it in the corresponding
  packaging flow, or document the explicit fallback policy (legacy highlighter).
- **Runtime guarantee:** a missing tokenizer never crashes ECLI; it logs a
  deterministic diagnostic and renders with the legacy highlighter.

## Theme numbering and config migration contract

Release artifacts must preserve the canonical theme-numbering policy documented
in `docs/architecture/extensions-layer.md` and the shipped `config.toml`:

- `1`-`8` are deprecated migration aliases only.
- `100`-`199` are light themes.
- `200`-`299` are dark themes.
- `300`-`399` are high-contrast themes.
- `800`-`899` are reserved for future custom/imported special themes.

The default shipped theme is `207` (`Dark+`). Packaging must not rewrite
`config.toml` or silently substitute missing theme numbers. User-config
migration must write
`~/.config/ecli/config.toml.pre-extension-theme-numbering.bak` before changing
an existing config. Old pre-extension aliases `1`-`8` migrate to the preserved
compatibility ids in the `18x`/`28x`/`38x` ranges; transitional ids from the
previous in-progress implementation migrate as `1`-`10` -> `101`-`110`,
`11`-`25` -> `201`-`215`, and `26`-`29` -> `301`-`304`.
