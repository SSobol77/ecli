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

## Rendering policy

Rendering work is Stage-2-locked unless the maintainer explicitly approves a narrow Stage 1b fix.

During Stage 1, Codex may only:

* inventory direct curses usage,
* inventory `stdscr.*`, `refresh`, `noutrefresh`, `doupdate`,
* inventory `len()`-based display geometry,
* inventory resize paths,
* inventory async redraw triggers,
* classify findings,
* write or print reports.

Codex must not implement the rendering rewrite during Stage 1.

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
