<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/architecture/extensions-layer.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Extensions Layer

## Status

- Class: Normative architecture contract.
- Milestone: v0.3.0 — Extensions Foundation.
- Scope of this document (issue #97): architecture contract only. No code, no
  imported asset tree, no runtime, no packaging implementation changes.

This document defines the **ECLI Extensions Layer** boundary before any asset is
imported. It is the authority for what `src/ecli/extensions/` is, what may live
there, and how ECLI is allowed to consume it. It exists so that issue #98 (asset
import) and later issues land against a contract that is already agreed.

> Current state: `src/ecli/extensions/` does not exist yet. This contract is
> written ahead of the import so the import is deterministic and reviewable.

## Definition

The ECLI Extensions Layer is the bounded location and contract for **imported,
VS Code / TextMate-compatible, data-only assets** that ECLI uses to drive editor
quality features: syntax highlighting, readable themes, a diagnostics/linter
path, snippets, and language-configuration metadata.

- Imported VS Code / TextMate-compatible assets live under
  `src/ecli/extensions/`.
- `src/ecli/extensions/` is the **only** approved location for imported
  extension assets. Do not invent `vendor/`, `third_party/`,
  `src/ecli/syntax/assets/`, or any other parallel asset tree.
- Imported / upstream assets are **read-only from the ECLI integration
  perspective**. They must remain byte-for-byte unchanged versus their upstream
  source.
- ECLI-specific behavior must be implemented through **deterministic adapter
  code** that reads those assets. ECLI must not patch, rewrite, or fork upstream
  files to change behavior.

The Extensions Layer is a **data layer plus adapter code**, not an extension
*host*. ECLI consumes static metadata and grammars; it does not execute
extension programs.

## Relationship to existing extension docs

This document is distinct from the existing `docs/extensions/*` set:

- `docs/extensions/plugin-api.md`, `extension-guardrails.md`,
  `ai-provider-runtime.md`, `diagnostics-model.md` describe ECLI's own runtime
  plugin/integration boundaries and the AI/diagnostics runtime.
- This document (`docs/architecture/extensions-layer.md`) describes the
  **imported, data-only asset tree** under `src/ecli/extensions/` and the
  adapter contract around it.

Where the two overlap (for example the diagnostics path), the imported asset
layer feeds ECLI's own normalization model defined in
`docs/extensions/diagnostics-model.md`; it does not replace it.

## Imported assets must remain unchanged

- Files imported under `src/ecli/extensions/` are upstream artifacts.
- ECLI must not edit them to add behavior, fix style, reformat, or relicense.
- Any required ECLI-specific transformation happens at read time in adapter
  code, never by mutating the imported file.
- Re-imports replace the asset wholesale from upstream; ECLI carries no private
  patches inside the tree.

This keeps provenance auditable and keeps re-import a mechanical, deterministic
operation.

## Adapter code contract

ECLI integration code around the imported assets must be **deterministic adapter
code**:

- pure, side-effect-free reads of declared data inputs,
- no execution of imported code paths,
- no network, auth, filesystem-mutation, or process-spawn side effects triggered
  by imported metadata,
- stable, testable mapping from asset data to ECLI internal models.

### Expected future adapter responsibilities (target state)

These are the planned adapters. They are **not implemented in issue #97**; they
are listed here so the boundary is fixed before implementation begins.

- **package.json contribution registry** — parse `contributes.*` declarations
  (languages, grammars, themes, snippets, configuration) into an ECLI-internal
  registry. Ignore `activationEvents`, `main`, `scripts`, and any executable
  hooks.
- **TextMate grammar catalog** — index `syntaxes/*.tmLanguage.json` and
  `syntaxes/*.tmLanguage` by scope name and language id.
- **language detection** — map file name / extension / first-line patterns
  (from `package.json` language contributions) to a language id.
- **syntax service** — apply the resolved grammar to editor text to produce
  scope spans for rendering.
- **scope-to-style / theme bridge** — map TextMate scopes to ECLI theme styles,
  producing readable, deterministic colors.
- **diagnostics / linter integration path** — feed external linter/diagnostic
  output into ECLI's existing diagnostics normalization model
  (`docs/extensions/diagnostics-model.md`). The Extensions Layer supplies
  language/linter metadata only; it does not itself run arbitrary tools.
- **snippets registry** — load `snippets/*.code-snippets` into an ECLI snippet
  store.
- **language-configuration registry** — load `language-configuration.json`
  (comments, brackets, auto-closing pairs, word patterns) for editor behavior.
- **schema registry** — index `schemas/*.json` where applicable for
  configuration/data validation.

## Explicitly supported data-only inputs

The Extensions Layer reads these file kinds and **only** these as data:

- `package.json` — contribution manifest (data only; no activation/scripts).
- `package.nls.json` — localization string table.
- `language-configuration.json` — language editor behavior metadata.
- `syntaxes/*.tmLanguage.json` — TextMate grammars (JSON form).
- `syntaxes/*.tmLanguage` — TextMate grammars (plist/XML form).
- `snippets/*.code-snippets` — snippet definitions.
- `schemas/*.json` — JSON schemas where applicable.
- `themes/*.json` — color themes, if present.
- `cgmanifest.json` — component governance / provenance manifest.

Any other file kind is out of scope for the Extensions Layer until this contract
is amended.

## Explicitly forbidden runtime behavior

The Extensions Layer is data + adapters only. The following are forbidden:

- **No VS Code extension host.** ECLI does not implement or embed the VS Code
  extension API or activation lifecycle.
- **No Node activation.** No Node.js/TypeScript extension runtime is started.
- **No `activationEvents` execution.** Activation declarations are ignored, not
  executed.
- **No arbitrary scripts from `package.json`.** `scripts`, `main`, and similar
  entrypoints are ignored.
- **No Copilot runtime activation.** Imported Copilot-related assets, if any, are
  treated as inert data and must not start any Copilot runtime.
- **No network or auth side effects** from imported extension code or metadata.
- **No hidden command execution through extensions.** Extension metadata must
  never become a path to running commands. There is no implicit
  metadata-to-command bridge.

## PySH boundary

The Extensions Layer must not weaken or bypass the panel-console boundary in
`docs/architecture/panel-console-stabilization.md`:

- **F11 remains the PySH Console Panel.** The Extensions Layer does not own,
  replace, or re-route F11.
- Command execution remains routed through **explicit ECLI services / PySH /
  CommandPlan surfaces** (see `docs/architecture/command-plan-service.md`).
- Extensions must not reintroduce terminal execution behavior, a generic PTY
  terminal emulator, or any interactive shell embedded in curses.

PySH is a command execution backend only. Imported extension assets are not a
side channel into it.

## Release / package-data impact

Issue #97 does **not** change packaging. This section records the contract that
later issues (#98/#99) must satisfy. The active release contract is the
`Canonical 21-Item Platform & Packaging Artifact Matrix` (summarized by the
`Platform & Packaging Release Contract Matrix`) in
`docs/release/artifact-contract.md`; this section is additive guidance, not a
new matrix entry.

- When the asset tree is imported (#98) and tested (#99), extension assets under
  `src/ecli/extensions/` **must be included in the wheel and sdist**. The wheel
  uses `[tool.hatch.build.targets.wheel] packages = ["src/ecli"]`, so Python
  packages are included automatically, but **non-`.py` data files**
  (`*.json`, `*.tmLanguage`, `*.code-snippets`, etc.) require explicit
  `force-include` (wheel) and `include` (sdist) coverage in `pyproject.toml`,
  mirroring how `src/ecli/assets/ecli.png` is handled today.
- **Package-data coverage must be tested.** A `tests/packaging/` test must assert
  that imported extension data files are present in the built wheel and sdist
  (added in #99), the same way other packaging contracts are enforced.
- **All active platform packaging contracts must remain green.** Adding the asset
  tree must not break any of the 21 canonical assets or their
  `tests/packaging/` contract tests across: PyPI wheel and sdist; Linux
  PyInstaller binary and tarball; Debian `.deb`; generic RPM; openSUSE RPM; Arch
  package; Slackware `.txz`; AppImage; FreeBSD `.pkg`, ports/chroot evidence, and
  the FreeBSD CI VM path; macOS `.app` evidence and `.dmg`; Windows portable EXE
  and NSIS installer; Nix flake and NixOS package evidence; Docker DEB/RPM build
  helper evidence; and the GitHub Actions workflow contract evidence.
- The exact-21-asset count is unchanged by this layer; extension assets ship
  *inside* the wheel/sdist artifacts, not as new top-level release assets.

## Sequencing

The Extensions Foundation is delivered as an ordered series. Each issue depends
on the previous one and must not be skipped or merged.

| Issue | Scope |
|---|---|
| #97 | Extensions Layer **architecture contract** (this document). No assets, no code. |
| #98 | Import the prepared assets **unchanged** under `src/ecli/extensions/`. |
| #99 | Asset **tree / package-data tests** (wheel/sdist inclusion, contract checks). |
| #100 | **Manifest registry** (`package.json` contribution parsing). |
| #101 | **TextMate grammar catalog** and **language detection**. |
| #102 | **Syntax service** wired to editor rendering. |
| #103 | **Theme bridge** (scope-to-style). |
| #104 | **Linter diagnostics path**. |
| #105 | **Snippets** and **language-configuration** metadata. |

Issue #97 is complete when this contract exists; it explicitly does **not**
import assets or implement adapters.

## VMLab note

VMLab is **not** part of the Extensions Foundation and is not touched by this
work. VMLab has moved to the **v0.3.5** milestone and is **blocked until the
v0.3.0 Extensions Foundation is complete**. This document does not change any
VMLab implementation; the VMLab implementation docs under `docs/extensions/`
remain as-is and out of scope for issue #97.

## Acceptance checklist (issue #97)

- [x] Defines the ECLI Extensions Layer.
- [x] States imported assets live under `src/ecli/extensions/` and remain
      unchanged.
- [x] States ECLI integration is deterministic adapter code around the assets.
- [x] Lists future adapter responsibilities.
- [x] Lists explicitly supported data-only inputs.
- [x] Lists explicitly forbidden runtime behavior (no host/Node/activation/
      scripts/Copilot/network/hidden command execution).
- [x] States the PySH boundary (F11 stays PySH Console Panel; no PTY emulator).
- [x] States the release/package-data impact for #98/#99.
- [x] States the #97–#105 sequencing.
- [x] No assets imported; no runtime; no packaging implementation changes.
