# ECLI F4 Diagnostics Linter Microservices

**Document status:** Architecture and implementation doctrine  
**Target area:** F4 Diagnostics / Linter Panel  
**Language:** English  
**Scope:** Runtime architecture, provider model, packaging contract, installation philosophy, test strategy, and implementation rules for the ECLI F4 linter system  
**Non-scope:** UI redesign, panel layout changes, visual redesign, new keybindings, optional post-install marketplace, VS Code extension emulation

---

## 1. Executive Summary

F4 Diagnostics in ECLI must evolve from a Ruff-only diagnostics feature into a complete, full-install, multi-language diagnostics system. The correct design is not a single generic external linter dispatcher and not a VS Code-style extension marketplace. The correct design is an ECLI-owned linter microservice architecture.

Each supported linter must be represented as an independent diagnostics microservice inside the ECLI source tree. A microservice is not a separate operating-system daemon. In this design, a microservice is a bounded runtime component with its own directory, provider, parser, manifest, packaging contract, tests, fixtures, and ownership boundary.

The F4 UI is already acceptable and must remain unchanged. The current Ruff-based user experience is the reference behavior. Every new linter must adapt its output to the existing normalized diagnostics contracts so the same panel, same list, same details popup, same PASS state, same navigation behavior, and same source-line highlight are reused without visual changes.

The product expectation is also strict: ECLI Full installation must be complete. Users must not be expected to install linters manually after installing ECLI. A normal ECLI Full installer must detect the operating system and the canonical artifact context, check which required linter/toolchain executables already exist, install or bundle only the missing required tools through the correct OS/artifact-specific mechanism, and verify executability plus version probes before declaring the installation complete. Doctor commands or manual installation notes may exist later only as repair or verification tools for damaged, development, minimal, or partial environments. They must not be part of the normal installation experience.

The release and packaging side of this feature must obey the existing canonical release contract: exactly 21 artifact contract entries. Not fewer, not more. Every change needed for full linter installation must be represented through those existing 21 artifact contract entries, their tests, docs, release runbooks, and packaging evidence.

---

## 2. Design Doctrine

### 2.1 ECLI Is Not VS Code

ECLI must not copy the VS Code extension marketplace model. VS Code can expect users to install a linter extension, configure it, install a runtime dependency, and then troubleshoot the result. ECLI must not push this burden to the user.

ECLI is a terminal-first engineering workbench. The F4 diagnostics feature must feel like part of the product, not a partially wired integration layer. When a user installs the full ECLI package and opens a supported file, F4 diagnostics should work immediately.

This means:

- No VS Code marketplace dependency.
- No raw TypeScript VS Code extension runtime source in `src/ecli/extensions`.
- No "install random extension" workflow.
- No normal user path where F4 says only that a linter is missing and leaves the user unsupported.
- No monolithic generic linter dispatcher that hides all tools in one large file.
- No UI-specific implementation per linter.

The correct ECLI design is a curated diagnostics platform with clear ownership and predictable behavior.

### 2.2 Full Installation Is the Product Contract

The F4 diagnostics system must be designed under the assumption that ECLI Full includes the required linter toolchain. Missing executables may still be handled at runtime for safety, but such messages represent one of these cases:

1. The user is running a development checkout.
2. The installation is partial or damaged.
3. The platform package has a packaging defect.
4. The user intentionally installed a minimal or unsupported build.

Missing executable handling is a defensive fallback. It is not the intended product experience.

A normal full installation must include the supported linter stack through one of these platform-appropriate mechanisms:

- Native package-manager dependencies where the target OS repository is reliable.
- Bundled standalone binaries where licensing, provenance, and artifact size allow it.
- Verified upstream release downloads, including GitHub release artifacts, where native packages are unavailable or unsuitable.
- Language package-manager installs where that ecosystem is the authoritative delivery channel.
- Dedicated ECLI-managed tool directories, such as an app-local tools directory or `~/.local/share/ecli-linters` for repair/minimal paths.
- Shims or wrappers where a tool is delivered as a JAR, toolchain component, or app-local binary.
- Runtime resources shipped with the ECLI artifact.
- Platform-specific packaging scripts that install or include the toolchain.

The installer must inspect already-installed tools before installing anything. It must not overwrite a valid user/system tool just to satisfy the linter pack unless the artifact contract explicitly owns that tool location.

GitHub and upstream binary, JAR, or tarball downloads are allowed provisioning strategies, but only under a provenance-aware contract:

- explicit source URL;
- pinned version;
- checksum verification where upstream publishes checksums, and an ECLI-maintained checksum/provenance record otherwise;
- executable permission handling;
- no silent unverified binary execution;
- clear provenance in each linter's `package_contract.py`;
- release artifact verification evidence;
- deterministic install logs.

This must be documented and tested per release artifact contract.

### 2.3 Microservice Architecture Means Directory-Level Ownership

For F4 linters, microservice architecture means each linter or linter family owns its own directory and internal files. It does not mean a distributed network service. It means independent implementation units with stable boundaries.

A linter microservice has:

- Its own directory.
- Its own `provider.py`.
- Its own `parser.py`.
- Its own `manifest.py`.
- Its own `package_contract.py`.
- Its own test fixtures.
- Its own tests.
- Its own runtime safety rules.
- Its own supported file/language detection logic.
- Its own command construction logic.
- Its own output parser and diagnostic normalization logic.
- Its own packaging dependency or bundling declaration.

This makes each linter replaceable. Biome can be replaced without touching Zig. Zig can be improved without touching Java. Java providers can be split into Checkstyle, PMD, and SpotBugs without modifying the C/C++ providers. C/C++ can evolve from Clang-Tidy plus Cppcheck to a richer profile without destabilizing ShellCheck.

### 2.4 The Existing F4 UI Is Frozen

The F4 panel behavior already works well with Ruff. The work now is to repeat the backend contract for each linter, not to redesign the interface.

The following must remain unchanged in this stage:

- F4 opens or closes the Diagnostics Panel.
- `r` runs diagnostics for the current file.
- `R` runs diagnostics for the workspace.
- `Enter` jumps to the selected diagnostic.
- `d` or Space opens details for the selected diagnostic.
- PASS remains visually green.
- Diagnostics rows continue using the existing normalized display.
- Source-line and gutter highlight behavior remains unchanged.
- Details popup layout remains unchanged.
- Panel layout remains unchanged.
- Colors remain unchanged.
- Keybindings remain unchanged.
- No separate UI per linter.
- No linter-specific panel.

Every linter must return the existing `DiagnosticResult` and `Diagnostic` model. The panel must not need to know whether the diagnostic came from Ruff, Biome, Zig, Clang-Tidy, Checkstyle, ShellCheck, or any other provider.

---

## 3. Current Baseline

### 3.1 Ruff Is the Reference Implementation

The existing Ruff integration is the model to repeat. It has a dedicated provider, runs a real command, parses output, handles subprocess failure, and returns normalized diagnostics.

The new linter system should not treat Ruff as a special UI case. Ruff is special only because it already exists and is the internal/core Python provider. Architecturally, every other linter should achieve the same shape:

- Determine applicability.
- Build safe argv.
- Execute with bounded runtime behavior.
- Parse stdout/stderr.
- Normalize findings to `Diagnostic`.
- Return `DiagnosticResult`.
- Preserve provider state.

### 3.2 The Current Catalog Is Not Runtime

**Path correction:** the monolithic `src/ecli/diagnostics/linter_catalog.py` from earlier drafts of this document has been replaced by `src/ecli/extensions/linters/core/registry.py` (the shared `LinterDefinition`/`PackageContract` types and generic lookup helpers) plus one `manifest.py` per linter microservice, aggregated by `src/ecli/extensions/linters/__init__.py`. This is valuable as metadata but must not be confused with the runtime implementation. Its proper role is to define product metadata, installation metadata, and pack metadata. It should not execute tools or parse output.

The catalog should answer questions such as:

- What is the default linter for a language group?
- Is the tool core, recommended, optional, or legacy?
- Which install group owns it?
- Is it bundled with full installation?
- What package hints or homepage metadata belong to it?
- Is it internal or external?
- What parser family is expected?
- What tool supersedes an older default?

The catalog must not become a dispatcher and must not become a hidden monolithic provider.

### 3.3 DiagnosticsService Must Remain the Runtime Registry

`DiagnosticsService` already owns provider registration, asynchronous execution, result merging, generation handling, coalescing, and final status construction. The microservice architecture must plug into this existing service instead of bypassing it.

The service must be extended carefully to support provider applicability. Providers that do not support the current request should not run and should not emit irrelevant skip messages. This is essential to prevent Ruff from producing Python-only skip messages for Markdown, Zig, Java, C/C++, YAML, or Web files.

---

## 4. Hard Invariants

### 4.1 UI Invariants

The UI is frozen for this workstream. Any change to panel rendering, layout, visual display, color model, keybindings, focus behavior, details popup, PASS state, or highlight behavior is out of scope unless it fixes a provider-neutral bug and is justified separately.

All new linter work must happen behind the existing diagnostics interface.

### 4.2 Installation Invariants

ECLI Full installation must install a complete diagnostics toolchain for the supported base language set. It is unacceptable for the normal product experience to require users to manually install linters after installation.

The only acceptable uses of missing-tool messages are:

- Development checkout diagnostics.
- Damaged install diagnostics.
- Minimal package diagnostics, if a minimal package is explicitly produced and documented.
- Platform limitation reports.
- Packaging defect detection.

### 4.3 Packaging Contract Invariants

The release contract has exactly 21 artifact contract entries. F4 linter installation work must be integrated into the existing 21-artifact matrix in `docs/release/artifact-contract.md`. It must not create an informal parallel release matrix and must not invent untracked packaging surfaces.

Every packaging change related to linter installation must update:

- Product/release documentation.
- Artifact contract documentation.
- Build and release runbooks.
- Packaging validation tests.
- Artifact verification where relevant.
- Agent contracts if they remain part of the repository workflow.

### 4.4 Runtime Safety Invariants

Each provider must obey the same runtime safety rules:

- No `shell=True`.
- Explicit argv list only.
- Timeout required.
- Bounded stdout/stderr capture required.
- No package-manager execution from F4.
- No auto-install from F4.
- No mutation of source files during diagnostics.
- No formatter/fix mode in Stage 1 diagnostics.
- No unbounded workspace scan on file diagnostics.
- No UI-thread blocking.
- No traceback surfacing in the panel.
- Controlled error or skipped result on tool failure.

### 4.5 Source Tree Invariants

Raw upstream linter runtime source should not be dumped under `src/ecli/extensions`. ECLI must own its Python runtime integration. If upstream source is used for reference, it should remain outside committed runtime code unless legal provenance, license, and architectural fit are established.

---

## 5. Target Directory Architecture

**Path correction:** F4 linter diagnostics live under the ECLI Extensions
Layer, not under `src/ecli/diagnostics/`. `src/ecli/diagnostics/` is
reserved for future general/system diagnostics (System Doctor / F8,
environment health checks) and must not contain F4 linter code. Every
`src/ecli/extensions/linters/...` path in earlier drafts of this document
is corrected to `src/ecli/extensions/linters/...` below and throughout this
document. This is a path correction only; every other invariant in this
document (UI freeze, microservice shape, full-install philosophy, the
21-artifact contract) is unchanged.

The target runtime structure is directory-based:

```text
src/ecli/extensions/linters/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── display.py
│   ├── models.py
│   ├── service.py
│   ├── provider_protocol.py
│   ├── registry.py
│   ├── command_runner.py
│   └── provider_utils.py
├── ruff/
│   ├── __init__.py
│   ├── provider.py
│   ├── parser.py
│   ├── manifest.py
│   ├── package_contract.py
│   └── fixtures/
├── biome/
│   ├── __init__.py
│   ├── provider.py
│   ├── parser.py
│   ├── manifest.py
│   ├── package_contract.py
│   └── fixtures/
├── zig/
├── clang_tidy/
├── cppcheck/
├── clang_format/
├── java_checkstyle/
├── java_pmd/
├── java_spotbugs/
├── shellcheck/
├── markdownlint/
├── yamllint/
├── actionlint/
├── hadolint/
├── taplo/
├── cargo_clippy/
├── golangci_lint/
├── sqlfluff/
└── tflint/
```

`core/` holds the shared, linter-agnostic diagnostics contract (normalized
`Diagnostic`/`DiagnosticResult` models, `DiagnosticsService`, the
`DiagnosticProvider` protocol, and the `LinterDefinition`/`PackageContract`
registry types every microservice's `manifest.py`/`package_contract.py`
builds an instance of). This structure intentionally avoids one giant
provider file. A small shared `command_runner.py` is allowed, but it must
not become a monolithic provider. It should only provide safe subprocess
primitives used by individual providers.

---

## 6. Microservice Internal Contract

Every linter microservice directory should follow a stable internal contract.

### 6.1 `manifest.py`

The manifest declares product and runtime metadata for the linter microservice. It may import or mirror a `LinterDefinition` from the central catalog, but the microservice owns the final executable/runtime contract.

Expected contents:

```python
SERVICE_NAME = "biome"
DISPLAY_NAME = "Biome"
LANGUAGES = (...)
FILE_EXTENSIONS = (...)
PRIMARY_EXECUTABLES = (...)
INSTALL_GROUP = "web"
TIER = "recommended"
BUNDLED_WITH_FULL_INSTALL = True
PROVIDER_KIND = "external"
WORKSPACE_CAPABLE = False
MUTATES_FILES_IN_DIAGNOSTICS = False
```

The manifest must also declare packaging expectations:

- Required binary names.
- Expected version command.
- Supported platform availability.
- Whether native packages can depend on the tool.
- Whether portable artifacts must bundle the tool.
- Whether a tool is internal, external, vendored, or build-integrated.

### 6.2 `provider.py`

The provider owns request applicability and execution.

Expected responsibilities:

- `name`.
- `enabled`.
- `supports(request)`.
- `run(request)`.
- File-scope command construction.
- Workspace-scope command construction where supported.
- Root detection where needed.
- Missing executable handling.
- Timeout handling.
- Error handling.
- Return `DiagnosticResult`.

A provider must not know about UI rendering. It returns normalized results only.

### 6.3 `parser.py`

The parser owns conversion from tool output to normalized `Diagnostic` objects.

Expected responsibilities:

- Parse stdout/stderr fixtures.
- Reject malformed structures safely.
- Preserve file, line, column, severity, code, message, and source where possible.
- Map tool severities into ECLI severities.
- Return sorted diagnostics or let the service sort them.
- Never raise unhandled exceptions for malformed output.

### 6.4 `package_contract.py`

The package contract declares how the linter is delivered in ECLI Full.

Expected responsibilities:

- Define platform-specific delivery mode.
- Define binary names expected after installation.
- Define validation commands.
- Define package dependencies or bundled binary locations.
- Define checks for all applicable artifacts in the canonical set of exactly 21 artifact contract entries.
- Define whether the tool is mandatory for Full installation.
- Define the preferred OS-aware delivery mode for each artifact family.
- Define fallback delivery modes for platforms where native package names or repository quality are not reliable.
- Define source URL, version pin, checksum/provenance evidence, and executable permission handling for GitHub or upstream release downloads.
- Define deterministic version verification evidence after installation.
- Treat manual install instructions as developer checkout, minimal install, or repair documentation only.

### 6.5 `fixtures/`

Each linter must have parser fixtures. Fixtures should include:

- Clean output.
- Single diagnostic output.
- Multiple diagnostics output.
- Malformed output.
- Nonzero exit output.
- Tool-specific edge cases.

---

## 7. Provider Interface

### 7.1 Required Provider Shape

The provider protocol should evolve to support `supports(request)`.

```python
class DiagnosticProvider(Protocol):
    name: str
    enabled: bool

    def supports(self, request: DiagnosticRequest) -> bool:
        ...

    def run(self, request: DiagnosticRequest) -> DiagnosticResult:
        ...
```

If backward compatibility is needed during migration, providers without `supports` can be treated as supporting all requests temporarily. The end state should require explicit `supports` for all providers.

### 7.2 Applicability Rule

A provider should be run only when it supports the request. This prevents unrelated skip messages.

Examples:

- Ruff supports Python and `.py`/`.pyi`.
- Biome supports JS/TS/JSON/CSS/GraphQL files.
- Zig supports `.zig`.
- Clang-Tidy supports `.c`, `.cc`, `.cpp`, `.cxx`, `.h`, `.hpp`, and related C/C++ extensions when enough compile context exists.
- Checkstyle supports `.java`.
- Actionlint supports `.github/workflows/*.yml` and `.github/workflows/*.yaml`, not every YAML file.
- Cargo Clippy supports Rust project scope when a `Cargo.toml` root exists.

### 7.3 No Applicable Provider

If no provider supports a request, the service should return a controlled skipped result:

```text
No diagnostics provider available for this file type.
```

This is different from a missing executable. A missing executable means the provider exists and supports the file, but the installation is incomplete or damaged.

---

## 8. Common Command Runner

A shared command runner is allowed because subprocess safety should be consistent. It must not contain linter-specific dispatch logic.

Expected API:

```python
@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    execution_error: str | None = None


def run_linter_command(
    argv: Sequence[str],
    *,
    cwd: str,
    input_text: str | None,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    runner: Runner = subprocess.run,
) -> CommandResult:
    ...
```

Rules:

- The runner must always call subprocess with a list.
- The runner must not use shell interpolation.
- Output must be bounded.
- Timeouts must be explicit.
- Errors must be converted to structured results.
- The runner must not know which linter it is running.

---

## 9. Provider Registration

Provider registration should be explicit and deterministic.

Recommended provider order:

1. Ruff
2. Biome
3. Zig
4. Clang-Tidy
5. Cppcheck
6. Clang-Format check component
7. Java Checkstyle
8. Java PMD
9. Java SpotBugs
10. ShellCheck
11. Markdownlint
12. Yamllint
13. Actionlint
14. Hadolint
15. Taplo
16. Cargo Clippy
17. GolangCI-Lint
18. SQLFluff
19. TFLint

The exact registration location must be where `RuffDiagnosticProvider` is currently registered. The change should not introduce a parallel diagnostics service.

---

## 10. Language and Tool Matrix

### 10.1 First-Class Base Profiles

The full diagnostics platform should treat the following profiles as first-class:

| Profile | Primary tools | Notes |
|---|---|---|
| Python | Ruff | Core/internal provider. Pylint is optional, not a replacement. |
| Web | Biome | Default for JS/TS/JSON/CSS/GraphQL. ESLint is legacy/optional. |
| C/C++ | Clang-Tidy, Cppcheck, Clang-Format check | First-class systems profile. |
| Java | Checkstyle, PMD, SpotBugs | First-class language profile. Error Prone is optional/build-integrated. |
| Zig | Zig toolchain | First-class systems language. |
| Rust | Cargo Clippy | Project-root aware. |
| Shell | ShellCheck | DevOps/script profile. |
| Markdown | markdownlint-cli2 | Core documentation profile. |
| YAML | yamllint | Core config profile. |
| GitHub Actions | actionlint | Only workflow YAML. |
| Dockerfile | Hadolint | Container build profile. |
| TOML | Taplo | Core config profile. |
| Go | golangci-lint | Recommended language profile. |
| SQL | SQLFluff | Data profile. |
| Terraform | TFLint | Infrastructure profile. |

### 10.2 Legacy and Optional Tools

The following tools should not be default providers in the base system:

| Tool | Status | Reason |
|---|---|---|
| ESLint | Legacy/optional | Superseded by Biome as default for ECLI's modern web profile. |
| Pylint | Optional | Ruff remains Python default. Pylint may be deep-lint opt-in. |
| Stylelint | Optional | Specialist CSS coverage beyond Biome. |
| Error Prone | Optional/build-integrated | Requires Java build/compiler integration. |
| Vale/Textlint/LanguageTool | Optional prose profile | Useful but outside base code diagnostics unless explicitly selected. |
| RuboCop/Reek/Brakeman | Optional Ruby profile | Important for Ruby/Rails, not base first stage. |
| PHPStan/PHP_CodeSniffer/Pint | Optional PHP profile | Important for PHP, not base first stage unless PHP is later elevated. |
| SwiftLint/Dart/Luacheck | Optional language profiles | Can be added as dedicated microservices later. |

---

## 11. C/C++ Profile

C/C++ must be first-class. It cannot be omitted from ECLI's F4 diagnostics strategy.

### 11.1 `clang_tidy` Microservice

Directory:

```text
src/ecli/extensions/linters/clang_tidy/
```

Purpose:

- C diagnostics where Clang-Tidy can operate.
- C++ diagnostics.
- Header diagnostics when compile context exists.
- Project-aware analysis using `compile_commands.json` when available.

Supported extensions:

```text
.c, .h, .cc, .cpp, .cxx, .hpp, .hh, .hxx
```

Command model:

```text
clang-tidy <file> --quiet --export-fixes=-
```

or a safer initial text-output mode if YAML fixes output is not needed.

Root/context detection:

- Prefer `compile_commands.json`.
- Detect CMake build directories where possible.
- For isolated files, run only if a safe fallback configuration exists.
- If compile context is missing, return controlled skipped result explaining that C/C++ diagnostics require compile database context.

### 11.2 `cppcheck` Microservice

Directory:

```text
src/ecli/extensions/linters/cppcheck/
```

Purpose:

- Secondary static analysis for C/C++.
- Useful even when Clang-Tidy context is limited.

Command model:

```text
cppcheck --enable=warning,style,performance,portability --template=json <file>
```

If JSON output is not stable across installed versions, use a fixture-backed text parser.

### 11.3 `clang_format` Check Component

Directory:

```text
src/ecli/extensions/linters/clang_format/
```

Purpose:

- Formatting compliance diagnostics.
- Not a semantic linter.
- Should report formatting drift as diagnostics without mutating files.

Command model:

```text
clang-format --dry-run --Werror <file>
```

This provider must never rewrite files during F4 diagnostics.

---

## 12. Java Profile

Java must be first-class. A useful Java diagnostics profile requires more than one tool because Java analysis spans style, source rules, bytecode bug detection, and optional build-integrated compiler checks.

### 12.1 `java_checkstyle` Microservice

Directory:

```text
src/ecli/extensions/linters/java_checkstyle/
```

Purpose:

- Java coding standard checks.
- Source-level style and convention diagnostics.

Command model:

```text
checkstyle -f xml -c <config> <file>
```

Config detection:

- `checkstyle.xml`
- `config/checkstyle/checkstyle.xml`
- Maven/Gradle project conventions where safe

If no config is available, the provider may use an ECLI-curated default config bundled with the Java diagnostics microservice, but this must be explicit and documented.

### 12.2 `java_pmd` Microservice

Directory:

```text
src/ecli/extensions/linters/java_pmd/
```

Purpose:

- Java static rules.
- Common code smells.
- Maintainability and correctness warnings.

Command model:

```text
pmd check --format json --dir <file-or-source-root> --rulesets <ruleset>
```

Config detection:

- `pmd.xml`
- `ruleset.xml`
- ECLI-curated default PMD ruleset if no project config exists

### 12.3 `java_spotbugs` Microservice

Directory:

```text
src/ecli/extensions/linters/java_spotbugs/
```

Purpose:

- Bytecode-level bug detection.
- Project/build diagnostics.

SpotBugs is not a normal single-source-file linter. It requires compiled classes. Therefore:

- It should support workspace/project diagnostics.
- It should skip gracefully for isolated `.java` files without build output.
- It should detect Maven/Gradle outputs where possible.
- It must not run expensive builds automatically from F4.

### 12.4 `java_error_prone` Optional Component

Directory:

```text
src/ecli/extensions/linters/java_error_prone/
```

Purpose:

- Compiler-integrated Java bug detection.

This should be modeled as optional/build-integrated, not as a basic per-file F4 provider. It belongs in the Java profile manifest and packaging docs, but it should not block the first F4 implementation.

---

## 13. Zig Profile

Zig is a first-class systems language for ECLI and must not be treated as an afterthought.

Directory:

```text
src/ecli/extensions/linters/zig/
```

Primary command:

```text
zig fmt --check --ast-check <file>
```

Purpose:

- Formatting compliance check.
- Lightweight syntax/AST validation.

Rules:

- Do not mutate files.
- Do not use stdin until fixture-tested.
- Parse text output conservatively.
- If Zig is unavailable in a supposedly full install, report this as an installation defect message, not as a normal user action.

---

## 14. Web Profile

Biome is the default ECLI web linter.

Directory:

```text
src/ecli/extensions/linters/biome/
```

Supported languages:

- JavaScript
- TypeScript
- JSX
- TSX
- JSON
- JSONC
- CSS
- GraphQL

Command model:

```text
biome lint --reporter=json <file>
```

or, after fixture confirmation, `biome check --reporter=json <file>` if the combined formatter/linter/import organization behavior is desired without mutation.

Rules:

- ESLint must not be the default.
- ESLint may remain legacy/optional.
- Biome output parser must be fixture-backed because reporter formats can evolve.
- No Biome daemon dependency should be introduced in Stage 1.
- The provider must not run `biome format --write` or any mutating command during F4 diagnostics.

---

## 15. Runtime Flow

### 15.1 Current File Diagnostics

When the user presses `F4` and then `r`:

1. The panel opens or is already open.
2. The UI requests diagnostics for the current buffer.
3. `DiagnosticsService` creates a `DiagnosticRequest`.
4. The service selects enabled providers whose `supports(request)` returns true.
5. Each applicable provider runs in the diagnostics worker flow.
6. Providers return `DiagnosticResult`.
7. The service merges diagnostics and statuses.
8. The existing panel renders the normalized result.

No panel changes are required.

### 15.2 Workspace Diagnostics

Workspace diagnostics are more dangerous than file diagnostics. Some tools operate on whole projects by design, while others should remain file-local.

Rules:

- Workspace mode must not blindly run every tool across the repository.
- Project-root tools must detect safe roots.
- Expensive tools must be bounded.
- Build-triggering tools must not trigger builds automatically.
- Tools requiring compiled artifacts must skip if artifacts are absent.
- Workspace diagnostics should be introduced per microservice only after file mode is stable, unless the tool is inherently workspace-only.

### 15.3 Result Aggregation

Aggregation must preserve useful messages and avoid unrelated pollution.

Bad behavior:

```text
Markdown file -> Ruff diagnostics are only available for Python files.
```

Correct behavior:

```text
Markdown file -> Markdownlint diagnostics, PASS, or installation-defect message.
```

The service should not run Ruff for Markdown once `supports(request)` exists. The same applies to all other unrelated providers.

---

## 16. Diagnostic Normalization

All providers must produce the existing `Diagnostic` structure:

```python
Diagnostic(
    file_path=...,
    line=...,
    column=...,
    severity="error" | "warning" | "info" | "hint",
    code=...,
    message=...,
    source=...,
    fix_hint=...,
    suggested_code=...,
)
```

Severity mapping must be documented per provider.

General mapping:

- Tool fatal errors that point to code defects -> `error`.
- Tool warnings -> `warning`.
- Style and maintainability notes -> `info` or `warning`, depending on the tool.
- Formatting suggestions -> `hint` or `warning`, depending on the F4 policy.

Diagnostic source must be stable and human-readable:

- `ruff`
- `biome`
- `zig`
- `clang-tidy`
- `cppcheck`
- `clang-format`
- `checkstyle`
- `pmd`
- `spotbugs`
- `shellcheck`
- `markdownlint-cli2`
- `yamllint`
- `actionlint`
- `hadolint`
- `taplo`
- `cargo-clippy`
- `golangci-lint`
- `sqlfluff`
- `tflint`

---

## 17. Error Handling Philosophy

### 17.1 Missing Executable

In full installation, a missing executable is an installation defect. The runtime still must handle it cleanly:

```text
Diagnostics unavailable: Biome executable is missing from the ECLI Full installation.
This indicates an incomplete or damaged ECLI installation.
```

The message may include repair information, but it must not frame manual installation as the normal product path.

### 17.2 Tool Timeout

A timeout should produce a controlled error result:

```text
Biome timed out after 15.0s.
```

The provider should not crash the diagnostics worker.

### 17.3 Parser Failure

Malformed output must not crash the provider. The parser should return either:

- Empty diagnostics with a controlled error message.
- Partial diagnostics plus a warning logged to `editor.log`.
- A provider error if the output is entirely unusable.

### 17.4 Tool Exit Codes

Each provider must understand its tool's normal diagnostic exit codes. Some linters return nonzero when diagnostics are found. That must not automatically mean provider failure.

Provider-specific exit code policy must live in the provider or parser tests.

---

## 18. Packaging and Full Installation Contract

### 18.1 Full Installation Requirement

ECLI Full must include the base linter set. A user should not install ECLI and then be expected to install Biome, Zig, Clang-Tidy, Checkstyle, ShellCheck, or Markdownlint separately before F4 works.

The full package must include or depend on:

- Ruff
- Biome
- Zig toolchain diagnostics component
- Clang-Tidy
- Cppcheck
- Clang-Format
- Java Checkstyle
- Java PMD
- Java SpotBugs
- ShellCheck
- markdownlint-cli2
- yamllint
- actionlint
- Hadolint
- Taplo
- Cargo Clippy or Rust toolchain component where feasible
- golangci-lint
- SQLFluff
- TFLint

Some tools may require platform-specific handling. The packaging contract must make this explicit.

### 18.2 Exactly 21 Artifact Contract Entries

All packaging work must be integrated into the existing canonical matrix in `docs/release/artifact-contract.md`. The linter pack must not create a shadow packaging matrix. Every Full installation provisioning contract must map to exactly 21 artifact contract entries:

1. PyPI wheel
2. PyPI source distribution
3. Linux generic PyInstaller executable
4. Linux release tarball
5. Debian / Ubuntu `.deb`
6. generic RPM `.rpm`
7. openSUSE / SUSE RPM
8. Arch Linux `PKGBUILD`
9. Slackware `.txz`
10. AppImage
11. FreeBSD `.pkg`
12. FreeBSD ports/chroot build path
13. macOS `.app`
14. macOS `.dmg`
15. Windows portable `.exe`
16. Windows NSIS installer `.exe`
17. Nix flake
18. Nix/NixOS package expression
19. Docker DEB build helper
20. Docker RPM build helper
21. GitHub Actions release/workflow contract map

Every entry must be tested according to the existing release contract. Do not describe this as a loose set of platforms or packaging targets when the normative requirement is exactly 21 artifact contract entries.

### 18.3 Platform Delivery Modes

Different artifact types may deliver linters differently, but every Full installer/provisioner path must first detect the OS/artifact context, then check for already-installed required tools before installing or bundling missing tools:

- Debian/Ubuntu `.deb`: two-stage model on Debian 13 — the standalone
  linter installer (`scripts/install_ecli_linters.py`) provisions the
  19-tool toolchain into `/opt/ecli/payload` first; the `.deb` installs
  only ECLI itself and discovers tools through `PATH`
  (see `docs/install/debian.md`).
- RPM/openSUSE: package dependencies or bundled tools.
- Arch: `depends`/`makedepends` or bundled tools.
- Slackware: bundled tools or documented package metadata.
- AppImage: bundled tools inside the AppImage runtime.
- Linux generic tarball: bundled tools under an ECLI-managed runtime directory.
- PyInstaller artifacts: bundled tools or adjacent runtime payload.
- FreeBSD pkg: package dependencies or bundled tools according to FreeBSD availability.
- macOS DMG: bundled tools inside app resources or companion runtime directory.
- Windows portable and NSIS: bundled `.exe` tools or managed runtime payload.
- Nix/NixOS: derivation dependencies.
- PyPI wheel/sdist: limited by Python packaging; must document that plain PyPI cannot reliably provision Node, Rust, Go, Zig, Java, and system binaries. PyPI/source installs may be minimal; Full platform artifacts are the supported user path for complete linter provisioning.

### 18.4 Validation

Every full-install artifact must have a validation path proving:

- The linter microservice files are present.
- Required binaries or package dependencies are present.
- The installer detects the operating system and artifact context before provisioning.
- Already-installed valid tools are detected before missing tools are installed or bundled.
- Version probes work.
- Executability checks pass.
- F4 provider registration is available.
- Basic smoke diagnostics can run or at least load without missing executable defects.
- Package-manager dependencies assert the package relationship and post-install executable availability.
- Bundled or upstream-downloaded tools have source URL, version pin, checksum/provenance evidence, executable permission handling, deterministic install logs, and post-install version checks.
- Checksum sidecars remain valid.
- The release artifact count remains exactly 21.
- A missing required linter after ECLI Full installation is a release blocker, unless the artifact entry explicitly documents a platform limitation and downgraded/minimal status before release.

---

## 19. Test Strategy

### 19.1 Unit Tests Per Microservice

Each microservice must have focused tests:

```text
tests/extensions/linters/test_biome_provider.py
tests/extensions/linters/test_biome_parser.py
tests/extensions/linters/test_biome_manifest.py
tests/extensions/linters/test_biome_package_contract.py
```

Equivalent tests are required for every first-class provider.

### 19.2 Shared Contract Tests

Shared tests must verify:

- Every provider implements `supports`.
- Every provider returns `DiagnosticResult`.
- No provider uses `shell=True`.
- Every command is argv-list based.
- Every provider has a timeout.
- Every provider has bounded output capture.
- No provider runs package-manager install commands.
- No provider mutates files during diagnostics.
- Every full-install provider has a package contract.
- Every full-install provider maps to exactly 21 artifact contract entries.

### 19.3 UI Regression Tests

UI tests must assert no regression in existing F4 behavior:

- F4 open behavior unchanged.
- `r` triggers current-file diagnostics.
- `R` triggers workspace diagnostics.
- Details popup unchanged.
- PASS state unchanged.
- Row rendering unchanged.
- Highlight behavior unchanged.
- Ruff behavior unchanged.

The UI tests should not become linter-specific.

### 19.4 Parser Fixture Tests

Every parser needs fixture tests. Examples:

- Biome JSON with one diagnostic.
- Biome JSON with multiple diagnostics.
- Zig text output.
- Clang-Tidy text/YAML output.
- Cppcheck XML/JSON/text output, depending on chosen mode.
- Checkstyle XML.
- PMD JSON/XML.
- SpotBugs XML.
- ShellCheck JSON.
- markdownlint-cli2 output.
- yamllint parsable output.
- actionlint text output.
- hadolint JSON.
- Taplo text output.
- Cargo JSON stream.

### 19.5 Packaging Tests

Packaging tests must verify the full-install claim per artifact type.

At minimum:

- Package metadata includes dependencies or bundled tool paths.
- Portable artifacts include the linter runtime payload.
- Checksums remain valid.
- No artifact count drift.
- No undocumented packaging surface appears.
- No linter microservice lacks a packaging contract.

---

## 20. Implementation Sequence

### Stage 0: Freeze and Document

- Write this design document.
- Document hard UI freeze.
- Document full-install requirement.
- Document microservice directory structure.
- Document exactly 21 artifact contract dependency.

### Stage 1: Restructure Ruff into Microservice Shape

- Move or adapt Ruff into `extensions/linters/ruff/` while preserving import compatibility if needed.
- Keep `ruff_provider.py` shim if existing imports require it.
- Add `supports(request)` to Ruff.
- Ensure Ruff no longer emits Python-only skip for unsupported files because unsupported files should not run Ruff.
- Keep all existing Ruff behavior for Python unchanged.

### Stage 2: Shared Safe Runner

- Add `command_runner.py`.
- Move common subprocess safety into reusable helper.
- Keep it generic and small.
- Prove no shell use and bounded output.

### Stage 3: Add First Provider Set

Add providers one by one, with tests:

1. Biome
2. Zig
3. ShellCheck
4. Markdownlint
5. Yamllint
6. Actionlint
7. Hadolint
8. Taplo

Do not add all providers in one unreviewable patch.

### Stage 4: Add Systems and Enterprise Languages

Add:

1. Clang-Tidy
2. Cppcheck
3. Clang-Format check
4. Java Checkstyle
5. Java PMD
6. Java SpotBugs
7. Cargo Clippy
8. GolangCI-Lint

### Stage 5: Add Data and Infra

Add:

1. SQLFluff
2. TFLint

### Stage 6: Full Installation Packaging

- Update package contracts.
- Update validation for exactly 21 artifact contract entries.
- Prove the full install includes the linter pack.
- Add release gate tests.

### Stage 7: Optional and Legacy Profiles

Only after the base system is stable:

- ESLint legacy provider.
- Pylint optional provider.
- Stylelint optional provider.
- Prose tools.
- Ruby/PHP/Swift/Dart/Lua profiles.

---

## 21. Acceptance Criteria

A linter microservice is accepted only when all of the following are true:

1. It has its own directory.
2. It has provider, parser, manifest, package contract, and fixtures.
3. It implements `supports(request)`.
4. It returns existing `DiagnosticResult`.
5. It never changes UI code.
6. It has parser tests.
7. It has provider tests.
8. It has package contract tests.
9. It obeys runtime safety rules.
10. It is integrated into provider registration.
11. It does not pollute unrelated file diagnostics.
12. It participates in full-install packaging evidence.
13. It does not introduce release artifact drift.
14. It preserves all Ruff behavior for Python.
15. It preserves all F4 panel behavior.

---

## 22. Explicit Non-Goals

This workstream must not do the following:

- Redesign F4 UI.
- Add a VS Code-like extension marketplace.
- Dump raw TypeScript linter extensions into `src/ecli/extensions`.
- Hide all linters in one monolithic provider.
- Make manual linter installation the normal user workflow.
- Run package managers from F4.
- Mutate files during diagnostics.
- Add fix-all/code actions in the first runtime stage.
- Change F7 AI.
- Change F10 File Browser.
- Change F11 PySH/terminal-console.
- Change TextMate rendering.
- Change theme numbering.
- Add unsupported release artifacts beyond the canonical 21-entry contract.

---

## 23. Terminology

### ECLI Linter Pack

The curated set of diagnostics tools that ECLI Full must include or depend on.

### Linter Microservice

A bounded in-process ECLI diagnostics component with its own directory, provider, parser, manifest, package contract, fixtures, and tests.

### Provider

The runtime object registered with `DiagnosticsService`. It decides applicability and returns `DiagnosticResult`.

### Parser

The module that converts tool-specific output into normalized ECLI `Diagnostic` objects.

### Manifest

The microservice metadata contract: language support, executable names, tier, install group, provider kind, and runtime properties.

### Package Contract

The per-microservice packaging contract describing how the tool is included in ECLI Full across exactly 21 artifact contract entries, including OS-aware delivery mode, version probe, executable names, and provenance/checksum requirements for upstream release downloads.

### Full Installation

The product installation that includes ECLI and its supported base linter toolchain. It must not require a second post-install step for supported F4 diagnostics.

---

## 24. Final Principle

The F4 Diagnostics system must behave like one coherent ECLI feature, not like a collection of optional external integrations. The backend may contain many independent linter microservices, but the user sees one stable panel and one consistent diagnostic experience.

The right model is:

```text
One F4 panel.
One normalized diagnostic contract.
Many isolated linter microservices.
One full installation.
Exactly 21 artifact contract entries.
No UI churn.
No marketplace burden.
No manual linter hunt.
```

This is the design boundary for all future F4 linter implementation work.
