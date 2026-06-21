<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/config/config-schema.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Configuration Schema (Current + Target Contract)

## Configuration Lifecycle Overview

Observed current state: parse+merge exist; strict validation is weak.  
Intended target state: parse -> validate -> normalize -> immutable runtime config.

```mermaid
flowchart LR
  SRC[Config Sources] --> PARSE[Parse]
  PARSE --> VALID[Validate]
  VALID --> NORM[Normalize]
  NORM --> IMM[Runtime Config (immutable view)]
```

## Canonical Config Tree (Target Contract)

```text
root
  theme
  logging
    file_level
    console_level
    log_to_console
    separate_error_log
  ai
    default_provider
    models.<provider>
    keys.<provider>    # via config/env, env preferred for secrets
  editor
    use_system_clipboard
    tab_size
    use_spaces
    show_line_numbers
    auto_indent
    auto_brackets
  settings
    auto_save_interval
    show_git_info
  file_icons
```

Internal comment delimiters, syntax fallback data, supported-format tables, and
keybinding defaults live in code. They are not public template sections in
`config.toml`.

## Theme Numbering Policy

The root `theme = N` value uses the stable Extensions Layer numbering contract:

- `1`-`8`: deprecated aliases for old pre-extension-theme configs only.
- `100`-`199`: light themes.
- `200`-`299`: dark themes.
- `300`-`399`: high-contrast themes.
- `800`-`899`: reserved for future custom/imported special themes.

The repository default is `theme = 207` (`Dark+`). Existing user configs with
old pre-extension aliases `1`-`8` are migrated to preserved built-in
compatibility themes in the `18x`/`28x`/`38x` ranges. Transitional ids from the
previous in-progress implementation migrate as `1`-`10` -> `101`-`110`,
`11`-`25` -> `201`-`215`, and `26`-`29` -> `301`-`304`.

Before modifying a user config, migration writes
`~/.config/ecli/config.toml.pre-extension-theme-numbering.bak`. Missing or
invalid theme numbers must keep the current valid theme when one exists, emit a
visible ECLI warning, and never map to an unrelated theme.

## Current-State vs Target-State

- **Observed current state**:
  - schema is implicit,
  - defaults duplicated between `config.toml` and embedded defaults,
  - malformed default/template risk exists.
- **Intended target state**:
  - single canonical internal schema model,
  - strict validation classes (fatal/warn),
  - deterministic unknown-key policy.
- **Validation required**:
  - key-by-key parity between template and embedded defaults.

## Normative Key Metadata Table (Core Keys)

| Key path | Type | Required | Default | Source(s) | Validation | Migration notes | Failure mode |
|---|---|---:|---|---|---|---|---|
| `logging.file_level` | string(enum log level) | No | `DEBUG` | defaults/user | must be valid log level token | normalize case | warn + fallback |
| `logging.console_level` | string(enum) | No | `WARNING` | defaults/user | valid token | normalize case | warn + fallback |
| `logging.log_to_console` | bool | No | `true` | defaults/user | boolean coercion disallowed unless explicit | none | warn + fallback |
| `theme` | int | No | `207` | defaults/user/env | must resolve to an imported or compatibility theme id | see theme numbering policy | warn + keep current/default |
| `ai.default_provider` | string | No | implementation default | defaults/user | must map to known provider set | legacy alias mapping allowed | warn + fallback |
| `ai.models.<provider>` | string | Provider-dependent | none | defaults/user | non-empty model id | provider alias normalization | warn; runtime feature degraded |
| `editor.tab_size` | int | No | `4` | defaults/user | integer > 0 | clamp policy allowed | warn + fallback |
| `settings.auto_save_interval` | int/float | No | `5` | defaults/user | > 0 | normalize numeric | warn + fallback |
| `comments.<language>.line_prefix` | string | No | language-dependent | defaults/user | non-empty where used | none | warn + feature degrade |

## Section-Level Schema Summary

| Section | Startup critical? | Strict-mode behavior | Runtime fallback behavior |
|---|---:|---|---|
| `logging` | No | type/unknown key warnings escalate to CI failure | fallback to safe defaults |
| `editor` | No | invalid types fail strict schema check | fallback per key |
| `settings` | No | invalid numeric constraints fail strict check | fallback with warning |
| `ai` | No (core editor) | malformed provider/model keys fail strict check | AI degraded, editor continues |
| `file_icons` | No | unknown structure fails strict check | generic icon fallback |

## Unknown-Key Handling Policy

- Current observed behavior: unknown keys are effectively tolerated through merge behavior.
- Target contract:
  - unknown top-level keys -> warning,
  - unknown nested keys in known sections -> warning,
  - optional strict mode (future): fail CI validation for unknown keys.

## Malformed-Value Handling Policy

- Fatal:
  - parse failure of active user config file at startup must produce explicit diagnostic; runtime may continue with fallback.
- Warning:
  - type mismatch on optional keys -> fallback + warning.
- Release-blocking:
  - malformed repository template/default config distributed with release artifacts.

## Secret-Bearing Key Handling Rules

- Secret values (provider API keys) must prefer environment channels.
- Secret-bearing keys in user config are allowed but discouraged.
- Secret values must not be logged in plaintext diagnostics.
- Strict mode should validate presence/shape constraints without leaking values.

## Minimal Valid Config (Normative Example)

```toml
[editor]
tab_size = 4

[settings]
auto_save_interval = 5
```

## Representative Full Config (Normative Example)

```toml
[logging]
file_level = "DEBUG"
console_level = "WARNING"
log_to_console = false
separate_error_log = false

[ai]
default_provider = "openai"

[ai.models]
openai = "gpt-5-codex"
gemini = "gemini-2.5-pro"
claude = "claude-4-opus"

[editor]
tab_size = 4
use_spaces = true
show_line_numbers = true
auto_indent = true
auto_brackets = true

[settings]
auto_save_interval = 5
show_git_info = true
```

## Malformed Config Examples + Expected Diagnostics

Example 1:
```toml
[editor]
tab_size = "four"
```
Expected: warning (`editor.tab_size` invalid type), fallback to default.

Example 2:
```toml
[ai.models]
mistral = "magistral-medium-1.2""
```
Expected: parse failure diagnostic; release-blocking if in distributed default/template.

## Observed Schema Duplication / Ambiguity

- Defaults live in both embedded Python dictionary and TOML template.
- Some nested conventions are represented differently across sources.
- Key parity and canonicalization require validation pass.

## Mapping Observed Sections -> Canonical Internal Model

| Observed section/key family | Canonical internal model section | Notes |
|---|---|---|
| `ai.models` and env keys | `ai.providers` canonical map (target) | keep backward-compatible paths during migration |
| `comments.<lang>` | comment rules registry | optional section |
| `supported_formats` + `file_icons` | file classification + icon map | fallback allowed |

## Release-Blocking Config Defects

- Syntax errors in distributed default/template config.
- Missing critical canonical defaults required for startup safety.
- CI schema validation drift against canonical key set.

## Inventory Coverage Status

- **Observed known inventory**: core sections listed in this document are repository-backed.
- **Complete inventory verified**: No (partial inventory only).
- **Validation required**: key-by-key parity check between embedded defaults, template config, and runtime consumers.

## Traceability to Known Problems

| Known problem | Governing section |
|---|---|
| Broken default config parsing | `Malformed-Value Handling Policy`, `Release-Blocking Config Defects` |
| Implicit/duplicated schema | `Current-State vs Target-State`, `Observed Schema Duplication / Ambiguity` |
| Weak fatal vs warning clarity | `Malformed-Value Handling Policy`, core key metadata `Failure mode` column |
