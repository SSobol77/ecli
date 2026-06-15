# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_runtime_import_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Runtime import guards for PyInstaller-packaged Linux artifacts."""

from __future__ import annotations

import importlib.util
import os
import site
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
IMPORT_GUARD_PATH = REPO_ROOT / "scripts" / "check_runtime_imports.py"

spec = importlib.util.spec_from_file_location(
    "check_runtime_imports", IMPORT_GUARD_PATH
)
assert spec is not None
check_runtime_imports = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(check_runtime_imports)


@pytest.fixture()
def isolated_runtime_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source_root = tmp_path / "src" / "ecli"
    source_root.mkdir(parents=True)
    monkeypatch.setattr(check_runtime_imports, "SOURCE_ROOT", source_root)
    return source_root


def _write_runtime_module(source_root: Path, source: str) -> None:
    (source_root / "module.py").write_text(source, encoding="utf-8")


def _guard_result(source_root: Path, source: str) -> int:
    _write_runtime_module(source_root, source)
    return check_runtime_imports.main()


def _python_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    python_paths = [str(REPO_ROOT / "src")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        python_paths.append(existing_pythonpath)
    user_site = site.getusersitepackages()
    if user_site:
        python_paths.append(user_site)
    env["HOME"] = str(tmp_path / "home")
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    return env


def test_runtime_modules_import_when_unittest_is_unavailable(tmp_path: Path) -> None:
    script = """
import importlib
import importlib.abc
import sys

for name in tuple(sys.modules):
    if name == "unittest" or name.startswith("unittest."):
        del sys.modules[name]

class BlockUnittest(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "unittest" or fullname.startswith("unittest."):
            raise ModuleNotFoundError("No module named 'unittest'")
        return None

sys.meta_path.insert(0, BlockUnittest())

for module_name in (
    "ecli.__main__",
    "ecli.core.Ecli",
    "ecli.ui.KeyBinder",
    "ecli.ui.PanelManager",
    "ecli.ui.DrawScreen",
):
    importlib.import_module(module_name)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_python_env(tmp_path),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_production_source_does_not_import_test_only_modules() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_runtime_imports.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "source",
    (
        "import unittest\n",
        "from unittest.mock import Mock\n",
        "import pytest\n",
    ),
)
def test_production_test_only_imports_fail(
    isolated_runtime_source: Path,
    source: str,
) -> None:
    assert _guard_result(isolated_runtime_source, source) == 1


def test_test_files_may_import_test_only_modules(
    isolated_runtime_source: Path,
    tmp_path: Path,
) -> None:
    _write_runtime_module(isolated_runtime_source, "VALUE = 1\n")
    test_root = tmp_path / "tests"
    test_root.mkdir()
    (test_root / "test_allowed_imports.py").write_text(
        "import unittest\nimport pytest\n",
        encoding="utf-8",
    )

    assert check_runtime_imports.main() == 0


def test_comments_and_strings_do_not_trigger_import_guard(
    isolated_runtime_source: Path,
) -> None:
    source = """
# import unittest
TEXT = "from unittest.mock import Mock"
LATEST = "latest contest"
"""
    assert _guard_result(isolated_runtime_source, source) == 0


def test_global_help_and_version_do_not_start_curses_or_log_critical(
    tmp_path: Path,
) -> None:
    env = _python_env(tmp_path)
    for argument in ("--help", "--version"):
        result = subprocess.run(
            [sys.executable, "-m", "ecli", argument],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip()

    log_path = Path(env["HOME"]) / ".config" / "ecli" / "logs" / "editor.log"
    if log_path.exists():
        assert "CRITICAL" not in log_path.read_text(encoding="utf-8")


def test_runtime_validator_enforces_current_release_directory() -> None:
    # Canonical implementation is the Python entrypoint.
    script = (REPO_ROOT / "scripts" / "verify_runtime.py").read_text(encoding="utf-8")

    assert "releases/{version}" in script
    assert "Artifact is outside current project version directory" in script


def test_runtime_validator_checks_exact_version_and_startup_logs() -> None:
    script = (REPO_ROOT / "scripts" / "verify_runtime.py").read_text(encoding="utf-8")

    assert 'f"ecli {version}"' in script
    assert "ModuleNotFoundError" in script
    assert "No module named 'unittest'" in script
    assert "Failed to import a critical application component" in script
