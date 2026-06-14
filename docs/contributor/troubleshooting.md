<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/contributor/troubleshooting.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Troubleshooting

## Symptom Matrix

| Symptom | Likely cause | Commands to run | Expected result | Next step |
|---|---|---|---|---|
| Startup failure | config/logging bootstrap issue | validate config syntax; run startup again | clear parse/init diagnostics | check `docs/config/*` and fix source |
| Config parse failure | malformed user/default/template config | inspect config file and key types | parseable config and valid key types | apply migration/precedence rules |
| Packaging mismatch | wrong output naming/path | run packaging script; inspect `releases/<ver>/` | artifact matches contract | use `docs/release/artifact-contract.md` |
| Missing platform tool | toolchain not installed | check tool command availability | tool found in PATH | install per setup guide |
| `makensis` missing | NSIS is not installed or not in `PATH` | `makensis /VERSION` | NSIS version prints | install NSIS and re-run Windows packaging |
| `hdiutil` missing | not running on macOS or Xcode CLT/system tools unavailable | `hdiutil help` | command help prints | run DMG packaging on macOS runner/host |
| `codesign` missing | Xcode CLT not installed | `codesign --version` | version prints | install Xcode Command Line Tools; signing remains Phase 1+ |
| `twine` missing | development dependencies not installed | `python -m twine --version` | twine version prints | run `make install` or install `.[dev]` |
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

## Decision Path: Release Validation Tool Missing

1. Run the failing `validate-*-contract` target directly.
2. If `twine` is missing, install development dependencies from `pyproject.toml`.
3. If `makensis` is missing, install NSIS and ensure its install directory is in `PATH`.
4. If `hdiutil` or `codesign` is missing, move the macOS packaging job to a macOS host with Xcode Command Line Tools.

## Decision Path: Undo/Redo Regression Report Preparation

1. Record exact key/action sequence.
2. Record expected vs observed behavior.
3. Attach logs and affected file snippet.
4. Reference architecture contract sections for mutation/history invariants.

## Cross-Doc Navigation

- Config failures: `docs/config/config-schema.md`, `docs/config/config-precedence.md`
- Packaging failures: `docs/release/artifact-contract.md`, `docs/release/artifact-verification.md`
- Runtime/concurrency behaviors: `docs/architecture/runtime-model.md`, `docs/architecture/event-and-concurrency-model.md`
