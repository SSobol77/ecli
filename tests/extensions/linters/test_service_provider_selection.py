# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/linters/test_service_provider_selection.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Provider applicability/selection tests for ``DiagnosticsService``.

These are the tests the previous Ruff-only architecture could not pass:
they prove F4 no longer runs an irrelevant provider (and shows its
irrelevant skip message) for a file type it does not handle, and that the
right provider is chosen per language/path. See
``docs/architecture/ecli-f4-linter-microservices-design.md`` section 7.2
("Applicability Rule") and section 15.3 ("Result Aggregation").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ecli.extensions.linters.actionlint.provider import ActionlintDiagnosticProvider
from ecli.extensions.linters.biome.provider import BiomeDiagnosticProvider
from ecli.extensions.linters.cargo_clippy.provider import CargoClippyDiagnosticProvider
from ecli.extensions.linters.clang_tidy.provider import ClangTidyDiagnosticProvider
from ecli.extensions.linters.core.models import DiagnosticRequest
from ecli.extensions.linters.core.service import DiagnosticsService
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


def _full_service() -> DiagnosticsService:
    service = DiagnosticsService()
    for provider in (
        RuffDiagnosticProvider(),
        MarkdownlintDiagnosticProvider(),
        YamllintDiagnosticProvider(),
        ShellCheckDiagnosticProvider(),
        BiomeDiagnosticProvider(),
        ZigDiagnosticProvider(),
        HadolintDiagnosticProvider(),
        TaploDiagnosticProvider(),
        ActionlintDiagnosticProvider(),
        ClangTidyDiagnosticProvider(),
        CppcheckDiagnosticProvider(),
        JavaCheckstyleDiagnosticProvider(),
        JavaPmdDiagnosticProvider(),
        CargoClippyDiagnosticProvider(),
    ):
        service.register_provider(provider)
    return service


def _buffer_request(
    tmp_path: Path, relative_path: str, *, language: str | None
) -> DiagnosticRequest:
    file_path = tmp_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("placeholder\n", encoding="utf-8")
    return DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(file_path),
        text="placeholder\n",
        project_root=str(tmp_path),
        language=language,
    )


def _applicable_names(
    service: DiagnosticsService, request: DiagnosticRequest
) -> list[str]:
    return sorted(
        provider.name
        for provider in service._enabled_providers()  # noqa: SLF001
        if service._provider_supports(provider, request)  # noqa: SLF001
    )


# ---------------------------------------------------------------------------
# 1. Ruff applicability
# ---------------------------------------------------------------------------


def test_ruff_supports_python_only(tmp_path: Path) -> None:
    provider = RuffDiagnosticProvider()
    request = _buffer_request(tmp_path, "a.py", language="python")
    assert provider.supports(request) is True


def test_ruff_does_not_support_markdown(tmp_path: Path) -> None:
    provider = RuffDiagnosticProvider()
    request = _buffer_request(tmp_path, "a.md", language="markdown")
    assert provider.supports(request) is False


def test_markdown_request_does_not_produce_ruff_only_skip(tmp_path: Path) -> None:
    """Regression test for the exact bug this task exists to fix."""
    service = _full_service()
    request = _buffer_request(tmp_path, "audit-report.md", language="markdown")
    result = service._run_providers(request)  # noqa: SLF001
    assert "Ruff diagnostics are only available for Python files" not in result.message
    assert (
        "markdownlint" in result.message.lower()
        or "markdownlint" in "".join(d.source for d in result.diagnostics)
        or result.message.startswith("Diagnostics unavailable: markdownlint-cli2")
    )


def test_markdown_request_uses_markdownlint_provider(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "audit-report.md", language="markdown")
    assert _applicable_names(service, request) == ["markdownlint-cli2"]


# ---------------------------------------------------------------------------
# 2. Per-language provider selection
# ---------------------------------------------------------------------------


def test_zig_request_uses_zig_provider(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "main.zig", language="zig")
    assert _applicable_names(service, request) == ["zig"]


def test_typescript_request_uses_biome_provider(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "app.ts", language="typescript")
    assert _applicable_names(service, request) == ["biome"]


def test_yaml_request_uses_yamllint_provider(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "config.yaml", language="yaml")
    assert "yamllint" in _applicable_names(service, request)


def test_github_workflow_yaml_can_use_actionlint(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, ".github/workflows/ci.yml", language="yaml")
    applicable = _applicable_names(service, request)
    assert "actionlint" in applicable
    assert "yamllint" in applicable


def test_random_yaml_does_not_use_actionlint(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "config/settings.yml", language="yaml")
    applicable = _applicable_names(service, request)
    assert "actionlint" not in applicable
    assert "yamllint" in applicable


@pytest.mark.parametrize("extension", ["c", "cc", "cpp", "cxx", "h", "hpp"])
def test_cpp_request_uses_clang_tidy_and_cppcheck(
    tmp_path: Path, extension: str
) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, f"main.{extension}", language="cpp")
    applicable = _applicable_names(service, request)
    assert "clang-tidy" in applicable
    assert "cppcheck" in applicable


def test_java_request_uses_checkstyle_and_pmd(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "Main.java", language="java")
    applicable = _applicable_names(service, request)
    assert "checkstyle" in applicable
    assert "pmd" in applicable


def test_dockerfile_request_uses_hadolint(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "Dockerfile", language="dockerfile")
    assert _applicable_names(service, request) == ["hadolint"]


def test_shell_request_uses_shellcheck(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "deploy.sh", language="shellscript")
    assert _applicable_names(service, request) == ["shellcheck"]


def test_toml_request_uses_taplo(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "pyproject.toml", language="toml")
    assert _applicable_names(service, request) == ["taplo"]


# ---------------------------------------------------------------------------
# 3. No applicable provider
# ---------------------------------------------------------------------------


def test_unsupported_file_type_reports_no_provider_available(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "notes.xyz", language=None)
    result = service._run_providers(request)  # noqa: SLF001
    assert result.status == "skipped"
    assert result.message == "No diagnostics provider available for this file type."


def test_rust_without_cargo_toml_reports_controlled_skip(tmp_path: Path) -> None:
    service = _full_service()
    request = _buffer_request(tmp_path, "lib.rs", language="rust")
    result = service._run_providers(request)  # noqa: SLF001
    assert result.status == "skipped"
    assert result.message == "Cargo Clippy requires a Cargo.toml crate root."
