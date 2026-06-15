<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/artifact-verification.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
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

## Granular Exit Codes for CI Scripting

The canonical verifier is `scripts/verify_artifact.py` (Python, standard library
only). GNU Make reports failed recipes with make process exit code `2`, so
callers that need the artifact-verifier exit contract must invoke the verifier
directly:

```sh
python3 scripts/verify_artifact.py releases/<version>/<artifact>
```

The Python verifier is the only active entrypoint under `scripts/`; the removed
shell verifier wrapper must not be restored for existing callers.

The verifier expects the sidecar at `<artifact>.sha256` and requires the
sidecar payload to use basename-only coreutils format:

```text
<64 lowercase hex characters>  <artifact basename>
```

To (re)generate the sidecar, use the companion `scripts/sign_checksums.py`:

```sh
python3 scripts/sign_checksums.py releases/<version>/<artifact>
```

Exit codes:

- `0`: artifact verified
- `1`: invalid invocation or malformed checksum sidecar
- `2`: artifact missing
- `3`: checksum sidecar missing
- `4`: checksum mismatch
- `5`: missing SHA256 verification tool (retained for contract compatibility;
  the standard-library `hashlib` implementation never reaches this state)

The `make validate-*-contract` targets call the same verifier, but CI logic that
branches on specific failure classes must call `python3 scripts/verify_artifact.py`
directly.

## Policy

- Verification must run in CI for official releases.
- Unverified artifacts must not be published as release assets.
