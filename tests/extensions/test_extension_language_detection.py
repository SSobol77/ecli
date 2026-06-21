# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_extension_language_detection.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for deterministic language detection (#101).

Detection is metadata-only: it maps file names/extensions/exact-filenames/
filename-patterns to language ids using #100 registry data, with deterministic
precedence and explicit ambiguity. These tests cover representative extensions,
precedence, case handling, unknown input, and deterministic ambiguity (via temp
fixtures). They never read file contents or render syntax.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from ecli.extensions.ecli_integration import (
    LanguageDetector,
    build_language_detector,
)


REPRESENTATIVE_EXTENSIONS = (
    ("main.py", "python"),
    ("data.json", "json"),
    ("app.js", "javascript"),
    ("app.ts", "typescript"),
    ("README.md", "markdown"),
    ("core.c", "c"),
    ("core.cpp", "cpp"),
    ("core.h", "cpp"),
    ("run.bat", "bat"),
)


@pytest.fixture(scope="module")
def detector() -> LanguageDetector:
    return build_language_detector()


def _make_extension(root: Path, name: str, manifest: Mapping[str, object]) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


# --------------------------------------------------------------------------- #
# Real imported tree.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("file_name", "expected"), REPRESENTATIVE_EXTENSIONS)
def test_representative_extension_detection(
    detector: LanguageDetector, file_name: str, expected: str
) -> None:
    result = detector.detect(file_name)
    assert result.matched
    assert result.language_id == expected
    assert result.matched_by == "extension"


def test_exact_filename_detection(detector: LanguageDetector) -> None:
    # 'SConstruct' is a real exact-filename rule for python in the imported tree.
    result = detector.detect("SConstruct")
    assert result.language_id == "python"
    assert result.matched_by == "filename"


def test_filename_pattern_detection(detector: LanguageDetector) -> None:
    # 'tsconfig.*.json' is a real filename pattern in the imported tree.
    result = detector.detect("tsconfig.build.json")
    assert result.language_id == "jsonc"
    assert result.matched_by == "filename_pattern"


def test_exact_filename_beats_extension(detector: LanguageDetector) -> None:
    # 'tsconfig.json' is both an exact filename (jsonc) and a '.json' extension.
    result = detector.detect("tsconfig.json")
    assert result.language_id == "jsonc"
    assert result.matched_by == "filename"


def test_extension_detection_is_case_insensitive(detector: LanguageDetector) -> None:
    assert detector.detect("Main.PY").language_id == "python"
    assert detector.detect("Main.py").language_id == "python"
    assert detector.detect_by_extension(".PY").language_id == "python"
    assert detector.detect_by_extension("py").language_id == "python"


def test_detection_handles_full_paths(detector: LanguageDetector) -> None:
    assert detector.detect("/home/user/project/main.py").language_id == "python"
    assert detector.detect("C:\\src\\app.ts").language_id == "typescript"


def test_unknown_extension_returns_no_match(detector: LanguageDetector) -> None:
    result = detector.detect("archive.zzz")
    assert not result.matched
    assert result.language_id is None
    assert result.candidates == ()


def test_no_extension_does_not_crash(detector: LanguageDetector) -> None:
    result = detector.detect("PLAINFILE_NO_RULE")
    assert not result.matched


# --------------------------------------------------------------------------- #
# Deterministic ambiguity via fixtures.
# --------------------------------------------------------------------------- #


def test_conflicting_extension_is_deterministically_ambiguous(tmp_path: Path) -> None:
    # Two extensions claim '.shared'; directory-name ordering is deterministic.
    _make_extension(
        tmp_path,
        "a_alpha",
        {
            "name": "a_alpha",
            "contributes": {"languages": [{"id": "alpha", "extensions": [".shared"]}]},
        },
    )
    _make_extension(
        tmp_path,
        "b_beta",
        {
            "name": "b_beta",
            "contributes": {"languages": [{"id": "beta", "extensions": [".shared"]}]},
        },
    )
    from ecli.extensions.ecli_integration import build_registry

    detector = build_language_detector(build_registry(root=tmp_path))
    first = detector.detect("thing.shared")
    second = detector.detect("thing.shared")

    assert first.is_ambiguous
    assert first.candidates == ("alpha", "beta")
    assert first.language_id == "alpha"
    assert first == second
