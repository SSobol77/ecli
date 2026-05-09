<!--
Path: docs/contributor/README.md
File: README.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Contributor Documentation

Operational entrypoint for contributors, maintainers, packagers, and local debuggers.

## Contributor Authority Map

| File | Authoritative for |
|---|---|
| `development-setup.md` | toolchain prerequisites and environment bootstrap |
| `build-from-source.md` | source build and packaging entrypoint mapping |
| `install.md` | installation flows, support tiers, verification |
| `local-validation.md` | minimum vs maintainer validation commands |
| `troubleshooting.md` | symptom-driven diagnosis and escalation |

## Reader Entrypoints

- **First-time contributor**: `development-setup.md` -> `local-validation.md`
- **Release maintainer**: `build-from-source.md` -> `install.md` -> `local-validation.md`
- **Packaging maintainer**: `build-from-source.md` -> `install.md` -> `troubleshooting.md`
- **Local debugger**: `local-validation.md` -> `troubleshooting.md`

## Cross-Folder Traceability

- Build/install artifacts: `docs/release/artifact-contract.md`
- Config-related runtime issues: `docs/config/*`
- Architecture mutation and concurrency boundaries: `docs/architecture/*`
- Execution priorities and risks: `docs/planning/*`
