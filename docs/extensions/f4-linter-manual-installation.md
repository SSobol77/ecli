<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/extensions/f4-linter-manual-installation.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# F4 Linter Manual Installation Reference

## Scope

ECLI Full installer behavior is automatic: detect the operating system and
artifact context, detect already-installed required tools first, install or
bundle only missing tools by the artifact-specific mechanism, and verify
executability plus versions. Manual installation is not the normal ECLI Full
user path.

Use this reference only for:

- developer checkouts;
- PyPI/source/minimal installs;
- repair of damaged or incomplete ECLI Full installs;
- advanced/custom system administration.

Commands below are examples. Package names and availability must be verified
against the active OS release, package manager, architecture, and selected ECLI
artifact before they become packaging implementation. Prefer OS packages where
they are reliable. When OS packages are absent, stale, or unsuitable, use an
ECLI-managed local tools directory, verified upstream release binaries/JARs, or
language package managers with pinned versions.

For GitHub or upstream binary, JAR, zip, tar.gz, or tar.xz downloads:

- record the source URL;
- pin the version;
- verify the checksum where upstream publishes one;
- keep ECLI-maintained checksum/provenance evidence where upstream does not;
- set executable permissions explicitly;
- do not run an unverified binary silently;
- retain deterministic install logs.

Example ECLI-managed locations:

```text
~/.local/share/ecli-linters/bin
~/.local/share/ecli-linters/npm-global/bin
~/.local/share/ecli-linters/venvs/<tool>/bin
~/.local/share/ecli-linters/java/<tool>
```

Add the selected `bin` directories to `PATH` or create shims under
`~/.local/bin`. Verify every tool after installation.

## Windows 10/11

For developer/minimal/repair use, prefer an ECLI-managed payload directory or a
well-maintained Windows package manager package. Exact `winget`, Scoop, or
Chocolatey IDs are to be verified in packaging implementation.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | `uv tool install ruff` or `pipx install ruff` | bundled ECLI tool payload | ensure the tool scripts directory is on `PATH` | `ruff --version` |
| Biome | npm custom prefix with pinned `@biomejs/biome` | verified upstream standalone binary | add npm prefix `bin` or shim `biome.exe` | `biome --version` |
| markdownlint-cli2 | npm custom prefix with pinned `markdownlint-cli2` | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | dedicated Python venv or `pipx install yamllint` | OS package manager package, to be verified | add venv `Scripts` path or shim | `yamllint --version` |
| ShellCheck | verified release binary or maintained package manager package | WSL package only for WSL-specific workflows | shim `shellcheck.exe` | `shellcheck --version` |
| Zig | verified upstream Windows zip | maintained package manager package, to be verified | add extracted directory or shim `zig.exe` | `zig version` |
| Hadolint | verified GitHub release binary | containerized/dev-only fallback | shim `hadolint.exe` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | verified release binary if provided | add Cargo `bin` | `taplo --version` |
| actionlint | verified GitHub release binary | `go install github.com/rhysd/actionlint/cmd/actionlint@<version>` | add Go/Cargo-style bin or shim | `actionlint --version` |
| clang-tidy | LLVM installer/package manager package, to be verified | ECLI-managed LLVM payload | ensure LLVM `bin` precedes stale versions | `clang-tidy --version` |
| cppcheck | maintained package manager package, to be verified | verified upstream installer or portable build | add install directory | `cppcheck --version` |
| Checkstyle | pinned Checkstyle JAR with Java runtime | maintained package manager package, to be verified | create `checkstyle.cmd` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned PMD release zip | maintained package manager package, to be verified | add PMD `bin` or shim `pmd.bat` | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | Rust toolchain package, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | LLVM installer/package manager package, to be verified | ECLI-managed LLVM payload | ensure LLVM `bin` precedes stale versions | `clang-format --version` |
| SpotBugs | pinned SpotBugs release zip plus Java runtime | maintained package manager package, to be verified | add `bin` or create shim | `spotbugs -version` |
| golangci-lint | verified upstream release binary | Go install/package manager package, to be verified | add selected `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv or `pipx install sqlfluff` | project-local venv for checkout only | add venv `Scripts` path or shim | `sqlfluff --version` |
| TFLint | verified GitHub release zip | maintained package manager package, to be verified | shim `tflint.exe` | `tflint --version` |

## Debian / Ubuntu

On Debian 13 amd64 the supported path is the official interactive
installer, `sudo python3 scripts/install_ecli_linters.py`, which
provisions all 19 tools from the committed lock
`packaging/debian/ecli-linter-lock.json` into `/opt/ecli/payload`
(see `docs/install/debian.md`). The manual strategies below remain valid
for developer checkouts and custom environments.

Debian 13 testing used a valid mixed user-space strategy: Ruff already in the
venv; npm custom prefix under `~/.local/share/ecli-linters/npm-global` for
Biome and markdownlint-cli2; dedicated venvs for yamllint and Python-delivered
tools; prebuilt binaries for ShellCheck, Hadolint, and actionlint where needed;
Zig upstream tar.xz; `cargo install` for Taplo; Checkstyle JAR shim; PMD release
tar.gz; and `rustup component add clippy`.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | existing ECLI/dev venv or `pipx install ruff` | OS package if version is acceptable, to be verified | add venv or pipx path | `ruff --version` |
| Biome | npm custom prefix with pinned `@biomejs/biome` | verified upstream binary | add `~/.local/share/ecli-linters/npm-global/bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix with pinned `markdownlint-cli2` | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | dedicated Python venv | `apt` package if version is acceptable, to be verified | shim venv executable into `~/.local/bin` | `yamllint --version` |
| ShellCheck | OS package where reliable | verified upstream/GitHub release binary | install under ECLI tools `bin` or shim | `shellcheck --version` |
| Zig | verified upstream tar.xz | OS package if version is acceptable, to be verified | add extracted directory or shim | `zig version` |
| Hadolint | verified GitHub release binary | OS package if available and current, to be verified | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | distro package if available, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | verified GitHub release binary | `go install github.com/rhysd/actionlint/cmd/actionlint@<version>` | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | OS LLVM package where reliable | dedicated ECLI-managed LLVM/venv strategy, to be verified | prefer versioned LLVM path if needed | `clang-tidy --version` |
| cppcheck | OS package where reliable | Python wheel with bundled native binary, to be verified | shim if installed in venv | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | OS package if current, to be verified | create `checkstyle` shim running `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream/GitHub release tar.gz | OS package if current, to be verified | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | distro Rust package if it includes Clippy, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | OS LLVM package where reliable | ECLI-managed LLVM payload, to be verified | prefer versioned LLVM path if needed | `clang-format --version` |
| SpotBugs | pinned upstream release tar.gz plus Java runtime | OS package if current, to be verified | add `bin` or shim | `spotbugs -version` |
| golangci-lint | verified upstream release tarball | distro package if current, to be verified | install under ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv | OS package if available/current, to be verified | shim venv executable | `sqlfluff --version` |
| TFLint | verified GitHub release zip | distro package if available/current, to be verified | install under ECLI tools `bin` | `tflint --version` |

## Fedora / RHEL

Use `dnf` packages where the active Fedora/RHEL/EPEL stream provides a current,
compatible tool. Mark package names and EPEL/AppStream enablement to be verified
in packaging implementation.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | `pipx install ruff` or dedicated venv | `dnf` package if current, to be verified | add pipx/venv path | `ruff --version` |
| Biome | npm custom prefix with pinned `@biomejs/biome` | verified upstream binary | add npm prefix `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | `dnf` package where current | dedicated Python venv | shim venv executable if used | `yamllint --version` |
| ShellCheck | `dnf`/EPEL package where current | verified upstream binary | install or shim into ECLI tools `bin` | `shellcheck --version` |
| Zig | upstream tar.xz with checksum | `dnf` package if current, to be verified | add extracted directory or shim | `zig version` |
| Hadolint | verified GitHub release binary | package manager package if current, to be verified | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | package manager package if current, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | verified GitHub release binary | Go install with pinned version | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | LLVM/clang-tools package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | `dnf` package where current | verified upstream or Python-wheel strategy, to be verified | shim if venv-based | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | package manager package if current, to be verified | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream release tar.gz | package manager package if current, to be verified | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | distro Rust package if it includes Clippy, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | LLVM/clang-tools package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | pinned release tar.gz plus Java runtime | package manager package if current, to be verified | add `bin` or shim | `spotbugs -version` |
| golangci-lint | verified upstream release tarball | `dnf` package if current, to be verified | install under ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv | package manager package if current, to be verified | shim venv executable | `sqlfluff --version` |
| TFLint | verified GitHub release zip | package manager package if current, to be verified | install under ECLI tools `bin` | `tflint --version` |

## openSUSE

Use `zypper` packages where the target openSUSE/SUSE repositories provide
current tools. Exact package names and repository requirements are to be
verified in packaging implementation.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | `pipx install ruff` or dedicated venv | `zypper` package if current, to be verified | add pipx/venv path | `ruff --version` |
| Biome | npm custom prefix with pinned package | verified upstream binary | add npm prefix `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | `zypper` package if current | dedicated Python venv | shim venv executable if used | `yamllint --version` |
| ShellCheck | `zypper` package if current | verified upstream binary | install or shim into ECLI tools `bin` | `shellcheck --version` |
| Zig | upstream tar.xz with checksum | `zypper` package if current, to be verified | add extracted directory or shim | `zig version` |
| Hadolint | verified GitHub release binary | package manager package if current, to be verified | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | package manager package if current, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | verified GitHub release binary | Go install with pinned version | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | LLVM package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | `zypper` package where current | verified upstream or Python-wheel strategy, to be verified | shim if venv-based | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | package manager package if current, to be verified | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream release tar.gz | package manager package if current, to be verified | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | distro Rust package if it includes Clippy, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | LLVM package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | pinned release tar.gz plus Java runtime | package manager package if current, to be verified | add `bin` or shim | `spotbugs -version` |
| golangci-lint | verified upstream release tarball | package manager package if current, to be verified | install under ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv | package manager package if current, to be verified | shim venv executable | `sqlfluff --version` |
| TFLint | verified GitHub release zip | package manager package if current, to be verified | install under ECLI tools `bin` | `tflint --version` |

## Arch Linux

Prefer official repository packages where available and current. AUR entries are
manual/developer repair options unless the packaging implementation adds its own
provenance and build evidence.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | `pacman` package if current | `pipx install ruff` or dedicated venv | add pipx/venv path if used | `ruff --version` |
| Biome | `pacman` package if current, to be verified | npm custom prefix or verified upstream binary | add npm/ECLI tools `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | AUR/package entry if maintained, to be verified | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | `pacman` package if current | dedicated Python venv | shim venv executable if used | `yamllint --version` |
| ShellCheck | `pacman` package if current | verified upstream binary | standard `/usr/bin` or ECLI tools `bin` | `shellcheck --version` |
| Zig | `pacman` package if current | upstream tar.xz with checksum | add extracted directory or shim | `zig version` |
| Hadolint | package entry if current, to be verified | verified GitHub release binary | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | package entry if current, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | `pacman` package if current, to be verified | verified GitHub release binary | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | `clang`/LLVM package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | `pacman` package if current | verified upstream or Python-wheel strategy, to be verified | shim if venv-based | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | package entry if current, to be verified | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream release tar.gz | package entry if current, to be verified | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | `rust` package component if present, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | `clang`/LLVM package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | pinned release tar.gz plus Java runtime | package entry if current, to be verified | add `bin` or shim | `spotbugs -version` |
| golangci-lint | `pacman` package if current | verified upstream release tarball | standard `/usr/bin` or ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | package entry if current, to be verified | dedicated Python venv | shim venv executable | `sqlfluff --version` |
| TFLint | package entry if current, to be verified | verified GitHub release zip | install under ECLI tools `bin` | `tflint --version` |

## Slackware

Slackware package names vary by release. Prefer official packages or
SlackBuilds only after verifying version, build inputs, and executable names.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | dedicated Python venv or `pipx` | SlackBuild/package if maintained, to be verified | add venv/pipx path | `ruff --version` |
| Biome | npm custom prefix | verified upstream binary | add npm/ECLI tools `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | dedicated Python venv | SlackBuild/package if maintained, to be verified | shim venv executable | `yamllint --version` |
| ShellCheck | SlackBuild/package if current, to be verified | verified upstream binary | standard path or ECLI tools `bin` | `shellcheck --version` |
| Zig | upstream tar.xz with checksum | SlackBuild/package if current, to be verified | add extracted directory or shim | `zig version` |
| Hadolint | verified GitHub release binary | SlackBuild/package if current, to be verified | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | SlackBuild/package if current, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | verified GitHub release binary | Go install with pinned version | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | LLVM package/SlackBuild, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | SlackBuild/package if current, to be verified | verified upstream or Python-wheel strategy | shim if venv-based | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | SlackBuild/package if current, to be verified | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream release tar.gz | SlackBuild/package if current, to be verified | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | SlackBuild Rust component if present, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | LLVM package/SlackBuild, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | pinned release tar.gz plus Java runtime | SlackBuild/package if current, to be verified | add `bin` or shim | `spotbugs -version` |
| golangci-lint | verified upstream release tarball | SlackBuild/package if current, to be verified | install under ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv | SlackBuild/package if current, to be verified | shim venv executable | `sqlfluff --version` |
| TFLint | verified GitHub release zip | SlackBuild/package if current, to be verified | install under ECLI tools `bin` | `tflint --version` |

## FreeBSD

Prefer `pkg` or ports where current and available. When a tool is absent or
stale, use ECLI-managed user-space installs or verified upstream release
artifacts with FreeBSD-compatible binaries.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | `pkg` package if current, to be verified | dedicated Python venv or `pipx` | add venv/pipx path | `ruff --version` |
| Biome | npm custom prefix | verified upstream binary if FreeBSD-compatible | add npm/ECLI tools `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | `pkg` package if current | dedicated Python venv | shim venv executable | `yamllint --version` |
| ShellCheck | `pkg` package if current | build/verified release path, to be verified | standard path or ECLI tools `bin` | `shellcheck --version` |
| Zig | `pkg` package if current | upstream tarball if FreeBSD-compatible, to be verified | add extracted directory or shim | `zig version` |
| Hadolint | `pkg` package if available/current, to be verified | build from source or verified compatible binary | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | ports/package if current, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | `pkg` package if current, to be verified | Go install with pinned version | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | LLVM package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | `pkg` package if current | verified upstream/build path, to be verified | standard path or shim | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | ports/package if current, to be verified | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream release tar.gz | ports/package if current, to be verified | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | ports/package Rust component if present, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | LLVM package, to be verified | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | pinned release tar.gz plus Java runtime | ports/package if current, to be verified | add `bin` or shim | `spotbugs -version` |
| golangci-lint | `pkg` package if current, to be verified | verified upstream/build path | standard path or ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv | `pkg` package if current, to be verified | shim venv executable | `sqlfluff --version` |
| TFLint | `pkg` package if current, to be verified | verified release zip/build path | install under ECLI tools `bin` | `tflint --version` |

## Nix / NixOS

Prefer Nix derivation inputs and wrapper construction over manual `PATH`
mutation. Exact attribute names are to be verified against the selected nixpkgs
revision.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | nixpkgs package input | dedicated venv for checkout only | wrapper should expose `ruff` | `ruff --version` |
| Biome | nixpkgs package input, to be verified | npm custom prefix for checkout only | wrapper should expose `biome` | `biome --version` |
| markdownlint-cli2 | nixpkgs package input, to be verified | npm custom prefix for checkout only | wrapper should expose `markdownlint-cli2` | `markdownlint-cli2 --version` |
| yamllint | nixpkgs package input | dedicated venv for checkout only | wrapper should expose `yamllint` | `yamllint --version` |
| ShellCheck | nixpkgs package input | none preferred | wrapper should expose `shellcheck` | `shellcheck --version` |
| Zig | nixpkgs package input | pinned upstream derivation if needed | wrapper should expose `zig` | `zig version` |
| Hadolint | nixpkgs package input, to be verified | pinned upstream derivation if needed | wrapper should expose `hadolint` | `hadolint --version` |
| Taplo | nixpkgs package input, to be verified | Rust build derivation | wrapper should expose `taplo` | `taplo --version` |
| actionlint | nixpkgs package input, to be verified | pinned upstream derivation if needed | wrapper should expose `actionlint` | `actionlint --version` |
| clang-tidy | LLVM package input | pinned LLVM package set | wrapper should expose `clang-tidy` | `clang-tidy --version` |
| cppcheck | nixpkgs package input | pinned derivation if needed | wrapper should expose `cppcheck` | `cppcheck --version` |
| Checkstyle | nixpkgs package/JAR derivation, to be verified | pinned JAR derivation | wrapper should expose `checkstyle` or JAR path | `java -jar checkstyle.jar --version` |
| PMD | nixpkgs package input, to be verified | pinned release derivation | wrapper should expose `pmd` | `pmd --version` |
| Cargo Clippy | Rust toolchain derivation with Clippy | rustup only for developer shells | wrapper/dev shell should expose Cargo | `cargo clippy -V` |
| clang-format | LLVM package input | pinned LLVM package set | wrapper should expose `clang-format` | `clang-format --version` |
| SpotBugs | nixpkgs package input, to be verified | pinned release derivation | wrapper should expose `spotbugs` | `spotbugs -version` |
| golangci-lint | nixpkgs package input | pinned derivation if needed | wrapper should expose `golangci-lint` | `golangci-lint --version` |
| SQLFluff | nixpkgs package input, to be verified | dedicated venv for checkout only | wrapper should expose `sqlfluff` | `sqlfluff --version` |
| TFLint | nixpkgs package input, to be verified | pinned upstream derivation | wrapper should expose `tflint` | `tflint --version` |

## macOS

Homebrew can be used for developer checkout, minimal install, repair, or
advanced administration. A normal Full DMG/app install must not require
post-install Homebrew linter setup.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | `brew` package or `pipx install ruff`, to be verified | dedicated Python venv | add pipx/venv path if used | `ruff --version` |
| Biome | `brew` package if current, to be verified | npm custom prefix or verified upstream binary | add npm/ECLI tools `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | `brew` package if current, to be verified | dedicated Python venv | shim venv executable | `yamllint --version` |
| ShellCheck | `brew install shellcheck` | verified upstream binary | standard Homebrew path or ECLI tools `bin` | `shellcheck --version` |
| Zig | `brew` package if current | upstream tar.xz with checksum | add extracted directory or shim | `zig version` |
| Hadolint | `brew` package if current, to be verified | verified GitHub release binary | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | package manager package if current, to be verified | add Cargo `bin` | `taplo --version` |
| actionlint | `brew` package if current, to be verified | verified GitHub release binary | standard Homebrew path or ECLI tools `bin` | `actionlint --version` |
| clang-tidy | LLVM/Homebrew package, to be verified | ECLI-managed LLVM payload | Homebrew LLVM may need explicit `PATH` | `clang-tidy --version` |
| cppcheck | `brew` package if current | verified upstream package, to be verified | standard Homebrew path | `cppcheck --version` |
| Checkstyle | `brew` package if current, to be verified | pinned JAR plus Java runtime | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | `brew` package if current, to be verified | pinned upstream release tar.gz | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | Homebrew Rust if it includes Clippy, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | LLVM/Homebrew package, to be verified | ECLI-managed LLVM payload | Homebrew LLVM may need explicit `PATH` | `clang-format --version` |
| SpotBugs | `brew` package if current, to be verified | pinned release tar.gz plus Java runtime | add `bin` or shim | `spotbugs -version` |
| golangci-lint | `brew` package if current | verified upstream release tarball | standard Homebrew path or ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | `brew` package if current, to be verified | dedicated Python venv | shim venv executable | `sqlfluff --version` |
| TFLint | `brew` package if current | verified GitHub release zip | standard Homebrew path or ECLI tools `bin` | `tflint --version` |

## Linux generic tarball / PyInstaller / AppImage

Preferred Full behavior is bundled tools or an ECLI-managed tools directory
next to the application or under `~/.local/share/ecli-linters`. Manual repair
uses the same directory model and shims into `~/.local/bin`.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | bundled/dev venv or ECLI-managed venv | `pipx install ruff` | shim into ECLI tools `bin` | `ruff --version` |
| Biome | ECLI-managed npm prefix | verified upstream binary | add ECLI npm `bin` | `biome --version` |
| markdownlint-cli2 | ECLI-managed npm prefix | project-local npm install for checkout only | add ECLI npm `bin` | `markdownlint-cli2 --version` |
| yamllint | ECLI-managed Python venv | OS package where reliable | shim venv executable | `yamllint --version` |
| ShellCheck | bundled or verified upstream binary | OS package where reliable | install under ECLI tools `bin` | `shellcheck --version` |
| Zig | bundled or verified upstream tar.xz | OS package where reliable | add extracted directory or shim | `zig version` |
| Hadolint | bundled or verified GitHub release binary | OS package where reliable | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | ECLI-managed Cargo install | bundled binary if available | add Cargo/ECLI tools `bin` | `taplo --version` |
| actionlint | bundled or verified GitHub release binary | Go install with pinned version | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | bundled LLVM payload | OS LLVM package where reliable | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | bundled binary or Python wheel strategy | OS package where reliable | shim if venv-based | `cppcheck --version` |
| Checkstyle | bundled pinned JAR plus Java runtime/shim | system Java plus verified JAR | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | bundled pinned release tar.gz | verified upstream release | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | managed Rust toolchain component | system rustup repair path | add Cargo `bin` | `cargo clippy -V` |
| clang-format | bundled LLVM payload | OS LLVM package where reliable | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | bundled pinned release plus Java runtime/shim | system Java plus verified release | add `bin` or shim | `spotbugs -version` |
| golangci-lint | bundled or verified upstream release | OS package where reliable | install under ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | ECLI-managed Python venv | OS package where reliable | shim venv executable | `sqlfluff --version` |
| TFLint | bundled or verified GitHub release zip | OS package where reliable | install under ECLI tools `bin` | `tflint --version` |

## PyPI wheel / sdist

Python package metadata cannot reliably provision Node, Rust, Go, Zig, Java, or
system binaries. PyPI wheel and source distribution installs may therefore be
minimal for F4 linter purposes. Full platform artifacts are the supported user
path for complete linter provisioning. Use this section for developer,
minimal/source, or repair work only.

| Tool | Preferred manual method | Fallback method | PATH/shim notes | Verification command |
|---|---|---|---|---|
| Ruff | installed with ECLI/dev dependencies or `pipx install ruff` | dedicated venv | add pipx/venv path | `ruff --version` |
| Biome | npm custom prefix with pinned package | verified upstream binary | add npm/ECLI tools `bin` | `biome --version` |
| markdownlint-cli2 | npm custom prefix | project-local npm install for checkout only | add npm prefix `bin` | `markdownlint-cli2 --version` |
| yamllint | dedicated Python venv or `pipx install yamllint` | OS package where reliable | shim venv executable | `yamllint --version` |
| ShellCheck | OS package where reliable | verified upstream binary | standard path or ECLI tools `bin` | `shellcheck --version` |
| Zig | OS package where reliable/current | verified upstream tar.xz | add extracted directory or shim | `zig version` |
| Hadolint | verified GitHub release binary | OS package where reliable/current | install under ECLI tools `bin` | `hadolint --version` |
| Taplo | `cargo install taplo-cli --locked` | OS package where reliable/current | add Cargo `bin` | `taplo --version` |
| actionlint | verified GitHub release binary | Go install with pinned version | install under ECLI tools `bin` | `actionlint --version` |
| clang-tidy | OS LLVM package where reliable | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-tidy --version` |
| cppcheck | OS package where reliable | Python wheel/upstream strategy, to be verified | shim if venv-based | `cppcheck --version` |
| Checkstyle | pinned JAR plus Java runtime | OS package where reliable/current | `checkstyle` shim for `java -jar` | `java -jar checkstyle.jar --version` |
| PMD | pinned upstream release tar.gz | OS package where reliable/current | add PMD `bin` or shim | `pmd --version` |
| Cargo Clippy | `rustup component add clippy` | OS Rust package if it includes Clippy, to be verified | add Cargo `bin` | `cargo clippy -V` |
| clang-format | OS LLVM package where reliable | ECLI-managed LLVM payload | ensure selected LLVM `bin` wins | `clang-format --version` |
| SpotBugs | pinned release tar.gz plus Java runtime | OS package where reliable/current | add `bin` or shim | `spotbugs -version` |
| golangci-lint | verified upstream release tarball | OS package where reliable/current | install under ECLI tools `bin` | `golangci-lint --version` |
| SQLFluff | dedicated Python venv or `pipx install sqlfluff` | OS package where reliable/current | shim venv executable | `sqlfluff --version` |
| TFLint | verified GitHub release zip | OS package where reliable/current | install under ECLI tools `bin` | `tflint --version` |
