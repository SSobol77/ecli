<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/planning/migration-map.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Documentation Migration Map

## Granular Migration Table

| Old file | New location(s) | Migration type | Status | Validation notes |
|---|---|---|---|---|
| `docs/architecture.md` | `docs/architecture/current-architecture.md`, `target-architecture.md`, `module-contracts.md` | split + rewrite | Complete | traceability and matrix coverage added |
| `docs/audit_report.md` | archived + mapped into planning/config/release docs | archive + redistribute | Complete | risk mapping maintained in `risk-register.md` |
| `docs/roadmap.md` | `docs/planning/roadmap.md` | rewrite | Complete | phase governance expanded |
| `docs/engineering_task.md` | `docs/planning/engineering-plan.md`, `execution-sequencing.md` | split + rewrite | Complete | execution gates added |
| `docs/BUILD_FROM_SOURCE.md` | `docs/contributor/build-from-source.md` | rewrite | Complete | operational matrix added |
| `docs/INSTALL.md` | `docs/contributor/install.md` | rewrite | Complete | support matrix added |
| `docs/freebsd-pkg-build-scripts-list.md` | `docs/release/packaging-flows.md` | normalize + merge | Complete | governance integrated with release contract |

## Unresolved Leftovers

- Validation-required details for exact legacy config key inventory remain open and tracked in `docs/config/config-migration-policy.md`.

## Archive Status Notes

- Legacy placeholders in `docs/archive/` are historical pointers only.
- Active references must target non-archive docs.
