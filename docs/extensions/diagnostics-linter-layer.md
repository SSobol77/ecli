<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/extensions/diagnostics-linter-layer.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Diagnostics Multi-Linter Layer — the ECLI Linter Pack

## Status

**Authoritative contract:** the F4 linter *runtime* architecture (provider
shape, microservice directory layout, packaging, full-installation rules,
and the F4 UI freeze) is governed by
[`docs/architecture/ecli-f4-linter-microservices-design.md`](../architecture/ecli-f4-linter-microservices-design.md),
which supersedes any runtime-shape guidance implied elsewhere in this
document. As that contract states: backend linter providers change; F4
panel visualization remains stable.

**Namespace migration complete.** F4 linter diagnostics live under
`src/ecli/extensions/linters/`, part of the ECLI Extensions Layer, not
under `src/ecli/diagnostics/`. `src/ecli/diagnostics/` no longer exists in
this tree; it is reserved for future general/system diagnostics (System
Doctor / F8, environment health checks), not F4 linters. See
`docs/architecture/extensions-layer.md` for the Extensions Layer tree
contract.

Current state:

- `src/ecli/extensions/linters/core/` holds the linter-agnostic contract:
  `models.py` (`Diagnostic`, `DiagnosticRequest`, `DiagnosticResult`,
  `DiagnosticsSnapshot`, `ProviderState`), `display.py`, `service.py`
  (`DiagnosticsService`), `provider_protocol.py` (`DiagnosticProvider`),
  and `registry.py` (`LinterDefinition`, `PackageContract`, and the
  generic catalog-lookup helpers).
- `src/ecli/extensions/linters/ruff/` has a fully working `provider.py`
  (moved unchanged from the retired `ruff_provider.py`) plus `manifest.py`
  and `package_contract.py`. Ruff is the only linter with a working
  provider; it remains the F4 linter microservices reference
  implementation and its Python behavior is unchanged by this migration.
- Every other first-class and legacy/optional linter (22 in total) has its
  own microservice directory with `manifest.py` and `package_contract.py`.
  Implemented providers/parsers remain separate from provisioning; the
  provisioning layer consumes only manifest/package-contract metadata and does
  not run F4 diagnostics.
- `src/ecli/extensions/linters/__init__.py` aggregates every
  microservice's `manifest.MANIFEST` into `LINTER_CATALOG` and exposes
  `get_linter(name)`, `iter_linters()`, `linters_for_language(language)`.
- `src/ecli/extensions/linters/core/provisioning_contract.py`,
  `provisioning_registry.py`, and `provisioning.py` implement the
  provider-neutral Full-install provisioning model, installer component data,
  dry-run evidence, and evidence verification. This is packaging/release
  contract logic only: no F4 UI change, no package-manager calls from F4, and
  no provider/parser behavior change.

See `docs/extensions/diagnostics-model.md` for the normalized `Diagnostic`
contract every provider must produce, and
`src/ecli/extensions/linters/ruff/provider.py` for the only diagnostics
provider that is actually wired up today.

## Why this exists

An earlier attempt imported a full VS Code "Linter" extension source tree
(TypeScript: `extension.ts`, `CodeActionProvider.ts`, per-linter modules,
helpers) directly under `src/ecli/extensions/linters/`. That was rejected
and removed:

- `src/ecli/extensions/` is a curated asset layer (see
  `docs/architecture/extensions-layer.md`); dumping raw upstream runtime
  source into it is never permitted, regardless of subdirectory.
- The imported tree broke the existing, deliberate extensions-tree contract
  (`tests/extensions/test_extensions_tree_contract.py`), which explicitly
  forbids TypeScript/JavaScript files anywhere under `src/ecli/extensions/`.
- License and upstream provenance for the imported source were never
  established -- no `LICENSE`, `NOTICE`, or header was present anywhere in
  the copied tree.

**This is not the same thing as the current `src/ecli/extensions/linters/`
package.** The rejected attempt was raw, unowned, foreign-language runtime
source. The current package is ECLI-authored Python only: every
`provider.py`, `manifest.py`, and `package_contract.py` under this tree is
written by ECLI, follows ECLI's own runtime safety rules, and is scanned by
`scripts/check_runtime_imports.py` like any other ECLI source (see
`tests/packaging/test_runtime_import_guard_scope.py`). Raw upstream linter
runtime source remains forbidden here, forever -- see the design contract's
Source Tree Invariants (section 4.5) and Explicit Non-Goals (section 22).

## Product decision: the ECLI Linter Pack

ECLI is not VS Code. There is no extension marketplace where a user can
browse and install a linter extension. If ECLI wants multi-language
diagnostics, ECLI has to own the curation: a single, opinionated toolchain
profile per language/ecosystem, with modern defaults chosen up front
instead of leaving the user to discover and wire up tools themselves.

That profile is the **ECLI Linter Pack**: the curated set of linter
microservices under `src/ecli/extensions/linters/`, plus Ruff, which ships
bundled with the editor itself. Each microservice's `manifest.py` declares
one `LinterDefinition` carrying enough metadata (`tier`, `install_group`,
`bundled_with_full_install`, `install_hint`, `homepage_url`,
`package_hints`, `supersedes`, `provider_kind`) for the installer and
repair UX to reason about the tool without embedding linter-specific policy
in the F4 panel.

Each microservice's `package_contract.py` is the single source of truth for
how that linter is provided per OS/artifact contract entry. The package
contract is metadata only today, but the required shape is fixed: ECLI Full
must provide mandatory tools, manual installation is only for developer
checkouts/minimal installs/repair, version probes are required, and GitHub
or upstream release artifacts require source URL, pinned version,
checksum/provenance evidence, executable permission handling, and
deterministic install logs. The mapping must cover exactly 21 artifact
contract entries from `docs/release/artifact-contract.md`; it must not grow
or shrink into a parallel release matrix.

### Modern defaults, not the most popular tool from 2015

The catalog favors actively maintained, fast, low-configuration tools over
legacy defaults that happened to be first:

| Ecosystem | Old default assumption | ECLI Linter Pack default | Why |
|---|---|---|---|
| JS/TS/JSON/CSS/GraphQL | ESLint | **Biome** | one Rust-native binary covers lint + format across JS/TS/JSON/CSS/GraphQL with near-zero config; ESLint requires a plugin ecosystem and per-project config just to get started |
| Python | (none / Pylint) | **Ruff** (bundled, internal) | already ECLI's existing embedded provider; Pylint remains available as an optional deep-lint, not a dependency |
| Systems | (none) | **Zig toolchain**, **Cargo Clippy**, **Clang-Tidy/Cppcheck/Clang-Format** | Zig, Rust, and C/C++ are core to ECLI's systems-programming audience, not afterthoughts |
| Java | (none) | **Checkstyle, PMD, SpotBugs** | first-class language profile spanning style, static rules, and bytecode bug detection |

`biome.manifest.MANIFEST.supersedes == ("eslint", "stylelint")` records
this decision directly in the registry data, so future tooling (and this
document) can derive "what replaced what" from one source instead of two.

### Tiers

Every microservice's `LinterDefinition` declares a `tier`:

| Tier | Meaning |
|---|---|
| `core` | bundled with the editor itself, no external binary — currently only Ruff |
| `recommended` | the modern, curated default for its language/ecosystem; enabled by default when the executable is present |
| `optional` | a specialist or power-user tool a user can opt into; never enabled by default |
| `legacy` | superseded by a `recommended` entry; kept for backward-compatible/opt-in use, never a default |

### Install groups

Every entry also declares an `install_group`, the packaging bucket a
future ECLI Linter Pack installer would use to offer tools together:

| Group | Contents |
|---|---|
| `core` | cross-language essentials present in nearly every project: `yamllint`, `taplo`, `markdownlint-cli2` |
| `web` | `biome`, `oxlint`, `eslint`, `stylelint` |
| `systems` | `cargo-clippy`, `zig`, `clang-tidy`, `cppcheck`, `clang-format` — ECLI's systems-programming identity |
| `devops` | `shellcheck`, `actionlint`, `hadolint` |
| `infra` | `tflint` |
| `data` | `sqlfluff` |
| `language` | other single-language profiles/specialists: `golangci-lint`, `checkstyle`, `pmd`, `spotbugs`, `pylint` |
| `prose` | reserved for a future writing profile (Proselint/Vale/LanguageTool/Textlint); no entries yet |

## The registry model

`src/ecli/extensions/linters/core/registry.py` declares the shared types
every microservice's `manifest.py`/`package_contract.py` builds an
instance of:

| Type | Meaning |
|---|---|
| `LinterDefinition` | frozen dataclass: `name`, `display_name`, `languages`, `file_extensions`, `executable`, `argv_template`, `stdin_mode`, `parser`, `config_files`, `capabilities`, `tier`, `install_group`, `install_hint`, `homepage_url`, `enabled_by_default`, `bundled_with_full_install`, `provider_kind`, `package_hints`, `supersedes` |
| `PackageContract` | frozen dataclass: `service_name`, `mandatory_for_full_install`, `bundled_with_full_install`, `binary_names`, `version_probe`, `delivery_notes` |

Field meanings:

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | canonical identifier, e.g. `"biome"` |
| `display_name` | `str` | human-readable name, e.g. `"Biome"` |
| `languages` | `tuple[str, ...]` | ECLI language identifiers this linter covers |
| `file_extensions` | `tuple[str, ...]` | extensions (and, where relevant, exact filenames such as `Dockerfile`) |
| `executable` | `str` | binary name to look up on `$PATH` — always the real tool binary, never a package manager (`npm`, `pip`, `apt`, ...) |
| `argv_template` | `tuple[str, ...]` | plain argv tokens, never a shell string; `"{file}"` marks the target-file placeholder |
| `stdin_mode` | `"unsupported" \| "optional" \| "required"` | whether the linter can read buffer contents from stdin |
| `parser` | one of `ALLOWED_PARSERS` | output-shape identifier for a future parser |
| `config_files` | `tuple[str, ...]` | filenames the linter conventionally looks for |
| `capabilities` | `tuple["lint" \| "fix", ...]` | what a future integration could do with this definition |
| `tier` | one of `ALLOWED_TIERS` | `"core" \| "recommended" \| "optional" \| "legacy"` |
| `install_group` | one of `ALLOWED_INSTALL_GROUPS` | packaging bucket, see above |
| `install_hint` | `str` | human-readable repair hint for developer/minimal/damaged installs; not the normal Full user path |
| `homepage_url` | `str` | canonical upstream URL |
| `enabled_by_default` | `bool` | future default on/off state; not consulted anywhere yet |
| `bundled_with_full_install` | `bool` | whether an "ECLI Full" install should ship/depend on this tool where platform packaging allows |
| `provider_kind` | `"internal" \| "external"` | `"internal"` for Ruff (embedded, dispatched through `ruff/provider.py`); `"external"` for everything shelled out to `$PATH` |
| `package_hints` | `tuple[str, ...]` | common package-manager identifiers for this tool |
| `supersedes` | `tuple[str, ...]` | names of other catalog entries this one replaces as the curated default |

`LinterDefinition.__post_init__` enforces, at construction time:

- `parser` must be a member of `ALLOWED_PARSERS` (`json_generic`,
  `eslint_json`, `cargo_json`, `biome_json`, `xml_generic`, `text_lines`,
  `zig_text`);
- `tier` must be a member of `ALLOWED_TIERS`;
- `install_group` must be a member of `ALLOWED_INSTALL_GROUPS`;
- `provider_kind` must be `"internal"` or `"external"`;
- at least one of `languages` / `file_extensions` must be non-empty;
- `executable` must be non-empty;
- no `argv_template` token may contain shell metacharacters
  (`&& || | ; > <`), since this catalog only ever produces plain argv lists
  for a future `subprocess.run(argv, shell=False)` call — never a shell
  string.

## The catalog (23 entries)

| `name` | Tier | Directory | Install group | Default |
|---|---|---|---|---|
| `ruff` | core | `ruff/` | core (internal) | yes |
| `biome` | recommended | `biome/` | web | yes |
| `oxlint` | optional | `oxlint/` | web | no |
| `eslint` | legacy | `eslint/` | web | no |
| `stylelint` | optional | `stylelint/` | web | no |
| `cargo-clippy` | recommended | `cargo_clippy/` | systems | yes |
| `zig` | recommended | `zig/` | systems | yes |
| `clang-tidy` | recommended | `clang_tidy/` | systems | yes |
| `cppcheck` | recommended | `cppcheck/` | systems | yes |
| `clang-format` | recommended | `clang_format/` | systems | yes |
| `checkstyle` | recommended | `java_checkstyle/` | language | yes |
| `pmd` | recommended | `java_pmd/` | language | yes |
| `spotbugs` | recommended | `java_spotbugs/` | language | yes |
| `shellcheck` | recommended | `shellcheck/` | devops | yes |
| `actionlint` | recommended | `actionlint/` | devops | yes |
| `hadolint` | recommended | `hadolint/` | devops | yes |
| `tflint` | recommended | `tflint/` | infra | yes |
| `sqlfluff` | recommended | `sqlfluff/` | data | yes |
| `golangci-lint` | recommended | `golangci_lint/` | language | yes |
| `pylint` | optional | `pylint/` | language | no |
| `markdownlint-cli2` | recommended | `markdownlint/` | core | yes |
| `yamllint` | recommended | `yamllint/` | core | yes |
| `taplo` | recommended | `taplo/` | core | yes |

C/C++ (Clang-Tidy, Cppcheck, Clang-Format) and Java (Checkstyle, PMD,
SpotBugs) are first-class base profiles per the design contract's Language
and Tool Matrix (section 10.1) and now have real microservice directories
and manifests in this migration -- they were not part of the earlier
17-entry Stage 1 catalog. None of the six has a `provider.py` yet; only
Ruff does.

Access via `iter_linters()`, `get_linter(name)`, and
`linters_for_language(language)` in `src/ecli/extensions/linters/__init__.py`.

### Zig is first-class, not an afterthought

Zig is one of ECLI's core systems-programming languages, alongside Rust
and C/C++. The `zig` entry is `tier="recommended"`,
`bundled_with_full_install=True`, and `enabled_by_default=True` — the same
standing Cargo Clippy has for Rust. Its command template uses Zig's own
built-in check mode rather than a separate linter binary, since the Zig
toolchain is the linter:

```text
zig fmt --check --ast-check {file}
```

`--check` makes the run non-destructive (report only, no rewrite);
`--ast-check` catches syntax-level problems beyond formatting drift. The
parser identifier for this output is `"zig_text"`, a dedicated `ParserId`
in `ALLOWED_PARSERS` — no parser implementation exists yet, this only
reserves the identifier.

## ECLI Full vs. minimal install

Two install shapes are represented in the provisioning contract:

- **Minimal install** — the editor only. Ruff works out of the box because
  it is bundled (`provider_kind="internal"`). Every other entry in the
  catalog is inert metadata until its executable is found on `$PATH` or in
  an ECLI-managed tools directory. Manual installation documentation applies
  to this shape, to developer checkouts, and to repair of damaged Full
  installs.
- **ECLI Full install** — the editor plus the
  `bundled_with_full_install=True` tools (Biome, Cargo Clippy, Zig,
  Clang-Tidy, Cppcheck, Clang-Format, Checkstyle, PMD, SpotBugs,
  ShellCheck, actionlint, hadolint, TFLint, SQLFluff, golangci-lint,
  markdownlint-cli2, yamllint, Taplo). The Full installer/provisioner
  detects the operating system and artifact context, checks already-installed
  tools first, installs or bundles missing required tools using the correct
  OS/artifact-specific method, and verifies executability plus versions.
  Legacy/optional entries (ESLint, Pylint, Stylelint, Oxlint) are
  deliberately excluded from Full — a user opts into those explicitly.

A normal Full installation must not require a post-install step to make
the `bundled_with_full_install=True` tools available. If a Full install is
missing one of them, that is a packaging defect or a damaged/partial
install condition, not expected product behavior — see
`docs/architecture/ecli-f4-linter-microservices-design.md` sections 2.2
and 4.2. Packaging work needed to satisfy this must land inside ECLI's
existing 21 artifact contract entries, never a parallel or informal release
matrix (design doc sections 4.3/18.2).

The accepted provisioning strategies are OS-aware: native package-manager
dependencies where reliable, bundled binaries where appropriate, verified
GitHub/upstream release downloads, language package-manager installs,
dedicated ECLI-managed tool directories, and shims/wrappers where a JAR or
toolchain component needs one. Upstream binary/JAR/tarball downloads are
allowed only with explicit source URL, version pinning, checksum verification
where available, clear provenance in `package_contract.py`, no silent
unverified execution, and deterministic install logs.

The repository exposes this contract through
`scripts/provision_f4_linters.py` and
`scripts/verify_f4_linter_provisioning.py`. `dry-run` planning is deterministic
and safe for CI; real missing-tool provisioning still belongs to
artifact-specific installer/package flows.

### The PyPI limitation

ECLI is published as a Python wheel on PyPI. Python wheels can only
reliably declare dependencies on other Python packages (`pip install
ecli-editor` only ever pulls in Python code). Most of the ECLI Linter
Pack's `recommended` tools are **not** Python packages:

- Biome and Oxlint are npm packages / standalone Node-ecosystem binaries.
- Cargo Clippy ships with the Rust toolchain (`rustup`), not pip.
- Zig is its own toolchain download, not a Python package.
- Clang-Tidy, Cppcheck, and Clang-Format ship via LLVM tooling or OS
  package managers, not pip.
- Checkstyle, PMD, and SpotBugs are JVM tools distributed as standalone
  jars or Maven/Gradle plugins, not pip.
- golangci-lint, TFLint, actionlint, hadolint are standalone Go/Haskell
  binaries with their own release channels.

`pip install ecli-editor` therefore **cannot** transitively install any of
these reliably. The PyPI distribution of ECLI is a minimal install with
respect to the Linter Pack unless a future wheel policy explicitly proves
otherwise. Ruff remains bundled; other tools require a Full platform
artifact for the normal user path, or the manual installation reference for
developer checkout, minimal install, or repair use. `install_hint` and
`package_hints` on each catalog entry are repair/developer metadata, not a
normal post-install checklist for ECLI Full.

## Proposed future commands (not implemented)

Two `ecli doctor` subcommands are proposed for a later stage, once a real
provider exists. Per the authoritative contract (design doc sections
2.2/4.2), these are **repair and verification tools for damaged,
development, minimal, or partial environments** — not the normal
installation path. A normal ECLI Full installation already includes the
base linter microservices' required executables; neither command is a
required post-install step:

- `ecli doctor --check-linters` — walk the catalog, check the effective
  tool search path (`$PATH` plus any ECLI-managed tools directory) for each
  `executable`, and report what is present, what is missing, and each
  missing tool's repair metadata.
- `ecli doctor --install-linters` — where the host platform and artifact
  context allow it, offer to repair a damaged/minimal/partial install by
  installing missing `bundled_with_full_install` tools with the same
  provenance/checksum/version rules as the installer. This is an opt-in,
  user-triggered repair action, never something F4 or any background
  diagnostics pass does on its own, and never advertised as a required step
  after installing ECLI.

Neither subcommand exists today. This document only records the intended
shape so a later stage does not have to re-derive it.

## F4 missing-tool UX (future behavior, not implemented)

In a normal ECLI Full installation, a missing linter executable is **not**
an expected condition — it signals a development checkout, a damaged or
partial install, a packaging defect, or an intentionally minimal build
(design doc sections 4.2, 17.1). When a future multi-linter runtime looks
up a catalog entry and finds its `executable` absent from `$PATH`, the
intended behavior is:

- **No auto-install.** F4 must never shell out to a package manager on its
  own.
- The diagnostics panel surfaces a controlled message naming the missing
  tool and framing it as an installation-defect condition (for example,
  "Diagnostics unavailable: Biome executable is missing from the ECLI Full
  installation. This indicates an incomplete or damaged ECLI
  installation."), plus the catalog entry's repair metadata as
  developer/minimal/repair information — not as instructions for a routine
  post-install step.
- Repair is opt-in and explicit: `ecli doctor --install-linters` (see
  above) or manual installation, used to fix a damaged, partial, or
  minimal install — never presented as "install the linter pack after
  ECLI."
- This mirrors the existing failure-degradation rule for git/linter/LSP/AI
  subprocess failures in `.claude/CLAUDE.md`: the relevant feature degrades
  gracefully, the editor keeps running.
- F4 panel rendering itself is unaffected by any of this: layout, colors,
  keybindings, details popup, PASS state, and source-line highlighting are
  frozen (design doc section 4.1) regardless of which providers are
  present.

## Explicitly out of scope for this stage

- Executing any non-Ruff microservice's binary.
- Parsing any non-Ruff linter's real output (the `parser` field only names
  a future parser; no parser implementation exists for any tool besides
  Ruff, including for `"zig_text"`, `"biome_json"`, and `"xml_generic"`).
- Registering any non-Ruff linter with `DiagnosticsService` or the F4
  panel.
- Changing `RuffDiagnosticProvider`'s Python behavior.
- Config-file discovery/loading logic (the `config_files` field is metadata
  only).
- Any packaging implementation for DEB/RPM/Homebrew/etc. dependencies, or
  the `ecli doctor` subcommands described above.
- Any change to F4 panel rendering, layout, colors, keybindings, details
  popup, PASS state, or source-line highlighting.

## Next steps (not part of this change)

Runtime implementation follows the linter microservice architecture
defined by `docs/architecture/ecli-f4-linter-microservices-design.md`:

1. `command_runner.py` under `src/ecli/extensions/linters/core/`: a small,
   linter-agnostic shared safe subprocess runner (design doc section 8 /
   Stage 2). Not yet implemented.
2. Per-linter `parser.py` and `provider.py` modules, one microservice at a
   time (design doc Stage 3 onward: Biome, Zig, ShellCheck, Markdownlint,
   Yamllint, Actionlint, Hadolint, Taplo first; then Clang-Tidy, Cppcheck,
   Clang-Format, Java Checkstyle/PMD/SpotBugs, Cargo Clippy,
   golangci-lint; then SQLFluff, TFLint) — never a single monolithic
   `external_linter_provider.py` that dispatches every tool from
   `argv_template` directly.
3. Backend registration of each new provider with `DiagnosticsService` in
   `src/ecli/integrations/LinterBridge.py` (where `RuffDiagnosticProvider`
   is registered today), gated on `enabled_by_default` and on the target
   binary actually being present on `$PATH` or in an ECLI-managed tools
   directory. This is registration only —
   the F4 panel, its layout, colors, keybindings, details popup, and PASS
   visualization stay frozen and reused unchanged (design doc section 4.1).
4. `ecli doctor --check-linters` and `ecli doctor --install-linters` as
   repair/verification tools only (see above).
5. Full-installation packaging work integrated into ECLI's existing 21
   artifact contract entries (design doc sections 4.3/18.2), not a
   parallel matrix.
