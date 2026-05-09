<!--
Path: docs/extensions/extension-guardrails.md
File: extension-guardrails.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Extension Guardrails

## Guardrail Matrix

| Guardrail | Applies to | Why | Enforcement candidate |
|---|---|---|---|
| No direct state mutation | all extensions | protects core invariants | review checklist + contract tests |
| No UI-thread blocking I/O | async/network extensions | keep editor responsive | runtime timeout tests |
| Failure isolation | all extensions | avoid core crash from extension error | event boundary handling |
| Secret hygiene | provider/network extensions | prevent credential leakage | log redaction checks |
| Subprocess boundary control | subprocess/command extensions | prevent unmanaged long-running processes | process lifecycle audit |
| Compatibility declaration | extension packages | avoid hidden breakage | version metadata policy |

## Safety Rule Classes

- Mutation safety
- Event-loop responsiveness
- Failure isolation

## Security Rule Classes

- credential source control
- subprocess boundary control
- sensitive log suppression

## Compatibility / Stability Rule Classes

- explicit version/stability declaration
- non-public API usage discouraged and unsupported

## Prohibited Extension Behaviors

| Behavior | Violates guardrail | Rationale |
|---|---|---|
| Direct writes to editor internal state structures | No direct state mutation | state invariants must be protected |
| Spawning unmanaged long-running subprocesses on UI thread | Subprocess boundary control | blocks editor responsiveness |
| Bypassing diagnostics normalization model | Data integrity | breaks diagnostic contract; all diagnostics must pass normalization |
| Reading/writing secrets from ad-hoc undocumented paths | Secret hygiene | credential leakage risk |

## Review Checklist

- Does extension mutate state only through allowed command path?
- Does extension call blocking I/O outside UI thread?
- Does extension expose sensitive data in logs/errors?
- Does extension declare compatibility/stability expectations?
- Does extension handle failures gracefully without crashing the core?

## CI/Review Enforcement Candidates

- targeted contract tests for mutation and event behavior
- static import/dependency checks for forbidden module access
- lint rules for prohibited direct state writes in extension adapters
