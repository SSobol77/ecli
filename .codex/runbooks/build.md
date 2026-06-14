<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/runbooks/build.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex build runbook

## Purpose

Stage 1 build target discovery, packaging inspection, and non-publishing build validation for ECLI.

This runbook is for prepare-only build review. Codex may inspect build targets, scripts, and descriptors; summarize artifact contracts; and identify drift. Codex must not publish, upload, tag, push, trigger workflows, or run release/publish targets.

Git, GitHub, workflow, release, publication, and artifact-upload actions are maintainer-owned.

## Read-only discovery commands

Use exact repository commands for build discovery:

```sh
make help
make sysinfo
```

Inspect scripts and packaging descriptors read-only:

```sh
find scripts -maxdepth 2 -type f -printf "%p\n"
find packaging -maxdepth 3 -type f -printf "%p\n"
rg -n "version|PACKAGE_VERSION|sed -i|twine|publish|release|gh release|workflow|artifact|license" pyproject.toml Makefile flake.nix scripts packaging .github/workflows docs
```

Do not use broad build commands. Before discussing any build target, inspect its body in `Makefile` and relevant scripts.

## Non-publishing build validation policy

Stage 1 build work may validate local build paths only when the target is known to be non-publishing and non-mutating. Prefer inspection over execution.

Before any local package target is considered, confirm:

1. the target does not publish or upload artifacts;
2. the target does not create or edit GitHub Releases;
3. the target does not trigger workflows;
4. the target does not tag, push, or commit;
5. the target does not mutate tracked packaging descriptors as a side effect.

If any condition is uncertain, classify the target as `needs-review` and do not run it.

## Artifact contract reporting

Report:

* artifact name and path expectations;
* version source and drift from `pyproject.toml`;
* entry-point consistency;
* license metadata consistency;
* packaging descriptor mutation risks;
* platform-specific dependencies;
* macOS, Windows, and Nix active-surface coverage;
* maintainer-only release or upload steps.

AUD-003 requires `pyproject.toml` to remain the version source of truth.

## Forbidden actions

Codex must not:

* mutate tracked packaging descriptors as a side effect of build preparation;
* upload artifacts;
* publish packages;
* run release or publish targets;
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
