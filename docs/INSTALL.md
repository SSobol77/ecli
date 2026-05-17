<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/INSTALL.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
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
