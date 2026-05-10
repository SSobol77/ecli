<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/planning/documentation-modernization-plan.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Documentation Modernization Plan

**Status: Completed** — The following sections document the modernization work that has been finished.

## A. What Was Wrong in Previous Model

- Top-level docs mixed architecture, audit, planning, and contributor guidance.
- No normative hierarchy existed for architecture vs release vs execution docs.
- Build/install docs were stale or placeholder-driven.
- FreeBSD packaging notes were isolated and not integrated into release governance.

## B. Missing Categories (Now Added)

- Product scope/compatibility layer
- Config schema and precedence layer
- Quality and security gate layer
- Extension boundary layer
- Explicit archive policy

## C. Duplicate/Conflated Categories (Resolved)

- architecture snapshot + roadmap + engineering plan were previously co-mingled in authority.
- now split into:
  - architecture contracts (`architecture/`)
  - planning execution (`planning/`)
  - release contract (`release/`)
  - contributor workflows (`contributor/`)

## D. Why New Structure Is Better

- clear ownership and authority boundaries
- deterministic discoverability for contributors
- explicit current vs target architecture separation
- explicit normative contracts for release artifacts and quality gates
