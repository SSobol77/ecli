<!--
Filename: docs/release/artifact-verification.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Artifact Verification

## Required Verification

- Artifact filename must follow the naming convention specified in `artifact-contract.md`
- File location is `releases/<version>/`
- Checksum file exists and matches generated digest
- Checksum sidecar format is `<hex>  <artifact basename>`

## Example Verification Commands

Linux:
- `sha256sum -c releases/<version>/<artifact>.sha256`

macOS:
- `shasum -a 256 -c releases/<version>/<artifact>.sha256`

FreeBSD:
- `shasum -a 256 -c releases/<version>/<artifact>.sha256`
- If `shasum` is unavailable, compare `sha256 -q releases/<version>/<artifact>` with the first field in the sidecar.

Windows (PowerShell):
```powershell
$expected = (Get-Content releases/<version>/<artifact>.sha256).Split()[0]
$actual = (Get-FileHash -Algorithm SHA256 <artifact>).Hash
if ($actual -eq $expected) { Write-Output "Verified" } else { Write-Output "Mismatch" }
```

## Policy

- Verification must run in CI for official releases.
- Unverified artifacts must not be published as release assets.
