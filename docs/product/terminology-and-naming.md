<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/product/terminology-and-naming.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Terminology and Naming

## Canonical Project Name

- Product name: `ECLI`
- Python package / executable identifiers may use `ecli`.

## Required Naming Consistency

- Use `current state`, `target state`, `planned follow-up` consistently across docs.
- Use `artifact contract` only for release naming and verification policy.
- Avoid mixing roadmap terms into normative architecture contracts.

## File Naming Policy for Docs

- Lowercase kebab-case filenames.
- The repository root keeps the only global `README.md`.
- Non-root folder overview files use `README-<folder>.md` to avoid path
  ambiguity in agent workflows and release review.
