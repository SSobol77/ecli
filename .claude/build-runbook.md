<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/build-runbook.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Build Runbook

This runbook defines non-publishing build and artifact-contract behavior.

## Build policy

Build automation may inspect and validate build paths. It must not publish artifacts.

Allowed build work:

- inspect `Makefile`,
- inspect `scripts/`,
- inspect `packaging/`,
- run shell syntax checks,
- run non-publishing build validation,
- report artifact naming drift.

Forbidden build work:

- release upload,
- PyPI upload,
- GitHub Release creation,
- git tag,
- git push,
- git commit,
- `make release*`,
- `make publish*`.

## Required discovery commands

Use:

```sh
make help
make sysinfo
```

Use script syntax checks:

```sh
sh -n scripts/*
bash -n scripts/*
```

## Artifact contract report

Every build validation must report:

```text
Build artifact contract report

Target:
Command:
Version source:
Expected artifact:
Actual artifact:
Checksum:
Status:
Drift detected:
Publishing attempted: no
Notes:
```

## Shell-to-Python script migration

Active build, packaging, verification, and release-helper scripts under
`scripts/` have been migrated to standard-library Python without changing the
release contract. The migration is **complete**: no active shell wrapper remains
under `scripts/`. Canonical Python implementations include verification:
`scripts/verify_artifact.py` exit codes `0`–`5`, `scripts/sign_checksums.py`,
`scripts/check_log_invariant.py`, `scripts/verify_runtime.py`; build/packaging:
`scripts/build_pyinstaller_linux.py`,
`scripts/build_and_package_{deb,rpm,opensuse_rpm,arch,slackware,macos,freebsd}.py`,
`scripts/package_appimage.py`, `scripts/build_freebsd_pkg.py`,
`scripts/build_freebsd_port.py`, `scripts/build_docker.py`,
`scripts/publish_pypi.py`. `scripts/build-and-package-windows.ps1` is a separate
Windows-native surface, not part of the migration. `.claude/hooks/block-mutations.sh`
is a Claude hook and `tools/freebsd-chroot-build.sh` is a separate FreeBSD chroot
helper. The unused the removed FreeBSD package-renaming shell helper helper was removed. The
`Makefile` calls the Python entrypoints directly. The contract is defined in
`docs/release/artifact-contract.md` under `Shell-to-Python Script Migration` and
enforced by `tests/packaging/test_scripts_python_migration_contract.py`. Migrated
scripts must never publish, upload, tag, push, or trigger workflows.

## Version policy

`pyproject.toml` is the version source of truth.

Any hard-coded version in packaging descriptors must be reported as drift unless it is generated from the canonical source.
