<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/runbooks/release.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex release runbook

## Purpose

Stage 1 prepare-only release readiness review for ECLI.

Codex may inspect, draft, and summarize release evidence. Codex is not a release executor. Release authorization and execution are maintainer-owned.

## Version source of truth

Treat `pyproject.toml` as the version source of truth.

Inspect version surfaces read-only:

```sh
rg -n "version|PACKAGE_VERSION|APP_VERSION|pkgver|Version|sed -i" pyproject.toml Makefile scripts packaging .github/workflows README.md CHANGELOG.md docs/release
```

Report any descriptor, script, documentation, or workflow value that can drift from `pyproject.toml`.

## Changelog and release-note review

Inspect:

* `CHANGELOG.md`;
* `docs/release/`;
* release-note drafts;
* version-specific release documents.

Check that release notes match validated behavior and do not claim gates are clean unless validation evidence proves it.

## Artifact contract review

Inspect:

* package console entry points;
* PyInstaller entry behavior;
* Nix, NSIS, Arch, AppImage, Python package, and platform packaging descriptors;
* `flake.nix` and `packaging/nix/package.nix`;
* artifact naming;
* checksum/signing expectations;
* generated metadata expectations;
* tracked descriptor mutation risks.

Use:

```sh
find docs/release packaging scripts .github/workflows -maxdepth 3 -type f -printf "%p\n"
rg -n "artifact|checksum|sha256|sign|release|publish|upload|twine|PyPI|gh release|workflow|Nix|nix|flake" Makefile flake.nix scripts .github/workflows docs README.md CHANGELOG.md pyproject.toml
```

## GitHub Release and PyPI readiness checklist

Prepare a checklist covering:

* validation evidence available;
* version consistency;
* changelog/release notes;
* artifact contract;
* package metadata;
* release notes and manual upload steps;
* maintainer-owned commands still required.

Do not execute checklist items that publish, upload, tag, push, or trigger workflows.

## Forward-only release policy

Release work is forward-only. If evidence is incomplete or drift is found, report the blocker and prepare a corrective checklist. Do not mutate public state to repair a release from Codex.

## Maintainer-only actions

The maintainer owns:

* `git tag`;
* `git push`;
* `gh release`;
* `gh workflow run`;
* `twine upload`;
* `uv publish`;
* `python -m twine upload`;
* artifact upload;
* release target execution;
* publish target execution.

## Forbidden actions

Codex must not run:

* `git commit`, `git push`, `git tag`;
* `gh pr create`, `gh issue edit`, `gh issue close`, `gh issue comment`;
* `gh workflow run`, `gh run rerun`, `gh run cancel`;
* `gh release`;
* `twine upload`, `uv publish`, or `python -m twine upload`;
* `make release`, `make release-*`, `make publish`, or `make publish-*`.

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
