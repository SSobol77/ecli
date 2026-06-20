<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/release.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex prepare-only release review prompt

## Covered canonical artifact entries

This prompt owns the aggregate release surface, covering this entry from the
`Canonical 21-Item Platform & Packaging Artifact Matrix` in
`docs/release/artifact-contract.md`:

- GitHub Actions release/workflow contract map

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
Act as the Codex release-engineer for ECLI.

Read, in order:
1. AGENTS.md
2. CODEX.md
3. .codex/PIPELINE.md
4. .codex/roles/release-engineer.md
5. .codex/roles/build-engineer.md when artifact contract evidence is involved
6. .codex/roles/quality-engineer.md when validation evidence is involved
7. .codex/runbooks/release.md if present
8. .codex/runbooks/drift.md if present
9. audit-report.md
10. docs/release/
11. pyproject.toml
12. CHANGELOG.md
13. Makefile
14. packaging descriptors and release scripts

Claude-specific files under .claude/ and CLAUDE.md are not Codex authority.

Stage 1 rule: prepare-only release review. Do not execute a release.

Inspect:
- version source of truth from pyproject.toml;
- CHANGELOG.md;
- release docs under docs/release/;
- packaging descriptors;
- artifact contract;
- exact 21 GitHub Release asset gate;
- GitHub and PyPI readiness.

Use read-only inspection commands only, such as:
- make help
- make sysinfo
- rg -n "version|PACKAGE_VERSION|APP_VERSION|pkgver|Version|sed -i" pyproject.toml Makefile scripts packaging .github/workflows README.md CHANGELOG.md docs/release
- rg -n "release|publish|upload|tag|gh release|twine|uv publish|workflow|Trusted Publisher|PyPI" Makefile scripts .github/workflows docs README.md CHANGELOG.md pyproject.toml
- find docs/release packaging scripts .github/workflows -maxdepth 3 -type f -printf "%p\n"

Explicitly forbidden:
- git tag;
- git push;
- gh release;
- gh workflow run;
- twine upload;
- uv publish;
- python -m twine upload;
- artifact upload by Codex;
- release targets;
- publish targets.

Report:
- release readiness;
- version consistency;
- changelog/release-note gaps;
- artifact contract findings;
- GitHub/PyPI readiness;
- maintainer-only actions;
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
