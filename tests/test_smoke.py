"""Smoke tests — fastest possible signal that the package imports."""

import re

import ecli


def test_package_imports() -> None:
    assert hasattr(ecli, "__version__")


def test_version_format() -> None:
    assert re.match(r"\d+\.\d+\.\d+", ecli.__version__) or "+local" in ecli.__version__
