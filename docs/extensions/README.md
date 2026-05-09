<!--
Path: docs/extensions/README.md
File: README.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
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
