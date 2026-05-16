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

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


_DISTRIBUTION_NAME = "ecli-editor"


def _read_pyproject_version(pyproject_path: Path) -> str | None:
    if not pyproject_path.is_file():
        return None
    try:
        with pyproject_path.open("rb") as pyproject_file:
            raw_version = tomllib.load(pyproject_file)["project"]["version"]
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError):
        return None
    if not isinstance(raw_version, str) or not raw_version.strip():
        return None
    return raw_version


def _source_tree_version(package_file: Path | None = None) -> str | None:
    source_file = Path(__file__) if package_file is None else package_file
    pyproject_path = source_file.resolve().parents[2] / "pyproject.toml"
    return _read_pyproject_version(pyproject_path)


def _installed_package_version(
    distribution_name: str = _DISTRIBUTION_NAME,
) -> str | None:
    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None


def _resolve_version() -> str:
    return _source_tree_version() or _installed_package_version() or "0.0.0+local"


__version__ = _resolve_version()

__all__ = ["__version__"]
