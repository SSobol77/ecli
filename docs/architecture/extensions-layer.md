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
- Scope: architecture contract plus the current curated runtime asset-tree
  contract for `src/ecli/extensions/`.

This document defines the **ECLI Extensions Layer** boundary. It is the authority
for what `src/ecli/extensions/` is, what may live there, and how ECLI is allowed
to consume it.

> Current state: `src/ecli/extensions/` exists as a curated runtime asset bundle.
> It is not a vendored copy of full VS Code extension repositories.

## Definition

The ECLI Extensions Layer is the bounded location and contract for **imported,
VS Code / TextMate-compatible, data-only assets** that ECLI uses to drive editor
quality features: syntax highlighting, readable themes, a diagnostics/linter
path, snippets, and language-configuration metadata.

- Imported VS Code / TextMate-compatible runtime assets live under
  `src/ecli/extensions/`, normalized into two curated asset groups: language /
  runtime declarative assets under `src/ecli/extensions/lang/` and colour-theme
  assets under `src/ecli/extensions/themes/`.
- `src/ecli/extensions/` is the **only** approved location for imported
  extension assets. Do not invent `vendor/`, `third_party/`,
  `src/ecli/syntax/assets/`, or any other parallel asset tree.
- Imported / upstream assets are **read-only from the ECLI integration
  perspective**. Retained runtime assets must remain byte-for-byte unchanged
  versus their upstream source.
- ECLI must not ship full VS Code extension source trees. Development artifacts,
  Node build inputs, tests, media/demo assets, generated output, and extension
  activation/runtime source are outside the runtime asset contract.
- ECLI-specific behavior must be implemented through **deterministic adapter
  code** that reads those assets. ECLI must not patch, rewrite, or fork upstream
  files to change behavior.

The Extensions Layer is a **data layer plus adapter code**, not an extension
*host*. ECLI consumes static metadata and grammars; it does not execute
extension programs.

The exact source root is `src/ecli/extensions/`. The misspelled
`src/extentions/` path and a top-level `src/extensions/` path are forbidden:
they bypass the ECLI package namespace, package-data tests, and runtime import
contracts.

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
- **scope-to-style / theme bridge** — load contributed color themes from
  `contributes.themes` and referenced theme JSON, then map TextMate scopes to
  ECLI theme styles from that data. Imported themes are the source of truth;
  missing themes must be diagnosed, not synthesized from hand-written color
  dictionaries.
- **diagnostics / linter integration path** — extract language/linter
  association metadata from imported `package.json` `contributes.*`
  declarations in the `lang/` asset tree, feeding ECLI's existing
  diagnostics normalization model (`docs/extensions/diagnostics-model.md`).
  This is data extraction only, distinct from the F4 linter microservices
  runtime under `src/ecli/extensions/linters/` (see
  `docs/architecture/ecli-f4-linter-microservices-design.md`), which
  executes tools and is ECLI-owned Python, not an imported asset.
- **snippets registry** — load `snippets/*.code-snippets` into an ECLI snippet
  store.
- **language-configuration registry** — load `language-configuration.json`
  (comments, brackets, auto-closing pairs, word patterns) for editor behavior.
- **schema registry** — out of the current runtime allowlist. It may be added
  only through a future contract amendment with package-data and enforcement
  tests.

## Explicitly supported data-only inputs

The Extensions Layer reads these file kinds and **only** these as data:

- `package.json` — contribution manifest (data only; no activation/scripts).
- `package.nls.json` — localization string table.
- `package.nls.*.json` — localized string tables.
- `language-configuration*.json` and package-referenced
  `*language-configuration*.json` files — language editor behavior metadata.
- `syntaxes/*.tmLanguage.json` — TextMate grammars (JSON form).
- `syntaxes/*.tmLanguage` — TextMate grammars (plist/XML form).
- `snippets/*.code-snippets` — snippet definitions.
- `themes/*.json` — color themes, if present.
- `LICENSE*`, `NOTICE*`, `THIRD_PARTY_NOTICES*`, and attribution-required
  `README.md` files — legal attribution for retained assets.

Any other file kind is out of scope for the Extensions Layer until this contract
is amended.

## Curated runtime asset bundle

`src/ecli/extensions/` is intentionally pruned and **normalized**. Its root is
small and contains only:

- `ecli_integration/` — ECLI-owned Python adapter code;
- `linters/` — ECLI-owned F4 linter microservices Python package (see
  `docs/architecture/ecli-f4-linter-microservices-design.md` and
  `docs/extensions/diagnostics-linter-layer.md`). Each supported linter is
  its own microservice directory (`linters/ruff/`, `linters/biome/`, ...)
  with `manifest.py` and `package_contract.py`, and, for Ruff only so far,
  a working `provider.py`. This is ECLI-authored Python runtime, not an
  imported asset -- raw upstream linter source (VS Code TypeScript or
  otherwise) is never permitted here, same as everywhere else under
  `src/ecli/extensions/`;
- `lang/` — imported language / runtime declarative extension assets, one folder
  per language or language bundle (for example `lang/python`, `lang/rust`,
  `lang/cpp`, `lang/typescript-basics`, `lang/json`, `lang/yaml`,
  `lang/markdown-basics`, `lang/git-base`);
- `themes/` — imported colour-theme extension assets, one folder per theme
  bundle with the `theme-` prefix dropped (for example `themes/defaults`,
  `themes/monokai`, `themes/solarized-dark`, `themes/abyss`);
- `THIRD_PARTY_NOTICES.md` — legal attribution for retained upstream assets;
- optionally `README.md` documenting the bundle.

The root **must not** contain dozens of flat imported language/theme extension
folders, a generated inventory file, complete VS Code extension repositories,
Node packages, test workspaces, demo media, generated bundles, or
activation/runtime implementation code.

Each imported folder under `lang/<name>` and `themes/<name>` may retain only:

- `package.json`;
- `package.nls.json` and `package.nls.*.json`;
- TextMate grammars under `syntaxes/`;
- colour themes under `themes/`;
- snippets under `snippets/`;
- language-configuration metadata at the path referenced by `package.json`
  (folder root, or a `languages/` subdir);
- legal attribution files: `LICENSE*`, `NOTICE*`, `THIRD_PARTY_NOTICES*`, and
  attribution-required `README.md`.

Disallowed imported files and directories include `.vscodeignore`, lockfiles,
`tsconfig*.json`, `esbuild*.mts`, webpack/rollup configs, TypeScript or
JavaScript activation/runtime source, `test/`, `tests/`, `media/`,
`screenshots/`, demo assets, `out/`, `dist/`, `node_modules/`, `.vscode/`,
`.github/`, `__pycache__/`, `.pyc`, `.pyo`, generated inventories, generated
bundles, and generated logs.

VS Code UI/runtime-only extensions that do not provide ECLI-consumed declarative
language, grammar, snippet, or theme assets are not part of the runtime bundle.
Examples removed from the curated tree include `references-view`,
`notebook-renderers`, the `*-language-features` language servers, `git`,
`github`, and the manifest-only / tooling-only folders `copilot`, `npm`,
`configuration-editing`, and `extension-editing`.

### Adapter discovery

`ecli_integration` discovers imported manifests by scanning the direct children
of `lang/` and `themes/` that contain a `package.json`
(`registry.MANIFEST_GROUP_DIRS`). Discovery is shallow within each group, so
nested `package.json` files are never picked up, and the tree root and the
`ecli_integration` package itself are never treated as imported manifests.
Contribution paths resolve relative to each manifest's own folder, so the
`lang/` and `themes/` prefixes are reflected automatically in the
`src/ecli/extensions/...` repo-relative records.

ECLI's file-icon layer currently uses the symbolic icon table in the ECLI config
path (`get_file_icon`) and does not consume imported VS Code icon themes.
Therefore imported icon-theme folders are not retained unless a future adapter
and tests make them runtime data.

The enforcement contract lives in `tests/extensions/test_extensions_tree_contract.py`.
It rejects source/build/test/media artifacts and verifies that retained files
match the runtime allowlist. Manifest, grammar, theme, language-detection, and
package-data tests verify that package-referenced runtime assets still resolve
and still ship in the wheel and sdist.

## Theme Numbering Contract

Theme numbers are a stable ECLI configuration contract. The active theme is
selected by the root `theme = N` setting in `config.toml`; imported theme JSON
and TextMate `tokenColors` remain the source of truth for extension-backed
professional themes.

Canonical ranges:

- `1`-`8`: deprecated aliases for old pre-extension-theme configs only. These
  values are migration inputs, not selectable professional themes.
- `100`-`199`: light themes.
- `200`-`299`: dark themes.
- `300`-`399`: high-contrast themes.
- `800`-`899`: reserved for a future custom/imported special-theme feature.
  They must not be silently assigned before that feature exists.

Canonical professional theme ids:

- Light: `101` GitHub Light Default, `102` GitHub Light, `103` GitHub Light
  Colorblind (Beta), `104` Visual Studio Light, `105` Visual Studio 2017 Light
  - C++, `106` Light Modern, `107` Light+, `108` Quiet Light, `109` Solarized
  Light, `110` JetBrains Rider New UI Light.
- Dark: `201` GitHub Dark Default, `202` GitHub Dark, `203` GitHub Dark
  Dimmed, `204` Visual Studio Dark, `205` Visual Studio 2017 Dark - C++,
  `206` Dark Modern, `207` Dark+, `208` Monokai, `209` Monokai Dimmed, `210`
  Tomorrow Night Blue, `211` Abyss, `212` Atom One Dark, `213` Kimbie Dark,
  `214` Solarized Dark, `215` Red.
- High contrast: `301` Dark High Contrast, `302` GitHub Dark High Contrast,
  `303` GitHub Light High Contrast, `304` Light High Contrast.

Built-in compatibility themes preserve their existing colour values and use
reserved compatibility ids: `181` PySH Light, `182` PySH Classic, `183` ECLI
Legacy Light, `281` PySH Dark, `282` PySH Classic Dark, `283` ECLI Legacy Dark,
`381` ECLI High Contrast Light, and `382` ECLI High Contrast Dark.

Missing professional themes are not synthesized or mapped to unrelated themes.
If a configured number is invalid or the imported theme is absent, ECLI keeps
the current valid theme when one exists, emits a visible warning, and does not
crash startup. Startup without a current theme uses the default `207` Dark+ with
a warning.

Config migrations must write
`~/.config/ecli/config.toml.pre-extension-theme-numbering.bak` before modifying
the user config. Old pre-extension ids `1`-`8` migrate to the matching
compatibility ids above. Transitional ids from the previous in-progress
implementation migrate as follows: `1`-`10` -> `101`-`110`, `11`-`25` ->
`201`-`215`, and `26`-`29` -> `301`-`304`.

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

The active release contract is the
`Canonical 21-Item Platform & Packaging Artifact Matrix` (summarized by the
`Platform & Packaging Release Contract Matrix`) in
`docs/release/artifact-contract.md`; this section is additive guidance, not a
new matrix entry.

- Curated extension assets under `src/ecli/extensions/` **must be included in
  the wheel and sdist**. The wheel uses
  `[tool.hatch.build.targets.wheel] packages = ["src/ecli"]`, so Python packages
  are included automatically. The retained non-`.py` data files (`package.json`,
  `package.nls*.json`, `*.tmLanguage`, `*.tmLanguage.json`,
  `*.code-snippets`, language-configuration JSON, theme JSON, and legal
  attribution files) are covered by package-data tests.
- **Package-data coverage must be tested.** A `tests/packaging/` test must assert
  that imported extension data files are present in the built wheel and sdist
  (added in #99), the same way other packaging contracts are enforced.
- **All active platform packaging contracts must remain green.** Adding the asset
  tree must not break any of the exactly 21 artifact contract entries or their
  `tests/packaging/` contract tests across: PyPI wheel and sdist; Linux
  PyInstaller binary and tarball; Debian `.deb`; generic RPM; openSUSE RPM; Arch
  package; Slackware `.txz`; AppImage; FreeBSD `.pkg`, ports/chroot evidence, and
  the FreeBSD CI VM path; macOS `.app` evidence and `.dmg`; Windows portable EXE
  and NSIS installer; Nix flake and NixOS package evidence; Docker DEB/RPM build
  helper evidence; and the GitHub Actions workflow contract evidence.
- The exact-21-asset count is unchanged by this layer; extension assets ship
  *inside* the wheel/sdist artifacts, not as new top-level release assets.
- **Status (#99):** tree and package-data contract tests live in
  `tests/extensions/` (`test_extensions_tree_contract.py`,
  `test_extensions_package_data_contract.py`). They prove the curated runtime
  asset allowlist, package-referenced contribution paths, and representative
  imported extension assets inside the built wheel and sdist. Hatchling's
  default file selection for `packages = ["src/ecli"]` already ships the
  retained data files, so **no additional `force-include`/`include` entries were
  required** in `pyproject.toml`.

## Adapter status

- **Status (#100):** ECLI now has a deterministic, **data-only** `package.json`
  contribution registry under `src/ecli/extensions/ecli_integration/`
  (`paths.py`, `manifest.py`, `registry.py`). It discovers direct-child
  extension folders that contain a `package.json` (no recursion into nested
  language-server/node `package.json` files), parses
  `contributes.languages|grammars|snippets|configuration` into typed, immutable
  metadata, resolves contribution target paths safely under
  `src/ecli/extensions/` (rejecting traversal), and exposes read-only lookups by
  language id, file extension, grammar, and snippet, plus deterministic
  diagnostics for malformed manifests. It executes **no** extension code: no
  extension host, no Node/TypeScript or Copilot runtime, no `activationEvents`,
  and no `package.json` scripts. Covered by
  `tests/extensions/test_extension_manifest_registry.py`.
- **Status (#101):** building on #100, ECLI now has a deterministic, **data-only**
  TextMate grammar catalog (`grammar_catalog.py`) and language detection
  (`language_detection.py`). The catalog lists grammar contributions, exposes
  them by language id and TextMate scope name (plus embedded-language and
  token-type metadata), verifies grammar files resolve under
  `src/ecli/extensions/`, and emits deterministic diagnostics for missing files,
  path traversal, malformed metadata, and conflicting scopes. Language detection
  maps a file name/extension/exact-filename/filename-pattern to a language id
  with deterministic precedence and explicit ambiguity metadata. `config.toml`
  now exposes the data-path switches via an `[extensions]` table (`enabled`,
  `metadata_registry`, `grammar_catalog`, `language_detection`,
  `syntax_engine = "legacy"`), parsed through `config.py`
  (`ExtensionLayerConfig`); no config value can enable an extension runtime.
  **Syntax rendering remains legacy:** the existing regex/Pygments highlighter is
  unchanged and stays authoritative — it is **not** removed or disabled in #101.
  An extension-backed syntax service and editor rendering replacement arrive in
  #102. Covered by `tests/extensions/test_textmate_grammar_catalog.py`,
  `tests/extensions/test_extension_language_detection.py`, and
  `tests/extensions/test_extension_layer_config.py`.
- **Status (#102):** #101 delivered the grammar catalog and language detection;
  #102 now delivers **real TextMate tokenization and visible editor rendering**.
  The ECLI-owned modules under `src/ecli/extensions/ecli_integration/` are:
  `syntax_service.py` (engine selection + per-line `LineHighlighter`),
  `textmate_tokenizer.py` (loads the imported `.tmLanguage.json` grammars and
  tokenizes each line into genuine TextMate scope stacks via the optional
  `python-textmate` engine, which uses Oniguruma), `theme_registry.py`
  (loads `contributes.themes`, follows local theme `include` chains, parses theme
  JSON/JSONC, and resolves TextMate `tokenColors`), and `theme_bridge.py`
  (deterministic scope → ECLI style-category mapping with specificity, flattening
  overlapping scopes into per-line spans). The editor consumes those spans in
  `Ecli.apply_syntax_highlighting_with_pygments`, mapping each style category onto
  the active theme's curses colour and drawing them through the existing
  `DrawScreen` path — so highlighting is **visibly** TextMate-driven and differs
  by language.
  - **Engine selection** is config-driven via `[extensions].syntax_engine`.
    `"extension"` is the **default**; `"legacy"` forces the built-in
    Pygments/regex highlighter. `editor.syntax_highlighting = false` disables
    visible highlighting for both engines.
  - **Legacy remains a always-available fallback.** Unknown files, grammars the
    engine cannot tokenize (the imported **Markdown** and some **C** constructs
    recurse), an uninstalled tokenizer, or any tokenizer error fall back to the
    legacy highlighter automatically — per file and per line — so rendering is
    never broken. Representative languages with real TextMate scopes today:
    Python, Markdown, JSON, Dockerfile, Makefile, YAML/YML, TypeScript,
    JavaScript, C/C++, Java, Rust, HTML, Perl, PHP, Lua, C#, BAT, logs, and
    gitignore. TOML, assembler, Ada/SPARK, and Fortran are detected
    deterministically but report missing imported grammar assets and use safe
    fallback highlighting until those assets are added.
  - **No runtime.** It reads grammar JSON only: no VS Code extension host, no
    Node/TypeScript or Copilot runtime, no `activationEvents`, no `package.json`
    scripts, no background workers; all engine stdout/stderr is suppressed so it
    cannot corrupt curses. The imported upstream tree is unchanged.
  - **Theme source of truth.** Professional theme ids are backed by real imported
    theme contributions and theme JSON using the numbering contract above:
    Visual Studio Light, Light Modern, Light+, Quiet Light, Solarized Light,
    Visual Studio Dark, Dark Modern, Dark+, Monokai, Monokai Dimmed, Tomorrow
    Night Blue, Abyss, Kimbie Dark, Solarized Dark, Red, Dark High Contrast, and
    Light High Contrast are loaded from the asset tree when present. Target names
    that are not present in the imported assets, including GitHub Light/Dark
    variants, VS2017, Atom One Dark, JetBrains Rider Light, and Tokyo variants,
    are reported as missing and are not replaced by fabricated palettes. The
    legacy PySH/ECLI palettes are retained only as explicit compatibility ids in
    the 18x/28x/38x ranges.
  - **Multiline protection layer.** TextMate scopes remain the primary token
    source. Because the current `python-textmate` adapter is line-oriented and
    cannot carry every grammar's rule stack across viewport lines, ECLI applies
    a bounded, language-aware protection pass over TextMate output for known
    multiline regions: Python triple-quoted strings/docstrings and inline
    strings; JavaScript/TypeScript `/* ... */`, `/** ... */`, `//` comments and
    quoted/template strings; HTML `<!-- ... -->` comments; and CSS `/* ... */`
    comments and quoted strings. The protection pass does not tokenize normal
    code and does not replace grammar tokenization. It only gives known
    comment/string regions priority over nested keyword, number, operator, tag,
    selector, or property scopes that leak from stateless per-line tokenization.
    Protected ranges are cached by buffer revision and mapped onto the current
    viewport, so scrolling reuses the existing viewport-first/per-line cache
    architecture instead of reparsing the file on every repaint.
  - **Acceptance coverage.** Large-file scroll responsiveness is locked by real
    repository-file tests over `Makefile`, `logs/freebsd-0.2.2-fail.log`,
    `logs/pr-46-body.md`, and `scripts/build_pyinstaller_linux.py`. Multiline
    rendering correctness is locked by synthetic fixtures for Python,
    JavaScript, TypeScript, HTML, and CSS because those exact adversarial comment
    bodies are not reliably present in repository files.
  - **Limitations / staged work.** Tokenization is still per line; the
    protection layer is a deterministic guard for known multiline
    comment/string regions, not a general TextMate state-stack implementation.
    Broader cross-line state for every TextMate grammar remains future
    stabilization work. **Linter diagnostics integration remains #104**, and
    **snippets + language-configuration metadata remain #105**.
  - Covered by `tests/extensions/test_textmate_tokenization.py`,
    `tests/extensions/test_extension_syntax_service.py`,
    `tests/extensions/test_editor_syntax_adapter.py`, and
    `tests/extensions/test_editor_syntax_rendering.py`,
    `tests/extensions/test_textmate_multiline_protection.py`,
    `tests/extensions/test_textmate_render_performance.py`, and
    `tests/extensions/test_textmate_scroll_regression.py`.
- **Dependencies (#102, release-contract).** TextMate rendering requires the
  optional tokenizer dependency, declared in `pyproject.toml`:
  - `python-textmate` (pure-Python TextMate grammar interpreter), which pulls
  - `onigurumacffi` (CFFI bindings to the **Oniguruma** regex engine). On Linux,
    macOS, and Windows, `onigurumacffi` ships binary wheels (no system library
    needed). Where only an sdist is available (notably **FreeBSD**, or Nix builds
    from source), the **Oniguruma** development headers/library must be present
    (`devel/oniguruma` on FreeBSD, `oniguruma` on Debian/Ubuntu/Arch, `oniguruma`
    in nixpkgs). Packaging surfaces must declare/install this where they build
    from source; see `docs/install/*`, `docs/release/packaging-flows.md`, and
    `docs/release/release-checklist.md`.
  - **Graceful degradation:** if the tokenizer or Oniguruma is unavailable at
    runtime, ECLI logs a deterministic diagnostic
    (`ECLI syntax engine=… textmate_tokenizer_available=False active_renderer=legacy`)
    and renders with the legacy highlighter. A missing tokenizer never crashes
    startup.
- **Config surface (#102).** `config.toml` is reduced to user-facing settings
  only; the internal `[comments.*]`, `[[syntax_highlighting.*]]`, and
  `[supported_formats]` tables moved into code (`DEFAULT_CONFIG`). The default is
  `[extensions].syntax_engine = "extension"`. A one-time, backed-up migration
  (`migrate_obsolete_config_tables`) strips those obsolete tables from an existing
  user `~/.config/ecli/config.toml` and flips a transitional
  `syntax_engine = "legacy"` to `"extension"`, so upgraded users actually get
  TextMate rendering instead of being pinned to a stale legacy config.

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
| #103 | **Theme registry / bridge** (`contributes.themes`, theme JSON, tokenColors, scope-to-style). |
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
