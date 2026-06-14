<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .codex/runbooks/runtime.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Codex runtime runbook

## Purpose

Stage 1 isolated runtime checks and runtime safety reporting for ECLI.

This runbook covers import checks, startup/help smoke checks, log path verification, and redacted runtime-log summaries. Runtime checks must not write to the user's real configuration unless the maintainer explicitly requests that behavior.

Git, GitHub, workflow, release, publication, build-upload, and artifact-upload actions are maintainer-owned.

## Isolated runtime environment

Use an isolated `HOME` and `XDG_CONFIG_HOME` for startup and runtime smoke checks:

```sh
tmp_home="$(mktemp -d)"
HOME="$tmp_home" XDG_CONFIG_HOME="$tmp_home/.config" uv run python -m ecli --help
```

Keep the temporary home path in the report if it is needed to explain log or config placement. Do not copy files from the user's real config into this temporary home unless explicitly requested.

## Runtime import check

Use the repository runtime import contract:

```sh
uv run python scripts/check_runtime_imports.py
```

If this command fails, report the failing import path, exception class, and whether the failure maps to AUD-001, AUD-003, or a new runtime concern.

## Startup/help smoke check

Use the isolated startup command:

```sh
tmp_home="$(mktemp -d)"
HOME="$tmp_home" XDG_CONFIG_HOME="$tmp_home/.config" uv run python -m ecli --help
```

Report:

* exit status;
* stderr summary;
* whether runtime config was created under the isolated home;
* whether any real user config path was touched.

## Log path verification

Inspect log creation paths and runtime logging references read-only:

```sh
rg -n "logging|log_path|log_file|basicConfig|getLogger|exception\\(" src/ecli scripts tests
```

When logs are generated inside the isolated home, report their location and high-level content. Do not quote logs before redaction.

## Redaction rules

Before quoting logs, redact:

* API keys;
* bearer tokens;
* provider URLs containing credentials;
* prompt-like content;
* raw provider responses;
* environment variable values that may contain secrets;
* sensitive local paths unless required for diagnosis.

## Forbidden actions

Codex must not:

* write to the user's real `HOME`, real XDG config, or real ECLI configuration;
* run interactive TUI automation unless explicitly requested;
* run release, publish, build-upload, or artifact-upload actions;
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
