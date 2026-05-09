<!--
Filename: docs/release/release-process.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
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

## Future Hardening

Protected GitHub environments are recommended once the project has at least two
active maintainers. At that point, release publication jobs should bind to
protected environments such as `pypi` or `production` and require maintainer
review before external publication. Gate 2 Phase 0 intentionally ships without
workflow `environment:` bindings because protected environments are not yet
configured for this repository.
