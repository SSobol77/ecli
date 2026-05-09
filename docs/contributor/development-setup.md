<!--
Path: docs/contributor/development-setup.md
File: development-setup.md
Project: Ecli
Site: www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0
Date: 19/04/2026
-->
# Development Setup

## Environment Bootstrap Checklist

- [ ] Clone repository
- [ ] Install Python 3.11+
- [ ] Install `uv`
- [ ] Sync dependencies (`uv sync`)
- [ ] Run runtime sanity check (`python main.py`)
- [ ] Optional packaging sanity checks: verify binary packaging, dependency licenses, architecture compatibility, checksum/signature verification, and sample install/run commands for your platform (see release documentation for details)

## Tool / Dependency Matrix

| Tool / Dependency | Required? | Why | Platform notes |
|---|---:|---|---|
| Python 3.11+ | Yes | runtime and build scripts | all platforms |
| `uv` | Recommended | deterministic dependency workflow | all platforms |
| `pipx` | Optional | convenient tool installation | all platforms |
| `ruff` / `pytest` toolchain | Role-dependent | local validation | maintainer-focused |
| `makensis` | Optional by role | Windows packaging | Windows packaging maintainers |
| `hdiutil` | Optional by role | macOS DMG packaging | macOS only |
| FreeBSD pkg toolchain | Optional by role | FreeBSD package build | FreeBSD environment only |

## Required Setup Steps

1. Clone:
   - `git clone <repo-url>` (replace <repo-url> with the repository SSH or HTTPS URL from the project README or repository page)
2. Enter repo:
   - `cd ecli`
3. Install `uv` (if not already installed):
   - `pip install --user uv` or `pipx install uv`
   - Verify with: `uv --version`
4. Install/sync dependencies:
   - `uv sync`
5. Runtime sanity:
   - `python main.py`

## Optional Setup by Role

- Release maintainer: install platform packaging dependencies.
- Packaging maintainer: install platform-specific build toolchain.
- Refactor engineer: ensure local lint/format/test command availability.

## Expected Success Criteria

- Source runtime starts without immediate fatal bootstrap errors.
- Lint/format commands are available for local validation path.
- Selected packaging command for your platform starts and emits expected preflight output.

## Validation Required

- Exact per-platform dependency package names may vary by distro/release and should be confirmed against active packaging scripts.
