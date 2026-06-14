<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/build-runbook.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Build Runbook

This runbook defines non-publishing build and artifact-contract behavior.

## Build policy

Build automation may inspect and validate build paths. It must not publish artifacts.

Allowed build work:

- inspect `Makefile`,
- inspect `scripts/`,
- inspect `packaging/`,
- run shell syntax checks,
- run non-publishing build validation,
- report artifact naming drift.

Forbidden build work:

- release upload,
- PyPI upload,
- GitHub Release creation,
- git tag,
- git push,
- git commit,
- `make release*`,
- `make publish*`.

## Required discovery commands

Use:

```sh
make help
make sysinfo
```

Use script syntax checks:

```sh
sh -n scripts/*
bash -n scripts/*
```

## Artifact contract report

Every build validation must report:

```text
Build artifact contract report

Target:
Command:
Version source:
Expected artifact:
Actual artifact:
Checksum:
Status:
Drift detected:
Publishing attempted: no
Notes:
```

## Version policy

`pyproject.toml` is the version source of truth.

Any hard-coded version in packaging descriptors must be reported as drift unless it is generated from the canonical source.
