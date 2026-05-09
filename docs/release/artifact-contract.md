# Artifact Contract (Normative)

## Contract Scope

Defines canonical artifact names, locations, and verification expectations for release outputs.

## Canonical Output Location

- All release artifacts must be emitted under `releases/<version>/`.

## Canonical Naming Rules

- DEB: `ecli_<version>_amd64.deb`
- RPM: `ecli_<version>_amd64.rpm`
- FreeBSD: `ecli_<version>_amd64.pkg`
- Windows: `ecli_<version>_win_x64.exe`
- macOS: `ecli_<version>_macos_<arch>.dmg` (`<arch>`: `x86_64` or `arm64`)

For each artifact, a checksum file must exist:
- `<artifact>.sha256`

## Forbidden Variants

- Mixed hyphen/underscore variants for final released names are forbidden.
- Artifacts outside `releases/<version>/` are non-contract outputs.

## Build Entrypoints

Canonical script entrypoints are those referenced by `Makefile` and active workflows under `.github/workflows/`.

Current-state note:
- repository/workflows/scripts reference `ecli.spec`, but the file is currently absent.
- this mismatch must be resolved before claiming deterministic release parity.

## CI Validation Requirements

- release workflow must validate expected artifact names and checksums before publish.
- missing contract artifact must fail the pipeline.
