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
2. Validate artifact contract and checksums
3. Publish package artifacts
4. Publish Python distribution (if enabled in workflow)
5. Publish release notes and release assets

## Required Controls

- Contract validation must happen before publish.
- `make validate-gate2` is the required pre-publish validation gate.
- Missing required artifacts must block release.
- Workflow references to non-existent files must be resolved as release blockers.
- Every active package/platform surface must appear in the `Canonical 21-Item
  Platform & Packaging Artifact Matrix` (summarized by the `Platform & Packaging
  Release Contract Matrix`), agent contracts, build/release runbooks, and
  repository-local validation tests under `tests/packaging/`. The canonical
  matrix has exactly 21 entries; coverage in tests, Claude commands, Codex
  prompts, and workflows must never be smaller than that matrix.
- Empty, stale, decorative, or unused packaging files are release blockers until
  they are either wired into the contract matrix or explicitly removed from
  active workflows/scripts.

## GitHub Actions Workflow Contract Map

Release readiness treats `.github/workflows/` as an explicit CI/release contract
surface. Every workflow must be documented here and in
`docs/release/artifact-contract.md`; adding an unmapped workflow is release
contract drift.

| Workflow | Release role |
|---|---|
| `.github/workflows/ci.yml` | Global quality gate, `validate-gate2`, and root `main.py` compatibility contract. |
| `.github/workflows/freebsd-pkg.yml` | FreeBSD `.pkg` / port / chroot package path and out-of-band attach workflow. |
| `.github/workflows/macos-dmg.yml` | macOS `.app` / `.dmg` package path. |
| `.github/workflows/macos-validate.yml` | macOS package validation. |
| `.github/workflows/project-automation.yml` | Repository automation, non-packaging; not a release artifact workflow. |
| `.github/workflows/pypi-validate.yml` | PyPI wheel and source distribution validation. |
| `.github/workflows/release.yml` | Aggregate release artifact matrix and publication orchestration. |
| `.github/workflows/windows-installer.yml` | Windows portable EXE and NSIS installer package path. |
| `.github/workflows/windows-validate.yml` | Windows package validation. |

## Release Tooling Prerequisites

Install release tooling before running Gate 2 validation from a clean
maintainer environment:

```sh
python3 -m pip install -e ".[release]"
```

The `validate-gate2` target requires `twine` for strict PyPI wheel/sdist
metadata validation. `twine` is declared only in release/development tooling
dependencies, not in ECLI runtime dependencies.

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

The SBOM and its SHA256 sidecar are uploaded as workflow artifacts and attached
to the GitHub Release. PyPI does not accept arbitrary release attachments, so the
SBOM is not uploaded to PyPI in Phase 1.

## FreeBSD Leg Is Best-Effort

The FreeBSD 14.x `.pkg` build runs inside `vmactions/freebsd-vm` on the
GitHub-hosted Linux runner (qemu-on-Linux). This path has historically
exhibited single-platform flakes that are not reproducible on the build
artifact itself. To keep a single-platform flake from blocking publication
of the Linux / macOS / Windows / Python release assets, the pipeline is
configured as follows:

- `build-freebsd` in `release.yml` runs with `continue-on-error: true`.
- `publish-github-release` keeps `build-freebsd` in `needs:` for ordering
  only. Its `if:` condition requires Linux / macOS / Windows / Python to be
  green but **does not require** FreeBSD success.
- If the FreeBSD leg succeeds, the `.pkg` flows into the release through the
  normal `actions/download-artifact` + `softprops/action-gh-release` path.
- If the FreeBSD leg fails or is skipped, the publisher injects a deferral
  note into the release body and the `.pkg` is attached out-of-band by
  dispatching the standalone `FreeBSD 14 .pkg` workflow with the
  `release_tag` input set to the published tag.
- All vmactions invocations are pinned by commit SHA (currently v1.4.5). In
  both workflows, the in-VM stdout is tee'd to `freebsd-build.log` which is
  uploaded as a workflow artifact named `freebsd-build-log-<run_id>` on
  failure, so a vmactions SSH disconnect cannot lose the in-VM trace.

### Out-of-Band FreeBSD Attach

```sh
# After the Release workflow publishes without FreeBSD, fix any FreeBSD-side
# regression, then attach the .pkg post-hoc:
gh workflow run freebsd-pkg.yml --ref main -f release_tag=v<version>
```

The standalone workflow builds the `.pkg` in a fresh vmactions VM, verifies
its checksum, and then runs:

```sh
gh release upload "v<version>" "<built.pkg>" "<built.pkg>.sha256" --clobber
```

This path requires `permissions: contents: write` on that workflow.

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
packaging surface. `.claude/hooks/block-mutations.sh` is a Claude hook, not a
packaging script. `tools/freebsd-chroot-build.sh` remains a FreeBSD chroot helper
outside this migration. The unused FreeBSD package-renaming shell helper was
removed as tracked tooling.

Maintainer-owned release/upload Make targets are guarded. Set
`ECLI_ALLOW_RELEASE=1` only when intentionally running targets such as
`release-deb`, `release-rpm`, `release-appimage`, `release-freebsd`,
`release-macos`, `release-windows`, or `publish-all`.

`Taskfile.yml` may expose convenience tasks such as `task publish-all`,
`task release-linux`, `task release-freebsd`, `task release-macos`,
`task release-windows`, and `task release-pypi`, but those tasks must only wrap
the existing Makefile targets and preserve their guard behavior. Makefile
remains the authoritative build/release contract; CI and release gates continue
to rely on the existing canonical command surfaces.
