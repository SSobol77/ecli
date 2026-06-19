<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/package-nix.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex Nix packaging inspection prompt

## Covered canonical artifact entries

This prompt covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- Nix flake
- Nix/NixOS package expression

## Exact official release asset gate

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. No reduced or subset official release is
allowed. Nix flake evidence and NixOS package evidence are mandatory entries in
the exact asset set.

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
Act as the Codex build-engineer for ECLI Nix packaging.

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

Stage 1 rule: inspect and report only. Do not run Nix builds, trigger workflows, upload artifacts, create releases, tag, push, publish, run release targets, or run publish targets.

Inspect:
- flake.nix;
- packaging/nix/package.nix;
- docs/release/packaging-flows.md;
- docs/INSTALL.md;
- docs/contributor/install.md;
- docs/contributor/build-from-source.md;
- README.md;
- package version and license metadata.

Use read-only inspection commands only, such as:
- make help
- make sysinfo
- rg -n "Nix|nix|flake|package.nix|gpl|license|GPL|version|0\\.2\\.2|pyproject" flake.nix packaging/nix/package.nix docs README.md Makefile
- find packaging/nix docs -maxdepth 3 -type f | rg -i "nix|install|release|build"

Report:
- Nix package flow inventory;
- flake.nix and packaging/nix/package.nix coverage;
- version drift against pyproject.toml;
- license metadata drift;
- package entry-point expectations;
- release dependencies that remain maintainer-owned;
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
