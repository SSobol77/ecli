<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/release-runbook.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Release Runbook

This runbook is prepare-only.

Claude Code must not publish ECLI releases in Stage 1.

## Release mode

Stage 1 release work may only produce:

- release readiness checklists,
- version consistency reports,
- artifact contract reports,
- changelog drafts,
- release note drafts,
- manual runbooks.

## Forbidden commands

Do not run:

```sh
git commit
git push
git tag
twine upload
gh workflow run
gh release create
gh release upload
make release
make release-*
make publish
make publish-*
```

## Version consistency report

Use this format:

```text
Version consistency report

Source of truth:
Declared version:
Checked files:
Hard-coded surfaces:
Generated surfaces:
Drift:
Risk:
Recommended correction:
Publishing attempted: no
```

## Prepare-only release summary

Every release-readiness task must end with:

```text
Prepare-only release summary:
- Version source:
- Version drift:
- Artifact contract:
- Workflow risks:
- Publishing commands blocked:
- Manual actions required:
- Recommended next step:
```