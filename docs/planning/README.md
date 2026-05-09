<!--
Path: docs/planning/README.md
File: README.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
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
