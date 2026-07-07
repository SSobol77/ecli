# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/cli/test_phase1_service_cli.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the minimal Phase 1 service CLI surface."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Iterator

import pytest

from ecli.cli import is_service_cli, run_service_cli


SERVICE_NAMES = (
    "ConfigService",
    "ProjectService",
    "CommandPlanService",
    "BuiltInPolicyEngine",
    "AuditLogService",
    "PrivilegedActionService",
    "SystemDoctor",
)


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-phase1-service-cli"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    (test_root / "pyproject.toml").write_text(
        "[project]\nname = 'cli-test'\n",
        encoding="utf-8",
    )
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def snapshot_tree(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()

    status = run_service_cli(args, stdout=stdout, stderr=stderr)

    return status, stdout.getvalue(), stderr.getvalue()


def test_default_editor_launch_arguments_are_not_service_cli() -> None:
    assert is_service_cli([]) is False
    assert is_service_cli(["pyproject.toml"]) is False
    assert is_service_cli(["logs/service"]) is False


def test_service_status_command_reports_phase_one_services(workspace: Path) -> None:
    status, output, error = run_cli(
        [
            "--services",
            "--project-root",
            str(workspace),
            "--logs-root",
            str(workspace / "logs-root"),
        ]
    )

    assert status == 0
    assert error == ""
    assert "ECLI Phase 1 service status" in output
    for service_name in SERVICE_NAMES:
        assert service_name in output
        assert "available" in output


def test_service_status_command_supports_deterministic_json(workspace: Path) -> None:
    status, output, error = run_cli(
        [
            "--services",
            "--json",
            "--project-root",
            str(workspace),
            "--logs-root",
            str(workspace / "logs-root"),
        ]
    )

    assert status == 0
    assert error == ""
    payload = json.loads(output)
    assert [service["name"] for service in payload["services"]] == list(SERVICE_NAMES)
    assert all(service["available"] for service in payload["services"])
    assert payload["project_root"] == str(workspace.resolve(strict=False))


def test_doctor_command_returns_structured_findings_without_mutation(
    workspace: Path,
) -> None:
    project = workspace / "project"
    project.mkdir()
    missing_logs = workspace / "missing-logs"
    before = snapshot_tree(workspace)

    status, output, error = run_cli(
        [
            "--doctor",
            "--project-root",
            str(project),
            "--logs-root",
            str(missing_logs),
            "--category",
            "config",
        ]
    )

    assert status == 0
    assert error == ""
    assert "SystemDoctor read-only findings" in output
    assert "DOCTOR-CONFIG-001" in output
    assert "remediation=yes" in output
    assert not missing_logs.exists()
    assert snapshot_tree(workspace) == before


def test_plan_preview_command_returns_draft_preview_json(workspace: Path) -> None:
    project = workspace / "project"
    project.mkdir()

    status, output, error = run_cli(
        [
            "--plan-preview",
            "--json",
            "--project-root",
            str(project),
            "--logs-root",
            str(workspace / "missing-logs"),
            "--category",
            "config",
        ]
    )

    assert status == 0
    assert error == ""
    payload = json.loads(output)
    assert payload["status"] == "DRAFT"
    assert payload["source"] == "DOCTOR"
    assert payload["metadata"]["doctor_finding_id"] == "DOCTOR-CONFIG-001"
    assert payload["commands"][0]["argv"][:2] == ["mkdir", "-p"]
    assert "executed" not in payload


def test_plan_preview_command_returns_human_preview_text(workspace: Path) -> None:
    project = workspace / "project"
    project.mkdir()

    status, output, error = run_cli(
        [
            "--plan-preview",
            "--project-root",
            str(project),
            "--logs-root",
            str(workspace / "missing-logs"),
            "--category",
            "config",
        ]
    )

    assert status == 0
    assert error == ""
    assert "# Command Plan: Doctor remediation preview" in output
    assert "Status: `DRAFT`" in output
    assert "Source: `DOCTOR`" in output


def test_missing_ai_api_key_does_not_affect_service_cli(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    status, output, error = run_cli(
        [
            "--services",
            "--project-root",
            str(workspace),
            "--logs-root",
            str(workspace / "logs-root"),
        ]
    )

    assert status == 0
    assert error == ""
    assert "Traceback" not in output
    assert "API key" not in output


def test_cli_source_adds_no_execution_privilege_or_network_usage() -> None:
    source = Path("src/ecli/cli.py").read_text(encoding="utf-8")

    forbidden_tokens = (
        "subprocess",
        "Popen",
        "os.system",
        ".run(",
        "sudo",
        "doas",
        "pkexec",
        "chmod",
        "chown",
        "usermod",
        "modprobe",
        "socket",
        "requests",
        "urllib",
        "aiohttp",
    )
    assert all(token not in source for token in forbidden_tokens)


def test_test_workspaces_remain_under_logs(workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_root)


# ---------------------------------------------------------------------------
# P1 – plan-preview log path must never point at site-packages / lib paths
# ---------------------------------------------------------------------------


def test_effective_logs_root_does_not_contain_site_packages() -> None:
    """The default --logs-root must not resolve to a site-packages path."""
    from ecli.cli import _effective_logs_root

    root = _effective_logs_root()
    root_str = str(root)

    assert "site-packages" not in root_str, (
        f"_effective_logs_root() resolved to a site-packages path: {root_str}"
    )
    assert "/usr/local/lib/python" not in root_str, (
        f"_effective_logs_root() resolved to a system lib path: {root_str}"
    )


def test_effective_logs_root_is_under_repo_or_user_config() -> None:
    """The default logs root must be within the repo or ~/.config/ecli."""
    from ecli.cli import _effective_logs_root

    home = Path.home()
    repo_logs = (Path.cwd() / "logs").resolve(strict=False)
    user_logs = home / ".config" / "ecli" / "logs"

    root = _effective_logs_root().resolve(strict=False)

    in_repo = root.is_relative_to(repo_logs) or str(root).startswith(str(repo_logs))
    in_user = root.is_relative_to(user_logs) or str(root).startswith(str(user_logs))

    assert in_repo or in_user, (
        f"_effective_logs_root() is neither under repo logs nor ~/.config/ecli/logs: {root}"
    )


def test_plan_preview_default_logs_root_does_not_reference_package_lib_path(
    workspace: Path,
) -> None:
    """Running --plan-preview with the DEFAULT --logs-root must not error on path."""
    from ecli.cli import _effective_logs_root

    default_root = _effective_logs_root()

    # If the default root is inside the repo logs directory the existing
    # workspace fixture already covers it.  We just verify it is reachable.
    project = workspace / "project"
    project.mkdir()

    # Run with the EXPLICIT default root (avoids needing to omit --logs-root
    # which would try to create a real user-config directory in CI).
    status, output, error = run_cli(
        [
            "--plan-preview",
            "--project-root",
            str(project),
            "--logs-root",
            str(default_root),
            "--category",
            "config",
        ]
    )

    # The command must succeed or return 2 (no findings) — never crash.
    assert status in (0, 2), f"Unexpected exit code {status}: {error}"
    assert "Traceback" not in output
    assert "Traceback" not in error
    assert "/usr/local/lib/python" not in output
    assert "site-packages" not in output
