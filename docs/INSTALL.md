<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/INSTALL.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Install ECLI

This page is the short user-facing install path. The fuller contributor and artifact matrix remains in `docs/contributor/install.md`.

## Install from PyPI

Recommended user-level installation with `pipx`:

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
pipx install ecli-editor
ecli
```

Optional Linux desktop launcher and icon integration after `pipx` or `pip` installation:

```bash
ecli-install-desktop-entry
```

This installs:

```text
~/.local/share/applications/ecli.desktop
~/.local/share/icons/hicolor/256x256/apps/ecli.png
```

It does not require `sudo` and is safe to run again. For GNOME, KDE, and XFCE, the launcher should appear in the application menu after the desktop database refreshes or the session refreshes. If needed, log out/in or restart the shell menu.

Isolated virtual environment installation:

```bash
python3 -m venv ~/.local/ecli-env
source ~/.local/ecli-env/bin/activate
pip install ecli-editor
ecli
```

`pip`/`pipx` installation provides the terminal command. GUI desktop launcher integration is installed explicitly by `ecli-install-desktop-entry`.

Native `.deb`, `.rpm`, `.dmg`, and `.exe` installers may provide launcher integration automatically.

## Platform Dependencies

### TextMate syntax highlighting

ECLI's default extension-backed syntax engine uses `python-textmate`, which
pulls `onigurumacffi` for the Oniguruma regular-expression engine. Standard
`pip`, `pipx`, and release artifact installs should receive these Python
dependencies automatically.

On source-build platforms where `onigurumacffi` cannot use a binary wheel,
install the Oniguruma development package before building. Typical package names
are `libonig-dev` or `oniguruma` on Debian/Ubuntu-style systems,
`oniguruma` on Arch and Nix, and `devel/oniguruma` on FreeBSD.

If the tokenizer or native dependency is unavailable at runtime, ECLI must start
and fall back to the legacy highlighter rather than crashing.

### SUSE / openSUSE

Runtime dependencies for the openSUSE/SUSE RPM path:

```bash
sudo zypper install ncurses6 libyaml-0-2 xclip xsel
```

Build dependencies for local RPM/package generation:

```bash
sudo zypper install python3 python3-pip python3-devel gcc make rpm-build
```

### Slackware

Slackware package names vary by release. Install these from the official Slackware series or SlackBuilds according to your Slackware release:

```text
ncurses
libyaml
xclip or xsel, if available
```

For `.txz` package builds, the build host also needs `makepkg`, `tar`, `xz`, `python3`, PyInstaller, and the project Python build dependencies.

### Windows

Prebuilt `.exe` installer and portable artifacts do not require a separate Python installation. Windows Terminal or another modern terminal is recommended. PowerShell is used for checksum examples, and Git is optional for repository workflows.

The official installer normally bundles required runtime components. Install a Visual C++ runtime only if a release note for a specific artifact says it is required.

For source/development builds on Windows, install Python 3.11+, Git,
PowerShell 7, NSIS for installer builds, and Visual Studio Build Tools only when native dependencies or build tooling require compilation.

## Installing from Linux packages

Release artifacts are published from the repository at
<https://github.com/SSobol77/ecli> when available.

Exact file names include the version and architecture.

### Debian / Ubuntu

```bash
sudo apt install ./ecli_<version>_linux_x86_64.deb
ecli
```

If the package is not available for your platform, use the `pipx` flow above.

The Debian/Ubuntu `externally-managed-environment` explanation below still applies to direct system `pip` installs.

### Fedora / RHEL

```bash
sudo dnf install ./ecli_<version>_linux_x86_64.rpm
ecli
```

### SUSE / openSUSE

```bash
sudo zypper install ./ecli_<version>_opensuse_x86_64.rpm
ecli
```

If dependencies are missing, let `zypper` resolve them from the configured SUSE repositories. Prefer the official release artifact when available.

### Arch Linux

Install a release artifact when available:

```bash
sudo pacman -U ./ecli_<version>_arch_x86_64.pkg.tar.zst
ecli
```

Build locally from the repository PKGBUILD:

```bash
cd packaging/arch
makepkg -si
ecli
```

ECLI is not yet published to AUR by this repository.

Raw `makepkg` output may use the native Arch filename

`ecli-editor-<version>-1-<arch>.pkg.tar.zst`

The ECLI release script normalizes this to

`ecli_<version>_arch_<arch>.pkg.tar.zst`

for GitHub Releases.

### Slackware

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

Run from the local flake:

```bash
nix run .
```

Build locally:

```bash
nix build .
```

Install into the current Nix profile:

```bash
nix profile install .
```

For NixOS configuration, import the local package expression or flake output manually and add it to `environment.systemPackages`.

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

## Debian 13 / Ubuntu Python Protection

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
