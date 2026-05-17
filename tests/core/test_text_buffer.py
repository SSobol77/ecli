# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/core/test_text_buffer.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Focused tests for editor text-buffer line splitting."""

from __future__ import annotations

import codecs

import pytest

import ecli.utils.text_buffer as text_buffer
from ecli.utils.text_buffer import detect_and_decode_text, split_text_preserving_content


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


def test_detect_and_decode_prefers_strict_utf8_for_cyrillic_source() -> None:
    source = (
        "# --- Потокобезопасный менеджер состояний ---\n"
        "class DeviceManager:\n"
        "    \"\"\"\n"
        "    Класс для управления состоянием устройств в памяти. Потокобезопасен.\n"
        "    \"\"\"\n"
        "    # Статическая информация об устройствах\n"
        "    # Динамическое состояние\n"
    )

    decoded, label = detect_and_decode_text(source.encode("utf-8"))

    assert decoded == source
    assert label == "UTF-8"
    assert "Потокобезопасный менеджер" in decoded
    assert "MACROMAN" not in label


def test_detect_and_decode_utf8_bom_does_not_expose_bom_character() -> None:
    source = "# Потокобезопасный менеджер\nclass DeviceManager:\n    pass\n"

    decoded, label = detect_and_decode_text(codecs.BOM_UTF8 + source.encode("utf-8"))

    assert decoded == source
    assert not decoded.startswith("\ufeff")
    assert label == "UTF-8"


def test_detect_and_decode_accepts_high_confidence_windows_1251_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "# Статическая информация об устройствах\n"
    raw = source.encode("windows-1251")
    monkeypatch.setattr(
        text_buffer.chardet,
        "detect",
        lambda _raw: {"encoding": "windows-1251", "confidence": 0.99},
    )

    decoded, label = detect_and_decode_text(raw)

    assert decoded == source
    assert label == "WINDOWS-1251"
