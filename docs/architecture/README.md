<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/architecture/README.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Architecture Documentation

Defines architecture authority, ownership contracts, lifecycle semantics, and migration-safe target design.

## Architecture-Internal Authority Map

| File | Class | Authoritative for |
|---|---|---|
| `current-architecture.md` | Descriptive | observed structure, current dependencies, coupling hotspots |
| `target-architecture.md` | Normative target | dependency direction, write-path rules, migration invariants |
| `module-contracts.md` | Normative contract | ownership, mutation rights, dependency policy |
| `runtime-model.md` | Operational | startup/steady-state/shutdown lifecycle |
| `event-and-concurrency-model.md` | Operational + contract | queue ownership, payload expectations, redraw triggers |
| `integration-boundaries.md` | Normative + operational | integration isolation, degradation semantics, failure consequence |
| `panel-console-stabilization.md` | Normative boundary | 0.2.x F11/PySH console direction and full PTY terminal emulator rejection |

## Explicit Authority Pointers

- Dependency rules: `target-architecture.md` + `module-contracts.md`
- Mutation rules: `module-contracts.md`
- Runtime lifecycle: `runtime-model.md`
- Queue/event ownership: `event-and-concurrency-model.md`
- Integration degradation semantics: `integration-boundaries.md`
- F11/PySH panel-console boundary: `panel-console-stabilization.md`

## Reader Entrypoints

- **Maintainer path**: `current-architecture.md` -> `module-contracts.md` -> `event-and-concurrency-model.md`
- **Contributor path**: `current-architecture.md` -> `runtime-model.md`
- **Refactor path**: `current-architecture.md` -> `target-architecture.md` -> `module-contracts.md`
- **Release impact path**: `integration-boundaries.md` -> `runtime-model.md` -> `docs/release/artifact-contract.md`

## What Is Intentionally Not Defined Here

- Artifact naming contracts (`docs/release/*`)
- Config key-level schema contracts (`docs/config/*`)
- Planning/scheduling commitments (`docs/planning/*`)
- Contributor setup/installation procedures (`docs/contributor/*`)

## Traceability to Known Repository Risks

| Known risk | Governing architecture document |
|---|---|
| Oversized `Ecli` orchestrator | `current-architecture.md`, `target-architecture.md` |
| Weak ownership boundaries | `module-contracts.md` |
| Weak panel mutation boundaries | `module-contracts.md` |
| Loose concurrency/event contracts | `event-and-concurrency-model.md` |
| Integration failure consequence ambiguity | `integration-boundaries.md` |
