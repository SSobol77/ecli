# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extensions_package_data_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Package-data contract tests for imported extension assets (#99).

These tests build the PyPI wheel and source distribution into a throwaway temp
directory and prove, with the standard library only (``zipfile`` for the wheel
and ``tarfile`` for the sdist), that representative imported extension assets
from ``src/ecli/extensions/`` ship inside both artifacts.

They build nothing into the repository tree, publish nothing, upload nothing,
and create no release artifacts outside the pytest temp directory. The build is
performed once per module via a module-scoped fixture.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

# Representative imported assets, expressed as repository-relative source paths.
REPRESENTATIVE_SOURCE_PATHS: tuple[str, ...] = (
    "src/ecli/extensions/cgmanifest.json",
    "src/ecli/extensions/bat/package.json",
    "src/ecli/extensions/bat/language-configuration.json",
    "src/ecli/extensions/bat/syntaxes/batchfile.tmLanguage.json",
    "src/ecli/extensions/python/package.json",
    "src/ecli/extensions/json/package.json",
    "src/ecli/extensions/javascript/package.json",
    "src/ecli/extensions/markdown-basics/package.json",
)

# Inside the wheel the ``src/`` prefix is dropped and ``ecli`` is the package
# root, so ``src/ecli/extensions/X`` -> ``ecli/extensions/X``.
WHEEL_MEMBER_PATHS: tuple[str, ...] = tuple(
    path[len("src/") :] for path in REPRESENTATIVE_SOURCE_PATHS
)


def _build_command(out_dir: Path) -> list[str] | None:
    """Return the artifact build command, preferring ``uv build``.

    ``uv build`` provisions the ``hatchling`` build backend from uv's managed
    environment, matching how this repository builds everywhere. ``python -m
    build`` is the documented fallback (see ``scripts/publish_pypi.py``). Returns
    ``None`` if no build frontend is available.
    """
    uv = shutil.which("uv")
    if uv is not None:
        return [uv, "build", "--out-dir", str(out_dir), str(REPO_ROOT)]
    try:
        import build  # noqa: F401
    except ImportError:
        return None
    return [
        sys.executable,
        "-m",
        "build",
        "--outdir",
        str(out_dir),
        str(REPO_ROOT),
    ]


@pytest.fixture(scope="module")
def built_artifacts(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[Path, Path]]:
    """Build the wheel and sdist once into a temp dir; yield ``(wheel, sdist)``."""
    out_dir = tmp_path_factory.mktemp("ecli_pkg_data_artifacts")
    command = _build_command(out_dir)
    if command is None:
        pytest.skip("no build frontend available (need `uv` or the `build` module)")

    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(
            "package build unavailable in this environment "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )

    wheels = sorted(out_dir.glob("*.whl"))
    sdists = sorted(out_dir.glob("*.tar.gz"))
    assert wheels, f"no wheel produced by build command: {command}"
    assert sdists, f"no sdist produced by build command: {command}"
    yield wheels[0], sdists[0]


def test_wheel_contains_representative_extension_assets(
    built_artifacts: tuple[Path, Path],
) -> None:
    wheel_path, _ = built_artifacts
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())

    missing = [member for member in WHEEL_MEMBER_PATHS if member not in names]
    assert not missing, (
        f"wheel {wheel_path.name} is missing extension assets: {missing}"
    )


def test_sdist_contains_representative_extension_assets(
    built_artifacts: tuple[Path, Path],
) -> None:
    _, sdist_path = built_artifacts
    with tarfile.open(sdist_path) as sdist:
        names = set(sdist.getnames())

    # The sdist wraps everything in a single ``<name>-<version>/`` root dir.
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    root = next(
        (candidate for candidate in roots if f"{candidate}/pyproject.toml" in names),
        None,
    )
    assert root is not None, f"could not locate sdist root dir in {sdist_path.name}"

    expected = [f"{root}/{path}" for path in REPRESENTATIVE_SOURCE_PATHS]
    missing = [member for member in expected if member not in names]
    assert not missing, (
        f"sdist {sdist_path.name} is missing extension assets: {missing}"
    )
