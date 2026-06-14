<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/contributor/development-setup.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
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
| `twine` | Release-only | PyPI artifact validation in `make validate-gate2` | install via `.[release]`, `.[dev]`, or `requirements-dev.txt` |
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

## Development Logs and Generated Evidence

All generated development logs, dry-run reports, smoke outputs, test evidence,
and agent-generated debug artifacts must be written only under the repository-level
`logs/` directory.

Generated artifacts must not be written to:

- project root
- `.ecli/`
- `.ecli/vmlab/`
- `src/`
- `tests/`
- `tmp/`
- `.tmp/`
- `.cache/`
- `$HOME`
- `/tmp`

Before opening a PR that may generate local artifacts, run:

```bash
./scripts/check-log-invariant.sh
```

The script must pass before merge.

## Validation Required

- Exact per-platform dependency package names may vary by distro/release and should be confirmed against active packaging scripts.
