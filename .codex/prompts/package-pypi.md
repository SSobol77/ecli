<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/package-pypi.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex PyPI packaging inspection prompt

## Covered canonical artifact entries

This prompt covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- PyPI wheel
- PyPI source distribution

## Exact official release asset gate

Every official ECLI release publishes exactly 21 physical GitHub Release assets,
one per canonical matrix entry. No reduced or subset official release is
allowed. The PyPI wheel and source distribution are two required entries in the
same exact asset set.

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
Act as the Codex build-engineer for ECLI PyPI packaging.

Read, in order:
1. AGENTS.md
2. CODEX.md
3. .codex/PIPELINE.md
4. .codex/roles/build-engineer.md
5. .codex/roles/release-engineer.md when release-readiness evidence is relevant
6. .codex/runbooks/build.md if present
7. .codex/runbooks/release.md if present
8. .codex/runbooks/drift.md if present
9. audit-report.md
10. docs/release/artifact-contract.md
11. docs/release/packaging-flows.md
12. pyproject.toml
13. README.md
14. LICENSE
15. CHANGELOG.md
16. scripts/publish_pypi.py

Claude-specific files under .claude/ and CLAUDE.md are not Codex authority.

Stage 1 rule: inspect and report only. Do not publish to PyPI, upload artifacts, create releases, trigger workflows, tag, push, run release targets, or run publish targets.

Inspect:
- pyproject.toml;
- package name and version metadata;
- README.md;
- LICENSE;
- CHANGELOG.md;
- scripts/publish_pypi.py (maintainer-owned publish guard; never uploads; supports --dry-run);
- release docs related to PyPI;
- source distribution and wheel expectations;
- Trusted Publisher assumptions if documented.

Use read-only inspection commands only, such as:
- make help
- make sysinfo
- rg -n "name =|version =|license|license-files|readme|classifiers|project.scripts|wheel|sdist|twine|publish|PyPI|Trusted Publisher|pypi" pyproject.toml README.md LICENSE CHANGELOG.md scripts docs Makefile .github/workflows
- rg -n "package-pypi|publish-pypi|PYPI_|twine|build --outdir|Trusted Publisher" Makefile scripts docs .github/workflows

Explicitly forbidden:
- twine upload;
- uv publish;
- python -m twine upload;
- GitHub release commands;
- workflow triggers;
- git tag;
- git push;
- artifact upload by Codex;
- release targets;
- publish targets.

Report:
- PyPI package metadata;
- source distribution and wheel expectations;
- README/license/changelog readiness;
- Trusted Publisher assumptions if documented;
- version drift against pyproject.toml;
- publication commands that remain maintainer-owned;
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
