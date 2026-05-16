<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/planning/risk-register.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Risk Register

| Risk | Likelihood | Impact | Severity | Detection | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| Undo/redo regressions during refactor | Medium | High | High | invariant test failures, bug reports | characterization + invariant suites | Core maintainers | Open |
| Artifact naming/packaging drift | Low | High | Medium | release CI contract gate | Phase 0 contract targets plus Phase 1 macOS/Windows/PyPI release workflow validation | Release maintainers | Mitigated in Phase 1 |
| Config schema ambiguity | High | High | Critical | schema validation failures, startup warnings | canonical schema + migration policy | Config maintainers | Open |
| Orchestrator coupling blocks safe change | High | Medium/High | High | review churn, regression density | service extraction with parity tests | Core maintainers | Open |
| Concurrency/event contract gaps | Medium | High | High | queue payload/runtime handling errors | typed payload contracts + gateway rules | Core + Integration maintainers | Open |
| Contributor workflow drift | Medium | Medium | Medium | setup/build docs mismatch reports | command verification policy | Contributor maintainers | Open |
| Extension safety boundary ambiguity | Medium | Medium | Medium | extension integration defects | extension guardrails + review checks | Extension maintainers | Open |
| Static PyPI token exposure | Medium | High | High | secret scanning, release workflow audit, PyPI project event history | keep token scoped to `ecli-editor`; migrate to PyPI Trusted Publishers/OIDC in a later release | Release maintainers | New Phase 1 residual |
| Unsigned Windows binary user friction | High | Medium | Medium | user install reports, SmartScreen prompts | document SmartScreen path; add Azure Trusted Signing or EV certificate in a later release | Release maintainers | New Phase 1 residual |
| macOS non-notarized first launch friction | High | Medium | Medium | user install reports, Gatekeeper prompts | document Gatekeeper workaround; add Developer ID signing, hardened runtime, notarization, and stapling in a later release | Release maintainers | New Phase 1 residual |
| FreeBSD package polish deferred | Medium | Medium | Medium | FreeBSD release validation, package metadata audit | keep canonical Phase 0 FreeBSD package flow functional; schedule manifest polish and canonical naming audit in Workstream D | Release maintainers | Deferred |
| License metadata drift | Low | Medium | Low | SPDX/header scan, package metadata review | PR #17 normalized Apache-2.0 headers and project-owned license metadata | Release maintainers | Mitigated in Phase 1 |

## Contingency Notes

- Critical/High risks block release if tied to artifact contract, config parse safety, or core mutation invariants.
- Current releases accept documented trust-friction risk for unsigned Windows
  artifacts and ad-hoc signed macOS artifacts. These risks must be closed before
  claiming production-grade first-launch trust.
- Static PyPI token exposure is acceptable only as a Phase 1 bridge. Treat OIDC
  migration as a later release-readiness item, not a long-term architecture.

## Related Contract References

- Architecture: `docs/architecture/*`
- Config: `docs/config/*`
- Release: `docs/release/*`
- Quality: `docs/quality/*`
