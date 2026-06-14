<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/validation-runbook.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# ECLI Validation Runbook

This runbook defines the Stage 1 validation behavior for Claude Code automation.

## Canonical validation commands

Use:

```sh
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
uv run pytest -ra -q
uv run python scripts/check_runtime_imports.py
```

When relevant, also use:

```sh
make help
make sysinfo
make test
make lint
```

## Gate interpretation

### Pytest

Pytest is the primary functional baseline. A failing pytest run is a direct validation failure.

### Ruff

Ruff failures must be reported exactly. If current baseline is red, do not hide it and do not call the gate clean.

### Mypy

Mypy may have known baseline debt. Treat it as baseline/diff unless the task explicitly targets full type cleanup.

P0-related mypy errors must be highlighted separately, especially errors in `src/ecli/core/History.py`.

### Runtime imports

Runtime import checks must use:

```sh
uv run python scripts/check_runtime_imports.py
```

Do not use bare `python` unless the environment proves it exists.

## Required validation report

Every validation run must finish with:

```text
Validation summary:
- Pytest:
- Ruff:
- Mypy:
- Runtime imports:
- Config/runtime validation:
- Artifact contract:
- Curses boundary:
- Logging risk:
- Blocked actions:
- Recommended next step:
```
