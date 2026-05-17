<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/contributor/install.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Install Guide

## Platform/Support Matrix

| Platform | Artifact | Support tier | Install command / flow | Verification | Notes |
|---|---|---|---|---|---|
| Linux (Debian/Ubuntu) | `.deb` | Supported with contract validation | `sudo apt install ./ecli_<ver>_linux_x86_64.deb` | `ecli --help` or launch command | requires matching artifact name |
| Linux (RHEL/Fedora family) | `.rpm` | Supported with contract validation | `sudo dnf install ./ecli_<ver>_linux_x86_64.rpm` | `ecli --help` | distro dependency resolution applies |
| FreeBSD | `.pkg` | Supported in FreeBSD environment | `sudo pkg install ./ecli_<ver>_freebsd_x86_64.pkg` | launch command | native environment required |
| macOS | `.dmg` | Provisionally supported (validate per release) | mount DMG and install app/binary flow | startup check | packaging flow depends on local tooling |
| Windows | `.exe` | Provisionally supported (validate per release) | run installer EXE or portable EXE | launch + version/help check | see `docs/install/windows.md`; NSIS installer is recommended |
| Any | Python package | Fallback path | `pipx install ecli-editor` | `ecli` | distribution name is `ecli-editor`; import and CLI names remain `ecli` |

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

The command does not require `sudo` and is safe to run again. For GNOME, KDE,and XFCE, the launcher should appear in the application menu after the desktop database refreshes or the session refreshes. If needed, log out/in or restart the shell menu.

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

## Checksum Verification Example

- Linux: `sha256sum -c ecli_<ver>_linux_x86_64.deb.sha256`
- Windows (PowerShell): `Get-FileHash -Algorithm SHA256 ecli_<ver>_win_x86_64_setup.exe`

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
- Verification commands: `docs/release/artifact-verification.md`
- Config-related startup failures: `docs/config/*`
