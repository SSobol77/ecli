# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/core/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Public facade for ecli.core: re-export main classes from CamelCase modules.

Keeps Java-like file names (AsyncEngine.py, History.py, ...),
but provides flat imports for convenience and stability.
"""

# Re-export classes/symbols from CamelCase modules
from .AsyncEngine import AsyncEngine  # noqa: F401
from .CodeCommenter import CodeCommenter  # noqa: F401
from .Ecli import Ecli  # noqa: F401
from .History import History  # noqa: F401


__all__ = [
    "AsyncEngine",
    "History",
    "Ecli",
    "CodeCommenter",
]
