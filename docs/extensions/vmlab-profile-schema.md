<!--
SPDX-License-Identifier: Apache-2.0

Project: ECLI
File: docs/extensions/vmlab-profile-schema.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
Author: Siergej Sobolewski
License: Apache License, Version 2.0

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->

# VMLab Profile Schema

**Phase 2 Runtime Profile Contract**

**Version:** 1.0
**Date:** 2026-05-15
**Status:** Strategic Architecture Direction
**Part of:**
[Product Vision](../architecture/product-vision.md) |
[Services Foundation](../architecture/services-foundation.md) |
[CommandPlanService](../architecture/command-plan-service.md) |
[VMLab Overview](./vmlab-overview.md)

---

## 1. Purpose

This document defines the typed TOML schema for VMLab VM profiles.

A VMLab profile is a versionable, Git-friendly, human-readable configuration file that describes:

- hardware resources;
- acceleration preference;
- storage attachments;
- optional host path shares;
- network interfaces;
- serial console configuration;
- QMP socket configuration;
- optional direct kernel boot parameters;
- console behavior and escape sequences.

Profiles are not execution commands.

Profiles are inputs to VMLab profile validation and to `CommandPlanService`.

A validated profile may be used to generate an explicit, previewable, confirmable, auditable, and reproducible command plan for VM lifecycle operations.

Critical rule:

```text
A profile alone never mutates system state.
Only a confirmed CommandPlan derived from a validated profile may trigger execution.
````

VMLab profile schema supports the wider ECLI direction:

```text
terminal-first
config-first
plain text first
plans before execution
audit before trust
```

---

## 2. Scope

### Development Log Location Rule

During development, all generated logs, dry-run reports, test evidence, mock runtime artifacts, and agent debug output must be written only under repository-level:

```text
logs/
```

Recommended VMLab development layout:

```text
logs/vmlab/
logs/vmlab/dry-run/
logs/vmlab/qmp/
logs/vmlab/serial/
logs/vmlab/runtime/
logs/vmlab/tests/
```

The `.ecli/vmlab/` paths described in this document are profile and future runtime layout concepts.

Phase 2A skeleton implementation must not create runtime logs, dry-run artifacts, test evidence, or agent logs under `.ecli/vmlab/`.

Forbidden development output locations:

```text
.ecli/
.ecli/vmlab/
src/
tests/
tmp/
.tmp/
.cache/
$HOME/
/tmp/
project root outside logs/
```

### 2.1 This Document Defines

| Aspect                              | Description                                                                                                       |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Profile file location and discovery | Where ECLI looks for `.toml` VM profiles                                                                          |
| Schema versioning                   | How profile schema versions are declared and evolved                                                              |
| Root structure                      | Required and optional top-level sections                                                                          |
| Section contracts                   | `[vm]`, `[hardware]`, `[[storage.disks]]`, `[[network.interfaces]]`, `[serial]`, `[qmp]`, `[console]`, `[kernel]` |
| Validation rules                    | Static checks before plan generation                                                                              |
| Acceleration selection              | Deterministic behavior for `acceleration = "auto"`                                                                |
| QEMU argv generation principles     | How validated fields map to command arguments                                                                     |
| Security constraints                | What must never appear in profiles                                                                                |
| Examples                            | Valid TOML examples for common workflows                                                                          |
| Required tests                      | Contract-level validation expectations                                                                            |

### 2.2 This Document Does Not Define

| Excluded                                       | Owner / Reason                             |
| ---------------------------------------------- | ------------------------------------------ |
| Runtime process management                     | `VMSupervisor` / `RuntimeService`          |
| QMP protocol details                           | Future `vmlab-qmp-client.md`               |
| Serial console I/O behavior                    | Future `vmlab-console-and-logs.md`         |
| Plan lifecycle and execution                   | `CommandPlanService`                       |
| Privileged remediation logic                   | `SystemDoctor` + `PrivilegedActionService` |
| UI rendering of profile editors                | TUI / GUI layer specifications             |
| Full backend abstraction for non-QEMU runtimes | Future backend adapter documents           |

---

## 3. Profile Discovery

### 3.1 Search Paths

VMLab discovers profiles in this precedence order:

```text
1. ./.ecli/vmlab/profiles/*.toml
2. $XDG_CONFIG_HOME/ecli/vmlab/profiles/*.toml
3. /etc/ecli/vmlab/profiles/*.toml
```

On Linux, if `$XDG_CONFIG_HOME` is not set, the user-global path resolves to:

```text
~/.config/ecli/vmlab/profiles/*.toml
```

### 3.2 Discovery Rules

| Rule                                                 | Rationale                                 |
| ---------------------------------------------------- | ----------------------------------------- |
| Project-local profiles have highest priority         | Reproducible project workflows            |
| User-global profiles are reusable personal templates | Avoid repeated local definitions          |
| System-wide profiles are shared machine defaults     | Site-level defaults                       |
| Higher-priority profile wins on name conflict        | Predictable resolution                    |
| Conflicts are reported in verbose mode               | Avoid silent surprises                    |
| Profiles are discovered by filename stem             | `kernel-dev.toml` becomes `kernel-dev`    |
| Hidden files are ignored                             | Avoid loading editor temp files           |
| Subdirectories are not traversed in v1               | Flat namespace keeps behavior predictable |

### 3.3 Profile Resolution Example

```text
User runs:
  ecli vm start kernel-dev

ECLI checks:
  1. ./.ecli/vmlab/profiles/kernel-dev.toml
  2. ~/.config/ecli/vmlab/profiles/kernel-dev.toml
  3. /etc/ecli/vmlab/profiles/kernel-dev.toml
```

If the project-local profile exists, it wins.

If no profile is found, ECLI must return a structured diagnostic error, not a stack trace.

### 3.4 Merge Rule

VMLab v1 does not merge profiles across scopes.

A profile is selected as a whole file.

Future schema versions may introduce explicit inheritance or template composition, but v1 must avoid silent merges.

---

## 4. Schema Versioning and Migration

### 4.1 Version Declaration

Every profile must declare its schema version:

```toml
schema_version = 1
```

### 4.2 Version Compatibility

| ECLI Version | Supported `schema_version`                    |
| ------------ | --------------------------------------------- |
| 0.1.x        | `1` only                                      |
| 0.2.x        | `1`, future `2` with migration support        |
| 1.0+         | Backward-compatible migrations where possible |

### 4.3 Migration Policy

Profile migration may modify user files, so it must not happen silently.

Rules:

- loading an older profile may produce a migration proposal;
- automatic in-memory normalization is allowed for compatibility;
- writing the migrated profile back to disk requires an explicit command plan or user confirmation;
- the original file must be backed up before any write;
- migration must be deterministic;
- destructive or lossy migration is not allowed without explicit user confirmation;
- users may opt out of automatic migration proposals via config.

Recommended migration flow:

```text
load profile
  -> detect older schema
  -> normalize in memory
  -> warn user
  -> optionally generate migration CommandPlan
  -> user confirms
  -> write backup
  -> write migrated profile
  -> audit event
```

### 4.4 Unknown and Deprecated Fields

For schema v1:

- unknown fields should produce warnings, not hard errors;
- unknown fields must not affect generated QEMU argv;
- deprecated fields should emit warnings and migration suggestions;
- fields that look like secrets must produce security warnings.

---

## 5. Root Structure

### 5.1 Minimal Valid Profile

```toml
schema_version = 1

[vm]
name = "my-vm"

[hardware]
arch = "x86_64"
memory_mb = 2048
cores = 2

[[storage.disks]]
name = "root"
path = "images/root.qcow2"
format = "qcow2"
boot = true
```

### 5.2 Required Top-Level Keys

| Key                               | Type        | Required    | Description                                 |
| --------------------------------- | ----------- | ----------- | ------------------------------------------- |
| `schema_version`                  | integer     | Yes         | Schema version for validation and migration |
| `[vm]`                            | table       | Yes         | VM identity and QEMU binary selection       |
| `[hardware]`                      | table       | Yes         | Architecture, CPU, memory, acceleration     |
| `[[storage.disks]]` or `[kernel]` | array/table | Conditional | At least one boot source is required        |

### 5.3 Optional Top-Level Sections

| Section                  | Purpose                                     |
| ------------------------ | ------------------------------------------- |
| `[[storage.disks]]`      | Disk image attachments and host-path shares |
| `[[network.interfaces]]` | Network interface definitions               |
| `[serial]`               | Serial console configuration                |
| `[qmp]`                  | QMP socket settings                         |
| `[console]`              | TUI console behavior                        |
| `[kernel]`               | Direct kernel boot configuration            |

---

## 6. Section Specifications

### 6.1 `[vm]`

| Field         | Type   | Required | Default     | Validation                                         |
| ------------- | ------ | -------- | ----------- | -------------------------------------------------- |
| `name`        | string | Yes      | —           | `a-z`, `A-Z`, `0-9`, `_`, `-`; no spaces           |
| `description` | string | No       | `""`        | Free text, recommended max 200 characters          |
| `qemu_binary` | string | No       | auto-detect | Absolute path or executable resolvable from `PATH` |

Example:

```toml
[vm]
name = "kernel-dev"
description = "Kernel development VM"
qemu_binary = "/usr/bin/qemu-system-x86_64"
```

Rules:

- `vm.name` must be stable because it is used in logs, runtime paths, and plan metadata;
- `vm.name` must not contain path separators;
- `qemu_binary` must not contain shell syntax.

---

### 6.2 `[hardware]`

| Field          | Type    | Required | Default                                         | Validation                                |
| -------------- | ------- | -------- | ----------------------------------------------- | ----------------------------------------- |
| `arch`         | string  | Yes      | —                                               | `x86_64`, `aarch64`, `riscv64`, `ppc64le` |
| `cpu`          | string  | No       | `"host"` where valid, otherwise backend default | QEMU `-cpu` argument value                |
| `cores`        | integer | Yes      | —                                               | `1..256`                                  |
| `memory_mb`    | integer | Yes      | —                                               | `>= 256`; multiple of 256 recommended     |
| `acceleration` | string  | No       | `"auto"`                                        | `auto`, `kvm`, `hvf`, `whpx`, `tcg`       |

Example:

```toml
[hardware]
arch = "x86_64"
cpu = "host"
cores = 4
memory_mb = 8192
acceleration = "auto"
```

Acceleration selection for `acceleration = "auto"`:

```text
Linux:   kvm -> tcg
macOS:   hvf -> tcg
Windows: whpx -> tcg
FreeBSD: tcg in v1; bhyve later
```

Rules:

- selected acceleration must be visible in generated command plans;
- fallback from hardware acceleration to TCG must be reported;
- VMLab must never run QEMU as root to bypass acceleration permissions.

---

### 6.3 `[[storage.disks]]`

Each entry describes either a QEMU disk image or a host path share.

| Field      | Type    | Required    | Default | Validation                                       |
| ---------- | ------- | ----------- | ------- | ------------------------------------------------ |
| `name`     | string  | Yes         | —       | Unique within profile                            |
| `path`     | string  | Yes         | —       | Relative to project root or absolute             |
| `format`   | string  | Yes         | —       | `qcow2`, `raw`, `vdi`, `vmdk`, `host-path`       |
| `size_gb`  | integer | Conditional | —       | Required for planned creation of new image files |
| `boot`     | boolean | No          | `false` | At most one disk may be bootable                 |
| `readonly` | boolean | No          | `false` | Attach read-only when supported                  |

Example:

```toml
[[storage.disks]]
name = "root"
path = "images/kernel-dev-root.qcow2"
format = "qcow2"
size_gb = 40
boot = true
readonly = false

[[storage.disks]]
name = "source"
path = "../source-tree"
format = "host-path"
readonly = true
```

Rules:

- `format = "host-path"` is not a normal block disk;
- `host-path` maps to a host directory share mechanism such as 9p in v1 or virtiofs later;
- `host-path` must not be bootable;
- at most one disk may have `boot = true`;
- image creation is a mutating operation and must be represented as a `CommandPlan`;
- missing existing disk files produce diagnostics unless `size_gb` is present and creation is planned.

Path rules:

- relative paths are resolved against the project root;
- absolute paths are allowed but must be shown during plan preview;
- shell expansion is forbidden in path fields;
- `~`, `$HOME`, `$(...)`, and backticks are not expanded;
- symlink escape checks must be performed before mutating operations;
- `/proc`, `/sys`, and unsafe `/dev` paths are forbidden unless explicitly allowed by policy.

---

### 6.4 `[[network.interfaces]]`

| Field     | Type             | Required | Default   | Validation                      |
| --------- | ---------------- | -------- | --------- | ------------------------------- |
| `name`    | string           | Yes      | —         | Unique within profile           |
| `type`    | string           | Yes      | —         | `user`, `tap`, `bridge`, `none` |
| `hostfwd` | array of strings | No       | `[]`      | QEMU hostfwd format             |
| `mac`     | string           | No       | generated | Valid MAC format if provided    |

Example:

```toml
[[network.interfaces]]
name = "net0"
type = "user"
hostfwd = [
  "tcp:127.0.0.1:2222-:22",
  "tcp:127.0.0.1:8080-:80"
]
```

Semantics:

- `user`: SLIRP user-mode networking; default safe mode; no privilege required;
- `tap`: TAP networking; privileged setup may be required;
- `bridge`: bridge networking; privileged setup may be required;
- `none`: no network interface.

Rules:

- `tap` and `bridge` setup must generate command plans;
- VMLab must not silently create host network devices;
- privileged network setup must go through `PrivilegedActionService`;
- `hostfwd` must bind to explicit host addresses where possible, preferably `127.0.0.1` for local development.

---

### 6.5 `[serial]`

| Field     | Type    | Required | Default | Validation                          |
| --------- | ------- | -------- | ------- | ----------------------------------- |
| `enabled` | boolean | No       | `false` | —                                   |
| `mode`    | string  | No       | `"pty"` | `pty`, `file`, `socket`, `none`     |
| `device`  | string  | No       | auto    | PTY path, file path, or Unix socket |
| `logfile` | string  | No       | —       | Serial output log path              |

Example:

```toml
[serial]
enabled = true
mode = "pty"
logfile = "logs/kernel-dev-serial.log"
```

Semantics:

- `pty`: QEMU creates a PTY; ECLI may attach interactively;
- `file`: serial output is written to a file and can be followed;
- `socket`: Unix socket for external tools;
- `none`: serial disabled.

Rules:

- `console --follow` is read-only and safe for multiple sessions;
- `console --attach` requires a single-attacher lock;
- `logfile` parent directory must exist or be creatable through a plan;
- serial logs must be treated as runtime artifacts, not source-controlled files by default.

Development note:

During skeleton development, profile-defined log paths must not be used as write targets. They may be parsed and validated, but all actual development logs must be redirected to repository-level `logs/`.

---

### 6.6 `[qmp]`

| Field     | Type    | Required | Default                  | Validation       |
| --------- | ------- | -------- | ------------------------ | ---------------- |
| `enabled` | boolean | No       | `true` recommended       | —                |
| `socket`  | string  | No       | `run/<vm.name>.qmp.sock` | Unix socket path |

Example:

```toml
[qmp]
enabled = true
socket = "run/kernel-dev.qmp.sock"
```

Rules:

- if enabled, generated QEMU argv must include `-qmp unix:<socket>,server=on,wait=off`;
- relative socket paths are resolved against the project root;
- `run/` under project root is the preferred location;
- `/tmp` sockets are discouraged and should produce a warning unless policy allows them;
- QMP socket paths must not contain shell expansion;
- mutating QMP commands require a plan or equivalent confirmation path.

Development note:

During skeleton development, profile-defined log paths must not be used as write targets. They may be parsed and validated, but all actual development logs must be redirected to repository-level `logs/`.

---

### 6.7 `[console]`

| Field             | Type    | Required | Default    | Validation                   |
| ----------------- | ------- | -------- | ---------- | ---------------------------- |
| `auto_attach`     | boolean | No       | `false`    | —                            |
| `escape_sequence` | string  | No       | `"ctrl+]"` | Valid ECLI keybinding string |

Example:

```toml
[console]
auto_attach = false
escape_sequence = "ctrl+]"
```

Rules:

- `escape_sequence` must not conflict with core editor bindings;
- `auto_attach = true` must be visible in the start plan;
- console attach must restore terminal state on exit.

---

### 6.8 `[kernel]`

Optional direct kernel boot configuration.

| Field     | Type    | Required    | Default | Validation                          |
| --------- | ------- | ----------- | ------- | ----------------------------------- |
| `enabled` | boolean | No          | `false` | —                                   |
| `bzimage` | string  | Conditional | —       | Required when enabled               |
| `initrd`  | string  | No          | —       | Optional unless profile requires it |
| `append`  | string  | No          | `""`    | Kernel command line                 |

Example:

```toml
[kernel]
enabled = true
bzimage = "../linux-source/arch/x86/boot/bzImage"
initrd = "../linux-source/initrd.img"
append = "console=ttyS0 root=/dev/vda ro"
```

Rules:

- `bzimage` is required when `enabled = true`;
- `initrd` may be optional depending on the guest workflow;
- if no boot disk exists, `append` should specify a usable root device or initrd-only workflow;
- kernel paths follow normal path resolution rules;
- `append` must not contain secrets;
- unsafe kernel command-line choices should produce warnings and may require confirmation.

---

## 7. Validation Rules

### 7.1 Per-Section Validation

| Section                  | Key Checks                                                                |
| ------------------------ | ------------------------------------------------------------------------- |
| `[vm]`                   | valid name; `qemu_binary` resolvable or auto-detectable                   |
| `[hardware]`             | supported arch; memory and core bounds; valid acceleration                |
| `[[storage.disks]]`      | unique names; valid paths; valid formats; boot constraints                |
| `[[network.interfaces]]` | unique names; valid type; parseable hostfwd; valid MAC                    |
| `[serial]`               | valid mode; log path safe and creatable through plan                      |
| `[qmp]`                  | safe socket path; writable parent directory or plan-generatable directory |
| `[console]`              | valid keybinding; no core shortcut conflict                               |
| `[kernel]`               | required paths exist when enabled; command line is safe                   |

### 7.2 Cross-Section Validation

| Rule                                                                      | Rationale                                                          |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| At most one disk may have `boot = true`                                   | Avoid ambiguous boot ordering                                      |
| A boot source is required                                                 | VM must be bootable or intentionally non-bootable in a future mode |
| `host-path` must not be bootable                                          | It is a host share, not a block boot disk                          |
| If `[kernel]` is enabled, serial should be enabled or warning emitted     | Kernel workflows need console visibility                           |
| If hardware acceleration is requested, platform readiness must be checked | Avoid failed runtime start                                         |
| If `tap` or `bridge` is used, remediation may require privileged plan     | Avoid silent host network mutation                                 |
| Relative paths must resolve safely                                        | Prevent path traversal and unexpected host access                  |
| Secrets must not appear in any field                                      | Avoid credential leakage                                           |

### 7.3 Validation Output

Invalid profiles produce structured diagnostics, not stack traces.

Example:

```text
Error: profile 'kernel-dev' validation failed
  • [hardware.memory_mb]: value 128 is below minimum 256
  • [[storage.disks][0].path]: file 'images/root.qcow2' does not exist and size_gb is not specified
  • [qmp.socket]: path '/tmp/qmp.sock' is discouraged; use 'run/kernel-dev.qmp.sock'

Hint:
  Run 'ecli vm validate kernel-dev --json' for machine-readable diagnostics.
  Run 'ecli vm doctor kernel-dev --plan-fixes' to generate remediation plans where possible.
```

---

## 8. QEMU argv Generation Principles

Profiles are transformed into QEMU command arguments through deterministic rules.

### 8.1 Core Mapping

| Profile Field                   | QEMU Argument                                                                                               |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `hardware.acceleration = "kvm"` | `-enable-kvm`                                                                                               |
| `hardware.cpu`                  | `-cpu <value>`                                                                                              |
| `hardware.cores`                | `-smp <value>`                                                                                              |
| `hardware.memory_mb`            | `-m <value>M`                                                                                               |
| image disk                      | `-drive file=<path>,format=<format>,if=virtio`                                                              |
| `host-path` share               | `-fsdev local,path=<path>,security_model=none,id=<id>` + `-device virtio-9p-pci,fsdev=<id>,mount_tag=<tag>` |
| user network                    | `-netdev user,id=<name>[,hostfwd=...]` + `-device virtio-net-pci,netdev=<name>`                             |
| serial PTY                      | `-serial pty`                                                                                               |
| serial file                     | `-serial file:<logfile>`                                                                                    |
| QMP enabled                     | `-qmp unix:<socket>,server=on,wait=off`                                                                     |
| direct kernel boot              | `-kernel <bzimage>` + optional `-initrd <initrd>` + `-append <append>`                                      |
| VM name                         | `-name <vm.name>`                                                                                           |

### 8.2 argv Construction Rules

- `argv` is a list of strings;
- no shell parsing is required;
- paths are resolved before inclusion;
- variables are not expanded in `argv`;
- `display` may be shell-like, but `argv` is authoritative;
- secrets must not appear in `argv`;
- generated `argv` must be previewable in TUI/CLI;
- generated `argv` must be exportable for review;
- QEMU command generation must be deterministic for the same profile and environment.

Example generated `argv`:

```python
[
    "/usr/bin/qemu-system-x86_64",
    "-enable-kvm",
    "-cpu", "host",
    "-smp", "4",
    "-m", "8192M",
    "-drive", "file=/abs/project/images/root.qcow2,format=qcow2,if=virtio",
    "-fsdev", "local,path=/abs/source,security_model=none,id=source",
    "-device", "virtio-9p-pci,fsdev=source,mount_tag=source",
    "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22",
    "-device", "virtio-net-pci,netdev=net0",
    "-qmp", "unix:/abs/project/run/kernel-dev.qmp.sock,server=on,wait=off",
    "-serial", "pty",
    "-name", "kernel-dev"
]
```

### 8.3 Deterministic Argv Ordering

Generated QEMU `argv` must be deterministic.

Required ordering:

1. QEMU binary;
2. machine and acceleration flags;
3. CPU, SMP, and memory flags;
4. storage devices in profile-defined order;
5. host-path shares in profile-defined order;
6. network devices in profile-defined order;
7. QMP monitor arguments;
8. serial console arguments;
9. direct kernel boot arguments;
10. VM name as the final logical identity flag.

Identical profile + identical platform + identical resolver context must produce byte-identical `argv`.

This determinism is required for:

- reliable tests;
- reproducible dry-run output;
- stable `argv_hash`;
- audit traceability;
- plan diffing.

### 8.4 Dry-Run Guarantees

For:

```bash
ecli vm start kernel-dev --dry-run
```

VMLab guarantees:

- profile is parsed;
- profile is validated;
- QEMU `argv` is generated;
- selected acceleration is reported;
- read-only prerequisite checks may run;
- no QEMU process is spawned;
- no disk image is created;
- no file is modified;
- no network interface is configured;
- no QMP socket is opened;
- no privileged command is executed.

## 8.5 Hashing Specification

VMLab uses deterministic hashes for traceability, audit, and reproducibility.

### Profile Hash

`profile_hash` is represented as:

```text
sha256:<hex>
```

It is computed over the canonical profile representation.

Canonicalization rules:

- parse TOML into the typed profile model;
- normalize path separators;
- sort mapping keys;
- preserve array order where order is semantically meaningful;
- omit comments and formatting whitespace;
- serialize using deterministic UTF-8 encoding.

### Argv Hash

`argv_hash` is represented as:

```text
sha256:<hex>
```

It is computed over:

```text
"\x00".join(argv)
```

Rationale:

- null-separated argv prevents argument concatenation collisions;
- byte-identical argv produces byte-identical hash;
- identical profile + identical platform + identical resolver context must produce identical `argv_hash`.

Every `CommandPlan` generated from a profile must include:

```json
{
  "metadata": {
    "profile_hash": "sha256:...",
    "argv_hash": "sha256:...",
    "acceleration_resolved": "kvm"
  }
}
```

Rules:

- hashes must use full SHA-256 hex values;
- hashes must not be truncated in machine-readable metadata;
- UI may display shortened hashes for readability;
- profile hash and argv hash must be computed before plan export;
- audit records should store hashes, not full raw profile content.

---

## 9. Security and Safety Constraints

### 9.1 Forbidden Content in Profiles

Profiles must never contain:

| Forbidden                                            | Reason                                                                  |
| ---------------------------------------------------- | ----------------------------------------------------------------------- |
| API keys, tokens, passwords                          | Secrets belong in external secret stores or environment providers       |
| Shell expansions such as `$VAR`, `$(...)`, backticks | Prevent command injection                                               |
| `sudo`, `doas`, `pkexec` directives                  | Privilege belongs to `CommandPlanService` and `PrivilegedActionService` |
| Inline cloud credentials                             | Avoid accidental source control leakage                                 |
| Raw private keys                                     | Must never be in profile files                                          |

### 9.2 Sensitive Path Rules

Profiles must not reference unsafe host paths unless policy explicitly allows them.

Forbidden or restricted paths include:

- `/proc`;
- `/sys`;
- unsafe `/dev` devices;
- credential directories such as `.ssh`, `.gnupg`, `.aws`, `.config/gcloud`;
- removable media or network filesystems unless policy allows them.

Path safety rules:

- relative paths must be normalized before use;
- symlink escapes must be detected before mutating operations;
- absolute paths must be shown in plan preview;
- profile validation may warn about risky paths even if not immediately rejected.

### 9.3 Acceleration Safety

If `acceleration = "auto"` and hardware acceleration is unavailable, ECLI must:

1. fall back to `tcg`;
2. emit a diagnostic warning;
3. include the fallback decision in generated plan metadata;
4. avoid silent performance degradation.

VMLab must never run QEMU with `sudo` to bypass `/dev/kvm` permission problems.

Instead, VMLab must use `SystemDoctor` to propose a remediation `CommandPlan`.

### 9.4 Audit and Traceability

Profile-related audit events should include:

- profile name;
- profile path;
- profile hash;
- schema version;
- validation result;
- selected acceleration mode;
- generated argv summary with redaction;
- warnings and remediation plan IDs where applicable.

Audit records must not include raw secrets.

---

## 10. Example Profiles

### 10.1 Minimal Development VM

```toml
schema_version = 1

[vm]
name = "dev-vm"

[hardware]
arch = "x86_64"
cores = 2
memory_mb = 2048
acceleration = "auto"

[[storage.disks]]
name = "root"
path = "images/dev-root.qcow2"
format = "qcow2"
size_gb = 20
boot = true
```

### 10.2 Kernel Development with Serial Console

```toml
schema_version = 1

[vm]
name = "kernel-dev"
description = "Kernel development with serial console"

[hardware]
arch = "x86_64"
cpu = "host"
cores = 4
memory_mb = 8192
acceleration = "auto"

[[storage.disks]]
name = "root"
path = "images/kernel-root.qcow2"
format = "qcow2"
size_gb = 40
boot = true

[[storage.disks]]
name = "source"
path = "../linux-source"
format = "host-path"
readonly = true

[[network.interfaces]]
name = "net0"
type = "user"
hostfwd = [
  "tcp:127.0.0.1:2222-:22"
]

[serial]
enabled = true
mode = "pty"
logfile = "logs/kernel-serial.log"

[qmp]
enabled = true
socket = "run/kernel-dev.qmp.sock"

[console]
auto_attach = false
escape_sequence = "ctrl+]"
```

### 10.3 Direct Kernel Boot with Rootfs

```toml
schema_version = 1

[vm]
name = "initrd-test"

[hardware]
arch = "x86_64"
cores = 1
memory_mb = 1024
acceleration = "auto"

[[storage.disks]]
name = "rootfs"
path = "images/rootfs.ext4"
format = "raw"
readonly = true
boot = true

[kernel]
enabled = true
bzimage = "../linux-source/arch/x86/boot/bzImage"
initrd = "../linux-source/initrd.img"
append = "console=ttyS0 root=/dev/vda ro"

[serial]
enabled = true
mode = "file"
logfile = "logs/initrd-test.log"

[qmp]
enabled = true
socket = "run/initrd-test.qmp.sock"
```

### 10.4 TCG-Only Portable VM

```toml
schema_version = 1

[vm]
name = "portable-test"
description = "Portable VM profile that does not require hardware acceleration"

[hardware]
arch = "x86_64"
cpu = "qemu64"
cores = 2
memory_mb = 2048
acceleration = "tcg"

[[storage.disks]]
name = "root"
path = "images/portable-root.qcow2"
format = "qcow2"
size_gb = 20
boot = true

[serial]
enabled = true
mode = "file"
logfile = "logs/portable-test-serial.log"

[qmp]
enabled = true
socket = "run/portable-test.qmp.sock"
```

---

## 11. Relationship to CommandPlanService

Profiles are inputs to `CommandPlanService`, not execution triggers.

### 11.1 Plan Generation Flow

```mermaid
graph LR
    P[Profile TOML] --> V[Validate Profile]
    V --> G[Generate QEMU argv]
    G --> C[Create CommandPlan]
    C --> PE[PolicyEngine]
    PE --> UC[User Confirmation]
    UC --> EX[Executor / PrivilegedActionService]
    EX --> ALS[AuditLogService]
```

### 11.2 Plan Metadata from Profile

Every `CommandPlan` generated from a profile should include:

```json
{
  "metadata": {
    "profile_name": "kernel-dev",
    "profile_hash": "sha256:<full-profile-hash>",
    "argv_hash": "sha256:<full-argv-hash>",
    "schema_version": 1,
    "acceleration_requested": "auto",
    "acceleration_resolved": "kvm",
    "generated_argv_preview": "/usr/bin/qemu-system-x86_64 -enable-kvm ...",
    "validation_warnings": []
  }
}
```

### 11.3 Remediation Plans from Validation or Doctor Findings

Profile validation may produce findings.

`SystemDoctor` may turn supported findings into remediation plans.

Example remediation plan metadata:

```json
{
  "schema_version": 1,
  "plan_id": "plan-20260512T184100Z-kvmfix01",
  "title": "Enable KVM access for current user",
  "category": "system",
  "risk": "low",
  "requires_privilege": true,
  "confirmation_required": true,
  "requires_relogin": true,
  "commands": [
    {
      "step_id": "add-user-to-kvm-group",
      "title": "Add current user to kvm group",
      "argv": ["sudo", "usermod", "-aG", "kvm", "ssobol"],
      "display": "sudo usermod -aG kvm \"$USER\"",
      "requires_privilege": true,
      "destructive": false,
      "expected_exit_codes": [0]
    }
  ],
  "metadata": {
    "source_profile": "kernel-dev",
    "doctor_finding_id": "kvm-permission"
  }
}
```

This plan routes through:

```text
CommandPlanService -> PolicyEngine -> User Confirmation -> PrivilegedActionService -> AuditLogService
```

---

## 12. Future Extensions

These are exploratory and not part of schema v1:

| Feature                      | Description                                             | Status   |
| ---------------------------- | ------------------------------------------------------- | -------- |
| `[[storage.snapshots]]`      | Named snapshot definitions with retention policy        | Proposed |
| `[security.secrets]`         | References to external secret store, not inline secrets | Proposed |
| `[[devices]]`                | USB, PCI, GPU, virtio device attachment                 | Future   |
| `[orchestration.depends_on]` | Profile dependencies for multi-VM workflows             | Future   |
| `[backend]`                  | Backend adapter selection, e.g. qemu/libvirt/bhyve      | Future   |
| schema `2`                   | Explicit inheritance and merge semantics                | Future   |

Any future schema changes must preserve migration paths where possible.

---

## 13. Required Tests

Implementations of this schema must include tests for:

| Test Category           | Example Cases                                                      |
| ----------------------- | ------------------------------------------------------------------ |
| Profile discovery       | project vs user vs system precedence; conflict reporting           |
| TOML parsing            | valid examples parse; invalid tables fail clearly                  |
| Schema validation       | missing fields; invalid enums; out-of-range values                 |
| Path resolution         | relative vs absolute; forbidden paths; symlink escape checks       |
| Acceleration selection  | platform-specific `auto` behavior; fallback to TCG                 |
| argv generation         | deterministic QEMU arguments; no shell injection                   |
| Security constraints    | secrets, shell expansions, unsafe paths rejected or warned         |
| Dry-run                 | no process spawn; no file mutation; no network mutation            |
| Migration               | older schema normalization and explicit write plan                 |
| CommandPlan integration | generated plans contain profile metadata and selected acceleration |

Tests must use actual repository imports and must not assume module names that do not exist yet.

---

## 14. Relationship to Other Documents

This document implements the profile contract required by:

- [Product Vision](../architecture/product-vision.md)
- [Services Foundation](../architecture/services-foundation.md)
- [CommandPlanService](../architecture/command-plan-service.md)
- [VMLab Overview](./vmlab-overview.md)

Future documents that depend on this schema:

- `docs/extensions/vmlab-qmp-client.md`
- `docs/extensions/vmlab-runtime-supervisor.md`
- `docs/extensions/vmlab-console-and-logs.md`
- `docs/extensions/vmlab-security-model.md`

---

## Appendix A: TOML Syntax Reference

VMLab profiles use standard TOML v1.0.

```toml
schema_version = 1

[vm]
name = "my-vm"
description = "A local VM profile"

[hardware]
cores = 4
memory_mb = 8192
acceleration = "auto"

[[storage.disks]]
name = "root"
path = "images/root.qcow2"
format = "qcow2"
boot = true
readonly = false

[[network.interfaces]]
name = "net0"
type = "user"
hostfwd = [
  "tcp:127.0.0.1:2222-:22",
  "tcp:127.0.0.1:8080-:80"
]
```

Common pitfalls:

- use `[[array_of_tables]]` with double brackets for repeated sections;
- strings require quotes;
- booleans are lowercase: `true` / `false`;
- integers are not quoted;
- single `[storage.disks]` is a table, not an array element.

---

## Appendix B: Validation Error Format

```json
{
  "profile_name": "kernel-dev",
  "schema_version": 1,
  "errors": [
    {
      "field": "[hardware.memory_mb]",
      "message": "value 128 is below minimum 256",
      "suggestion": "Set memory_mb to at least 256"
    },
    {
      "field": "[[storage.disks][0].path]",
      "message": "file 'images/root.qcow2' does not exist and size_gb is not specified",
      "suggestion": "Specify size_gb to create the image, or ensure the file exists"
    }
  ],
  "warnings": [
    {
      "field": "[qmp.socket]",
      "message": "socket path is in /tmp; project-local run/ is preferred",
      "suggestion": "Use run/kernel-dev.qmp.sock instead"
    }
  ]
}
```

This format is used by:

```text
ecli vm validate --json
SystemDoctor
CommandPlanService metadata
```

---

## Approval

- **Status:** Approved as VMLab Profile Schema Strategic Architecture Direction after review corrections
- **Approved by:** Siergej Sobolewski
- **Date:** 2026-05-12
- **Next step:** Prepare `docs/extensions/vmlab-qmp-client.md`
