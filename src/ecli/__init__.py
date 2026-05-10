# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/__init__.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""ECLI — terminal-based text editor."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("ecli-editor")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
