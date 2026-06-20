<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: CODEX.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex Operating Policy for ECLI

This file defines Codex-specific operating rules for the ECLI repository.

Shared cross-agent rules live in `AGENTS.md`. Codex must read `AGENTS.md` first, then this file, then the relevant `.codex/` role or runbook.

Claude-specific files under `.claude/` are not Codex authority unless the maintainer explicitly asks Codex to compare or mirror them.

## Operating model

Codex is used for:

* read-only inventory,
* diagnostics,
* static analysis,
* validation summaries,
* report drafting,
* narrow patch proposals when explicitly requested,
* prepare-only release or packaging review.

Codex is not a release executor.

The maintainer performs all git, GitHub, release, publishing, and workflow actions manually.

## Default safety mode

For Stage 1 inspection, prefer:

```sh
codex exec --sandbox read-only --ephemeral --cd .
```

For any task that may write files, Codex must first explain:

* why the write is needed,
* which files will be touched,
* which Stage / audit finding authorizes it,
* which validation will be run afterward.

Do not use `danger-full-access` for normal ECLI work.

## Forbidden Codex actions

Codex must not run:

```sh
git add
git commit
git push
git tag
git reset
git clean
gh pr create
gh issue edit
gh issue close
gh issue comment
gh workflow run
gh run rerun
gh run cancel
gh release create
gh release upload
gh release edit
gh release delete
twine upload
uv publish
python -m twine upload
make release
make release-*
make publish
make publish-*
```

If the maintainer needs one of these actions, Codex may print a manual checklist or command block, but must not execute it.

## Codex source order

For Codex work, read:

1. `AGENTS.md`
2. `CODEX.md`
3. `.codex/PIPELINE.md`
4. relevant `.codex/runbooks/*.md`
5. relevant `.codex/roles/*.md`
6. `audit-report.md`
7. `docs/planning/roadmap.md`
8. `docs/adr/0001-single-writer-screen.md`
9. `pyproject.toml`
10. `Makefile`
11. relevant source, test, script, packaging, workflow, or documentation files

If a `.codex/` file is missing, report it and continue with `AGENTS.md` + `CODEX.md`.

## Stage 1 Codex policy

Stage 1 is active by default.

Allowed:

* inspect source files,
* run read-only grep/static queries,
* summarize validation output,
* produce Markdown reports,
* draft issue/PR/release text,
* propose patches without applying them unless explicitly requested.

Forbidden:

* broad rendering rewrites,
* broad architecture rewrites,
* splitting `src/ecli/core/Ecli.py`,
* splitting `src/ecli/ui/panels.py`,
* production release actions,
* public artifact publication,
* unapproved file writes.

For packaging/release work, Codex must treat every active platform/package
surface as part of the release contract. The active matrix is documented in
`docs/release/artifact-contract.md` under `Platform & Packaging Release Contract
Matrix`; missing docs, agent contracts, runbooks, or validation coverage are
AUD-003 drift. Codex may repair documentation/tests when explicitly authorized,
but must not publish, upload, tag, push, or trigger workflows.

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. Release publication is blocked unless
`scripts/verify_release_assets.py` verifies the exact top-level asset set under
`releases/<version>/`. Checksum sidecars are mandatory verification evidence,
but they are not GitHub Release assets.

Active build, packaging, verification, and release-helper scripts under
`scripts/` have been migrated to standard-library Python without changing the
release contract. The migration is **complete**: no active shell wrapper remains
under `scripts/`. Canonical Python implementations include verification:
`scripts/verify_artifact.py`, `scripts/sign_checksums.py`,
`scripts/check_log_invariant.py`, `scripts/verify_release_assets.py`,
`scripts/verify_runtime.py`; build/packaging:
`scripts/build_pyinstaller_linux.py`,
`scripts/build_and_package_{deb,rpm,opensuse_rpm,arch,slackware,macos,freebsd}.py`,
`scripts/package_appimage.py`, `scripts/build_freebsd_pkg.py`,
`scripts/build_freebsd_port.py`, `scripts/build_docker.py`,
`scripts/publish_pypi.py`. `scripts/build-and-package-windows.ps1` is a separate
Windows-native surface, not part of the migration. `.claude/hooks/block-mutations.sh`
is a Claude hook, `tools/freebsd-chroot-build.sh` is a separate FreeBSD chroot
helper, and the removed FreeBSD package-renaming shell helper was removed as unused tracked tooling.
The `Makefile`, workflows, and `.cirrus.yml` call the Python entrypoints
directly. The migration contract is defined in
`docs/release/artifact-contract.md` under `Shell-to-Python Script Migration` and
enforced by `tests/packaging/test_scripts_python_migration_contract.py`. Release
readiness is blocked if active shell logic is reintroduced under `scripts/`.
Migrated scripts must never
publish, upload, sign with external keys, tag, push, or trigger workflows.

The root `Makefile` is the primary Codex-inspectable command surface. Use
`make help`, `make help-full`, `make list-targets`, `make doctor`, and
`make sysinfo` for read-only discovery. Do not run maintainer-owned
release/upload targets; they are guarded and remain outside Codex execution.

`Taskfile.yml` may be used only as an optional developer convenience wrapper
around existing Makefile targets. Codex must not introduce Taskfile-only
build/release behavior, must not weaken release/publish guards, and must keep
packaging scripts as Python entrypoints under `scripts/*.py`. Makefile remains
the authoritative build/release contract; CI and release gates continue to use
the existing canonical command surfaces.

## Rendering policy

Rendering work is Stage-2-locked unless the maintainer explicitly approves a narrow Stage 1b fix.

For ECLI 0.2.x, do not implement a full PTY terminal emulator. F11 must be treated as an ECLI-owned PySH Console Panel direction. PySH is a command execution backend only. Do not migrate PySH source into ECLI and do not mix this work with VMLab/QEMU/QMP scope.

During Stage 1, Codex may only:

* inventory direct curses usage,
* inventory `stdscr.*`, `refresh`, `noutrefresh`, `doupdate`,
* inventory `len()`-based display geometry,
* inventory resize paths,
* inventory async redraw triggers,
* classify findings,
* write or print reports.

Codex must not implement the rendering rewrite during Stage 1.

## Extensions Layer contract (v0.3.0 Foundation)

The ECLI Extensions Layer is the imported, data-only, VS Code / TextMate-compatible
asset tree and the deterministic adapter code around it. Its normative contract is
`docs/architecture/extensions-layer.md`. Until the asset tree is imported in a
later issue, this is documentation/architecture only.

Codex must obey:

* `src/ecli/extensions/` is the **only** approved location for imported extension
  assets. Do not invent or use `vendor/`, `third_party/`, or
  `src/ecli/syntax/assets/`.
* Imported/upstream files under `src/ecli/extensions/` are **read-only** from the
  ECLI integration perspective. Do not edit, reformat, or relicense them.
* Implement ECLI-specific behavior through **deterministic adapter code** that
  reads those assets, never by modifying upstream files.
* **No VS Code extension host, no Node/TypeScript activation, no
  `activationEvents` execution, no `package.json` scripts, no Copilot runtime,
  no network/auth side effects, no hidden command execution** through extension
  metadata.
* Preserve **F11 as the PySH Console Panel**; command execution stays routed
  through explicit ECLI services / PySH / CommandPlan surfaces.
* **No generic PTY terminal emulator.** Extensions must not reintroduce terminal
  execution behavior.
* Do not import the prepared asset tree in issue #97. Sequencing is #97 contract,
  #98 import unchanged, #99 package-data tests, #100–#105 adapters.
* VMLab is out of scope: it moved to v0.3.5 and is blocked until the v0.3.0
  Extensions Foundation is complete.

## Expected Codex final response

For non-trivial work, finish with:

```text
Result:
- What changed:
- Evidence:
- Commands run:
- Commands blocked:
- Files touched:
- Remaining risks:
- Recommended next step:
```

If no files were changed, say so explicitly.
