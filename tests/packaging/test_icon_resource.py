# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/packaging/test_icon_resource.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Packaging-resource regression coverage for the ECLI icon."""

from __future__ import annotations

from importlib import resources

from ecli.utils.resources import get_icon_path


def test_packaged_icon_resource_resolves() -> None:
    icon = resources.files("ecli.assets").joinpath("ecli.png")

    assert icon.is_file()
    assert icon.name == "ecli.png"


def test_get_icon_path_returns_canonical_icon_resource() -> None:
    icon = get_icon_path()

    assert icon.is_file()
    assert icon.name == "ecli.png"
