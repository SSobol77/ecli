<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/runbooks/drift.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex drift inventory runbook

## Purpose

Stage 1 drift inventory for ECLI policy, validation, runtime, packaging, release, documentation, and rendering boundaries.

Codex may inspect and classify drift. Codex must not perform automatic broad rewrites, release execution, publication, workflow actions, or public-state mutations.

Git, GitHub, workflow, release, publication, and artifact-upload actions are maintainer-owned.

## Drift categories

Track these categories:

* license metadata;
* version metadata;
* docs/commands;
* packaging descriptors;
* release artifact contract;
* runtime/config paths;
* rendering boundary.

## Read-only inspection commands

Use targeted inspection:

```sh
python3 tools/license_guard.py --report logs/license-guard.md
rg -n "version|PACKAGE_VERSION|APP_VERSION|pkgver|Version" pyproject.toml Makefile scripts packaging docs README.md CHANGELOG.md .github/workflows
rg -n "make |uv run|python3 tools/license_guard.py|scripts/|package-|release-|publish-" README.md docs .codex Makefile
rg -n "config.toml|load_config|ConfigService|XDG_CONFIG_HOME|HOME|logging|log" config.toml src/ecli scripts tests docs
rg -n "import curses|from curses|stdscr\\.|refresh\\(|noutrefresh\\(|doupdate\\(|KEY_RESIZE|SIGWINCH|len\\(" src/ecli tests docs .codex
find scripts packaging docs .codex -maxdepth 3 -type f -printf "%p\n"
```

Run only exact commands that are relevant to the drift category under review.

## Output table format

Use this table:

```text
| ID | Category | File/Surface | Evidence | Classification | Owner | Recommended next step |
|---|---|---|---|---|---|---|
| DRIFT-001 | version metadata | packaging/... | observed value differs from pyproject.toml | baseline | build-engineer | prepare narrow fix proposal |
```

## Classification

Use:

* `baseline` — known current drift consistent with accepted audit evidence;
* `new-drift` — newly introduced or outside known baseline;
* `needs-review` — more evidence or maintainer decision required;
* `blocked` — cannot proceed without external input, missing files, or maintainer-owned action.

## Forbidden actions

Codex must not:

* perform automatic broad rewrites;
* edit source code, tests, workflows, or packaging descriptors during drift inventory;
* run `git commit`, `git push`, `git tag`;
* run `gh pr create`, `gh issue edit`, `gh issue close`, `gh issue comment`;
* run `gh workflow run`, `gh run rerun`, `gh run cancel`;
* run `gh release`;
* run `twine upload`, `uv publish`, or `python -m twine upload`;
* run `make release`, `make release-*`, `make publish`, or `make publish-*`.

## Output

Finish with:

```text
Result:
- What was inspected:
- Evidence:
- Commands run:
- Commands blocked:
- Files touched:
- Remaining risks:
- Recommended next step:
```
