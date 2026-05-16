# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/models/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Typed service model definitions."""

from ecli.services.models.audit import AuditActor, AuditEventType, AuditRecord
from ecli.services.models.config import (
    AIConfig,
    AIProviderConfig,
    ConfigDiagnostic,
    ConfigDiagnosticLevel,
    ConfigLoadResult,
    ConfigSource,
    ECLIConfig,
    EditorConfig,
    GitConfig,
    KeybindingConfig,
    LSPConfig,
    SafetyPolicyConfig,
    UIConfig,
)
from ecli.services.models.plan import (
    CommandPlan,
    CommandStep,
    PlanCategory,
    PlanRisk,
    PlanSource,
    PlanStatus,
    PolicyDecision,
    needs_confirmation,
    new_plan_id,
)
from ecli.services.models.privileged import (
    ExecutionRequest,
    ExecutionResult,
    PrivilegeBackend,
)
from ecli.services.models.project import (
    ProjectDiagnostic,
    ProjectDiagnosticLevel,
    ProjectDiscoveryResult,
    ProjectMarker,
    ProjectMetadata,
    ProjectPathResolutionResult,
)


__all__ = [
    "AuditActor",
    "AuditEventType",
    "AuditRecord",
    "AIConfig",
    "AIProviderConfig",
    "ConfigDiagnostic",
    "ConfigDiagnosticLevel",
    "ConfigLoadResult",
    "ConfigSource",
    "CommandPlan",
    "CommandStep",
    "ECLIConfig",
    "EditorConfig",
    "ExecutionRequest",
    "ExecutionResult",
    "GitConfig",
    "KeybindingConfig",
    "LSPConfig",
    "PlanCategory",
    "PlanRisk",
    "PlanSource",
    "PlanStatus",
    "PolicyDecision",
    "PrivilegeBackend",
    "SafetyPolicyConfig",
    "UIConfig",
    "ProjectDiagnostic",
    "ProjectDiagnosticLevel",
    "ProjectDiscoveryResult",
    "ProjectMarker",
    "ProjectMetadata",
    "ProjectPathResolutionResult",
    "needs_confirmation",
    "new_plan_id",
]
