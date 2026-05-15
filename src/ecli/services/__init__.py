# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Core service foundations for ECLI."""

from ecli.services.config_service import ConfigService
from ecli.services.project_service import ProjectService, UnsafeProjectPathError


__all__ = ["ConfigService", "ProjectService", "UnsafeProjectPathError"]
