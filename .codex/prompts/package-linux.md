<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/package-linux.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex Linux packaging inspection prompt

## Covered canonical artifact entries

This prompt covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- Linux generic PyInstaller executable
- Linux release tarball
- Debian / Ubuntu `.deb`
- generic RPM `.rpm`
- openSUSE / SUSE RPM
- Arch Linux `PKGBUILD`
- Slackware `.txz`
- AppImage
- Docker DEB build helper
- Docker RPM build helper

## Exact official release asset gate

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. No reduced or subset official release is
allowed. AppImage, openSUSE, Arch, Slackware, FreeBSD `.pkg`, FreeBSD
ports/chroot evidence, Nix flake evidence, NixOS package evidence, Docker helper
evidence, and workflow contract evidence are mandatory.

Release readiness is blocked unless `scripts/verify_release_assets.py` verifies
the exact top-level asset set under `releases/<version>/`. Checksum sidecars are
verification evidence under `.checksums/` or workflow artifacts; they are not
GitHub Release assets.

Use with:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT"
```

Prompt:

```text
Act as the Codex build-engineer for ECLI Linux packaging.

Read, in order:
1. AGENTS.md
2. CODEX.md
3. .codex/PIPELINE.md
4. .codex/roles/build-engineer.md
5. .codex/roles/release-engineer.md when release-readiness evidence is relevant
6. .codex/runbooks/build.md if present
7. .codex/runbooks/drift.md if present
8. audit-report.md
9. docs/release/artifact-contract.md
10. docs/release/packaging-flows.md
11. pyproject.toml
12. Makefile

Claude-specific files under .claude/ and CLAUDE.md are not Codex authority.

Stage 1 rule: inspect and report only. Do not build packages, publish, upload, tag, push, trigger workflows, create releases, run release targets, run publish targets, or mutate tracked packaging descriptors.

Script-migration note: the shell-to-Python migration is complete. Active shell wrappers under scripts/ have been removed; canonical Python implementations include scripts/verify_artifact.py exit codes 0-5, scripts/sign_checksums.py, scripts/check_log_invariant.py, scripts/verify_runtime.py, scripts/build_pyinstaller_linux.py, scripts/build_and_package_deb.py, scripts/build_and_package_rpm.py, scripts/build_and_package_opensuse_rpm.py, scripts/build_and_package_arch.py, scripts/build_and_package_slackware.py, scripts/package_appimage.py, and scripts/build_docker.py. The migration contract lives in docs/release/artifact-contract.md under "Shell-to-Python Script Migration" and is enforced by tests/packaging/test_scripts_python_migration_contract.py. Report any active shell logic reintroduced under scripts/ as release-blocking drift.

Inspect:
- pyproject.toml;
- packaging/arch/PKGBUILD;
- packaging/linux/;
- packaging/nix/package.nix;
- packaging/pyinstaller/;
- Linux build scripts under scripts/;
- release docs related to Linux packaging.

Use read-only inspection commands only, such as:
- make help
- make sysinfo
- rg -n "version|PACKAGE_VERSION|pkgver|sed -i|license|GPL|artifact|AppImage|deb|rpm|nix|pyinstaller" pyproject.toml Makefile scripts packaging docs/release
- find packaging/linux packaging/arch packaging/nix packaging/pyinstaller -maxdepth 3 -type f -printf "%p\n"
- find scripts -maxdepth 1 -type f -printf "%p\n"

Report:
- package target inventory;
- artifact naming expectations;
- version drift against pyproject.toml;
- license metadata drift;
- tracked descriptor mutation risks;
- release/publication commands that Codex must not run;
- whether findings are clean, baseline, new regression, or needs-review.

If a report file is needed, print Markdown only; the maintainer redirects stdout to the target file.

Finish with:

Result:
* What was inspected:
* Evidence:
* Commands run:
* Commands blocked:
* Files touched:
* Remaining risks:
* Recommended next step:
```
