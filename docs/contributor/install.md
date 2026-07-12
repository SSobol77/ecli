<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/contributor/install.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Install Guide

## Platform/Support Matrix

| Platform | Artifact | Support tier | Install command / flow | Verification | Notes |
|---|---|---|---|---|---|
| Linux (Debian/Ubuntu) | `.deb` | Supported with contract validation | `sudo apt install ./ecli_<version>_linux_x86_64.deb` | `ecli --help` or launch command | requires matching artifact name |
| Linux (RHEL/Fedora family) | `.rpm` | Supported with contract validation | `sudo dnf install ./ecli_<version>_linux_x86_64.rpm` | `ecli --help` | distro dependency resolution applies |
| Linux (SUSE/openSUSE) | `.rpm` | Supported with SUSE-oriented build script | `sudo zypper install ./ecli_<version>_opensuse_x86_64.rpm` | `ecli --help` | use zypper to resolve dependencies |
| Linux (Arch) | `pkg.tar.zst` / PKGBUILD | Local build support | `sudo pacman -U ./ecli_<version>_arch_x86_64.pkg.tar.zst` | `ecli --help` | AUR publishing is not implemented |
| Linux (Slackware) | `.txz` | Local build support | `sudo installpkg ecli_<version>_slackware_x86_64.txz` | `ecli --help` | requires Slackware `makepkg` to build |
| Linux (AppImage) | `.AppImage` | Cross-distro artifact | `chmod +x ./ecli_<version>_linux_x86_64.AppImage && ./ecli_<version>_linux_x86_64.AppImage` | launch command | no package-manager integration |
| NixOS / Nix | flake / Nix package | Local build support | `nix run .` | launch command | local flake, not a nixpkgs submission |
| FreeBSD | `.pkg` | Supported in FreeBSD environment | `sudo pkg install ./ecli_<version>_freebsd_x86_64.pkg` | launch command | native environment required |
| macOS | `.dmg` | Provisionally supported (validate per release) | mount DMG and install app/binary flow | startup check | packaging flow depends on local tooling |
| Windows | `.exe` | Provisionally supported (validate per release) | run installer EXE or portable EXE | launch + version/help check | see `docs/install/windows.md`; NSIS installer is recommended |
| Any | Python package | Fallback path | `pipx install ecli-editor` | `ecli` | distribution name is `ecli-editor`; import and CLI names remain `ecli` |

## Full F4 Linter Provisioning Policy

ECLI Full artifacts are responsible for complete F4 linter provisioning. The
installer or package flow must detect the operating system and canonical
artifact context, check already-installed required linters/toolchains before
installing anything, install or bundle missing required tools with the
OS/artifact-specific mechanism, and verify executable availability plus version
probes.

Manual linter installation is a developer checkout, PyPI/source/minimal install,
damaged Full install repair, or advanced administration path only. It is not the
normal post-install path for ECLI Full. The manual reference is
`docs/extensions/f4-linter-manual-installation.md`.

Debian 13 testing demonstrated a valid mixed provisioning class: npm with a
custom prefix under an ECLI-managed tools directory, dedicated Python virtual
environments, prebuilt binaries, `cargo install`, JAR shims, upstream release
downloads with provenance/checksum/version verification, and `rustup component
add clippy`. The Full installer must automate and verify those steps where that
strategy is selected.

The PyPI wheel/sdist and local source checkout cannot reliably provision Node,
Rust, Go, Zig, Java, or system binaries through Python package metadata. Treat
those paths as minimal/developer installs for F4 linter purposes unless a future
artifact entry proves complete provisioning under the exact 21 artifact contract
entries.

## Platform Dependencies

### SUSE / openSUSE

Runtime packages for installed RPMs:

```bash
sudo zypper install ncurses6 libyaml-0-2 xclip xsel
```

Build packages for local RPM/package generation:

```bash
sudo zypper install python3 python3-pip python3-devel gcc make rpm-build
```

### Slackware

**Slackware** package names and repository layout vary by release. Install these from the official **Slackware** series or SlackBuilds according to your **Slackware** release:

```text
ncurses
libyaml
xclip or xsel, if available
```

For `.txz` package builds, the build host also needs `makepkg`, `tar`, `xz`, `python3`, PyInstaller, and the project Python build dependencies.

### Windows

Prebuilt installer and portable `.exe` artifacts do not require a separate Python installation. Windows Terminal or another modern terminal is recommended. PowerShell is used for checksum examples. Git is optional for repository workflows.

The official installer normally bundles required runtime components. Install a Visual C++ runtime only if release notes for a specific artifact identify that requirement.

For source/development builds on Windows, install Python 3.11+, Git,
PowerShell 7, NSIS for installer builds, and Visual Studio Build Tools only when native dependencies or build tooling require compilation.

## Install from PyPI

For user-level application installs on Linux, `pipx` is the recommended path.

It keeps ECLI isolated from the system Python environment while exposing the terminal command on the user's `PATH`.

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
pipx install ecli-editor
ecli
```

`pip`/`pipx` installation provides the terminal command. GUI desktop launcher integration is explicit:

```bash
ecli-install-desktop-entry
```

On Linux this installs:

```text
~/.local/share/applications/ecli.desktop
~/.local/share/icons/hicolor/256x256/apps/ecli.png
```

The command does not require `sudo` and is safe to run again. For GNOME, KDE, and XFCE, the launcher should appear in the application menu after the desktop database refreshes or the session refreshes. If needed, log out/in or restart the shell menu.

For development or isolated testing, use a virtual environment:

```bash
python3 -m venv ~/.local/ecli-env
source ~/.local/ecli-env/bin/activate
pip install ecli-editor
ecli
```

Native `.deb`, `.rpm`, `.dmg`, and `.exe` installers may provide launcher integration automatically. The official `.deb` package from GitHub Releases is also an option when available.

### Why do I get "externally-managed-environment" on Debian 13 or newer Ubuntu?

Newer Debian and Ubuntu releases intentionally protect the system Python environment from direct pip modifications. This prevents pip from overwriting or conflicting with Python packages managed by apt.

Recommended installation paths:

Option A — use pipx for a user-level application install:

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
pipx install ecli-editor
ecli
```

Option B — use a virtual environment for development or isolated testing:

```bash
python3 -m venv ~/.local/ecli-env
source ~/.local/ecli-env/bin/activate
pip install ecli-editor
ecli
```

Option C — use the official .deb package from GitHub Releases when available.

Avoid using:

```bash
pip install --break-system-packages ecli-editor
```

unless you fully understand the consequences. It can conflict with Python packages managed by apt and is not the preferred installation path.

## Installing from Linux packages

Use release artifacts from <https://github.com/SSobol77/ecli> when available.

Exact artifact names include the version and architecture.

### Debian / Ubuntu

On Debian 13 (Trixie) amd64, the recommended full sequence is two stages:
first provision the 19-tool F4 linter toolchain with the dedicated
installer, then install the ECLI package (see `docs/install/debian.md`):

```bash
sudo python3 scripts/install_ecli_linters.py
sudo apt install ./releases/0.2.4/ecli_0.2.4_linux_x86_64.deb
```

The `.deb` installs ECLI itself and its direct runtime dependencies only;
it does not bundle or download linters. ECLI discovers installed linter
executables through `PATH`, and F4 diagnostics list any missing tools.

Installing only the package also works:

```bash
sudo apt install ./ecli_<version>_linux_x86_64.deb
ecli
```

If no `.deb` is available, use the `pipx` fallback documented above.

### Fedora / RHEL / AlmaLinux / Rocky Linux

```bash
sudo dnf install ./ecli_<version>_linux_x86_64.rpm
ecli
```

### SUSE / openSUSE

```bash
sudo zypper install ./ecli_<version>_opensuse_x86_64.rpm
ecli
```

The openSUSE RPM build uses the same FHS payload as the generic RPM package:

`/usr/bin/ecli`, `/usr/share/applications/ecli.desktop`, and
`/usr/share/icons/hicolor/256x256/apps/ecli.png`.

If dependencies are missing, use `zypper` to resolve them from configured SUSE repositories. Prefer the official release artifact when available.

### Arch Linux

Release artifact install:

```bash
sudo pacman -U ./ecli_<version>_arch_x86_64.pkg.tar.zst
ecli
```

Local PKGBUILD build:

```bash
cd packaging/arch
makepkg -si
ecli
```

The Arch package name is `ecli-editor`, matching the Python distribution name.

It installs the `ecli` executable. AUR publishing is not implemented by this repository yet.

Raw `makepkg` output may use the native Arch filename
`ecli-editor-<version>-1-<arch>.pkg.tar.zst`.

The ECLI release script normalizes this to `ecli_<version>_arch_<arch>.pkg.tar.zst` for GitHub Releases.

### Slackware

Install:

```bash
sudo installpkg ecli_<version>_slackware_x86_64.txz
ecli
```

Upgrade:

```bash
sudo upgradepkg ecli_<version>_slackware_x86_64.txz
```

Remove:

```bash
sudo removepkg ecli
```

### NixOS / Nix

Run locally:

```bash
nix run .
```

Build locally:

```bash
nix build .
```

Install into the current profile:

```bash
nix profile install .
```

For NixOS configuration, import the local flake output or
`packaging/nix/package.nix` manually and add the package to
`environment.systemPackages`.

### FreeBSD

```bash
sudo pkg add ./ecli_<version>_freebsd_x86_64.pkg
ecli
```

### AppImage

```bash
chmod +x ./ecli_<version>_linux_x86_64.AppImage
./ecli_<version>_linux_x86_64.AppImage
```

## Checksum Verification Example

- Linux: `sha256sum -c ecli_<version>_linux_x86_64.deb.sha256`

- Windows (PowerShell): `Get-FileHash -Algorithm SHA256 ecli_<version>_win_x86_64_setup.exe`

## Startup Verification Example

1. Launch Ecli.

2. Confirm process starts and terminal returns cleanly on exit.

3. Optionally open a small test file and save.

## Update/Uninstall Notes

- Update: install newer artifact of same platform family.

- Uninstall: use platform package manager uninstall operation.

- Validation required: exact uninstall command per package family should match platform package manager policy.

## Fallback Strategy

- If artifact is unavailable, unverified, or mismatched with artifact contract, use Python package installation path.

## Local PyPI Packaging Verification

```bash
python -m pip install -e .
python -c "from ecli.utils.resources import get_icon_path; print(get_icon_path())"
ecli-install-desktop-entry
python -m build
python - <<'PY'
import glob
import zipfile

wheels = glob.glob("dist/*.whl")
assert wheels, "No wheel produced"

with zipfile.ZipFile(wheels[0]) as z:
    names = z.namelist()
    assert "ecli/assets/ecli.png" in names, "Missing ecli/assets/ecli.png in wheel"

print("OK: wheel contains ecli/assets/ecli.png")
PY
pytest
```

## Traceability

- Artifact names and paths: `docs/release/artifact-contract.md`
  (`Canonical 21-Item Platform & Packaging Artifact Matrix`)

- Verification commands: `docs/release/artifact-verification.md`

- Config-related startup failures: `docs/config/*`

## Script Migration Note

Active shell wrappers under `scripts/` have been removed. Build and verification
examples use canonical Python entrypoints under `scripts/`. Windows PowerShell
packaging remains separate at `scripts/build-and-package-windows.ps1`.
`tools/freebsd-chroot-build.sh` remains a FreeBSD chroot
helper outside the script migration. the removed FreeBSD package-renaming shell helper was removed
as unused tracked tooling.
