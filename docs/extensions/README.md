<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/extensions/README.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
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
