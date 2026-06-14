<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/package-windows.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex Windows packaging inspection prompt

## Covered canonical artifact entries

This prompt covers these entries from the `Canonical 21-Item Platform &
Packaging Artifact Matrix` in `docs/release/artifact-contract.md`:

- Windows portable `.exe`
- Windows NSIS installer `.exe`

Use with:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT"
```

Prompt:

```text
Act as the Codex build-engineer for ECLI Windows packaging.

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
11. docs/install/windows.md if present
12. pyproject.toml
13. Makefile

Claude-specific files under .claude/ and CLAUDE.md are not Codex authority.

Stage 1 rule: inspect and report only. Do not run Windows builds, trigger workflows, upload artifacts, create releases, tag, push, publish, run release targets, or run publish targets.

Inspect:
- packaging/windows/;
- NSIS descriptors if present;
- Windows workflow and release docs if present;
- PyInstaller Windows expectations if documented;
- icon/resource packaging references;
- artifact naming and license metadata.

Use read-only inspection commands only, such as:
- make help
- make sysinfo
- rg -n "Windows|windows|NSIS|nsis|PyInstaller|pyinstaller|icon|resource|license|GPL|artifact|PACKAGE_VERSION|version" Makefile scripts packaging docs .github/workflows README.md CHANGELOG.md
- find packaging/windows -maxdepth 3 -type f -printf "%p\n"
- find .github/workflows docs -maxdepth 3 -type f | rg -i "windows|release|install"

Report:
- Windows package flow inventory;
- NSIS and PyInstaller expectations;
- artifact naming expectations;
- icon/resource references;
- version drift against pyproject.toml;
- license metadata drift;
- workflow or release dependencies that remain maintainer-owned;
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
