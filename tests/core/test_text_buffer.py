# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_text_buffer.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Focused tests for editor text-buffer line splitting."""

from __future__ import annotations

import codecs

import pytest

from ecli.utils import text_buffer
from ecli.utils.text_buffer import detect_and_decode_text, split_text_preserving_content


CYRILLIC_HEADER = (
    "# --- \u041f\u043e\u0442\u043e\u043a\u043e\u0431\u0435\u0437\u043e"
    "\u043f\u0430\u0441\u043d\u044b\u0439 \u043c\u0435\u043d\u0435"
    "\u0434\u0436\u0435\u0440 \u0441\u043e\u0441\u0442\u043e\u044f"
    "\u043d\u0438\u0439 ---\n"
)
CYRILLIC_DOC = (
    "    \u041a\u043b\u0430\u0441\u0441 \u0434\u043b\u044f \u0443"
    "\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f \u0441"
    "\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435\u043c \u0443"
    "\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432 \u0432 \u043f"
    "\u0430\u043c\u044f\u0442\u0438. \u041f\u043e\u0442\u043e\u043a"
    "\u043e\u0431\u0435\u0437\u043e\u043f\u0430\u0441\u0435\u043d.\n"
)
CYRILLIC_STATIC_COMMENT = (
    "    # \u0421\u0442\u0430\u0442\u0438\u0447\u0435\u0441"
    "\u043a\u0430\u044f \u0438\u043d\u0444\u043e\u0440\u043c"
    "\u0430\u0446\u0438\u044f \u043e\u0431 \u0443\u0441\u0442"
    "\u0440\u043e\u0439\u0441\u0442\u0432\u0430\u0445\n"
)
CYRILLIC_DYNAMIC_COMMENT = (
    "    # \u0414\u0438\u043d\u0430\u043c\u0438\u0447\u0435"
    "\u0441\u043a\u043e\u0435 \u0441\u043e\u0441\u0442\u043e"
    "\u044f\u043d\u0438\u0435\n"
)
CYRILLIC_HEADER_FRAGMENT = (
    "\u041f\u043e\u0442\u043e\u043a\u043e\u0431\u0435\u0437\u043e"
    "\u043f\u0430\u0441\u043d\u044b\u0439 \u043c\u0435\u043d\u0435"
    "\u0434\u0436\u0435\u0440"
)
CYRILLIC_BOM_SOURCE = (
    "# \u041f\u043e\u0442\u043e\u043a\u043e\u0431\u0435\u0437\u043e"
    "\u043f\u0430\u0441\u043d\u044b\u0439 \u043c\u0435\u043d\u0435"
    "\u0434\u0436\u0435\u0440\nclass DeviceManager:\n    pass\n"
)
CYRILLIC_WINDOWS_1251_SOURCE = (
    "# \u0421\u0442\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0430"
    "\u044f \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438"
    "\u044f \u043e\u0431 \u0443\u0441\u0442\u0440\u043e\u0439"
    "\u0441\u0442\u0432\u0430\u0445\n"
)


def test_split_text_preserves_whitespace_except_lf_terminators() -> None:
    raw = "    indented    \n\t    mixed\n    \nno-newline    "

    assert split_text_preserving_content(raw) == [
        "    indented    ",
        "\t    mixed",
        "    ",
        "no-newline    ",
    ]


def test_split_text_preserves_whitespace_except_crlf_terminators() -> None:
    raw = "class Example:\r\n    def method(self):    \r\n\treturn None\r\n"

    assert split_text_preserving_content(raw) == [
        "class Example:",
        "    def method(self):    ",
        "\treturn None",
    ]


def test_split_text_empty_file_model_is_single_empty_line() -> None:
    assert split_text_preserving_content("") == [""]


def test_split_text_does_not_break_on_form_feed_page_break() -> None:
    # A form feed (\x0c) is a legal in-line character in Python source. It must
    # stay inside a single logical line, not split it the way str.splitlines does.
    raw = "x = 1\x0cy = 2"

    assert split_text_preserving_content(raw) == ["x = 1\x0cy = 2"]


def test_split_text_does_not_break_on_exotic_unicode_separators() -> None:
    # Vertical tab, NEL and the Unicode line/paragraph separators are content,
    # not editor line boundaries.
    for separator in ("\x0b", "\x85", " ", " ", "\x1c", "\x1d", "\x1e"):
        raw = f"left{separator}right"
        assert split_text_preserving_content(raw) == [f"left{separator}right"]


def test_split_text_mixed_real_and_exotic_terminators() -> None:
    raw = "a\nb\x0cstill-b\r\nc"

    assert split_text_preserving_content(raw) == ["a", "b\x0cstill-b", "c"]


def test_detect_and_decode_prefers_strict_utf8_for_cyrillic_source() -> None:
    source = "".join(
        [
            CYRILLIC_HEADER,
            "class DeviceManager:\n",
            '    """\n',
            CYRILLIC_DOC,
            '    """\n',
            CYRILLIC_STATIC_COMMENT,
            CYRILLIC_DYNAMIC_COMMENT,
        ]
    )

    decoded, label = detect_and_decode_text(source.encode("utf-8"))

    assert decoded == source
    assert label == "UTF-8"
    assert CYRILLIC_HEADER_FRAGMENT in decoded
    assert "MACROMAN" not in label


def test_detect_and_decode_utf8_bom_does_not_expose_bom_character() -> None:
    source = CYRILLIC_BOM_SOURCE

    decoded, label = detect_and_decode_text(codecs.BOM_UTF8 + source.encode("utf-8"))

    assert decoded == source
    assert not decoded.startswith("\ufeff")
    assert label == "UTF-8"


def test_detect_and_decode_accepts_high_confidence_windows_1251_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = CYRILLIC_WINDOWS_1251_SOURCE
    raw = source.encode("windows-1251")
    monkeypatch.setattr(
        text_buffer.chardet,
        "detect",
        lambda _raw: {"encoding": "windows-1251", "confidence": 0.99},
    )

    decoded, label = detect_and_decode_text(raw)

    assert decoded == source
    assert label == "WINDOWS-1251"
