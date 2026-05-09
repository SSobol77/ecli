<!--
Filename: docs/contributor/install.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Install Guide

## Platform/Support Matrix

| Platform | Artifact | Support tier | Install command / flow | Verification | Notes |
|---|---|---|---|---|---|
| Linux (Debian/Ubuntu) | `.deb` | Supported with contract validation | `sudo apt install ./ecli_<ver>_linux_x86_64.deb` | `ecli --help` or launch command | requires matching artifact name |
| Linux (RHEL/Fedora family) | `.rpm` | Supported with contract validation | `sudo dnf install ./ecli_<ver>_linux_x86_64.rpm` | `ecli --help` | distro dependency resolution applies |
| FreeBSD | `.pkg` | Supported in FreeBSD environment | `sudo pkg install ./ecli_<ver>_freebsd_x86_64.pkg` | launch command | native environment required |
| macOS | `.dmg` | Provisionally supported (validate per release) | mount DMG and install app/binary flow | startup check | packaging flow depends on local tooling |
| Windows | `.exe` | Provisionally supported (validate per release) | run installer EXE | launch + version/help check | NSIS-based path |
| Any | Python package | Fallback path | `pip install ecli-editor` | `python -m ecli` or CLI startup | distribution name is `ecli-editor`; import and CLI names remain `ecli` |

## Checksum Verification Example

- Linux: `sha256sum -c ecli_<ver>_linux_x86_64.deb.sha256`
- Windows (PowerShell): `Get-FileHash -Algorithm SHA256 ecli_<ver>_win_x86_64.exe`

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
