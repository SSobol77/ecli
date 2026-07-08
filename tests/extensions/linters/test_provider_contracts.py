# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/linters/test_provider_contracts.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Shared contract tests for every implemented F4 linter microservice provider.

Mirrors ``docs/architecture/ecli-f4-linter-microservices-design.md``
section 19.2 ("Shared Contract Tests"): every provider implements
``supports``, returns ``DiagnosticResult``, never uses ``shell=True``,
builds argv as a plain list, has a timeout, and reports a missing
executable as a controlled result rather than raising.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ecli.extensions.linters.actionlint.provider import ActionlintDiagnosticProvider
from ecli.extensions.linters.biome.provider import BiomeDiagnosticProvider
from ecli.extensions.linters.cargo_clippy.provider import CargoClippyDiagnosticProvider
from ecli.extensions.linters.clang_tidy.provider import ClangTidyDiagnosticProvider
from ecli.extensions.linters.core.models import DiagnosticRequest, DiagnosticResult
from ecli.extensions.linters.cppcheck.provider import CppcheckDiagnosticProvider
from ecli.extensions.linters.hadolint.provider import HadolintDiagnosticProvider
from ecli.extensions.linters.java_checkstyle.provider import (
    JavaCheckstyleDiagnosticProvider,
)
from ecli.extensions.linters.java_pmd.provider import JavaPmdDiagnosticProvider
from ecli.extensions.linters.markdownlint.provider import MarkdownlintDiagnosticProvider
from ecli.extensions.linters.ruff.provider import RuffDiagnosticProvider
from ecli.extensions.linters.shellcheck.provider import ShellCheckDiagnosticProvider
from ecli.extensions.linters.taplo.provider import TaploDiagnosticProvider
from ecli.extensions.linters.yamllint.provider import YamllintDiagnosticProvider
from ecli.extensions.linters.zig.provider import ZigDiagnosticProvider


REPO_ROOT = Path(__file__).resolve().parents[3]
LINTERS_ROOT = REPO_ROOT / "src" / "ecli" / "extensions" / "linters"

# (directory name, provider class, a representative supported file path)
PROVIDER_CASES: tuple[tuple[str, type, str], ...] = (
    ("ruff", RuffDiagnosticProvider, "a.py"),
    ("markdownlint", MarkdownlintDiagnosticProvider, "a.md"),
    ("yamllint", YamllintDiagnosticProvider, "a.yaml"),
    ("shellcheck", ShellCheckDiagnosticProvider, "a.sh"),
    ("biome", BiomeDiagnosticProvider, "a.ts"),
    ("zig", ZigDiagnosticProvider, "a.zig"),
    ("hadolint", HadolintDiagnosticProvider, "Dockerfile"),
    ("taplo", TaploDiagnosticProvider, "a.toml"),
    ("actionlint", ActionlintDiagnosticProvider, ".github/workflows/ci.yml"),
    ("clang_tidy", ClangTidyDiagnosticProvider, "a.cpp"),
    ("cppcheck", CppcheckDiagnosticProvider, "a.cpp"),
    ("java_checkstyle", JavaCheckstyleDiagnosticProvider, "A.java"),
    ("java_pmd", JavaPmdDiagnosticProvider, "A.java"),
    ("cargo_clippy", CargoClippyDiagnosticProvider, "a.rs"),
)

_IDS = [case[0] for case in PROVIDER_CASES]

# Ruff is a documented exception (see ruff/provider.py's module docstring):
# parsing helpers stay inline rather than in a separate parser.py, and its
# command-construction variable is named `command`, not `argv`, preserved
# verbatim from the pre-migration ``ruff_provider.py`` for behavior
# preservation. It is covered by its own tests in
# tests/core/test_diagnostics_service.py instead.
_CASES_WITH_OWN_PARSER_MODULE = tuple(
    case for case in PROVIDER_CASES if case[0] != "ruff"
)
_IDS_WITH_OWN_PARSER_MODULE = [case[0] for case in _CASES_WITH_OWN_PARSER_MODULE]


def _make_request(tmp_path: Path, relative_path: str) -> DiagnosticRequest:
    file_path = tmp_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("placeholder\n", encoding="utf-8")
    return DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(file_path),
        text="placeholder\n",
        project_root=str(tmp_path),
        language=None,
    )


# ---------------------------------------------------------------------------
# 1. provider.py / parser.py existence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service_dir,_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_module_exists(service_dir: str, _cls: type, _path: str) -> None:
    assert (LINTERS_ROOT / service_dir / "provider.py").is_file()


@pytest.mark.parametrize(
    "service_dir,_cls,_path",
    _CASES_WITH_OWN_PARSER_MODULE,
    ids=_IDS_WITH_OWN_PARSER_MODULE,
)
def test_parser_module_exists(service_dir: str, _cls: type, _path: str) -> None:
    assert (LINTERS_ROOT / service_dir / "parser.py").is_file()


# ---------------------------------------------------------------------------
# 2. Provider class shape: name/enabled/supports/run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service_dir,provider_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_class_has_required_shape(
    service_dir: str, provider_cls: type, _path: str
) -> None:
    instance = provider_cls()
    assert isinstance(instance.name, str) and instance.name
    assert isinstance(instance.enabled, bool)
    assert callable(instance.supports)
    assert callable(instance.run)


@pytest.mark.parametrize(
    "service_dir,provider_cls,supported_path", PROVIDER_CASES, ids=_IDS
)
def test_provider_supports_its_representative_file(
    tmp_path: Path, service_dir: str, provider_cls: type, supported_path: str
) -> None:
    instance = provider_cls()
    request = _make_request(tmp_path, supported_path)
    assert instance.supports(request) is True, (
        f"{service_dir} provider does not support its own representative file"
    )


@pytest.mark.parametrize("service_dir,provider_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_does_not_support_unrelated_extension(
    tmp_path: Path, service_dir: str, provider_cls: type, _path: str
) -> None:
    instance = provider_cls()
    request = _make_request(tmp_path, "unrelated.veryunlikelyext")
    assert instance.supports(request) is False


# ---------------------------------------------------------------------------
# 3. Missing executable produces a controlled result, never raises
# ---------------------------------------------------------------------------

# Ruff's missing-executable handling is the pre-existing reference behavior
# (status="error", "Ruff executable not found in PATH.") and is intentionally
# preserved unchanged -- see tests/ui/test_diagnostics_panel.py's assertion
# on "Diagnostics failed: Ruff executable not found". Every other linter is a
# full-install-optional microservice: a missing executable there is a
# controlled "skipped" outcome per
# docs/architecture/ecli-f4-linter-microservices-design.md section 17.1, not
# a provider/runtime error.
_MISSING_EXECUTABLE_MAX_MESSAGE_LENGTH = 80


@pytest.mark.parametrize(
    "service_dir,provider_cls,supported_path", PROVIDER_CASES, ids=_IDS
)
def test_missing_executable_produces_controlled_result(
    tmp_path: Path, service_dir: str, provider_cls: type, supported_path: str
) -> None:
    instance = provider_cls(executable="ecli-definitely-not-a-real-binary-xyz")
    request = _make_request(tmp_path, supported_path)
    result = instance.run(request)
    assert isinstance(result, DiagnosticResult)
    expected_status = "error" if service_dir == "ruff" else "skipped"
    assert result.status == expected_status
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    "service_dir,provider_cls,supported_path",
    tuple(case for case in PROVIDER_CASES if case[0] != "ruff"),
    ids=[case[0] for case in PROVIDER_CASES if case[0] != "ruff"],
)
def test_missing_executable_message_is_concise_and_not_a_failure(
    tmp_path: Path, service_dir: str, provider_cls: type, supported_path: str
) -> None:
    """Missing-tool messages must read as a controlled skip, not a crash.

    Regression coverage: these messages must never be framed as
    "Diagnostics failed" (that prefix is reserved for the panel's
    status == "error" branch) and must stay short enough to fit the F4
    panel's one-line summary without being truncated illegibly.
    """
    instance = provider_cls(executable="ecli-definitely-not-a-real-binary-xyz")
    request = _make_request(tmp_path, supported_path)
    result = instance.run(request)
    assert not result.message.startswith("Diagnostics failed")
    assert not result.message.startswith("Diagnostics unavailable")
    assert len(result.message) <= _MISSING_EXECUTABLE_MAX_MESSAGE_LENGTH, (
        f"{service_dir}: missing-executable message is too long for the F4 "
        f"panel summary line: {result.message!r}"
    )
    assert "unavailable" in result.message
    assert "ECLI Full installation is incomplete" in result.message


# ---------------------------------------------------------------------------
# 4. Command safety: argv is list-only, no shell=True, in source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service_dir,_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_source_has_no_shell_true(
    service_dir: str, _cls: type, _path: str
) -> None:
    source = (LINTERS_ROOT / service_dir / "provider.py").read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "os.system(" not in source


@pytest.mark.parametrize("service_dir,_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_source_argv_uses_list_literals(
    service_dir: str, _cls: type, _path: str
) -> None:
    """Every ``argv``/``command`` assignment in provider.py is a list, not a string.

    Ruff's variable is named ``command`` (preserved verbatim from the
    pre-migration provider); every other provider uses ``argv``.
    """
    source = (LINTERS_ROOT / service_dir / "provider.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename=f"{service_dir}/provider.py")
    variable_names = {"command"} if service_dir == "ruff" else {"argv"}
    checked_any = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in variable_names
            for target in node.targets
        ):
            checked_any = True
            assert isinstance(node.value, ast.List | ast.Tuple), (
                f"{service_dir}: argv assignment is not a list/tuple literal"
            )
    assert checked_any, f"{service_dir}: no argv assignment found to check"


@pytest.mark.parametrize("service_dir,_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_declares_a_timeout(service_dir: str, _cls: type, _path: str) -> None:
    source = (LINTERS_ROOT / service_dir / "provider.py").read_text(encoding="utf-8")
    assert "timeout_seconds" in source


@pytest.mark.parametrize("service_dir,_cls,_path", PROVIDER_CASES, ids=_IDS)
def test_provider_does_not_mutate_files(
    service_dir: str, _cls: type, _path: str
) -> None:
    """No provider writes to disk: forbid common mutation APIs in provider.py."""
    source = (LINTERS_ROOT / service_dir / "provider.py").read_text(encoding="utf-8")
    for forbidden in ("open(", ".write(", ".write_text(", "--write", "--fix", "-i "):
        assert forbidden not in source, (
            f"{service_dir}: found mutating call {forbidden!r}"
        )
