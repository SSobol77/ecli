# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/textops.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Central, pure text utilities for copy / paste / selection.

These are the single source of truth for turning a buffer selection into
clipboard text (buffer content only — never UI chrome / line numbers / borders)
and for sanitising pasted text (strip bracketed-paste and ANSI control
sequences, normalise newlines) while preserving valid Unicode. They are
deliberately free of curses / editor state so they can be unit-tested directly.
"""

from __future__ import annotations

import re


# Bracketed-paste markers, then OSC, then CSI (SGR/cursor/etc.), then 2-char
# escapes. Stripping order matters so multi-byte sequences are removed whole.
_BRACKETED_PASTE = re.compile(r"\x1b\[20[01]~")
_ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_TWO_CHAR = re.compile(r"\x1b[@-Z\\-_]")
# Control characters except TAB (\t), LF (\n) and CR (\r, normalised later).
_FORBIDDEN_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_terminal_paste_sequences(text: str) -> str:
    r"""Remove bracketed-paste markers, ANSI escape sequences and stray control
    characters from *text*, while preserving printable Unicode, ``\\t`` and
    newlines. Never raises; never introduces replacement characters.
    """
    text = _BRACKETED_PASTE.sub("", text)
    text = _ANSI_OSC.sub("", text)
    text = _ANSI_CSI.sub("", text)
    text = _ANSI_TWO_CHAR.sub("", text)
    return _FORBIDDEN_CONTROL.sub("", text)


def normalize_paste_text(text: str) -> str:
    r"""Sanitise a paste payload: strip terminal control sequences and normalise
    ``\\r\\n`` / ``\\r`` to ``\\n``. Valid Unicode is preserved exactly.
    """
    text = strip_terminal_paste_sequences(text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def selection_to_text(
    buffer_lines: list[str],
    start: tuple[int, int],
    end: tuple[int, int],
) -> str:
    """Extract the selected text from logical buffer lines (buffer coords only).

    Returns only file content for the (row, col) span — never line numbers,
    gutter markers, borders or any UI chrome. Coordinates are clamped and
    normalised so start <= end. Multi-line selections preserve line breaks.
    """
    if not buffer_lines:
        return ""

    if start > end:
        start, end = end, start
    start_row, start_col = start
    end_row, end_col = end

    last = len(buffer_lines) - 1
    start_row = max(0, min(start_row, last))
    end_row = max(0, min(end_row, last))
    start_col = max(0, min(start_col, len(buffer_lines[start_row])))
    end_col = max(0, min(end_col, len(buffer_lines[end_row])))

    if start_row == end_row:
        return buffer_lines[start_row][start_col:end_col]

    parts = [buffer_lines[start_row][start_col:]]
    parts.extend(buffer_lines[start_row + 1 : end_row])
    parts.append(buffer_lines[end_row][:end_col])
    return "\n".join(parts)


def utf8_continuation_needed(data: bytes) -> int:
    """Return how many more bytes are needed to finish a trailing UTF-8 char.

    Used by the input layer to reassemble a multi-byte character whose bytes
    arrived split across reads (otherwise a lead byte like ``0xE2`` would be
    mis-decoded as Latin-1, producing mojibake such as U+00E2. Returns 0 when
    the data ends on a complete character or an invalid lead byte.
    """
    if not data:
        return 0
    i = len(data) - 1
    trailing = 0
    while i >= 0 and 0x80 <= data[i] <= 0xBF:
        trailing += 1
        i -= 1
    if i < 0:
        return 0  # only continuation bytes: nothing to anchor to
    lead = data[i]
    if lead < 0x80:
        return 0  # ASCII; complete
    if 0xC0 <= lead <= 0xDF:
        total = 2
    elif 0xE0 <= lead <= 0xEF:
        total = 3
    elif 0xF0 <= lead <= 0xF7:
        total = 4
    else:
        return 0  # invalid lead byte; do not block waiting for more
    return max(0, total - (trailing + 1))
