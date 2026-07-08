# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/linters/test_provider_utils.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for shared provider helpers, focused on diagnostic file-path
normalization.

Regression coverage for the Biome TSX/CSS "Diagnostics: file not
available" bug: linter output frequently reports the target file as a
bare basename or a path relative to the tool's own working directory
instead of the exact path ECLI opened. ``Ecli.goto_diagnostic`` resolves
a relative ``Diagnostic.file_path`` against the *editor process's* cwd,
not the file's own directory, so an unresolved path silently breaks
Enter-jump even though the diagnostic belongs to the file currently open.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ecli.extensions.linters.biome.provider import BiomeDiagnosticProvider
from ecli.extensions.linters.core.models import DiagnosticRequest
from ecli.extensions.linters.core.provider_utils import normalize_diagnostic_file_path
from ecli.extensions.linters.markdownlint.provider import MarkdownlintDiagnosticProvider


# ---------------------------------------------------------------------------
# normalize_diagnostic_file_path -- pure unit tests
# ---------------------------------------------------------------------------


def test_normalize_empty_reported_path_returns_request_file_path(
    tmp_path: Path,
) -> None:
    request_file = tmp_path / "app" / "layout.tsx"
    assert normalize_diagnostic_file_path(None, request_file, tmp_path) == request_file
    assert normalize_diagnostic_file_path("", request_file, tmp_path) == request_file


def test_normalize_absolute_path_equal_to_request_file(tmp_path: Path) -> None:
    request_file = tmp_path / "app" / "layout.tsx"
    result = normalize_diagnostic_file_path(str(request_file), request_file, tmp_path)
    assert result == request_file


def test_normalize_absolute_path_that_exists_on_disk(tmp_path: Path) -> None:
    other_file = tmp_path / "other.ts"
    other_file.write_text("x", encoding="utf-8")
    request_file = tmp_path / "app" / "layout.tsx"
    result = normalize_diagnostic_file_path(str(other_file), request_file, tmp_path)
    assert result == other_file


def test_normalize_relative_path_resolves_against_cwd(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    request_file = app_dir / "layout.tsx"
    request_file.write_text("x", encoding="utf-8")

    result = normalize_diagnostic_file_path("app/layout.tsx", request_file, tmp_path)

    assert result == request_file
    assert result.is_absolute()


def test_normalize_relative_path_resolves_against_request_file_parent(
    tmp_path: Path,
) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    request_file = app_dir / "layout.tsx"
    sibling = app_dir / "layout.tsx.snap"
    sibling.write_text("x", encoding="utf-8")

    # No cwd provided; must still resolve via request_file_path.parent.
    result = normalize_diagnostic_file_path("layout.tsx.snap", request_file, None)

    assert result == sibling


def test_normalize_bare_basename_matching_request_file_name(tmp_path: Path) -> None:
    """The concrete Biome bug: tool reports only 'layout.tsx' / 'globals.css'."""
    request_file = tmp_path / "app" / "layout.tsx"
    result = normalize_diagnostic_file_path("layout.tsx", request_file, tmp_path)
    assert result == request_file

    css_request_file = tmp_path / "app" / "globals.css"
    css_result = normalize_diagnostic_file_path(
        "globals.css", css_request_file, tmp_path
    )
    assert css_result == css_request_file


def test_normalize_never_returns_a_bare_basename(tmp_path: Path) -> None:
    """Unresolvable, different-file diagnostics still get a joined path."""
    request_file = tmp_path / "app" / "layout.tsx"
    result = normalize_diagnostic_file_path(
        "components/unrelated.tsx", request_file, tmp_path
    )
    assert result.is_absolute()
    assert result != Path("components/unrelated.tsx")
    assert str(result) != "unrelated.tsx"


# ---------------------------------------------------------------------------
# Biome provider integration -- TSX / CSS
# ---------------------------------------------------------------------------


def _biome_stdout(basename: str, *, line: int, column: int) -> str:
    return json.dumps(
        {
            "diagnostics": [
                {
                    "category": "lint/style/useConst",
                    "severity": "warning",
                    "description": "Use const instead of let.",
                    "location": {
                        "path": {"file": basename},
                        "start": {"line": line, "column": column},
                    },
                }
            ]
        }
    )


def _fake_biome_runner(
    stdout: str,
) -> Any:
    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout=stdout, stderr="")

    return runner


def test_biome_tsx_diagnostic_file_path_resolves_to_request_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    target_file = app_dir / "layout.tsx"
    target_file.write_text("export default function Layout() {}\n", encoding="utf-8")

    monkeypatch.setattr(
        "ecli.extensions.linters.biome.provider.find_executable", lambda _: "biome"
    )
    provider = BiomeDiagnosticProvider(
        runner=_fake_biome_runner(_biome_stdout("layout.tsx", line=52, column=1))
    )
    request = DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(target_file),
        text=target_file.read_text(),
        project_root=str(tmp_path),
        language="typescriptreact",
    )

    result = provider.run(request)

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.file_path == str(target_file)
    assert diagnostic.file_path != "layout.tsx"


def test_biome_css_diagnostic_file_path_resolves_to_request_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    target_file = app_dir / "globals.css"
    target_file.write_text(":root { --x: 1; }\n", encoding="utf-8")

    monkeypatch.setattr(
        "ecli.extensions.linters.biome.provider.find_executable", lambda _: "biome"
    )
    provider = BiomeDiagnosticProvider(
        runner=_fake_biome_runner(_biome_stdout("globals.css", line=4, column=2))
    )
    request = DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(target_file),
        text=target_file.read_text(),
        project_root=str(tmp_path),
        language="css",
    )

    result = provider.run(request)

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.file_path == str(target_file)
    assert diagnostic.file_path != "globals.css"


# ---------------------------------------------------------------------------
# Markdown must not regress
# ---------------------------------------------------------------------------


def test_markdownlint_diagnostic_file_path_unchanged_when_already_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The markdownlint-cli2 tool already reports the exact path it was
    invoked with.

    Normalization must be a no-op here: it must not alter an already
    correct absolute path that matches the request file.
    """
    target_file = tmp_path / "audit-report.md"
    target_file.write_text("# report\n", encoding="utf-8")

    monkeypatch.setattr(
        "ecli.extensions.linters.markdownlint.provider.find_executable",
        lambda _: "markdownlint-cli2",
    )
    stdout = f"{target_file}:1 MD013/line-length Expected: 80; Actual: 90\n"
    provider = MarkdownlintDiagnosticProvider(
        runner=lambda command, **_kw: subprocess.CompletedProcess(
            command, 1, stdout=stdout, stderr=""
        )
    )
    request = DiagnosticRequest(
        generation=1,
        scope="buffer",
        file_path=str(target_file),
        text=target_file.read_text(),
        project_root=str(tmp_path),
        language="markdown",
    )

    result = provider.run(request)

    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].file_path == str(target_file)
