# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/services/test_service_registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Tests for the Phase 1D ServiceRegistry composition root."""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from ecli.services import ServiceRegistry
from ecli.services.audit_log_service import AuditLogService
from ecli.services.command_plan_service import CommandPlanService
from ecli.services.config_service import ConfigService
from ecli.services.policy import BuiltInPolicyEngine, PolicyEngine
from ecli.services.privileged_action_service import PrivilegedActionService
from ecli.services.project_service import ProjectService
from ecli.services.system_doctor import SystemDoctor


class FakeService:
    """Simple identity-preserving fake service."""


class FakeDoctor:
    """Doctor fake that tracks whether checks were invoked."""

    def __init__(self) -> None:
        """Initialize check tracking."""
        self.detect_problems_called = False

    def detect_problems(self, context: object) -> list[object]:
        """Track unexpected doctor checks."""
        del context
        self.detect_problems_called = True
        return []


class FakeAuditLogService:
    """Audit fake that tracks append calls."""

    def __init__(self) -> None:
        """Initialize append tracking."""
        self.append_calls = 0

    def append(self, record: object) -> object:
        """Track unexpected audit writes."""
        self.append_calls += 1
        return record


@pytest.fixture
def workspace(request: pytest.FixtureRequest) -> Iterator[Path]:
    repo_logs = Path.cwd() / "logs" / "test-service-registry"
    test_root = repo_logs / request.node.name.replace("/", "_").replace(":", "_")
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    try:
        yield test_root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_registry_constructor_preserves_injected_services_exactly() -> None:
    config_result = FakeService()
    config_service = FakeService()
    project_service = FakeService()
    policy_engine = FakeService()
    audit_log_service = FakeService()
    command_plan_service = FakeService()
    privileged_action_service = FakeService()
    system_doctor = FakeService()

    registry = ServiceRegistry(
        config_result=config_result,  # type: ignore[arg-type]
        config_service=config_service,  # type: ignore[arg-type]
        project_service=project_service,  # type: ignore[arg-type]
        policy_engine=policy_engine,  # type: ignore[arg-type]
        audit_log_service=audit_log_service,  # type: ignore[arg-type]
        command_plan_service=command_plan_service,  # type: ignore[arg-type]
        privileged_action_service=privileged_action_service,  # type: ignore[arg-type]
        system_doctor=system_doctor,  # type: ignore[arg-type]
    )

    assert registry.config_result is config_result
    assert registry.config_service is config_service
    assert registry.project_service is project_service
    assert registry.policy_engine is policy_engine
    assert registry.audit_log_service is audit_log_service
    assert registry.command_plan_service is command_plan_service
    assert registry.privileged_action_service is privileged_action_service
    assert registry.system_doctor is system_doctor


def test_create_wires_config_and_project_services(workspace: Path) -> None:
    project_config = workspace / ".ecli.toml"
    project_config.write_text("[editor]\ntab_size = 2\n", encoding="utf-8")

    registry = ServiceRegistry.create(
        project_root=workspace,
        logs_root=workspace,
        env={},
    )

    assert isinstance(registry.config_result, object)
    assert isinstance(registry.config_service, ConfigService)
    assert isinstance(registry.project_service, ProjectService)
    assert registry.project_service.root == workspace.resolve(strict=False)
    assert registry.config_service.get_editor_config().tab_size == 2


def test_create_wires_phase_one_service_instances(workspace: Path) -> None:
    registry = ServiceRegistry.create(
        project_root=workspace,
        logs_root=workspace,
        env={},
    )

    assert isinstance(registry.policy_engine, BuiltInPolicyEngine)
    assert isinstance(registry.policy_engine, PolicyEngine)
    assert isinstance(registry.audit_log_service, AuditLogService)
    assert isinstance(registry.command_plan_service, CommandPlanService)
    assert isinstance(registry.privileged_action_service, PrivilegedActionService)
    assert isinstance(registry.system_doctor, SystemDoctor)


def test_construction_order_is_deterministic_where_observable(
    workspace: Path,
) -> None:
    calls: list[str] = []
    discovery = ProjectService.discover(workspace)
    config_result = ConfigService.load(env={})

    def project_discoverer(project_root: Path | str | None) -> object:
        calls.append("project_discoverer")
        assert project_root == workspace
        return discovery

    def project_service_factory(discovery_value: object) -> object:
        calls.append("project_service_factory")
        assert discovery_value is discovery
        return ProjectService.from_discovery(discovery)

    def config_loader(**kwargs: Any) -> object:
        calls.append("config_loader")
        assert kwargs["env"] == {}
        return config_result

    def config_service_factory(config: object) -> object:
        calls.append("config_service_factory")
        assert config is config_result.config
        return ConfigService(config_result.config)

    def audit_factory(audit_dir: Path | None) -> object:
        calls.append("audit_factory")
        assert audit_dir == workspace / "audit"
        return FakeAuditLogService()

    def command_plan_factory() -> object:
        calls.append("command_plan_factory")
        return FakeService()

    def policy_factory() -> object:
        calls.append("policy_factory")
        return FakeService()

    def privileged_factory(audit: object) -> object:
        calls.append("privileged_factory")
        assert isinstance(audit, FakeAuditLogService)
        return FakeService()

    def doctor_factory(logs_root: Path | None) -> object:
        calls.append("doctor_factory")
        assert logs_root == workspace
        return FakeDoctor()

    ServiceRegistry.create(
        project_root=workspace,
        logs_root=workspace,
        env={},
        project_discoverer=project_discoverer,  # type: ignore[arg-type]
        project_service_factory=project_service_factory,  # type: ignore[arg-type]
        config_loader=config_loader,  # type: ignore[arg-type]
        config_service_factory=config_service_factory,  # type: ignore[arg-type]
        audit_log_service_factory=audit_factory,  # type: ignore[arg-type]
        command_plan_service_factory=command_plan_factory,  # type: ignore[arg-type]
        policy_engine_factory=policy_factory,  # type: ignore[arg-type]
        privileged_action_service_factory=privileged_factory,  # type: ignore[arg-type]
        system_doctor_factory=doctor_factory,  # type: ignore[arg-type]
    )

    assert calls == [
        "project_discoverer",
        "project_service_factory",
        "config_loader",
        "config_service_factory",
        "audit_factory",
        "command_plan_factory",
        "policy_factory",
        "privileged_factory",
        "doctor_factory",
    ]


def test_registry_construction_does_not_run_doctor_checks() -> None:
    doctor = FakeDoctor()

    registry = ServiceRegistry(
        config_result=None,
        config_service=FakeService(),  # type: ignore[arg-type]
        project_service=FakeService(),  # type: ignore[arg-type]
        policy_engine=FakeService(),  # type: ignore[arg-type]
        audit_log_service=FakeService(),  # type: ignore[arg-type]
        command_plan_service=FakeService(),  # type: ignore[arg-type]
        privileged_action_service=FakeService(),  # type: ignore[arg-type]
        system_doctor=doctor,  # type: ignore[arg-type]
    )

    assert registry.system_doctor is doctor
    assert doctor.detect_problems_called is False


def test_registry_construction_does_not_append_audit_records() -> None:
    audit_log_service = FakeAuditLogService()

    ServiceRegistry(
        config_result=None,
        config_service=FakeService(),  # type: ignore[arg-type]
        project_service=FakeService(),  # type: ignore[arg-type]
        policy_engine=FakeService(),  # type: ignore[arg-type]
        audit_log_service=audit_log_service,  # type: ignore[arg-type]
        command_plan_service=FakeService(),  # type: ignore[arg-type]
        privileged_action_service=FakeService(),  # type: ignore[arg-type]
        system_doctor=FakeService(),  # type: ignore[arg-type]
    )

    assert audit_log_service.append_calls == 0


def test_create_does_not_append_audit_records_or_create_audit_files(
    workspace: Path,
) -> None:
    registry = ServiceRegistry.create(
        project_root=workspace,
        logs_root=workspace,
        env={},
    )

    assert isinstance(registry.audit_log_service, AuditLogService)
    assert not (workspace / "audit").exists()


def test_registry_does_not_introduce_singleton_or_service_locator_behavior(
    workspace: Path,
) -> None:
    first = ServiceRegistry.create(project_root=workspace, logs_root=workspace, env={})
    second = ServiceRegistry.create(project_root=workspace, logs_root=workspace, env={})

    assert first is not second
    assert first.config_service is not second.config_service
    assert first.audit_log_service is not second.audit_log_service


def test_registry_has_no_business_logic_methods() -> None:
    public_methods = {
        name
        for name, member in inspect.getmembers(ServiceRegistry)
        if not name.startswith("_") and callable(member)
    }

    assert public_methods == {"create"}


def test_registry_source_has_no_execution_privilege_or_network_usage() -> None:
    source = Path("src/ecli/services/registry.py").read_text(encoding="utf-8")

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
