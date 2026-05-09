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
