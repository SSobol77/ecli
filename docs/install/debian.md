<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/install/debian.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Installing on Debian 13 (Trixie)

ECLI installation on Debian 13 amd64 is a **two-stage** process:

1. **Stage 1 — ECLI Linter Installer** provisions the complete 19-tool F4
   linter toolchain into the operating system and into the managed payload
   tree `/opt/ecli/payload`.
2. **Stage 2 — ECLI Debian package** installs ECLI itself.

The recommended full sequence is:

```bash
sudo python3 scripts/install_ecli_linters.py
sudo apt install ./releases/0.2.4/ecli_0.2.4_linux_x86_64.deb
```

The `.deb` installs only ECLI and its direct runtime dependencies. It never
bundles, downloads, or installs the linter toolchains; ECLI discovers the
installed linter executables through `PATH`. If the linter payload is
absent, ECLI still installs and runs — F4 diagnostics list any missing
executables instead of failing.

## Obtaining the linter installer bundle

The linter installer is a standalone **four-file bundle**. Copying only
`install_ecli_linters.py` is **not sufficient** — it loads its production
lock and npm lock from paths next to its own location, so all four files
must be fetched together, preserving this exact flat layout:

```text
install_ecli_linters.py
ecli-linter-lock.json
markdownlint-cli2/
  package.json
  package-lock.json
```

(A full repository checkout already satisfies this layout automatically:
the script also looks one directory up, under
`packaging/debian/ecli-linter-lock.json` and
`packaging/debian/markdownlint-cli2/`.)

### Prerequisite: Python 3

A minimal or netinst Debian 13 install does not ship Python. Install it
before running the bundle:

```bash
sudo apt-get update && sudo apt-get install -y python3
```

### Option A — clone the repository

```bash
git clone --branch v0.2.4 --depth 1 https://github.com/SSobol77/ecli.git
cd ecli
sudo python3 scripts/install_ecli_linters.py
```

### Option B — fetch only the four bundle files

```bash
mkdir -p ecli-linter-bundle/markdownlint-cli2 && cd ecli-linter-bundle
curl -fsSLO https://raw.githubusercontent.com/SSobol77/ecli/v0.2.4/scripts/install_ecli_linters.py
curl -fsSLO https://raw.githubusercontent.com/SSobol77/ecli/v0.2.4/packaging/debian/ecli-linter-lock.json
curl -fsSL -o markdownlint-cli2/package.json \
  https://raw.githubusercontent.com/SSobol77/ecli/v0.2.4/packaging/debian/markdownlint-cli2/package.json
curl -fsSL -o markdownlint-cli2/package-lock.json \
  https://raw.githubusercontent.com/SSobol77/ecli/v0.2.4/packaging/debian/markdownlint-cli2/package-lock.json
sudo python3 install_ecli_linters.py
```

The installer itself is never executed by any downloaded/piped shell
command — always fetch the four files, inspect them if desired, then run
`python3` directly against the local copy.

## Stage 1 — ECLI Linter Installer

Run the dedicated interactive installer as root (from a repository
checkout or the bundle fetched above):

```bash
sudo python3 scripts/install_ecli_linters.py
```

The installer refuses to run unless all of the following hold: effective
UID 0, Linux, Debian, Debian major version 13, architecture `amd64`.

It presents a 19-entry menu:

```text
[ A ] - Install All Linters

1.  Ruff
2.  Biome
3.  markdownlint-cli2
4.  yamllint
5.  shellcheck
6.  Zig
7.  Hadolint
8.  Taplo
9.  actionlint
10. clang-tidy
11. cppcheck
12. clang-format
13. Checkstyle
14. PMD
15. SpotBugs
16. cargo-clippy
17. golangci-lint
18. SQLFluff
19. TFLint
```

Enter `A` for all tools, or a comma-separated list of numbers (for example
`1,4,5`). Non-interactive automation can use
`--select A` or `--select 1,4,5`.

What the installer does:

- Resolves the complete APT package set for the selection (yamllint,
  shellcheck, clang-tidy, cppcheck, clang-format, checkstyle, cargo,
  rust-clippy, sqlfluff, plus runtime dependencies such as nodejs/npm,
  default-jre-headless, golang-go) and installs it in **one**
  `apt-get install --yes --no-install-recommends` transaction.
- Installs the standalone tools (Ruff, Biome, Zig, Hadolint, Taplo,
  actionlint, PMD, SpotBugs, golangci-lint, TFLint, and the npm-locked
  markdownlint-cli2) into `/opt/ecli/payload` from the committed
  production lock `packaging/debian/ecli-linter-lock.json`: pinned
  versions, HTTPS-only downloads, exact SHA-256 verification, safe
  archive extraction, and atomic promotion. No `releases/latest` queries
  and no Zig `master` builds.
- Configures `/etc/profile.d/ecli_payload.sh` so login shells put
  `/opt/ecli/payload/bin` on `PATH` (idempotent — no duplicate entries).
- Verifies every selected tool with its version probe and prints a
  per-tool `[OK] / [SKIPPED] / [FAILED]` report. The success message
  `ECLI linter installation completed successfully: 19/19 tools verified.`
  is printed only when all 19 tools pass.

The installer is safely rerunnable: tools already at the locked version
are verified and skipped; outdated or corrupted managed installations are
replaced atomically; unmanaged files are never overwritten. A root-owned
log is written to `/var/log/ecli/linter-installer.log`.

Managed payload layout:

```text
/opt/ecli/payload/bin        executable entry points (PATH surface)
/opt/ecli/payload/packages   versioned distributions (zig, pmd, spotbugs, nodejs)
/opt/ecli/payload/state      managed installation state
/opt/ecli/payload/cache      verified download cache
```

## Stage 2 — ECLI Debian package

After the linter installer completes, install ECLI:

```bash
sudo apt install ./releases/0.2.4/ecli_0.2.4_linux_x86_64.deb
```

Verify the artifact checksum first when installing a downloaded release:

```bash
sha256sum -c ecli_0.2.4_linux_x86_64.deb.sha256
```

The package's maintainer scripts are intentionally conservative:

- `remove` and `purge` never delete user configuration
  (`~/.config/ecli`, including `/root/.config/ecli`).
- No maintainer script uses the network, invokes APT, or touches
  `/opt/ecli/payload`.
- `postinst` only reports whether the optional linter payload is present;
  its absence never fails the installation.

## Verify

```bash
ecli --version
```

Open a new login shell (or `source /etc/profile.d/ecli_payload.sh`) so
`/opt/ecli/payload/bin` is on `PATH`, then run the headless toolchain
verifier:

```bash
ecli --f4-check
```

This proves, from the installed runtime, that all 19 provisioned
toolchain executables resolve from their approved managed or system
location (11 managed, 8 Debian-packaged). It reports two distinct counts
that must never be conflated: up to 19 **provisioned/verified
executables**, and a fixed **14 registered diagnostic providers** — the
number of linters F4 currently runs live diagnostics through inside the
editor. The remaining five provisioned tools (SpotBugs, golangci-lint,
SQLFluff, TFLint, clang-format) are installed and on `PATH` but do not
yet have a diagnostic provider wired into F4. Missing executables are
listed in the editor log by the startup toolchain check instead of
causing errors.
