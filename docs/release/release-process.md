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
- Missing required artifacts must block release.
- Workflow references to non-existent files must be resolved as release blockers.
