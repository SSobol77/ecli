<!--
Filename: docs/config/README.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
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
