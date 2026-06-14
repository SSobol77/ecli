# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/services/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Core service foundations for ECLI."""

from ecli.services.audit_log_service import AuditLogService
from ecli.services.command_plan_service import CommandPlanService
from ecli.services.config_service import ConfigService
from ecli.services.policy import BuiltInPolicyEngine, PolicyContext, PolicyEngine
from ecli.services.privileged_action_service import PrivilegedActionService
from ecli.services.project_service import ProjectService, UnsafeProjectPathError
from ecli.services.registry import ServiceRegistry
from ecli.services.system_doctor import SystemDoctor


__all__ = [
    "AuditLogService",
    "BuiltInPolicyEngine",
    "CommandPlanService",
    "ConfigService",
    "PolicyContext",
    "PolicyEngine",
    "PrivilegedActionService",
    "ProjectService",
    "ServiceRegistry",
    "SystemDoctor",
    "UnsafeProjectPathError",
]
