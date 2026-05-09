# Artifact Verification

## Required Verification

- Artifact filename must follow the naming convention specified in `artifact-contract.md`
- File location is `releases/<version>/`
- Checksum file exists and matches generated digest

## Example Verification Commands

Linux:
- `sha256sum -c releases/<version>/<artifact>.sha256`

macOS:
- `shasum -c releases/<version>/<artifact>.sha256`

FreeBSD:
- `sha256 -c releases/<version>/<artifact>.sha256`

Windows (PowerShell):
```powershell
$expected = (Get-Content releases/<version>/<artifact>.sha256).Split()[0]
$actual = (Get-FileHash -Algorithm SHA256 <artifact>).Hash
if ($actual -eq $expected) { Write-Output "Verified" } else { Write-Output "Mismatch" }
```

## Policy

- Verification must run in CI for official releases.
- Unverified artifacts must not be published as release assets.
