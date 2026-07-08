<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/install/windows.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Windows Installation

ECLI publishes two unsigned Windows x86_64 artifacts:

- Installer, recommended: `ecli_<version>_win_x86_64_setup.exe`

- Portable executable: `ecli_<version>_win_x86_64.exe`

Download the EXE and matching `.sha256` sidecar from the GitHub Release for the version you intend to install.

## Requirements

Prebuilt installer and portable `.exe` artifacts do not require a separate Python installation.

Recommended runtime environment:

- Windows Terminal or another modern terminal.

- PowerShell for checksum verification examples.

- Git, optional, for repository workflows inside ECLI.

The official installer normally bundles required runtime components. Install a Visual C++ runtime only if the release notes for a specific artifact say it is required.

For ECLI Full, the Windows installer/portable artifact must also provision the
required F4 linter tools or managed runtime payload, detect already-installed
tools before adding missing ones, and verify executable/version probes. Manual
linter installation is only for developer checkouts, PyPI/source/minimal
installs, damaged-install repair, or advanced administration; see
`docs/extensions/f4-linter-manual-installation.md`.

For source/development builds on Windows, install:

- Python 3.11 or newer.

- Git.

- PowerShell 7, recommended.

- NSIS for installer builds.

- Visual Studio Build Tools only if native dependencies or build tooling require compilation.

## Verify Checksums

PowerShell checksum verification should be performed before first execution:

```powershell
$version = "0.2.3"
$file = "ecli_${version}_win_x86_64_setup.exe"
$expected = (Get-Content "$file.sha256" -Raw).Trim().Split()[0]
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLowerInvariant()
if ($actual -ne $expected) {
    throw "SHA256 mismatch for $file"
}
```

For the portable executable, change `$file` to:

```powershell
$file = "ecli_${version}_win_x86_64.exe"
```

The sidecar format is compatible with coreutils:

```text
<64 lowercase hex characters>  <artifact basename>
```

## Installer Path

The installer is the recommended Windows path for normal workstations:

```powershell
.\ecli_<version>_win_x86_64_setup.exe
```

The NSIS installer writes ECLI under `C:\Program Files\Cartesian School\ECLI`, creates an uninstaller, and registers ECLI in Programs & Features under:

```text
HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\ECLI
```

The registered uninstall metadata includes `DisplayName`, `DisplayVersion`, `Publisher`, `InstallLocation`, and `UninstallString`.

## Portable Path

Use the portable executable when you do not want a machine-level installation:

```powershell
.\ecli_<version>_win_x86_64.exe
```

The portable artifact is a PyInstaller `--onefile` executable. It does not register uninstall metadata and does not modify machine state beyond normal runtime file access performed by **ECLI**.

## SmartScreen

Current **ECLI** Windows artifacts are unsigned. Windows SmartScreen may block first launch or installation with a warning. To proceed after verifying the checksum:

1. Select **More info**.

2. Confirm the publisher is shown as unknown or unsigned.

3. Select **Run anyway**.

Code signing is planned for a later release. Until signed artifacts are available, checksum verification against the release sidecar is the integrity check.
