<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/contributor/README-contributor.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Contributor Documentation

Operational entrypoint for contributors, maintainers, packagers, and local debuggers.

## Contributor Authority Map

| File | Authoritative for |
|---|---|
| `development-setup.md` | toolchain prerequisites and environment bootstrap |
| `build-from-source.md` | source build and packaging entrypoint mapping |
| `install.md` | installation flows, support tiers, verification |
| `local-validation.md` | minimum vs maintainer validation commands |
| `troubleshooting.md` | symptom-driven diagnosis and escalation |

## Reader Entrypoints

- **First-time contributor**: `development-setup.md` -> `local-validation.md`
- **Release maintainer**: `build-from-source.md` -> `install.md` -> `local-validation.md`
- **Packaging maintainer**: `build-from-source.md` -> `install.md` -> `troubleshooting.md`
- **Local debugger**: `local-validation.md` -> `troubleshooting.md`

## Cross-Folder Traceability

- Build/install artifacts: `docs/release/artifact-contract.md`
- Config-related runtime issues: `docs/config/*`
- Architecture mutation and concurrency boundaries: `docs/architecture/*`
- Execution priorities and risks: `docs/planning/*`
