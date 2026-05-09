<!--
Path: docs/extensions/plugin-api.md
File: plugin-api.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Plugin API Boundary

## Current-State Disclaimer

- Observed current state: no stable plugin API is formally published.
- Internal symbols are implementation details and non-public.

## Target Extension Lifecycle

```mermaid
flowchart LR
  REG[Register extension] --> CAP[Capability negotiation]
  CAP --> INIT[Initialize adapter/hooks]
  INIT --> RUN[Active runtime]
  RUN --> ERR[Failure handling/isolation]
  ERR --> STOP[Disable/unload]
```

## Extension Point Matrix

| Extension point | Current state | Target contract | Stability | Notes |
|---|---|---|---|---|
| Command/action hooks | implicit/internal | explicit registration API | Unstable -> Planned stable | must route through command gateway |
| Panel extensions | internal-only | panel capability registration | Unstable -> Planned stable | no direct state writes |
| Diagnostics providers | partially implicit via integrations | normalized diagnostics adapter API | Unstable -> Planned stable | must map to canonical schema |
| AI provider adapters | concrete internal adapters exist | capability-scoped provider interface | Internal stable only | secrecy and timeout contract required |

## Capability Contract Table

| Capability | Allowed? | Through what interface? | Forbidden shortcut |
|---|---:|---|---|
| register command | Target yes | command registration API | direct mutation callbacks |
| register panel | Target yes | panel registration API | direct state ownership |
| publish diagnostics | Target yes | diagnostics adapter API | bypass normalization |
| perform network call | Limited | provider adapter boundary | direct UI-thread blocking |

## Sync vs Async Expectations

- Sync extension operations must be quick and non-blocking.
- Async extension operations must publish results through event gateway semantics.

## Error/Failure Contract

- Extension failure must be isolated from core editor runtime.
- Failed extension path should degrade feature behavior, not crash core loop.

## Compatibility Notes

- Until versioned API is published, extension compatibility is best-effort and non-guaranteed.
