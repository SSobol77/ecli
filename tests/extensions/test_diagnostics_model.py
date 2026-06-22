# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_model.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Unit tests for the deterministic diagnostics data model (#104)."""

from __future__ import annotations

import pytest

from ecli.extensions.ecli_integration.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    DiagnosticsState,
    DiagnosticsStatus,
    sort_diagnostics,
)


def _diag(
    file_path: str = "a.py",
    line: int = 1,
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING,
    column: int | None = 1,
    code: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        file_path=file_path,
        line=line,
        severity=severity,
        source="ruff",
        message=code or "msg",
        column=column,
        code=code,
    )


# --------------------------------------------------------------------------- #
# Severity normalization.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (DiagnosticSeverity.ERROR, DiagnosticSeverity.ERROR),
        ("error", DiagnosticSeverity.ERROR),
        ("ERROR", DiagnosticSeverity.ERROR),
        ("warning", DiagnosticSeverity.WARNING),
        ("warn", DiagnosticSeverity.WARNING),
        ("info", DiagnosticSeverity.INFO),
        ("convention", DiagnosticSeverity.INFO),
        ("refactor", DiagnosticSeverity.HINT),
        ("hint", DiagnosticSeverity.HINT),
        (1, DiagnosticSeverity.ERROR),
        (2, DiagnosticSeverity.WARNING),
        (3, DiagnosticSeverity.INFO),
        (4, DiagnosticSeverity.HINT),
        ("E501", DiagnosticSeverity.WARNING),
        ("F401", DiagnosticSeverity.WARNING),
        ("C901", DiagnosticSeverity.INFO),
        ("N802", DiagnosticSeverity.INFO),
    ],
)
def test_severity_normalization(value: object, expected: DiagnosticSeverity) -> None:
    assert DiagnosticSeverity.normalize(value) is expected


@pytest.mark.parametrize("value", [None, "", "mystery", object(), True, 99, -1])
def test_unknown_severity_defaults_to_warning(value: object) -> None:
    assert DiagnosticSeverity.normalize(value) is DiagnosticSeverity.WARNING


def test_severity_labels_are_stable() -> None:
    assert DiagnosticSeverity.ERROR.label == "ERROR"
    assert DiagnosticSeverity.WARNING.label == "WARN"
    assert DiagnosticSeverity.INFO.label == "INFO"
    assert DiagnosticSeverity.HINT.label == "HINT"


def test_severity_orders_most_severe_first() -> None:
    ordered = sorted(DiagnosticSeverity)
    assert ordered == [
        DiagnosticSeverity.ERROR,
        DiagnosticSeverity.WARNING,
        DiagnosticSeverity.INFO,
        DiagnosticSeverity.HINT,
    ]


# --------------------------------------------------------------------------- #
# Deterministic sorting.
# --------------------------------------------------------------------------- #


def test_sort_orders_by_severity_then_path_line_column_message() -> None:
    unsorted = [
        _diag("b.py", 2, DiagnosticSeverity.WARNING, 1, "W1"),
        _diag("a.py", 1, DiagnosticSeverity.ERROR, 3, "E2"),
        _diag("a.py", 1, DiagnosticSeverity.ERROR, None, "E1"),
        _diag("a.py", 1, DiagnosticSeverity.INFO, 1, "I1"),
    ]
    ordered = sort_diagnostics(unsorted)
    # severity rank first (ERROR < WARNING < INFO), then path/line/column/message.
    assert [diag.code for diag in ordered] == ["E1", "E2", "W1", "I1"]


def test_sort_is_deterministic_regardless_of_input_order() -> None:
    a = _diag("a.py", 1, DiagnosticSeverity.ERROR, 1, "E1")
    b = _diag("a.py", 1, DiagnosticSeverity.ERROR, 2, "E2")
    assert sort_diagnostics([a, b]) == sort_diagnostics([b, a])


def test_missing_column_sorts_before_known_columns() -> None:
    no_col = _diag("a.py", 5, DiagnosticSeverity.ERROR, None, "E0")
    col_one = _diag("a.py", 5, DiagnosticSeverity.ERROR, 1, "E1")
    assert sort_diagnostics([col_one, no_col])[0] is no_col


# --------------------------------------------------------------------------- #
# Diagnostic helpers.
# --------------------------------------------------------------------------- #


def test_location_includes_column_when_present() -> None:
    assert _diag("a.py", 12, column=4).location == "a.py:12:4"


def test_location_omits_column_when_absent() -> None:
    assert _diag("a.py", 12, column=None).location == "a.py:12"


# --------------------------------------------------------------------------- #
# State factories and counts.
# --------------------------------------------------------------------------- #


def test_from_diagnostics_sets_ok_and_sorts() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff",
        "a.py",
        [
            _diag("a.py", 2, DiagnosticSeverity.WARNING, 1, "W1"),
            _diag("a.py", 1, DiagnosticSeverity.ERROR, 1, "E1"),
        ],
    )
    assert state.status is DiagnosticsStatus.OK
    assert [diag.code for diag in state.diagnostics] == ["E1", "W1"]
    assert state.has_diagnostics is True


def test_from_diagnostics_with_empty_list_is_no_diagnostics() -> None:
    state = DiagnosticsState.from_diagnostics("ruff", "a.py", [])
    assert state.status is DiagnosticsStatus.NO_DIAGNOSTICS
    assert state.total == 0
    assert state.has_diagnostics is False


def test_counts_per_severity() -> None:
    state = DiagnosticsState.from_diagnostics(
        "ruff",
        "a.py",
        [
            _diag(severity=DiagnosticSeverity.ERROR),
            _diag(severity=DiagnosticSeverity.ERROR),
            _diag(severity=DiagnosticSeverity.WARNING),
            _diag(severity=DiagnosticSeverity.INFO),
            _diag(severity=DiagnosticSeverity.HINT),
        ],
    )
    assert state.total == 5
    assert state.error_count == 2
    assert state.warning_count == 1
    assert state.info_count == 1
    assert state.hint_count == 1


def test_empty_state_factories() -> None:
    assert DiagnosticsState.disabled().status is DiagnosticsStatus.DISABLED
    assert DiagnosticsState.no_active_file().status is DiagnosticsStatus.NO_ACTIVE_FILE
    outside = DiagnosticsState.outside_workspace("/etc/x.py", "outside")
    assert outside.status is DiagnosticsStatus.OUTSIDE_WORKSPACE
    assert outside.file_path == "/etc/x.py"
    assert DiagnosticsState.unreadable().status is DiagnosticsStatus.UNREADABLE
    unsupported = DiagnosticsState.unsupported("a.css", "no provider", "use ruff")
    assert unsupported.status is DiagnosticsStatus.UNSUPPORTED
    assert unsupported.hint == "use ruff"
    missing = DiagnosticsState.provider_unavailable("ruff", "missing")
    assert missing.status is DiagnosticsStatus.PROVIDER_UNAVAILABLE
    assert missing.detail == "missing"
    assert DiagnosticsState.collecting().status is DiagnosticsStatus.COLLECTING
    assert DiagnosticsState.error("ruff", "boom").status is DiagnosticsStatus.ERROR


def test_state_is_immutable() -> None:
    state = DiagnosticsState.no_active_file()
    with pytest.raises((AttributeError, TypeError)):
        state.status = DiagnosticsStatus.OK  # type: ignore[misc]
