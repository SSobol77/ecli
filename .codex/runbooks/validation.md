<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/runbooks/validation.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex validation runbook

## Purpose

Stage 1 validation evidence collection and summary for ECLI.

This runbook separates maintainer-run validation from Codex read-only interpretation. Codex may summarize outputs, classify failures, and identify P0 signals. Codex must not edit files during a validation summary and must not hide failing gates.

Git, GitHub, workflow, release, publication, and artifact-upload actions are maintainer-owned.

## Maintainer-run command block

The maintainer may run the canonical validation commands:

```sh
python3 tools/license_guard.py --report logs/license-guard.md
uv run ruff check . --output-format=concise
uv run mypy src/ecli tests
uv run pytest -ra -q
uv run python scripts/check_runtime_imports.py
```

Do not replace these with broad commands such as `uv run python *`, `make *`, or `gh run *`.

## Codex read-only summary procedure

Use Codex in read-only mode:

```sh
codex exec --sandbox read-only --ephemeral --cd . "Read AGENTS.md, CODEX.md, .codex/PIPELINE.md, .codex/roles/quality-engineer.md, .codex/runbooks/validation.md, audit-report.md, and the supplied validation logs. Summarize validation status. Do not edit files. Do not run git or gh."
```

If a report file is needed, Codex prints Markdown only and the maintainer redirects stdout:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT" > logs/validation-summary.md
```

Codex summary steps:

1. Confirm which command output is available.
2. Report missing command output explicitly.
3. Summarize each command's exit status and key findings.
4. Highlight P0-related signals separately, especially AUD-001, AUD-002, AUD-003, and `src/ecli/core/History.py` mypy errors.
5. Treat `pytest` as the primary functional baseline.
6. Report ruff failures exactly.
7. Treat mypy as baseline/diff unless the task explicitly targets type cleanup.

## PASS/FAIL interpretation

Use:

* `PASS` — all required evidence is present and the command passed with no relevant findings.
* `FAIL` — a command failed or produced a release-blocking finding.
* `BLOCKED` — required evidence is missing or ambiguous.

Do not mark validation clean if any required gate failed.

## Classification

Classify findings as:

* `clean` — no finding remains for that gate.
* `baseline debt` — known existing debt consistent with `audit-report.md` or prior accepted baseline.
* `new regression` — newly introduced, unexplained, or outside the known baseline.
* `needs-review` — insufficient evidence or ownership is unclear.

## Forbidden actions

Codex must not:

* edit files during validation summary;
* suppress, skip, normalize, or hide failing gates;
* run `git commit`, `git push`, `git tag`;
* run `gh pr create`, `gh issue edit`, `gh issue close`, `gh issue comment`;
* run `gh workflow run`, `gh run rerun`, `gh run cancel`;
* run `gh release`;
* run `twine upload`, `uv publish`, or `python -m twine upload`;
* run `make release`, `make release-*`, `make publish`, or `make publish-*`.

## Output

Finish with:

```text
Result:
- What was inspected:
- Evidence:
- Commands run:
- Commands blocked:
- Files touched:
- Remaining risks:
- Recommended next step:
```
