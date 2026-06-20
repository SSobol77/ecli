<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/PIPELINE.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# ECLI Codex Pipeline

This is the Codex-specific prepare-only pipeline.

Claude Code uses `.claude/PIPELINE.md`.
Codex uses `.codex/PIPELINE.md`.

Do not mix the two.

## Authority model

Codex may inspect, diagnose, validate, summarize, and draft.

The maintainer owns:

* git commits,
* git pushes,
* git tags,
* GitHub issue writes,
* GitHub PR creation,
* GitHub workflow triggers,
* GitHub releases,
* PyPI publishing,
* release artifact upload.

## Recommended Codex execution mode

For Stage 1 inventory and diagnostics:

```sh
codex exec --sandbox read-only --ephemeral --cd .
```

Use output redirection from the shell when a report file is needed:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT" > logs/report.md
```

Do not ask Codex to write files while using read-only sandbox.

## Stage 0 — Preflight

Maintainer:

```sh
git status --short --branch
```

Codex:

```sh
codex exec --sandbox read-only --ephemeral --cd . \
  "Read AGENTS.md, CODEX.md, .codex/PIPELINE.md, audit-report.md, docs/planning/roadmap.md."
Report current Stage, Stage 2 gates, and whether ECLI is GPL-2.0-only.
Do not edit files. Do not run git or gh."
```

Gate:

```text
Stage = 1
License = GPL-2.0-only
No git/release action by Codex
```

## Stage A — License guard

Maintainer runs the actual guard:

```sh
python3 tools/license_guard.py --report logs/license-guard.md
```

Codex may summarize:

```sh
codex exec --sandbox read-only --ephemeral --cd . \
  "Read logs/license-guard.md and summarize: missing headers, wrong SPDX values, legacy license residue, and final PASS/FAIL. Do not edit files."
```

Gate:

```text
Missing headers = 0
Wrong SPDX = 0
Legacy license residue = 0
```

## Stage B — Validation summary

Maintainer runs validation:

```sh
uv run pytest -q tests/packaging tests/test_version_resolution.py
uv run python scripts/check_runtime_imports.py
uv run pytest -ra -q
```

Codex may summarize pasted output or log files.

## Stage C — Rendering inventory

Use `.codex/runbooks/render-inventory.md`.

Codex must remain read-only unless maintainer explicitly authorizes Stage 1b or Stage 2.

## Stage D — Release prepare-only

Codex may inspect versions, docs, packaging descriptors, and release notes.
Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. Release publication is blocked unless
`scripts/verify_release_assets.py` verifies the exact top-level asset set under
`releases/<version>/`. Checksum sidecars are verification evidence, not GitHub
Release assets.

Codex must not:

* tag,
* push,
* create release,
* upload artifacts,
* publish to PyPI,
* trigger workflows.

The maintainer performs release actions manually.
