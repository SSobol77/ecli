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
| Any | Python package | Fallback path | `pip install ecli-editor` | `python -m ecli` or CLI startup | distribution name is `ecli-editor`; import and CLI names remain `ecli` |

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

## Traceability

- Artifact names and paths: `docs/release/artifact-contract.md`
- Verification commands: `docs/release/artifact-verification.md`
- Config-related startup failures: `docs/config/*`
