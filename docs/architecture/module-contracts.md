<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/architecture/module-contracts.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Module Contracts (Normative)

## Core Contract Matrix

| Module / Concept | Owner | May mutate state? | May call integrations? | Must not do |
|---|---|---:|---:|---|
| `EditorState` concept | Core maintainers | Yes | No | import UI/integration concerns |
| `Ecli` (current) | Core maintainers | Yes | Yes | add new uncontracted mutation paths |
| `History` | Core maintainers | Yes (through contract path) | No | assume undefined editor fields |
| `DrawScreen` | UI maintainers | No | No | mutate domain state |
| `KeyBinder` | UI maintainers | No (target) | No | perform integration/network work |
| `PanelManager` + panels | UI maintainers | No direct (target) | No direct | bypass command gateway |
| `GitBridge` | Integration maintainers | No direct | Yes | direct state mutation from worker thread |
| `LinterBridge` | Integration maintainers | No direct | Yes | bypass event re-entry |
| `AI` adapters | Integration maintainers | No | Yes | leak secret-bearing data |

## Dependency Policy Matrix

| Source layer | Allowed dependencies | Forbidden dependencies |
|---|---|---|
| UI | Read model, command gateway | direct state writes, direct integration mutation path |
| Command layer | services, state read checks | network/provider calls |
| Services | state model, history contracts | UI rendering logic |
| Integrations | event gateway, external systems | direct mutation of editor state |

## State Access Rights

| Actor | Read rights | Mutate rights | Path |
|---|---|---|---|
| Renderer (`DrawScreen`) | Yes | No | read projection only |
| Input handlers (`KeyBinder`, panels) | Limited context read | No direct | command gateway |
| Domain services | Yes | Yes | service API |
| Integration workers | No direct | No direct | publish events only |

## Command Gateway Interface Expectations

- Must accept typed command payload.
- Must validate preconditions and reject malformed commands.
- Must route one mutation intent to one owning service.
- Must emit consistent mutation outcome for redraw/status logic.

## Integration Result Re-entry Expectations

| Integration class | Re-entry method | Mutation permission |
|---|---|---|
| Git | queue event -> UI consumer -> command/core update | UI-thread only |
| Lint/LSP | queue message -> normalization -> UI consumer | UI-thread only |
| AI provider | async result queue -> UI consumer | UI-thread only |

## Code Review Checklist

- Does this change add a direct write path outside command/service flow?
- Does this UI change add integration dependencies?
- Does this integration callback touch state directly?
- Does this change preserve current/target distinction in docs and code comments?

## CI / Static Enforcement Candidates

| Candidate | Scope | Enforcement target |
|---|---|---|
| Dependency direction lint | imports | forbid UI -> integration direct mutation paths |
| Mutation path checks | selected modules | block direct state writes outside gateway/services |
| Contract test suite | behavior | verify gateway-only mutation behavior |

## Traceability: Risk -> Contract -> Enforcement Point

| Known architecture risk | Governing contract section | Expected enforcement point |
|---|---|---|
| Oversized orchestrator | dependency policy + gateway expectations | PR review + refactor roadmap |
| Weak ownership boundaries | core contract matrix + state access rights | review checklist + service extraction tests |
| Weak panel boundaries | state access rights + panel prohibition | panel contract tests |
| Loose concurrency details | integration re-entry expectations | queue/event contract tests |
