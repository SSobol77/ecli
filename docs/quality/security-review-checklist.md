<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/quality/security-review-checklist.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Security Review Checklist

## Subprocess and Command Execution

- [ ] All subprocess invocations use explicit argument arrays (no shell=True or string commands).
- [ ] Working directory assumptions are validated.
- [ ] Timeout behavior is defined for external commands.
- [ ] Error output is sanitized before user display where needed.

## Credential Handling

- [ ] API keys are loaded from expected env/config sources only.
- [ ] No credentials are committed in repository.
- [ ] Provider errors do not leak sensitive values.

## Integration Boundaries

- [ ] AI/Git/LSP adapters do not mutate editor state without contract path.
- [ ] External process failures cannot crash the editor loop.

## Release and Artifact Safety

- [ ] Artifacts include checksums.
- [ ] Release pipeline validates expected files only.
- [ ] Unexpected binary artifacts are rejected by contract checks.
