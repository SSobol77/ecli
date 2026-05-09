<!--
Path: docs/planning/engineering-plan.md
File: engineering-plan.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Engineering Plan

## Scope Boundary

- In scope: correctness, release determinism, architecture decoupling, schema hardening, contributor operability.
- Out of scope: one-shot rewrite and immediate stable plugin ABI guarantees.

## Workstream Plan Matrix

| Workstream | Goal | Deliverables | Dependencies | Evidence | Exit gate |
|---|---|---|---|---|---|
| A Correctness | eliminate critical runtime defects | config parse stability, undo/redo invariants | baseline tests | test reports + repro closure | critical defect class closed |
| B Release Reliability | deterministic artifact outputs | artifact contract checks, workflow alignment | release docs + scripts | CI release runs | contract-enforced release |
| C Quality Baseline | actionable validation gates | lint/format/test path and documented expectations | toolchain/setup | CI + local evidence | minimum quality gate present |
| D Architecture Evolution | reduce coupling safely | service extraction slices, panel boundary hardening | A + C | parity tests + review checks | coupling reduction without regression |
| E Extension/Diagnostics Hardening | enforce extension runtime safety | extension contracts + diagnostics schema normalization | D baseline | integration tests + docs evidence | extension safety gate defined |

## Acceptance Gates

- Gate 1: critical defects addressed (A)
- Gate 2: release artifact contract enforced (B)
- Gate 3: baseline validation reproducible (C)
- Gate 4: refactor-safe architecture slices proven (D)
- Gate 5: extension boundary contracts operational (E)

## Rollback / Containment Notes

- If a refactor slice breaks invariants, rollback to previous stable slice and preserve contract test additions.
- If release contract checks fail, block publish and keep prior stable artifacts.

## Cross-Doc Governance Links

- Architecture contracts: `docs/architecture/*`
- Config contracts: `docs/config/*`
- Release contracts: `docs/release/*`
- Quality gates: `docs/quality/*`
- Contributor procedures: `docs/contributor/*`
