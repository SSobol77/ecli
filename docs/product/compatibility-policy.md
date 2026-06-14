<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/product/compatibility-policy.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Compatibility Policy

## Configuration Compatibility

- Existing user config must remain loadable when possible.
- Breaking schema changes must include migration notes and fallback behavior.

## Command and Workflow Compatibility

- Contributor-facing build/release command changes must be documented in `contributor/` and `release/` in the same change set.

## Artifact Compatibility

- Artifact naming must follow `release/artifact-contract.md`.
- Renaming output patterns without policy updates is prohibited.
