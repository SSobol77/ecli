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

import chardet


MIN_DETECTOR_CONFIDENCE = 0.80
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
    """Preserve every character except line terminators."""
    if raw == "":
        return [""]

    lines = raw.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        if line.endswith("\r\n"):
            result.append(line[:-2])
        elif line.endswith("\n") or line.endswith("\r"):
            result.append(line[:-1])
        else:
            result.append(line)
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
