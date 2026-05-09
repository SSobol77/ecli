<!--
Filename: docs/product/compatibility-policy.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
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
