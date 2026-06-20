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

## Extensions Layer Terminology

- `ECLI Extensions Layer` is the canonical name for the imported, data-only,
  VS Code / TextMate-compatible asset tree and the deterministic adapter code
  around it. It is defined in `docs/architecture/extensions-layer.md`.
- `src/ecli/extensions/` is the only approved location for imported extension
  assets. Do not introduce or refer to `vendor/`, `third_party/`, or
  `src/ecli/syntax/assets/` for this purpose.
- `imported assets` (or `upstream assets`) are read-only from the ECLI
  integration perspective; ECLI behavior is added through `adapter code`, not by
  editing imported files.
- The Extensions Layer is a data + adapter layer, not an extension `host`. Do not
  describe it as a VS Code extension host or a runtime that activates Node,
  `activationEvents`, or Copilot.

## File Naming Policy for Docs

- Lowercase kebab-case filenames.
- The repository root keeps the only global `README.md`.
- Non-root folder overview files use `README-<folder>.md` to avoid path
  ambiguity in agent workflows and release review.
