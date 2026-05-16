# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/cli.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Minimal read-only CLI surface for Phase 1 services."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from ecli.services.models.doctor import DoctorContext, DoctorFinding
from ecli.services.models.plan import CommandPlan
from ecli.services.registry import ServiceRegistry


SERVICE_CLI_FLAGS = frozenset({"--services", "--doctor", "--plan-preview"})

SERVICE_STATUS_NAMES: tuple[tuple[str, str], ...] = (
    ("ConfigService", "config_service"),
    ("ProjectService", "project_service"),
    ("CommandPlanService", "command_plan_service"),
    ("BuiltInPolicyEngine", "policy_engine"),
    ("AuditLogService", "audit_log_service"),
    ("PrivilegedActionService", "privileged_action_service"),
    ("SystemDoctor", "system_doctor"),
)


def is_service_cli(argv: list[str]) -> bool:
    """Return true when argv selects an explicit Phase 1 service CLI command."""
    return any(argument in SERVICE_CLI_FLAGS for argument in argv)


def run_service_cli(
    argv: list[str],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the minimal service CLI and return a process-style status code."""
    out = _TextIOProxy(stdout, sys.stdout)
    err = _TextIOProxy(stderr, sys.stderr)
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return _run_service_command(args, out)
    except ValueError as exc:
        err.write(f"Error: {exc}\n")
        return 2
    except Exception as exc:
        err.write(f"ECLI service CLI error: {exc}\n")
        return 1

    parser.print_help(file=err.file)
    return 2


def _run_service_command(args: argparse.Namespace, stdout: _TextIOProxy) -> int:
    registry = _create_registry(args)
    if args.services:
        payload = _service_status_payload(registry)
        _write_output(stdout, payload, _format_service_status(payload), args.as_json)
        return 0
    if args.doctor:
        findings = _detect_findings(registry, args)
        payload = {
            "findings": [finding.as_dict() for finding in findings],
            "count": len(findings),
        }
        _write_output(stdout, payload, _format_doctor_findings(findings), args.as_json)
        return 0
    if args.plan_preview:
        findings = _detect_findings(registry, args)
        plan = _first_preview_plan(registry, findings, args.finding_id)
        return _write_plan_preview(stdout, registry, plan, args.as_json)
    return 2


def _write_plan_preview(
    stdout: _TextIOProxy,
    registry: ServiceRegistry,
    plan: CommandPlan | None,
    as_json: bool,
) -> int:
    if plan is None:
        message = "No eligible SystemDoctor finding has a command plan preview."
        if as_json:
            stdout.write(_json_dumps({"plan": None, "message": message}) + "\n")
        else:
            stdout.write(message + "\n")
        return 2
    if as_json:
        stdout.write(registry.command_plan_service.export_json(plan) + "\n")
    else:
        stdout.write(registry.command_plan_service.export_markdown(plan))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecli",
        description="Read-only Phase 1 service inspection commands.",
    )
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument(
        "--services",
        action="store_true",
        help="Print ServiceRegistry service status.",
    )
    command_group.add_argument(
        "--doctor",
        action="store_true",
        help="Run read-only SystemDoctor diagnostics.",
    )
    command_group.add_argument(
        "--plan-preview",
        action="store_true",
        help="Print a draft CommandPlan preview from an eligible doctor finding.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Print deterministic JSON.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root or start path for discovery.",
    )
    parser.add_argument(
        "--logs-root",
        type=Path,
        default=_repo_logs_root(),
        help="Repository logs root used by read-only service diagnostics.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="SystemDoctor category to include. May be repeated.",
    )
    parser.add_argument(
        "--finding-id",
        help="Specific SystemDoctor finding ID to use for plan preview.",
    )
    return parser


def _create_registry(args: argparse.Namespace) -> ServiceRegistry:
    logs_root = Path(args.logs_root).resolve(strict=False)
    _assert_under_repo_logs(logs_root)
    return ServiceRegistry.create(
        project_root=Path(args.project_root),
        logs_root=logs_root,
        env={},
    )


def _detect_findings(
    registry: ServiceRegistry,
    args: argparse.Namespace,
) -> list[DoctorFinding]:
    context = DoctorContext(
        project_root=registry.project_service.root,
        categories=tuple(args.category),
        dry_run=True,
    )
    findings = registry.system_doctor.detect_problems(context)
    return sorted(findings, key=lambda finding: finding.finding_id)


def _first_preview_plan(
    registry: ServiceRegistry,
    findings: list[DoctorFinding],
    finding_id: str | None,
) -> CommandPlan | None:
    for finding in findings:
        if finding_id is not None and finding.finding_id != finding_id:
            continue
        if not finding.remediation_available:
            continue
        return registry.command_plan_service.create_plan_from_doctor_finding(
            finding,
            actor="ecli-cli",
        )
    return None


def _service_status_payload(registry: ServiceRegistry) -> dict[str, Any]:
    services = []
    for label, attribute in SERVICE_STATUS_NAMES:
        service = getattr(registry, attribute, None)
        services.append(
            {
                "name": label,
                "available": service is not None,
                "implementation": None
                if service is None
                else service.__class__.__name__,
            }
        )
    diagnostics = []
    if registry.config_result is not None:
        diagnostics = [
            diagnostic.as_dict()
            for diagnostic in getattr(registry.config_result, "diagnostics", ())
        ]
    return {
        "services": services,
        "config_diagnostics": diagnostics,
        "project_root": str(registry.project_service.root),
    }


def _format_service_status(payload: dict[str, Any]) -> str:
    lines = [
        "ECLI Phase 1 service status",
        f"Project root: {payload['project_root']}",
        "",
    ]
    for service in payload["services"]:
        status = "available" if service["available"] else "unavailable"
        implementation = service["implementation"] or "none"
        lines.append(f"{service['name']}: {status} ({implementation})")
    diagnostics = payload["config_diagnostics"]
    lines.extend(["", f"Config diagnostics: {len(diagnostics)}"])
    return "\n".join(lines) + "\n"


def _format_doctor_findings(findings: list[DoctorFinding]) -> str:
    lines = ["SystemDoctor read-only findings"]
    if not findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"
    for finding in findings:
        remediation = "yes" if finding.remediation_available else "no"
        lines.append(
            f"{finding.finding_id}: {finding.severity.value} "
            f"{finding.category} remediation={remediation} - {finding.title}"
        )
    return "\n".join(lines) + "\n"


def _write_output(
    stdout: _TextIOProxy,
    payload: dict[str, Any],
    human_text: str,
    as_json: bool,
) -> None:
    if as_json:
        stdout.write(_json_dumps(payload) + "\n")
    else:
        stdout.write(human_text)


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_logs_root() -> Path:
    return (_repo_root() / "logs").resolve(strict=False)


def _assert_under_repo_logs(path: Path) -> None:
    logs_root = _repo_logs_root()
    if not path.resolve(strict=False).is_relative_to(logs_root):
        raise ValueError("logs root must stay under repository-level logs/")


class _TextIOProxy:
    """Small wrapper around optional text streams."""

    def __init__(self, file: TextIO | None, default: TextIO) -> None:
        """Use the supplied stream or resolve the current standard stream lazily."""
        self.file = default if file is None else file

    def write(self, value: str) -> None:
        """Write text to the wrapped stream."""
        self.file.write(value)
