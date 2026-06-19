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
- Official GitHub Release publication requires exactly 21 top-level asset files,
  one per canonical matrix entry.
- Checksum file exists under `releases/<version>/.checksums/` and matches
  generated digest.
- Checksum sidecar format is `<hex>  <artifact basename>`
- Top-level `.sha256` files in `releases/<version>/` are extra release assets
  and must fail the release asset verifier.

## Exact Release Asset Gate

Use the canonical 21-asset verifier before publication:

```sh
uv run python scripts/verify_release_assets.py
```

The verifier reads the version from `pyproject.toml`, validates
`releases/<version>/`, fails when the directory is missing, fails on missing or
extra top-level files, and passes only when the exact 21 physical GitHub Release
assets are present. It ignores `.checksums/` only when that path is a directory.

Mandatory GitHub Release asset names for each `<version>`:

```text
01_pypi_wheel__ecli_editor-<version>-py3-none-any.whl
02_pypi_sdist__ecli_editor-<version>.tar.gz
03_linux_pyinstaller__ecli_<version>_linux_x86_64.bin
04_linux_tarball__ecli_<version>_linux_x86_64.tar.gz
05_debian__ecli_<version>_linux_x86_64.deb
06_rpm__ecli_<version>_linux_x86_64.rpm
07_opensuse__ecli_<version>_opensuse_x86_64.rpm
08_arch__ecli_<version>_arch_x86_64.pkg.tar.zst
09_slackware__ecli_<version>_slackware_x86_64.txz
10_appimage__ecli_<version>_linux_x86_64.AppImage
11_freebsd_pkg__ecli_<version>_freebsd_x86_64.pkg
12_freebsd_ports_chroot__ecli_<version>_freebsd_ports_chroot_evidence.tar.gz
13_macos_app__ecli_<version>_macos_universal2_app_evidence.tar.gz
14_macos_dmg__ecli_<version>_macos_universal2.dmg
15_windows_portable__ecli_<version>_win_x86_64.exe
16_windows_nsis__ecli_<version>_win_x86_64_setup.exe
17_nix_flake__ecli_<version>_nix_flake_evidence.tar.gz
18_nixos_package__ecli_<version>_nixos_package_evidence.tar.gz
19_docker_deb_helper__ecli_<version>_docker_deb_helper_evidence.tar.gz
20_docker_rpm_helper__ecli_<version>_docker_rpm_helper_evidence.tar.gz
21_workflow_contract__ecli_<version>_workflow_contract_evidence.tar.gz
```

## Example Verification Commands

Linux:
- `sha256sum -c releases/<version>/.checksums/<asset>.sha256`

macOS:
- `shasum -a 256 -c releases/<version>/.checksums/<asset>.sha256`

FreeBSD:
- `shasum -a 256 -c releases/<version>/.checksums/<asset>.sha256`
- If `shasum` is unavailable, compare `sha256 -q releases/<version>/<asset>` with the first field in the sidecar.

Windows (PowerShell):
```powershell
$expected = (Get-Content releases/<version>/.checksums/<asset>.sha256).Split()[0]
$actual = (Get-FileHash -Algorithm SHA256 releases/<version>/<asset>).Hash
if ($actual -eq $expected) { Write-Output "Verified" } else { Write-Output "Mismatch" }
```

## Granular Exit Codes for CI Scripting

The per-file checksum verifier is `scripts/verify_artifact.py` (Python,
standard library only). GNU Make reports failed recipes with make process exit
code `2`, so callers that need the artifact-verifier exit contract must invoke
the verifier directly:

```sh
uv run python scripts/verify_artifact.py releases/<version>/<artifact>
```

The Python verifier is the only active entrypoint under `scripts/`; the removed
shell verifier wrapper must not be restored for existing callers.

For package-builder output, the verifier expects the sidecar at
`<artifact>.sha256` and requires the sidecar payload to use basename-only
coreutils format. Before GitHub Release publication, sidecars must be moved or
regenerated under `.checksums/` so the top-level asset set remains exactly 21.

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
branches on specific failure classes must call `uv run python scripts/verify_artifact.py`
directly.

## Policy

- Verification must run in CI for official releases.
- Unverified artifacts must not be published as release assets.
- GitHub Release publication must not upload `.sha256` sidecars or SBOM files
  as release assets.
