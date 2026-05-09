<!--
Path: docs/architecture/README.md
File: README.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
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

## Explicit Authority Pointers

- Dependency rules: `target-architecture.md` + `module-contracts.md`
- Mutation rules: `module-contracts.md`
- Runtime lifecycle: `runtime-model.md`
- Queue/event ownership: `event-and-concurrency-model.md`
- Integration degradation semantics: `integration-boundaries.md`

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
