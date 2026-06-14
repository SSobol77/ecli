# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_service_panels.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for Phase 1 service right-side TUI panels."""

from __future__ import annotations

import curses
import inspect
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from ecli.services.command_plan_service import CommandPlanService
from ecli.services.models.doctor import DoctorFinding, DoctorSeverity
from ecli.ui.panels import (
    CommandPlanPanel,
    ServicesPanel,
    SystemDoctorPanel,
    _ReadOnlyRightPanel,
)


class FakeWindow:
    def __init__(self) -> None:
        """Initialize a fake curses window."""
        self.keypad_values: list[bool] = []
        self.drawn_text: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (32, 120)

    def keypad(self, value: bool) -> None:
        self.keypad_values.append(value)

    def erase(self) -> None:
        self.drawn_text.clear()

    def border(self) -> None:
        return None

    def addnstr(self, _y: int, _x: int, text: str, _width: int, _attr: int = 0) -> None:
        self.drawn_text.append(text)

    def refresh(self) -> None:
        return None

    def noutrefresh(self) -> None:
        return None


class FakePanelManager:
    def __init__(self) -> None:
        """Initialize panel call recording."""
        self.shown: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def show_panel(self, name: str, **kwargs: Any) -> None:
        self.shown.append((name, kwargs))

    def close_active_panel(self) -> None:
        self.closed = True


class FakeDoctor:
    def __init__(self, findings: list[DoctorFinding]) -> None:
        """Initialize deterministic findings."""
        self.findings = findings
        self.contexts: list[Any] = []

    def detect_problems(self, context: Any) -> list[DoctorFinding]:
        self.contexts.append(context)
        return list(self.findings)


class FakeRegistry:
    def __init__(self, findings: list[DoctorFinding]) -> None:
        """Initialize a service-registry-shaped fake."""
        self.config_service = object()
        self.project_service = type(
            "FakeProjectService",
            (),
            {"root": Path.cwd()},
        )()
        self.command_plan_service = CommandPlanService()
        self.policy_engine = object()
        self.audit_log_service = object()
        self.privileged_action_service = object()
        self.system_doctor = FakeDoctor(findings)
        self.config_result = type("FakeConfigResult", (), {"diagnostics": []})()


class FakeEditor:
    def __init__(self, registry: FakeRegistry) -> None:
        """Initialize a panel-compatible editor double."""
        self.stdscr = FakeWindow()
        self.focus = "panel"
        self._force_full_redraw = False
        self.colors = {
            "status": curses.A_BOLD,
            "function": curses.A_BOLD,
            "default": curses.A_NORMAL,
            "comment": curses.A_DIM,
            "warning": curses.A_BOLD,
            "error": curses.A_BOLD,
        }
        self.filename = None
        self.service_registry = registry
        self.panel_manager = FakePanelManager()
        self.status_messages: list[str] = []

    def _set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def _get_service_registry(self) -> FakeRegistry:
        return self.service_registry

    def toggle_focus(self) -> None:
        self.focus = "editor" if self.focus == "panel" else "panel"


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-ui-service-panels"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


@pytest.fixture(autouse=True)
def fake_curses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ecli.ui.panels.curses.newwin", lambda *args: FakeWindow())
    monkeypatch.setattr("ecli.ui.panels.curses.curs_set", lambda value: None)


def finding(remediation_available: bool = True) -> DoctorFinding:
    return DoctorFinding(
        finding_id="DOCTOR-CONFIG-001",
        title="Repository logs directory is missing",
        severity=DoctorSeverity.WARNING,
        category="config",
        description="Repository-level logs/ is absent.",
        affected_resources=("logs",),
        remediation_available=remediation_available,
        remediation_plan_id="plan-20260101T000000Z-12345678",
    )


def rendered_text(window: FakeWindow) -> str:
    return "\n".join(window.drawn_text)


def test_system_doctor_panel_renders_structured_findings() -> None:
    registry = FakeRegistry([finding()])
    editor = FakeEditor(registry)
    panel = SystemDoctorPanel(editor.stdscr, editor, registry=registry)

    panel.open()
    panel.draw()

    text = rendered_text(panel.win)
    assert "System Doctor" in text
    assert "WARNING" in text
    assert "config" in text
    assert "DOCTOR-CONFIG-001" in text
    assert "Repository logs directory is missing" in text
    assert "remediation=yes" in text


def test_system_doctor_panel_opens_command_plan_preview_for_finding() -> None:
    registry = FakeRegistry([finding()])
    editor = FakeEditor(registry)
    panel = SystemDoctorPanel(editor.stdscr, editor, registry=registry)

    panel.open()

    assert panel.handle_key(ord("p")) is True
    assert editor.panel_manager.shown
    name, kwargs = editor.panel_manager.shown[-1]
    assert name == "command_plan"
    assert kwargs["plans"][0].plan_id == "plan-20260101T000000Z-12345678"
    assert kwargs["plans"][0].status.value == "DRAFT"


def test_system_doctor_panel_does_not_open_plan_for_unavailable_remediation() -> None:
    registry = FakeRegistry([finding(remediation_available=False)])
    editor = FakeEditor(registry)
    panel = SystemDoctorPanel(editor.stdscr, editor, registry=registry)

    panel.open()

    assert panel.handle_key(ord("p")) is True
    assert editor.panel_manager.shown == []
    assert "no remediation preview" in editor.status_messages[-1]


def test_system_doctor_panel_opens_services_status_view() -> None:
    registry = FakeRegistry([finding()])
    editor = FakeEditor(registry)
    panel = SystemDoctorPanel(editor.stdscr, editor, registry=registry)

    panel.open()

    assert panel.handle_key(ord("s")) is True
    assert editor.panel_manager.shown[-1][0] == "services_status"


def test_command_plan_panel_renders_draft_plan_preview() -> None:
    plan = CommandPlanService().create_plan_from_doctor_finding(finding())
    assert plan is not None
    registry = FakeRegistry([finding()])
    editor = FakeEditor(registry)
    panel = CommandPlanPanel(editor.stdscr, editor, registry=registry, plans=[plan])

    panel.open()
    panel.draw()

    text = rendered_text(panel.win)
    assert "Command Plans" in text
    assert plan.plan_id in text
    assert "Risk: LOW" in text
    assert "Status: DRAFT" in text
    assert "Confirmation: True" in text
    assert "mkdir -p logs" in text
    assert "Markdown preview:" in text


def test_services_panel_renders_phase_one_service_status() -> None:
    registry = FakeRegistry([finding()])
    editor = FakeEditor(registry)
    panel = ServicesPanel(editor.stdscr, editor, registry=registry)

    panel.open()
    panel.draw()

    text = rendered_text(panel.win)
    assert "Services" in text
    assert "ConfigService" in text
    assert "ProjectService" in text
    assert "CommandPlanService" in text
    assert "BuiltInPolicyEngine" in text
    assert "AuditLogService" in text
    assert "PrivilegedActionService" in text
    assert "SystemDoctor" in text
    assert "available" in text


def test_new_service_panel_source_has_no_forbidden_runtime_operations() -> None:
    source = "\n".join(
        inspect.getsource(item)
        for item in (
            _ReadOnlyRightPanel,
            SystemDoctorPanel,
            CommandPlanPanel,
            ServicesPanel,
        )
    )

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
        "QEMU",
    )
    assert all(token not in source for token in forbidden_tokens)


def test_test_workspaces_remain_under_logs(workspace: Path) -> None:
    logs_root = (Path.cwd() / "logs").resolve(strict=False)

    assert workspace.resolve(strict=False).is_relative_to(logs_root)
