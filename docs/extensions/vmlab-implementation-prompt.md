<!--
SPDX-License-Identifier: Apache-2.0

Project: ECLI
File: docs/extensions/vmlab-implementation-prompt.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
Author: Siergej Sobolewski
License: Apache License, Version 2.0

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->

# VMLab Implementation Prompt

**Phase 1/2 Skeleton Implementation Brief**

**Version:** 1.0
**Date:** 2026-05-15
**Status:** Implementation Directive
**Part of:**
[Product Vision](../architecture/product-vision.md) |
[Services Foundation](../architecture/services-foundation.md) |
[CommandPlanService](../architecture/command-plan-service.md) |
[VMLab Overview](./vmlab-overview.md) |
[VMLab Profile Schema](./vmlab-profile-schema.md) |
[QMP Client Contract](./vmlab-qmp-client.md) |
[VMSupervisor Contract](./vmlab-runtime-supervisor.md) |
[Console and Logs Contract](./vmlab-console-and-logs.md) |
[VMLab Security Model](./vmlab-security-model.md)

---

## 1. Purpose

This document is an implementation directive for building the VMLab skeleton for ECLI.

Critical scope limitation:

```text
This is not a full VMLab implementation.

This is a minimal, safe, testable skeleton that validates architecture contracts.
```

The goal is to prove that:

* VMLab integrates cleanly with `CommandPlanService`;
* profile discovery and validation work end-to-end;
* dry-run QEMU argv generation is deterministic and safe;
* no real runtime mutation occurs;
* no real QEMU process is spawned;
* no privileged remediation is executed;
* no mutating QMP command is sent;
* all development logs and evidence are written only under `logs/`;
* security guardrails are enforced by tests.

---

## 2. Non-Negotiable Development Log Rule

All development logs must be written only under the repository-level `logs/` directory.

This applies to:

* agent execution logs;
* test logs;
* debug logs;
* dry-run reports;
* generated QEMU argv previews;
* fake/simulated runtime logs;
* doctor diagnostics;
* smoke outputs;
* coverage artifacts if configured by this task;
* any VMLab skeleton evidence.

Allowed development log root:

```text
logs/
```

Recommended VMLab development layout:

```text
logs/
└── vmlab/
    ├── argv/
    ├── console/
    ├── doctor/
    ├── dry-run/
    ├── qmp/
    ├── runtime/
    ├── smoke/
    └── tests/
```

Forbidden development log locations:

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

Rules:

* do not write logs to `.ecli/vmlab/run/` during skeleton development;
* do not write logs to `/tmp`;
* do not write logs next to source files;
* do not write logs into test directories;
* do not write hidden runtime artifacts outside `logs/`;
* tests must verify that skeleton code does not create logs outside `logs/`;
* dry-run must not create log files at all unless explicitly testing log report generation under `logs/`.

The conceptual production paths described in architecture contracts are future runtime layout examples. For this skeleton and all development work, `logs/` is mandatory.

---

## 3. Scope: What to Implement

### 3.1 Files to Create

```text
src/ecli/extensions/vmlab/
├── __init__.py
├── models.py             # Typed models: VMProfile, validation results, state enums
├── profiles.py           # Profile discovery + validation
├── argv_generator.py     # QEMU argv generation, dry-run only
├── service.py            # VMLabService skeleton
├── doctor.py             # VMLab-specific read-only diagnostics stub
└── log_paths.py          # Development log path helpers; must force logs/ root

tests/extensions/vmlab/
├── test_profiles.py
├── test_argv_generator.py
├── test_service_integration.py
├── test_security_guardrails.py
├── test_dry_run_guarantee.py
└── test_log_location_invariant.py
```

Optional shared model file only if it matches existing repo architecture:

```text
src/ecli/services/models/vmlab.py
```

Do not create this optional shared file unless it is actually needed and consistent with existing imports.

---

## 4. Core Contracts to Implement

### 4.1 Development Log Path Helper

Create a small helper that centralizes all development log paths.

```python
# src/ecli/extensions/vmlab/log_paths.py

from pathlib import Path


def get_vmlab_logs_root(repo_root: Path) -> Path:
    """
    Return the only allowed development log root for VMLab.

    All development logs, dry-run reports, simulated runtime artifacts,
    and test evidence must live under repo_root / "logs" / "vmlab".

    This helper must not create directories unless the caller explicitly
    requests a write operation that is allowed by the current mode.
    """
    return repo_root / "logs" / "vmlab"


def ensure_under_logs(path: Path, repo_root: Path) -> Path:
    """
    Validate that path is under repository-level logs/.

    Raises ValueError if the path escapes logs/.
    """
    logs_root = (repo_root / "logs").resolve()
    resolved = path.resolve(strict=False)

    if resolved != logs_root and logs_root not in resolved.parents:
        raise ValueError(f"Development log path must stay under logs/: {path}")

    return resolved
```

Rules:

* all generated test/debug/dry-run log paths must use this helper;
* no component may construct arbitrary log paths independently;
* any path outside `logs/` must fail validation.

---

### 4.2 Profile Discovery

```python
# Conceptual contract — implement with actual repo imports.

from pathlib import Path
from typing import Protocol


class VMProfileDiscovery(Protocol):
    """Discover and load VMLab profiles from configured scopes."""

    def discover_profiles(
        self,
        project_root: Path | None = None,
        include_user: bool = True,
        include_system: bool = False,
    ) -> list["VMProfile"]:
        """
        Return profiles in precedence order:

        1. project-local: .ecli/vmlab/profiles/
        2. user-global: ~/.config/ecli/vmlab/profiles/
        3. system-wide: /etc/ecli/vmlab/profiles/ if enabled

        Conflicts with the same profile name are reported, not silently merged.

        This method must not create files, directories, logs, sockets, or runtime state.
        """
        ...
```

---

### 4.3 Profile Validation

```python
class VMProfileValidator(Protocol):
    """Validate VMProfile against schema and security rules."""

    def validate(
        self,
        profile: "VMProfile",
        project_root: Path,
        policy_context: "PolicyContext",
    ) -> "ValidationResult":
        """
        Validate:

        - schema_version is supported;
        - required fields are present;
        - path-like fields resolve safely;
        - symlink escapes are rejected;
        - shell expansion is rejected in path-like fields;
        - forbidden paths are rejected;
        - acceleration selection is policy-compliant;
        - secret-like values trigger warnings or errors per policy;
        - development log targets are forced under logs/.

        This method must not mutate filesystem state.
        This method must not create logs.
        This method must not spawn processes.
        """
        ...
```

---

### 4.4 Dry-Run QEMU argv Generation

```python
class QEMUArgvGenerator(Protocol):
    """Generate QEMU argv from validated profile — dry-run only in skeleton."""

    def generate_argv(
        self,
        profile: "VMProfile",
        project_root: Path,
        dry_run: bool = True,
    ) -> list[str]:
        """
        Generate QEMU argv list from profile.

        Rules:

        - argv is list[str], no shell parsing;
        - path-like args are resolved to absolute paths;
        - secrets in argv are rejected or redacted;
        - acceleration mode is visible in argv;
        - QMP/serial options are included if configured;
        - skeleton must not execute the generated argv.

        If dry_run=True:

        - do not validate by creating files;
        - do not create directories;
        - do not create runtime logs;
        - do not create QMP sockets;
        - do not open serial devices;
        - do not spawn QEMU.

        Returns argv list for CommandPlan embedding.
        """
        ...
```

---

### 4.5 VMLabService Skeleton

```python
class VMLabService(Protocol):
    """VMLab entry point integrating with CommandPlanService."""

    def list_profiles(self, project_root: Path | None = None) -> list["VMProfile"]:
        """Return discovered profiles for TUI/CLI listing."""
        ...

    def get_profile(self, name: str, project_root: Path | None = None) -> "VMProfile":
        """Load a specific profile by name."""
        ...

    def validate_profile(self, profile: "VMProfile") -> "ValidationResult":
        """Validate profile and return structured result."""
        ...

    def generate_start_plan(
        self,
        profile: "VMProfile",
        dry_run: bool = True,
    ) -> "CommandPlan":
        """
        Generate a CommandPlan for starting a VM.

        Preconditions:

        - profile is validated;
        - argv is generated via QEMUArgvGenerator;
        - dry_run defaults to True in skeleton.

        Plan metadata must include:

        - profile_name;
        - profile_hash;
        - argv_hash;
        - acceleration_selected;
        - qmp_socket_path if configured;
        - serial_config summary;
        - development_log_root = logs/vmlab.

        If dry_run=True:

        - plan status remains DRAFT or VALIDATED;
        - no execution handoff occurs;
        - no process is spawned;
        - no files or directories are created;
        - no logs are written outside logs/.
        """
        ...

    def diagnose_runtime(self, profile: "VMProfile") -> list["DoctorFinding"]:
        """
        Generate VMLab-specific diagnostics via SystemDoctor.

        Checks are read-only:

        - QEMU binary availability;
        - KVM/HVF/WHPX readiness;
        - disk path existence;
        - QMP socket path policy;
        - serial/log path policy;
        - development log location invariant.

        Returns findings only.
        Does not apply fixes.
        Does not create logs outside logs/.
        """
        ...
```

---

## 5. Minimal CLI Surface

Wire only the minimal skeleton commands:

```bash
ecli vm list
ecli vm show <profile-name>
ecli vm validate <profile-name>
ecli vm start <profile-name> --dry-run
ecli vm export <profile-name> --format qemu-argv
ecli vm doctor <profile-name>
ecli vm doctor <profile-name> --json
```

CLI rules:

* use `ServiceRegistry` or existing service wiring;
* do not instantiate low-level VMLab classes directly in UI code;
* never call QEMU;
* never call sudo;
* never send QMP commands;
* never open serial devices;
* print structured diagnostics;
* no stack traces in normal user-facing output;
* if CLI writes diagnostics/logs during development, they must go under `logs/`.

---

## 6. Scope: What Not to Implement

Explicitly forbidden in this skeleton:

| Feature                      | Reason                                              |
| ---------------------------- | --------------------------------------------------- |
| Real QEMU process execution  | Requires full `VMSupervisor` and execution policy   |
| Real privileged remediation  | Requires production-ready `PrivilegedActionService` |
| Mutating QMP commands        | Requires authorized `QMPClient` flow                |
| Interactive serial attach    | Requires terminal state manager and attach locks    |
| Runtime log rotation         | Requires `RuntimeLogService` production behavior    |
| Runtime log cleanup          | Filesystem mutation; not part of skeleton           |
| GUI Desktop integration      | Future thin client                                  |
| Plugin API for VMLab         | Future stabilized API                               |
| Cloud/remote QEMU workflows  | Out of scope                                        |
| Multi-VM orchestration       | Out of scope                                        |
| Writing logs outside `logs/` | Forbidden during development                        |

Rule:

```text
If a feature mutates host state, guest state, filesystem state, process state,
network state, or writes logs outside logs/, it is out of scope.
```

---

## 7. Security Guardrails

### 7.1 Trust Boundaries

```text
- Profile TOML is untrusted input.
- Guest output, QMP events, serial logs, AI responses are untrusted.
- Plugins cannot bypass service boundaries.
- User config cannot weaken stricter system/project policy.
```

### 7.2 Path Safety

```text
- Only path-like fields are path-validated.
- Do not treat every argv element as a filesystem path.
- Symlink escape detection is required for path-like fields.
- Forbidden paths are rejected by policy.
- Development log paths must stay under repository-level logs/.
```

### 7.3 Redaction Failure

```text
- If redaction cannot be applied, abort audit/export/AI operation.
- Never write unredacted sensitive data to audit records.
- Never send unredacted content to external AI providers.
```

### 7.4 Dry-Run Guarantee

```text
dry_run=True must never:

- spawn processes;
- create files;
- create directories;
- open devices for write;
- open sockets;
- mutate filesystem state;
- mutate process state;
- send QMP commands;
- call sudo/doas/pkexec;
- write logs outside logs/.
```

### 7.5 No Automatic Telemetry

```text
- No anonymous usage stats.
- No automatic crash uploads.
- No automatic remote diagnostics.
- No telemetry by default.
- Any future telemetry must be explicit opt-in.
```

### 7.6 Privilege Escalation Boundary

```text
- VMLab code must never call sudo directly.
- VMLab code must never call doas directly.
- VMLab code must never call pkexec directly.
- All privileged operations route through PrivilegedActionService.
- In skeleton, privileged operations fail closed with clear diagnostics.
```

---

## 8. Test Requirements

Tests must use actual repository imports and verify safety boundaries.

### 8.1 Unit Tests

| Module              | Test Cases                                                               |
| ------------------- | ------------------------------------------------------------------------ |
| `models.py`         | typed model creation, validation defaults, profile hash, argv hash       |
| `profiles.py`       | discovery precedence, conflict reporting, schema validation, path safety |
| `argv_generator.py` | deterministic argv, acceleration flags, QMP/serial args, no shell syntax |
| `service.py`        | profile loading, plan generation, dry-run behavior                       |
| `doctor.py`         | read-only diagnostics, no fixes applied                                  |
| `log_paths.py`      | all development log paths forced under `logs/`                           |

### 8.2 Integration Tests

| Test                             | Purpose                                         |
| -------------------------------- | ----------------------------------------------- |
| `test_service_integration.py`    | VMLabService integrates with CommandPlanService |
| `test_cli_surface.py`            | CLI routes through service layer                |
| `test_dry_run_guarantee.py`      | dry-run creates no files, sockets, processes    |
| `test_log_location_invariant.py` | no log path outside `logs/` is accepted         |

### 8.3 Security Guardrail Tests

| Test                           | Purpose                                                    |
| ------------------------------ | ---------------------------------------------------------- |
| `test_path_safety.py`          | symlink escape blocked, forbidden paths rejected           |
| `test_redaction_failure.py`    | redaction failure aborts export/AI/audit                   |
| `test_privilege_boundary.py`   | direct sudo/doas/pkexec calls forbidden                    |
| `test_config_precedence.py`    | user config cannot weaken policy                           |
| `test_untrusted_input.py`      | shell expansion, secret-like values, unsafe paths rejected |
| `test_no_logs_outside_logs.py` | skeleton does not create or accept logs outside `logs/`    |

### 8.4 Required Test Commands

```bash
pytest tests/extensions/vmlab/ -v
pytest tests/extensions/vmlab/test_dry_run_guarantee.py -v
pytest tests/extensions/vmlab/test_log_location_invariant.py -v
pytest tests/extensions/vmlab/ --cov=src/ecli/extensions/vmlab --cov-report=term-missing
```

---

## 9. Acceptance Criteria

This skeleton is acceptable only when all criteria are met.

| Criterion                                   | Verification Method                   |
| ------------------------------------------- | ------------------------------------- |
| No real QEMU execution                      | code review + tests                   |
| No direct privileged execution              | grep/code review for sudo/doas/pkexec |
| No mutating QMP commands                    | tests and code review                 |
| No interactive serial attach                | tests and code review                 |
| Profile validation rejects unsafe input     | unit tests                            |
| Path safety validates only path-like fields | targeted tests                        |
| Dry-run never mutates state                 | integration tests                     |
| Logs are written only under `logs/` | `test_log_location_invariant.py` plus `scripts/check-log-invariant.sh` when available |
| No `.ecli/` runtime logs in development     | filesystem assertions                 |
| No `/tmp` logs                              | filesystem assertions                 |
| User config cannot weaken policy            | config precedence tests               |
| All tests pass with actual repo imports     | pytest                                |
| No new dependencies added                   | dependency audit                      |
| Documentation references updated            | docs review                           |

---

## 10. Implementation Checklist

```text
[ ] Create src/ecli/extensions/vmlab/ package structure
[ ] Implement log_paths.py with logs/ invariant
[ ] Implement VMProfile typed model
[ ] Implement profile discovery with precedence rules
[ ] Implement profile validation with security rules
[ ] Implement QEMUArgvGenerator with dry_run=True default
[ ] Implement VMLabService skeleton
[ ] Implement VMLabDoctor read-only diagnostics stub
[ ] Wire minimal CLI surface
[ ] Add unit tests
[ ] Add integration tests
[ ] Add security guardrail tests
[ ] Add log location invariant tests
[ ] Verify dry-run creates no files/directories/sockets/processes
[ ] Verify no logs outside logs/
[ ] Run ruff check and ruff format on new files
[ ] Run mypy or pyright if already configured in repo
[ ] Verify no new dependencies added
[ ] Update inline docstrings
[ ] Run scripts/check-log-invariant.sh if present
```

---

## 11. Next Steps After Skeleton

After this skeleton is approved:

1. Phase 2A — VMSupervisor skeleton with metadata model, still dry-run/no process spawn.
2. Phase 2B — QMPClient read-only query support, no mutating commands.
3. Phase 2C — Console follow mode, read-only only.
4. Phase 3 — Real QEMU execution via approved `CommandPlan`.
5. Phase 3+ — Interactive attach, authorized mutating QMP, log export, AI integration.

Each phase requires:

* security review;
* updated tests;
* documentation updates;
* explicit approval before merge.

---

## 12. Relationship to Other Documents

This implementation prompt is derived from:

* [Product Vision](../architecture/product-vision.md)
* [Services Foundation](../architecture/services-foundation.md)
* [CommandPlanService](../architecture/command-plan-service.md)
* [VMLab Overview](./vmlab-overview.md)
* [VMLab Profile Schema](./vmlab-profile-schema.md)
* [QMP Client Contract](./vmlab-qmp-client.md)
* [VMSupervisor Contract](./vmlab-runtime-supervisor.md)
* [Console and Logs Contract](./vmlab-console-and-logs.md)
* [VMLab Security Model](./vmlab-security-model.md)

---

## Appendix A: Example Profile Validation Test

```python
# tests/extensions/vmlab/test_profiles.py

from pathlib import Path


def test_profile_rejects_shell_expansion(tmp_path: Path) -> None:
    """Profile with shell expansion in a path-like field must fail validation."""
    profile = VMProfile(
        schema_version=1,
        vm=VMConfig(name="unsafe", qemu_binary="/usr/bin/qemu-system-x86_64"),
        hardware=HardwareConfig(arch="x86_64", cores=2, memory_mb=2048),
        storage=StorageConfig(
            disks=[
                DiskConfig(
                    name="root",
                    path="$(echo /etc)/malicious.qcow2",
                    format="qcow2",
                    boot=True,
                )
            ]
        ),
    )

    validator = VMProfileValidatorImpl()
    result = validator.validate(
        profile=profile,
        project_root=tmp_path,
        policy_context=mock_policy_context(),
    )

    assert not result.is_valid
    assert any("shell expansion" in error.message.lower() for error in result.errors)
```

---

## Appendix B: Example Dry-Run Guarantee Test

```python
# tests/extensions/vmlab/test_dry_run_guarantee.py

from pathlib import Path


def test_generate_start_plan_dry_run_creates_no_files(tmp_path: Path) -> None:
    """Dry-run plan generation must not create files or directories."""
    profile = valid_test_profile(project_root=tmp_path)
    service = create_test_vmlab_service(project_root=tmp_path)

    before_files = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    plan = service.generate_start_plan(profile, dry_run=True)

    after_files = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert after_files == before_files
    assert plan.status in (PlanStatus.DRAFT, PlanStatus.VALIDATED)
```

---

## Appendix C: Example Log Location Invariant Test

```python
# tests/extensions/vmlab/test_log_location_invariant.py

from pathlib import Path

import pytest


def test_development_log_path_must_be_under_logs(tmp_path: Path) -> None:
    """VMLab development log paths must stay under repository-level logs/."""
    repo_root = tmp_path
    valid_path = repo_root / "logs" / "vmlab" / "dry-run" / "plan.json"
    invalid_path = repo_root / ".ecli" / "vmlab" / "run" / "plan.log"

    assert ensure_under_logs(valid_path, repo_root) == valid_path.resolve(strict=False)

    with pytest.raises(ValueError, match="logs"):
        ensure_under_logs(invalid_path, repo_root)


def test_tmp_log_path_is_rejected(tmp_path: Path) -> None:
    """VMLab development logs must not be written to /tmp."""
    repo_root = tmp_path
    outside_path = Path("/tmp/ecli-vmlab-test.log")

    with pytest.raises(ValueError, match="logs"):
        ensure_under_logs(outside_path, repo_root)
```

---

## Appendix D: Example Security Guardrail Test

```python
# tests/extensions/vmlab/test_security_guardrails.py

from pathlib import Path


FORBIDDEN_TOKENS = (
    "sudo",
    "doas",
    "pkexec",
    "qemu-system-",
    "subprocess.Popen",
    "subprocess.run",
)


def test_vmlab_skeleton_does_not_directly_execute_forbidden_commands() -> None:
    """
    VMLab skeleton must not directly execute QEMU or privileged commands.

    Real execution belongs to later phases and must be mediated through
    CommandPlanService and PrivilegedActionService.
    """
    root = Path("src/ecli/extensions/vmlab")

    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")

        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"Forbidden token {token!r} found in {path}"
```

---

## Approval

* **Status:** Approved as VMLab Skeleton Implementation Directive after review corrections
* **Approved by:** Siergej Sobolewski
* **Date:** 2026-05-12
* **Next step:** Implement skeleton per this directive; submit PR for architecture review before merge
