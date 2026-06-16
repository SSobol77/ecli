<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/validate.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex validation summary prompt

Use with:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT"
```

Prompt:

```text
Act as the Codex quality-engineer for ECLI.

Read, in order:
1. AGENTS.md
2. CODEX.md
3. .codex/PIPELINE.md
4. .codex/roles/quality-engineer.md
5. .codex/roles/runtime-engineer.md when runtime-import evidence is involved
6. .codex/runbooks/validation.md if present
7. audit-report.md
8. pyproject.toml
9. Makefile
10. relevant validation logs or pasted output

Claude-specific files under .claude/ and CLAUDE.md are not Codex authority.

Stage 1 rule: summarize validation honestly. Do not fix source code, tests, workflows, packaging descriptors, or documentation unless explicitly asked in a separate scoped task. Do not hide failing gates.

Expected validation evidence:
- python3 tools/license_guard.py --report logs/license-guard.md
- uv run ruff check . --output-format=concise
- uv run mypy src/ecli tests
- uv run pytest -ra -q
- uv run python scripts/check_runtime_imports.py
- uv run pytest -q tests/packaging/test_scripts_python_migration_contract.py
- uv run python scripts/check_log_invariant.py

If outputs are already present in logs or pasted into the request, summarize those outputs instead of rerunning. If evidence is missing, say exactly which command output is missing. If you do run commands, run only the exact commands listed above.

Classify each result as:
- clean: command passed and no relevant findings remain;
- baseline: known existing debt consistent with audit-report.md or prior logs;
- new regression: newly introduced or not explained by the baseline;
- needs-review: insufficient evidence or ambiguous ownership.

For mypy, highlight P0-related errors separately, especially History.py. For pytest, treat the result as the primary functional baseline. For ruff, report failures exactly.

Do not run git commit, git push, git tag, GitHub write commands, workflow triggers, GitHub release commands, release targets, publish targets, artifact upload commands, twine upload, uv publish, or python -m twine upload.

`Taskfile.yml` is optional developer convenience only. You may use `task` only
when it delegates to existing Makefile targets. Makefile remains the
authoritative build/release contract, release/publish tasks must remain guarded,
and packaging scripts must remain Python entrypoints under `scripts/*.py`.

If a report file is needed, print Markdown only; the maintainer redirects stdout to the target file.

Finish with:

Result:
* What was inspected:
* Evidence:
* Commands run:
* Commands blocked:
* Files touched:
* Remaining risks:
* Recommended next step:
```
