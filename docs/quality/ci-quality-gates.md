<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/quality/ci-quality-gates.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# CI Quality Gates

## Gate Classes

- Static quality: lint/format/type checks
- Test quality: unit/integration/smoke suites
- Release quality: artifact contract validation
- Documentation quality: stale command/path checks for contributor/release docs

## Current-State Gaps

- CI references test paths that are not currently present in repository baseline.
- Coverage/report configuration may drift from actual generated paths.

## Normative Rules

- A release tag build must fail if artifact naming contract is violated.
- When build or release commands are changed (e.g., in scripts or CI configuration), update the corresponding contributor and release documentation.
- Config syntax validation must be enforced in CI.
