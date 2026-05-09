<!--
Path: docs/contributor/troubleshooting.md
File: troubleshooting.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Troubleshooting

## Symptom Matrix

| Symptom | Likely cause | Commands to run | Expected result | Next step |
|---|---|---|---|---|
| Startup failure | config/logging bootstrap issue | validate config syntax; run startup again | clear parse/init diagnostics | check `docs/config/*` and fix source |
| Config parse failure | malformed user/default/template config | inspect config file and key types | parseable config and valid key types | apply migration/precedence rules |
| Packaging mismatch | wrong output naming/path | run packaging script; inspect `releases/<ver>/` | artifact matches contract | use `docs/release/artifact-contract.md` |
| Missing platform tool | toolchain not installed | check tool command availability | tool found in PATH | install per setup guide |
| Undo/redo regression | known high-risk mutation path | reproduce minimal action sequence | deterministic reproduction case | open issue with sequence + logs |

## Decision Path: Startup Failure

1. Confirm runtime command and environment.
2. Check config parse diagnostics.
3. Validate precedence/fallback behavior.
4. Escalate with logs and config snippet (no secrets).

## Decision Path: Config Parse Failure

1. Validate syntax.
2. Validate key/value types against schema.
3. Apply migration policy for legacy keys.
4. Re-run startup and capture result.

## Decision Path: Packaging Mismatch

1. Run target packaging script.
2. Compare output name/path with artifact contract.
3. Verify checksum generation.
4. Escalate as release-contract drift if mismatch persists.

## Decision Path: Platform Tool Missing

1. Confirm role requirements in `development-setup.md`.
2. Install required toolchain.
3. Re-run build/install flow.

## Decision Path: Undo/Redo Regression Report Preparation

1. Record exact key/action sequence.
2. Record expected vs observed behavior.
3. Attach logs and affected file snippet.
4. Reference architecture contract sections for mutation/history invariants.

## Cross-Doc Navigation

- Config failures: `docs/config/config-schema.md`, `docs/config/config-precedence.md`
- Packaging failures: `docs/release/artifact-contract.md`, `docs/release/artifact-verification.md`
- Runtime/concurrency behaviors: `docs/architecture/runtime-model.md`, `docs/architecture/event-and-concurrency-model.md`
