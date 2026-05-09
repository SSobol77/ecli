<!--
Filename: docs/extensions/README.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Extensions Documentation

Defines extension boundaries, runtime contracts, and safety guardrails.

## Authority Map

| File | Authoritative for |
|---|---|
| `plugin-api.md` | extension boundary, lifecycle, capability model |
| `ai-provider-runtime.md` | provider request lifecycle and failure/degradation behavior |
| `diagnostics-model.md` | canonical diagnostics normalization schema |
| `extension-guardrails.md` | safety/security/compatibility guardrails |

## Current Public Stability Stance

- Observed current state: no stable public plugin ABI is implemented.
- Target state: explicit capability-scoped extension contract.
- Validation required: implementation-side API surface inventory for stabilization roadmap.
