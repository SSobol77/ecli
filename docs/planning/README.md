<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/planning/README.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Planning Documentation

Planning is non-normative for architecture contracts, but normative for execution governance and delivery tracking.

## Planning Authority Map

| File | Authoritative for |
|---|---|
| `roadmap.md` | work items, phase commitments, ownership metadata |
| `execution-sequencing.md` | order of execution, dependencies, go/no-go gates |
| `risk-register.md` | risk tracking, mitigation ownership, status |
| `engineering-plan.md` | workstream deliverables, gates, evidence expectations |
| `migration-map.md` | doc migration state and unresolved leftovers |
| `documentation-modernization-plan.md` | scope and success measures for doc governance |
| `documentation-dod.md` | acceptance criteria for documentation completeness |

## Cross-Folder Relationship

- architecture contracts: `docs/architecture/*`
- config contracts: `docs/config/*`
- release contracts: `docs/release/*`
- quality gates: `docs/quality/*`
- contributor operations: `docs/contributor/*`

Planning items must link to governing docs in those folders.
