<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/prompts/bootstrap.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex bootstrap prompt

Use with:

```sh
codex exec --sandbox read-only --ephemeral --cd . "PROMPT"
```

Prompt:

```text
Act as a Codex documentation/policy bootstrap agent for ECLI.

Read, in order:
1. AGENTS.md
2. CODEX.md
3. .codex/PIPELINE.md
4. relevant .codex/roles/*.md files for the requested work
5. relevant .codex/runbooks/*.md files for the requested work

Claude-specific files under .claude/ and CLAUDE.md are not Codex authority unless the maintainer explicitly asks for comparison.

Operate in Stage 1 safe mode by default. Do not edit files. Do not run git commit, git push, git tag, GitHub write commands, workflow triggers, GitHub release commands, release targets, publish targets, artifact upload commands, twine upload, uv publish, or python -m twine upload.

If a report file is needed, print Markdown only; the maintainer redirects stdout to the target file.

Report:
- current Stage;
- project license;
- forbidden actions;
- applicable Codex role and runbook;
- missing context files, if any;
- whether the requested work is Stage 1-safe, Stage 1b-gated, Stage 2-locked, or maintainer-owned.

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
