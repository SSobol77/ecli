# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/policy/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Policy engine interfaces and built-in deterministic policy rules."""

from ecli.services.policy.builtin import BuiltInPolicyEngine
from ecli.services.policy.engine import PolicyContext, PolicyEngine, PolicyRuleResult


__all__ = [
    "BuiltInPolicyEngine",
    "PolicyContext",
    "PolicyEngine",
    "PolicyRuleResult",
]
