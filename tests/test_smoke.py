# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/test_smoke.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Smoke tests — fastest possible signal that the package imports."""

import re

import ecli


def test_package_imports() -> None:
    assert hasattr(ecli, "__version__")


def test_version_format() -> None:
    assert re.match(r"\d+\.\d+\.\d+", ecli.__version__) or "+local" in ecli.__version__
