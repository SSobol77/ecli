# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Phase 1D service composition root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ecli.services.audit_log_service import AuditLogService
from ecli.services.command_plan_service import CommandPlanService
from ecli.services.config_service import ConfigService
from ecli.services.models.config import ConfigLoadResult, ECLIConfig
from ecli.services.models.project import ProjectDiscoveryResult
from ecli.services.policy import BuiltInPolicyEngine, PolicyEngine
from ecli.services.privileged_action_service import PrivilegedActionService
from ecli.services.project_service import ProjectService
from ecli.services.system_doctor import SystemDoctor


ConfigLoader = Callable[..., ConfigLoadResult]
ConfigServiceFactory = Callable[[ECLIConfig], ConfigService]
ProjectDiscoverer = Callable[[Path | str | None], ProjectDiscoveryResult]
ProjectServiceFactory = Callable[[ProjectDiscoveryResult], ProjectService]
PolicyEngineFactory = Callable[[], PolicyEngine]
AuditLogServiceFactory = Callable[[Path | None], AuditLogService]
CommandPlanServiceFactory = Callable[[], CommandPlanService]
PrivilegedActionServiceFactory = Callable[[AuditLogService], PrivilegedActionService]
SystemDoctorFactory = Callable[[Path | None], SystemDoctor]


def _default_privileged_action_service_factory(
    audit_log_service: AuditLogService,
) -> PrivilegedActionService:
    return PrivilegedActionService(audit_sink=audit_log_service)


@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    """Explicit Phase 1 service composition root.

    The registry owns object wiring only. It does not evaluate policy, run doctor
    checks, append audit records, execute plans, or make business decisions.
    """

    config_result: ConfigLoadResult | None
    config_service: ConfigService
    project_service: ProjectService
    policy_engine: PolicyEngine
    audit_log_service: AuditLogService
    command_plan_service: CommandPlanService
    privileged_action_service: PrivilegedActionService
    system_doctor: SystemDoctor

    @classmethod
    def create(  # noqa: PLR0913
        cls,
        *,
        user_config_path: Path | None = None,
        project_config_path: Path | None = None,
        project_root: Path | None = None,
        logs_root: Path | None = None,
        cli_overrides: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
        config_loader: ConfigLoader = ConfigService.load,
        config_service_factory: ConfigServiceFactory = ConfigService,
        project_discoverer: ProjectDiscoverer = ProjectService.discover,
        project_service_factory: ProjectServiceFactory = ProjectService.from_discovery,
        policy_engine_factory: PolicyEngineFactory = BuiltInPolicyEngine,
        audit_log_service_factory: AuditLogServiceFactory = AuditLogService,
        command_plan_service_factory: CommandPlanServiceFactory = CommandPlanService,
        privileged_action_service_factory: PrivilegedActionServiceFactory = (
            _default_privileged_action_service_factory
        ),
        system_doctor_factory: SystemDoctorFactory = SystemDoctor,
    ) -> ServiceRegistry:
        """Create the Phase 1 service graph in deterministic dependency order."""
        discovery = project_discoverer(project_root)
        project_service = project_service_factory(discovery)
        effective_project_config_path = (
            project_config_path
            if project_config_path is not None
            else project_service.get_project_config_path()
        )

        config_result = config_loader(
            user_config_path=user_config_path,
            project_config_path=effective_project_config_path,
            cli_overrides=cli_overrides,
            env=env,
        )
        config_service = config_service_factory(config_result.config)

        audit_dir = None if logs_root is None else logs_root / "audit"
        audit_log_service = audit_log_service_factory(audit_dir)
        command_plan_service = command_plan_service_factory()
        policy_engine = policy_engine_factory()
        privileged_action_service = privileged_action_service_factory(audit_log_service)
        system_doctor = system_doctor_factory(logs_root)

        return cls(
            config_result=config_result,
            config_service=config_service,
            project_service=project_service,
            policy_engine=policy_engine,
            audit_log_service=audit_log_service,
            command_plan_service=command_plan_service,
            privileged_action_service=privileged_action_service,
            system_doctor=system_doctor,
        )
