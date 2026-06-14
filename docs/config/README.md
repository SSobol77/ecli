<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/config/README.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Configuration Documentation

Defines schema contracts, source precedence, migration policy, and runtime diagnostics expectations.

## Config Authority Map

| File | Authoritative for |
|---|---|
| `config-schema.md` | canonical keys, types, constraints, failure classes |
| `config-precedence.md` | source priority, bootstrap, merge/override behavior |
| `config-migration-policy.md` | legacy-key handling, deprecation lifecycle, migration diagnostics |

## Reader Entry Points

- **Runtime debugging**: start with `config-precedence.md`, then `config-schema.md`
- **Adding a new key**: `config-schema.md` -> `config-migration-policy.md`
- **Changing defaults**: `config-precedence.md` + `config-schema.md`
- **Deprecating/removing a key**: `config-migration-policy.md`

## Normative Example Rule

- Examples/tables marked as normative are contract material and must remain synchronized with implementation.

## Validation-Required Example Rule

- If an example uses not-yet-verified behavior, it must explicitly include a “Validation required” note.
