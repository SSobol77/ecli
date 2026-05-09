# ECLI Documentation System

This documentation is organized as an engineering subsystem with explicit authority boundaries.

## How to Navigate

- Start with this file, then read category `README.md` files.
- Use `architecture/` for system structure and contracts.
- Use `release/` for packaging and artifact rules.
- Use `contributor/` for setup and local workflows.
- Use `planning/` for phased execution and risks.

## Documentation Classes

- **Normative**: defines required behavior and contracts (`must`, `must not`).
- **Descriptive**: captures current implementation reality.
- **Planning**: execution intent, sequencing, and risk management.

## Authority Map (Single Source of Truth)

- Architecture boundaries: `architecture/module-contracts.md`
- Current runtime reality: `architecture/current-architecture.md`
- Target architecture: `architecture/target-architecture.md`
- Config schema and precedence: `config/config-schema.md`, `config/config-precedence.md`
- CI quality gates: `quality/ci-quality-gates.md`
- Artifact contract and release policy: `release/artifact-contract.md`, `release/release-process.md`
- Contributor workflows: `contributor/development-setup.md`, `contributor/local-validation.md`
- Execution roadmap: `planning/roadmap.md`

## Current-State vs Target-State Rule

All architecture and release documents must explicitly separate:
- **current state** (implemented and observed),
- **target state** (desired design),
- **planned follow-up** (not yet implemented).

## Archive Policy

- Superseded documents are moved to `archive/`.
- Archived docs are historical references and are **not** authoritative.
