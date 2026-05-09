<!--
Filename: docs/planning/risk-register.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Risk Register

| Risk | Likelihood | Impact | Severity | Detection | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| Undo/redo regressions during refactor | Medium | High | High | invariant test failures, bug reports | characterization + invariant suites | Core maintainers | Open |
| Artifact naming/packaging drift | Medium | High | High | release CI contract gate | enforce artifact contract checks | Release maintainers | Open |
| Config schema ambiguity | High | High | Critical | schema validation failures, startup warnings | canonical schema + migration policy | Config maintainers | Open |
| Orchestrator coupling blocks safe change | High | Medium/High | High | review churn, regression density | service extraction with parity tests | Core maintainers | Open |
| Concurrency/event contract gaps | Medium | High | High | queue payload/runtime handling errors | typed payload contracts + gateway rules | Core + Integration maintainers | Open |
| Contributor workflow drift | Medium | Medium | Medium | setup/build docs mismatch reports | command verification policy | Contributor maintainers | Open |
| Extension safety boundary ambiguity | Medium | Medium | Medium | extension integration defects | extension guardrails + review checks | Extension maintainers | Open |

## Contingency Notes

- Critical/High risks block release if tied to artifact contract, config parse safety, or core mutation invariants.

## Related Contract References

- Architecture: `docs/architecture/*`
- Config: `docs/config/*`
- Release: `docs/release/*`
- Quality: `docs/quality/*`
