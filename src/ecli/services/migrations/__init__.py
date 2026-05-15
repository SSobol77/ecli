# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/services/migrations/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Configuration migration helpers."""

from ecli.services.migrations.config_migrations import (
    calculate_config_backup_path,
    detect_config_schema_version,
    migrate_to_current,
    migrate_v1_to_v2,
)


__all__ = [
    "calculate_config_backup_path",
    "detect_config_schema_version",
    "migrate_to_current",
    "migrate_v1_to_v2",
]
