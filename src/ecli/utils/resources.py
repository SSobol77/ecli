# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/utils/resources.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Package-resource helpers for ECLI runtime assets."""

from __future__ import annotations

import importlib.resources as resources

from importlib.resources.abc import Traversable


def get_asset_path(name: str) -> Traversable:
    """Return a traversable package resource for an ECLI asset."""
    if not name or "/" in name or "\\" in name:
        raise ValueError("asset name must be a non-empty file name")
    return resources.files("ecli.assets").joinpath(name)


def get_icon_path() -> Traversable:
    """Return the canonical packaged ECLI PNG icon resource."""
    return get_asset_path("ecli.png")
