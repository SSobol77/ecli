<!--
Filename: docs/release/artifact-contract.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Artifact Contract (Normative)

## Contract Scope

Defines canonical artifact names, locations, and verification expectations for release outputs.

## Canonical Output Location

- All release artifacts must be emitted under `releases/<version>/`.

## Canonical Naming Rules

Final release artifact names must use this schema:

`ecli_<version>_<os>_<arch>.<ext>`

Short form: `ecli_<v>_<os>_<arch>.<ext>`

Allowed `<os>` tokens:

- `linux`
- `freebsd`
- `macos`
- `win`

Allowed `<arch>` tokens:

- `x86_64`
- `arm64`
- `universal2` (macOS DMG only)

Current artifact forms:

- DEB: `ecli_<version>_linux_<arch>.deb`
- RPM: `ecli_<version>_linux_<arch>.rpm`
- AppImage: `ecli_<version>_linux_<arch>.AppImage`
- Linux tarball: `ecli_<version>_linux_<arch>.tar.gz`
- Snap: `ecli_<version>_linux_<arch>.snap`
- FreeBSD: `ecli_<version>_freebsd_<arch>.pkg`
- Windows: `ecli_<version>_win_<arch>.exe`
- macOS: `ecli_<version>_macos_universal2.dmg`

The DEB internal `Architecture` field remains package-manager native
(`amd64` on x86_64). Only the final release filename uses the canonical
architecture token.

For each artifact, a checksum file must exist:
- `<artifact>.sha256`

Checksum sidecars use coreutils-compatible format:

```text
<64 lowercase hex characters>  <artifact basename>
```

The artifact basename must not include a directory component.

## Forbidden Variants

- Mixed hyphen/underscore variants for final released names are forbidden.
- Artifacts outside `releases/<version>/` are non-contract outputs.

## Build Entrypoints

Canonical script entrypoints are those referenced by `Makefile` and active workflows under `.github/workflows/`.

Current-state note:
- repository workflows and scripts use `packaging/pyinstaller/ecli.spec`; the
  root `ecli.spec` is a compatibility wrapper.
- deterministic release parity depends on keeping the PyInstaller spec,
  Makefile targets, workflows, and packaging scripts aligned on the canonical
  output names.

## Naming Migration Notes

Gate 2 Phase 0 replaces legacy platform-specific filename conventions with one
cross-platform schema. The removed legacy forms include:

- `ecli_<version>_amd64.deb`
- `ecli_<version>_amd64.rpm`
- `ecli_<version>_amd64.pkg`
- `ecli_<version>_Linux_x86_64.AppImage`
- `ecli_<version>_Linux_x86_64.tar.gz`
- `ecli_<version>_win_x64.exe`

The migration makes artifact discovery deterministic for CI and release
automation while preserving package-manager metadata inside each artifact.

## CI Validation Requirements

- release workflow must validate expected artifact names and checksums before publish.
- missing contract artifact must fail the pipeline.
