# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_linters_namespace_migration.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""F4 linter diagnostics namespace-migration contract tests.

F4 linter diagnostics moved from ``src/ecli/diagnostics/`` to
``src/ecli/extensions/linters/`` (see
``docs/architecture/ecli-f4-linter-microservices-design.md``).
``src/ecli/diagnostics/`` is reserved for future general/system
diagnostics (System Doctor / F8, environment health checks) and must not
contain F4 linter code again.

These tests guard:

* the new namespace exists with the required shape;
* the retired namespace is gone;
* the normalized ``Diagnostic``/``DiagnosticsService``/
  ``RuffDiagnosticProvider`` types import from the new namespace;
* no ECLI runtime source or test (other than this migration-contract file)
  still imports the retired ``ecli.diagnostics`` namespace;
* every required first-class linter microservice directory exists with a
  ``manifest.py`` and ``package_contract.py``;
* exactly the implemented-provider set (``IMPLEMENTED_PROVIDER_DIRECTORIES``)
  has a working ``provider.py`` and is registered with ``LinterBridge`` --
  no more, no less.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "ecli"
LINTERS_ROOT = SRC_ROOT / "extensions" / "linters"
CORE_ROOT = LINTERS_ROOT / "core"
DIAGNOSTICS_ROOT = SRC_ROOT / "diagnostics"

# This migration-contract file is the one place allowed to name the retired
# namespace (as a plain string, never as a live import) so it can assert the
# namespace is gone.
_THIS_FILE = Path(__file__).resolve()

# First-class linter microservice directories required by the design
# contract's Language and Tool Matrix (section 10.1) and directory
# architecture (section 5), using this migration's directory-naming
# convention (snake_case; the tool's real identity lives in manifest.py's
# ``LinterDefinition.name``).
REQUIRED_FIRST_CLASS_MICROSERVICES: frozenset[str] = frozenset(
    {
        "ruff",
        "biome",
        "zig",
        "clang_tidy",
        "cppcheck",
        "clang_format",
        "java_checkstyle",
        "java_pmd",
        "java_spotbugs",
        "shellcheck",
        "markdownlint",
        "yamllint",
        "actionlint",
        "hadolint",
        "taplo",
        "cargo_clippy",
        "golangci_lint",
        "sqlfluff",
        "tflint",
    }
)


# ---------------------------------------------------------------------------
# 1. Namespace tests
# ---------------------------------------------------------------------------


def test_linters_extensions_root_exists() -> None:
    assert LINTERS_ROOT.is_dir(), (
        f"missing F4 linter microservices root: {LINTERS_ROOT}"
    )


def test_core_models_exists() -> None:
    assert (CORE_ROOT / "models.py").is_file()


def test_core_service_exists() -> None:
    assert (CORE_ROOT / "service.py").is_file()


def test_core_display_exists() -> None:
    assert (CORE_ROOT / "display.py").is_file()


def test_core_provider_protocol_exists() -> None:
    assert (CORE_ROOT / "provider_protocol.py").is_file()


def test_core_registry_exists() -> None:
    assert (CORE_ROOT / "registry.py").is_file()


def test_ruff_provider_exists() -> None:
    assert (LINTERS_ROOT / "ruff" / "provider.py").is_file()


def test_diagnostics_package_no_longer_contains_f4_linter_code() -> None:
    """src/ecli/diagnostics is reserved for future non-linter diagnostics.

    It must not exist bearing the retired F4 linter modules. An absent
    directory and a present-but-linter-code-free directory are both
    acceptable; only the specific retired filenames are forbidden.
    """
    forbidden_files = (
        "linter_catalog.py",
        "ruff_provider.py",
        "service.py",
        "models.py",
        "display.py",
    )
    if not DIAGNOSTICS_ROOT.exists():
        return
    present = [name for name in forbidden_files if (DIAGNOSTICS_ROOT / name).is_file()]
    assert present == [], (
        f"src/ecli/diagnostics/ must not contain retired F4 linter modules: {present}"
    )


# ---------------------------------------------------------------------------
# 2. Import tests
# ---------------------------------------------------------------------------


def test_diagnostic_model_importable_from_new_namespace() -> None:
    from ecli.extensions.linters.core.models import Diagnostic

    diagnostic = Diagnostic(
        file_path="a.py",
        line=1,
        column=1,
        severity="error",
        code="E001",
        message="test",
        source="test",
    )
    assert diagnostic.file_path == "a.py"


def test_diagnostics_service_importable_from_new_namespace() -> None:
    from ecli.extensions.linters.core.service import DiagnosticsService

    service = DiagnosticsService()
    assert service.provider_states() == ()


def test_ruff_diagnostic_provider_importable_from_new_namespace() -> None:
    from ecli.extensions.linters.ruff.provider import RuffDiagnosticProvider

    provider = RuffDiagnosticProvider()
    assert provider.name == "ruff"


def test_runtime_import_gate_passes() -> None:
    result = subprocess.run(
        ["python3", "scripts/check_runtime_imports.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# 3. No old linter namespace tests
# ---------------------------------------------------------------------------


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _imports_old_diagnostics_namespace(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.startswith("ecli.diagnostics") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "ecli.diagnostics" or module.startswith("ecli.diagnostics."):
                return True
    return False


def test_no_src_runtime_file_imports_old_diagnostics_namespace() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _iter_python_files(SRC_ROOT)
        if _imports_old_diagnostics_namespace(path)
    ]
    assert offenders == [], (
        f"src/ runtime files must not import the retired ecli.diagnostics "
        f"namespace: {offenders}"
    )


def test_no_test_file_imports_old_diagnostics_namespace() -> None:
    tests_root = REPO_ROOT / "tests"
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _iter_python_files(tests_root)
        if path.resolve() != _THIS_FILE and _imports_old_diagnostics_namespace(path)
    ]
    assert offenders == [], (
        f"tests must not import the retired ecli.diagnostics namespace: {offenders}"
    )


# ---------------------------------------------------------------------------
# 6. Microservice skeleton tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service_dir", sorted(REQUIRED_FIRST_CLASS_MICROSERVICES))
def test_required_first_class_microservice_directory_exists(service_dir: str) -> None:
    assert (LINTERS_ROOT / service_dir).is_dir(), (
        f"required first-class linter microservice directory missing: "
        f"src/ecli/extensions/linters/{service_dir}/"
    )


def _microservice_directories() -> list[Path]:
    return sorted(
        child
        for child in LINTERS_ROOT.iterdir()
        if child.is_dir() and child.name not in ("core", "__pycache__")
    )


@pytest.mark.parametrize(
    "service_dir", _microservice_directories(), ids=lambda p: p.name
)
def test_every_microservice_directory_has_a_manifest(service_dir: Path) -> None:
    assert (service_dir / "manifest.py").is_file(), (
        f"{service_dir.name} is missing manifest.py"
    )


@pytest.mark.parametrize(
    "service_dir", _microservice_directories(), ids=lambda p: p.name
)
def test_every_microservice_directory_has_a_package_contract(
    service_dir: Path,
) -> None:
    assert (service_dir / "package_contract.py").is_file(), (
        f"{service_dir.name} is missing package_contract.py"
    )


# Microservices with a real, working provider.py as of this implementation
# stage. Everything else under linters/ (eslint, pylint, stylelint, oxlint,
# golangci_lint, sqlfluff, tflint, clang_format, java_spotbugs) remains a
# manifest/package_contract-only skeleton: either legacy/optional (never
# registered) or not yet safely implementable per the design contract
# (clang-format must stay check-only and is not yet wired; SpotBugs must
# not run blindly on source without build output).
IMPLEMENTED_PROVIDER_DIRECTORIES: frozenset[str] = frozenset(
    {
        "ruff",
        "markdownlint",
        "yamllint",
        "shellcheck",
        "biome",
        "zig",
        "hadolint",
        "taplo",
        "actionlint",
        "clang_tidy",
        "cppcheck",
        "java_checkstyle",
        "java_pmd",
        "cargo_clippy",
    }
)


def test_only_implemented_microservices_have_a_working_provider() -> None:
    with_provider = {
        service_dir.name
        for service_dir in _microservice_directories()
        if (service_dir / "provider.py").is_file()
    }
    assert with_provider == IMPLEMENTED_PROVIDER_DIRECTORIES, (
        f"provider.py directories drifted from the implemented set: "
        f"{with_provider.symmetric_difference(IMPLEMENTED_PROVIDER_DIRECTORIES)}"
    )


def test_only_implemented_providers_are_registered_with_linter_bridge() -> None:
    """LinterBridge.py -- the F4 provider-registration site -- must register
    exactly the providers that have a real provider.py, and nothing else
    (no legacy/optional/not-yet-safe provider is registered).
    """
    bridge_source = (SRC_ROOT / "integrations" / "LinterBridge.py").read_text(
        encoding="utf-8"
    )
    assert "register_provider" in bridge_source
    referenced_providers = set(re.findall(r"(\w+)DiagnosticProvider\(", bridge_source))
    expected = {
        "".join(part.title() for part in name.split("_"))
        for name in IMPLEMENTED_PROVIDER_DIRECTORIES
    }
    # ShellCheck's class name capitalizes "Check" mid-word; normalize both
    # sides by comparing case-insensitively against the known class names.
    expected = {"ShellCheck" if name == "Shellcheck" else name for name in expected}
    assert referenced_providers == expected, (
        f"LinterBridge provider registration drifted from the implemented "
        f"set: {referenced_providers.symmetric_difference(expected)}"
    )


def test_non_ruff_manifests_do_not_import_diagnostics_service() -> None:
    """Manifest/package-contract skeletons are metadata only: they must not
    reach into DiagnosticsService or execute anything.
    """
    offenders = []
    for service_dir in _microservice_directories():
        if service_dir.name == "ruff":
            continue
        for filename in ("manifest.py", "package_contract.py", "__init__.py"):
            path = service_dir / filename
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if "DiagnosticsService" in text or "register_provider" in text:
                offenders.append(f"{service_dir.name}/{filename}")
    assert offenders == [], (
        f"non-Ruff microservice skeletons must not reference "
        f"DiagnosticsService/register_provider yet: {offenders}"
    )
