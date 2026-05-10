<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/release/release-process.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
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
   python3 -m twine check --strict dist/*
   python3 -m twine upload dist/*
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

Trusted Publishers (OIDC) are deferred to v0.2. That migration will remove the
static token requirement.

## SBOM

Release builds emit a CycloneDX SBOM for the Python distribution:

```text
dist/ecli-editor-<version>.cdx.json
dist/ecli-editor-<version>.cdx.json.sha256
```

The SBOM is generated with the `cyclonedx-bom` Python distribution, invoked as
`python3 -m cyclonedx_py environment`, in JSON format and CycloneDX schema
version 1.5. The workflow invokes the generator with `--validate`, so malformed
SBOM output fails the release build before artifact upload.

The SBOM and its SHA256 sidecar are uploaded as workflow artifacts and attached
to the GitHub Release. PyPI does not accept arbitrary release attachments, so the
SBOM is not uploaded to PyPI in Phase 1.

## Future Hardening

Protected GitHub environments are recommended once the project has at least two
active maintainers. At that point, release publication jobs should bind to
protected environments such as `pypi` or `production` and require maintainer
review before external publication. Gate 2 Phase 0 intentionally ships without
workflow `environment:` bindings because protected environments are not yet
configured for this repository.
