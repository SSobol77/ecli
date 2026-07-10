<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/release-process.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Release Process

## Trigger Model

- Tag-driven release pipeline is defined in workflow files.
- Platform build jobs must complete before artifact publication.

## Process Stages

1. Build platform artifacts
2. Assemble current-version release artifacts with adjacent checksum evidence
3. Run the built-artifact gate
4. Stage checksum sidecars under `.checksums/` and verify the exact 21-asset set
5. Publish package artifacts, release notes, and release assets

## Required Controls

- Contract validation must happen before publish.
- `make validate-gate2` is the source and structural contract gate; it must not
  inspect ignored historical release directories.
- `make validate-built-artifacts` is the required built-artifact gate after the
  current release directory is assembled with adjacent checksum sidecars and
  before GitHub Release or PyPI publication can run.
- `make validate-release-assets` is the exact 21 ECLI-owned GitHub Release asset
  gate after checksum sidecars have been staged under `.checksums/`.
- Missing required artifacts must block release.
- Every official ECLI release uploads exactly 21 ECLI-owned physical GitHub
  Release assets, one per canonical matrix entry. Release publication is
  blocked unless the exact 21 ECLI-owned assets are present and verified.
- The GitHub release page may show **Assets 23** because GitHub automatically
  adds `Source code (zip)` and `Source code (tar.gz)`. Those generated source
  archives are not ECLI-owned uploaded artifacts and are not part of the
  canonical 21 artifact contract entries.
- Workflow references to non-existent files must be resolved as release blockers.
- Every active package/platform surface must appear in the `Canonical 21-Item
  Platform & Packaging Artifact Matrix` (summarized by the `Platform & Packaging
  Release Contract Matrix`), agent contracts, build/release runbooks, and
  repository-local validation tests under `tests/packaging/`. The canonical
  matrix defines exactly 21 ECLI-owned uploaded physical GitHub Release assets;
  coverage in tests, Claude commands, Codex prompts, and workflows must never be
  smaller than that matrix.
- Empty, stale, decorative, or unused packaging files are release blockers until
  they are either wired into the contract matrix or explicitly removed from
  active workflows/scripts.
- Checksum sidecars are mandatory CI/release verification evidence under
  `releases/<version>/.checksums/` or workflow validation artifacts; they are
  not uploaded as separate GitHub Release assets.
- ECLI Full release readiness includes F4 linter provisioning across exactly 21
  artifact contract entries. Each Full artifact must detect OS/artifact context,
  check already-installed required tools before provisioning, install or bundle
  missing tools by the entry's mechanism, and verify executable availability
  plus version probes.
- Bundled or GitHub/upstream downloaded linter tools require explicit source
  URL, pinned version, checksum/provenance evidence, executable permission
  handling, deterministic install logs, and no silent unverified binary
  execution.
- Missing required F4 linters after ECLI Full install are release blockers, not
  normal user remediation.

## GitHub Actions Workflow Contract Map

Release readiness treats `.github/workflows/` as an explicit CI/release contract
surface. Every workflow must be documented here and in
`docs/release/artifact-contract.md`; adding an unmapped workflow is release
contract drift.

| Workflow | Release role |
|---|---|
| `.github/workflows/ci.yml` | Global quality gate, release contract tests, and root `main.py` compatibility contract. |
| `.github/workflows/freebsd-pkg.yml` | FreeBSD `.pkg` / port / chroot package validation workflow. It does not publish official release assets. |
| `.github/workflows/macos-dmg.yml` | macOS `.app` / `.dmg` package path. |
| `.github/workflows/macos-validate.yml` | macOS package validation. |
| `.github/workflows/project-automation.yml` | Repository automation, non-packaging; not a release artifact workflow. |
| `.github/workflows/pypi-validate.yml` | PyPI wheel and source distribution validation. |
| `.github/workflows/release.yml` | Aggregate exact 21 ECLI-owned asset release matrix and publication orchestration. |
| `.github/workflows/windows-installer.yml` | Windows portable EXE and NSIS installer package path. |
| `.github/workflows/windows-validate.yml` | Windows package validation. |

## Release Tooling Prerequisites

Install release tooling before running Gate 2 validation from a clean
maintainer environment:

```sh
python3 -m pip install -e ".[release]"
```

The `validate-gate2` target runs source and structural contract validation
without inspecting pre-existing local release artifacts. Use
`make validate-built-artifacts` for explicit final artifact verification; that
target validates complete artifact/sidecar pairs and fails closed on partial
artifact sets. When a complete wheel/sdist set and adjacent sidecars are present,
it delegates to `validate-pypi-contract`, which requires `twine` for strict PyPI
wheel/sdist metadata validation. `twine` is declared only in release/development
tooling dependencies, not in ECLI runtime dependencies.

The canonical `Release` workflow runs `make validate-built-artifacts` in the
`validate-built-artifacts` job after downloading all build outputs, assembling
`releases/<version>/`, and generating adjacent `.sha256` sidecars. The workflow
then moves those sidecars under `releases/<version>/.checksums/`, runs
`scripts/verify_release_assets.py` for the final exact-21 contract, and only then
allows GitHub Release or PyPI publication jobs to run.

## PyPI Namespace Pre-Reservation

The Python distribution name is `ecli-editor`; the import package and console
script remain `ecli`.

Before enabling a publish workflow for a new package name:

1. Confirm the configured distribution name:

   ```sh
   python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["name"])'
   ```

2. Check whether the PyPI namespace already exists:

   ```sh
   python3 -m pip index versions ecli-editor
   ```

3. If the project does not exist, build and upload a minimal placeholder release
   from a clean maintainer workstation using a scoped PyPI API token:

   ```sh
   python3 -m build
   version=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
   python3 -m build --outdir "releases/${version}"
   python3 -m twine check --strict "releases/${version}"/*.whl "releases/${version}"/ecli_editor-*.tar.gz
   python3 -m twine upload "releases/${version}"/*.whl "releases/${version}"/ecli_editor-*.tar.gz
   ```

4. Rotate or replace any token used for the bootstrap upload with a
   project-scoped token. Store only the scoped token in GitHub Secrets until
   Trusted Publishers is configured.

5. Re-run the namespace guard:

   ```sh
   python3 -m pip index versions ecli-editor
   ```

Do not embed PyPI API tokens in repository files, workflow YAML, release notes,
or documentation.

## PyPI Publishing - Phase 1 Static Token

Phase 1 publishes `ecli-editor` to PyPI from the tag-triggered release workflow
using the GitHub secret `PYPI_API_TOKEN`.

Token policy:

- The token must be project-scoped to `ecli-editor`.
- The token is stored only in GitHub Secrets.
- The token must be rotated after any public exposure event, suspected runner
  compromise, maintainer offboarding, or accidental local logging.
- The workflow must not request `id-token: write` for PyPI publishing while the
  static-token path is active.

The PyPI namespace guard remains mandatory before publish. It verifies that
`pyproject.toml` declares `ecli-editor` and that the project exists on PyPI
before the upload step can run.

Trusted Publishers (OIDC) are deferred to a later release. That migration will
remove the static token requirement.

## Mandatory GitHub Release Assets

```text
ecli_editor-<version>-py3-none-any.whl
ecli_editor-<version>.tar.gz
ecli_<version>_linux_x86_64.bin
ecli_<version>_linux_x86_64.tar.gz
ecli_<version>_linux_x86_64.deb
ecli_<version>_linux_x86_64.rpm
ecli_<version>_opensuse_x86_64.rpm
ecli_<version>_arch_x86_64.pkg.tar.zst
ecli_<version>_slackware_x86_64.txz
ecli_<version>_linux_x86_64.AppImage
ecli_<version>_freebsd_x86_64.pkg
ecli_<version>_freebsd_ports_chroot_evidence.tar.gz
ecli_<version>_macos_universal2_app_evidence.tar.gz
ecli_<version>_macos_universal2.dmg
ecli_<version>_win_x86_64.exe
ecli_<version>_win_x86_64_setup.exe
ecli_<version>_nix_flake_evidence.tar.gz
ecli_<version>_nixos_package_evidence.tar.gz
ecli_<version>_docker_deb_helper_evidence.tar.gz
ecli_<version>_docker_rpm_helper_evidence.tar.gz
ecli_<version>_workflow_contract_evidence.tar.gz
```

## SBOM

Release builds emit a CycloneDX SBOM for the Python distribution:

```text
releases/<version>/ecli-editor-<version>.cdx.json
releases/<version>/ecli-editor-<version>.cdx.json.sha256
```

The SBOM is generated with the `cyclonedx-bom` Python distribution, invoked as
`python3 -m cyclonedx_py environment`, in JSON format and CycloneDX schema
version 1.5. The workflow invokes the generator with `--validate`, so malformed
SBOM output fails the release build before artifact upload.

The SBOM and its SHA256 sidecar are verification evidence only. They may be
uploaded as workflow artifacts or included in workflow contract evidence, but
they must not be uploaded as GitHub Release assets. PyPI does not accept
arbitrary release attachments, so the SBOM is not uploaded to PyPI in Phase 1.

## FreeBSD Release Gate

The FreeBSD 14.x `.pkg` build runs inside `vmactions/freebsd-vm` on the
GitHub-hosted Linux runner (qemu-on-Linux). This path has historically
exhibited single-platform flakes that are not reproducible on the build artifact
itself. That risk does not relax the official release contract.

FreeBSD may be built by VM, native host, chroot, or ports route, but official
GitHub Release publication must wait until both required FreeBSD entries are
present in the exact 21 ECLI-owned asset set:

- `ecli_<version>_freebsd_x86_64.pkg`
- `ecli_<version>_freebsd_ports_chroot_evidence.tar.gz`

The standalone `FreeBSD 14 .pkg` workflow is validation evidence only. It may be
rerun to diagnose or restore the FreeBSD package leg, but it does not attach
assets to an official GitHub Release. The aggregate `Release` workflow blocks
until FreeBSD succeeds and `scripts/verify_release_assets.py` passes.

All vmactions invocations are pinned by commit SHA (currently v1.4.5). In both
workflows, the in-VM stdout is tee'd to `freebsd-build.log` and uploaded as a
workflow artifact on failure, so a vmactions SSH disconnect cannot lose the
in-VM trace.

## Future Hardening

Protected GitHub environments are recommended once the project has at least two
active maintainers. At that point, release publication jobs should bind to
protected environments such as `pypi` or `production` and require maintainer
review before external publication. Gate 2 Phase 0 intentionally ships without
workflow `environment:` bindings because protected environments are not yet
configured for this repository.

## Script Migration Contract

Active shell wrappers under `scripts/` have been removed. Release preparation and
workflow inspection must use canonical Python entrypoints under `scripts/`.
`scripts/build-and-package-windows.ps1` remains a separate Windows PowerShell
packaging surface. `tools/freebsd-chroot-build.sh` remains a FreeBSD chroot helper
outside this migration. The unused FreeBSD package-renaming shell helper was
removed as tracked tooling.

Maintainer-owned release/upload Make targets are guarded. Set
`ECLI_ALLOW_RELEASE=1` only when intentionally running the aggregate
`publish-all` target. Legacy per-platform `release-*` targets fail closed
because partial GitHub Release uploads are incompatible with the exact 21
ECLI-owned asset contract.

`Taskfile.yml` may expose convenience tasks such as `task publish-all`,
`task validate-release-assets`, `task release-linux`, `task release-freebsd`,
`task release-macos`, `task release-windows`, and `task release-pypi`, but those
tasks must only wrap the existing Makefile targets and preserve their guard or
blocked-target behavior. Makefile remains the authoritative build/release
contract; CI and release gates continue to rely on the existing canonical
command surfaces.
