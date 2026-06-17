# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/utils/text_buffer.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Text-buffer conversion helpers for editor file I/O."""

from __future__ import annotations

import codecs
import logging
import re

import chardet


MIN_DETECTOR_CONFIDENCE = 0.80

# Logical line terminators recognised by the editor. Deliberately restricted to
# the three real end-of-line conventions (CRLF / CR / LF). ``str.splitlines()``
# additionally breaks on form-feed, vertical-tab, NEL and the Unicode line/para
# separators, which would silently split a single logical source line in two and
# corrupt the buffer (e.g. a ``.py`` file containing a ``\f`` page break).
_LINE_TERMINATOR_RE = re.compile(r"\r\n|\r|\n")
RISKY_LEGACY_ENCODINGS = frozenset(
    {
        "mac",
        "mac-cyrillic",
        "mac-roman",
        "mac_cyrillic",
        "mac_roman",
        "maccyrillic",
        "macintosh",
        "macroman",
    }
)


def split_text_preserving_content(raw: str) -> list[str]:
    r"""Split file text into logical lines, preserving every non-terminator byte.

    Only ``\r\n``, ``\r`` and ``\n`` are treated as line boundaries. Any other
    character that ``str.splitlines()`` would treat as a break (form-feed,
    vertical-tab, NEL, U+2028/U+2029, ...) is preserved inside the logical line so
    that a single source line never collapses or splits unexpectedly.

    A trailing terminator does not produce an extra empty line; that final-newline
    state is tracked separately by the caller.
    """
    if raw == "":
        return [""]

    result: list[str] = []
    position = 0
    for match in _LINE_TERMINATOR_RE.finditer(raw):
        result.append(raw[position : match.start()])
        position = match.end()
    if position < len(raw):
        result.append(raw[position:])
    return result


def detect_and_decode_text(raw_data: bytes) -> tuple[str, str]:
    """Decode editor text bytes using a deterministic UTF-8-first policy."""
    if raw_data.startswith(codecs.BOM_UTF8):
        return raw_data.decode("utf-8-sig", errors="strict"), "UTF-8"

    try:
        return raw_data.decode("utf-8", errors="strict"), "UTF-8"
    except UnicodeDecodeError:
        pass

    detector_result = chardet.detect(raw_data)
    encoding_guess = detector_result.get("encoding")
    confidence = float(detector_result.get("confidence") or 0.0)

    if encoding_guess and confidence >= MIN_DETECTOR_CONFIDENCE:
        normalized_guess = _normalize_detector_encoding(encoding_guess)
        if normalized_guess not in RISKY_LEGACY_ENCODINGS:
            try:
                decoded = raw_data.decode(encoding_guess, errors="strict")
            except (LookupError, UnicodeDecodeError) as exc:
                logging.warning(
                    "Rejected detected encoding %r with confidence %.2f: %s",
                    encoding_guess,
                    confidence,
                    exc,
                )
            else:
                return decoded, _canonical_encoding_label(encoding_guess)

    logging.warning(
        "Falling back to UTF-8 replacement decode after detector result %r "
        "with confidence %.2f.",
        encoding_guess,
        confidence,
    )
    return raw_data.decode("utf-8", errors="replace"), "UTF-8"


def _normalize_detector_encoding(encoding: str) -> str:
    return encoding.replace(" ", "").replace("_", "-").lower()


def _canonical_encoding_label(encoding: str) -> str:
    normalized = codecs.lookup(encoding).name.upper().replace("_", "-")
    if normalized in {"UTF-8", "UTF-8-SIG"}:
        return "UTF-8"
    if normalized == "CP1251":
        return "WINDOWS-1251"
    return normalized
