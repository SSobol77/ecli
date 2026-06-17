# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_file_roundtrip_stability.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Regression coverage for the editor save/load round-trip.

These tests exercise the *real* ``open_file`` -> modify -> ``save_file`` ->
reopen path (the same path ``Ctrl+S`` uses) and assert that logical lines never
collapse into a single line and that newline separators survive on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ecli.core.Ecli import Ecli


class FakeHistory:
    def clear(self) -> None:
        return None

    def add_action(self, _action: dict[str, Any]) -> None:
        return None


def make_editor() -> Ecli:
    editor = Ecli.__new__(Ecli)
    editor.text = [""]
    editor.cursor_x = 0
    editor.cursor_y = 0
    editor.scroll_top = 0
    editor.scroll_left = 0
    editor.modified = False
    editor.encoding = "utf-8"
    editor.filename = None
    editor.status_message = "Ready"
    editor.is_selecting = False
    editor.selection_start = None
    editor.selection_end = None
    editor.highlighted_matches = []
    editor.search_matches = []
    editor.search_term = ""
    editor.current_match_idx = -1
    editor.history = FakeHistory()
    editor.git = None
    editor.git_panel_instance = None
    editor._lexer = None
    editor.current_language = None
    editor.custom_syntax_patterns = []
    editor.colors = {"default": 0}
    editor.config = {}
    editor.is_256_color_terminal = True
    editor._force_full_redraw = False
    editor._file_loaded_from_disk = False
    editor._file_had_final_newline = False
    # Keep the linter thread from doing real work during tests.
    editor.run_lint_async = lambda *_a, **_k: False  # type: ignore[method-assign]
    return editor


PY_LINES = [
    "import os",
    "",
    "",
    "def main() -> None:",
    '    x = {"a": 1, "b": 2}',
    "    for key, value in x.items():",
    "        print(key, value)",
    "",
    "",
    "if __name__ == '__main__':",
    "    main()",
]


def _open_modify_save_reopen(tmp_path: Path, raw: bytes, name: str) -> Ecli:
    """Open ``raw`` bytes, flag the buffer modified, save, then reopen."""
    source = tmp_path / name
    source.write_bytes(raw)

    editor = make_editor()
    assert editor.open_file(str(source)) is True
    loaded_after_open = list(editor.text)

    # Force the real write path: ``save_file`` short-circuits when not modified.
    editor.modified = True
    assert editor.save_file() is True

    reopened = make_editor()
    assert reopened.open_file(str(source)) is True
    # Stash the post-open snapshot for callers that want it.
    reopened._loaded_after_first_open = loaded_after_open  # type: ignore[attr-defined]
    return reopened


def test_roundtrip_lf_with_final_newline_keeps_lines_separate(tmp_path: Path) -> None:
    raw = ("\n".join(PY_LINES) + "\n").encode("utf-8")
    editor = _open_modify_save_reopen(tmp_path, raw, "lf.py")

    assert editor.text == PY_LINES
    assert len(editor.text) == len(PY_LINES)
    # No single-line collapse.
    assert len(editor.text) > 1


def test_roundtrip_lf_without_final_newline(tmp_path: Path) -> None:
    raw = "\n".join(PY_LINES).encode("utf-8")
    editor = _open_modify_save_reopen(tmp_path, raw, "lf_no_final.py")

    assert editor.text == PY_LINES
    assert len(editor.text) == len(PY_LINES)


def test_roundtrip_crlf_normalizes_to_lf_without_collapse(tmp_path: Path) -> None:
    raw = ("\r\n".join(PY_LINES) + "\r\n").encode("utf-8")
    editor = _open_modify_save_reopen(tmp_path, raw, "crlf.py")

    # The important guarantee: lines stay separate (no collapse, no doubling).
    assert editor.text == PY_LINES
    assert len(editor.text) == len(PY_LINES)


def test_saved_file_on_disk_contains_newline_separators(tmp_path: Path) -> None:
    raw = ("\n".join(PY_LINES) + "\n").encode("utf-8")
    source = tmp_path / "disk.py"
    source.write_bytes(raw)

    editor = make_editor()
    assert editor.open_file(str(source)) is True
    editor.modified = True
    assert editor.save_file() is True

    on_disk = source.read_bytes()
    assert b"\n" in on_disk
    # The file must not be a single physical line.
    assert on_disk.count(b"\n") >= len(PY_LINES) - 1
    # Lines must remain individually recoverable.
    assert source.read_text(encoding="utf-8").split("\n")[0] == "import os"


def test_roundtrip_form_feed_line_stays_single_logical_line(tmp_path: Path) -> None:
    # A .py file whose single logical line embeds a form-feed must not be split
    # into two lines on open, nor corrupted into two real lines after save.
    lines = ["import os", "x = 1\x0cy = 2", "print(x, y)"]
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    editor = _open_modify_save_reopen(tmp_path, raw, "formfeed.py")

    assert editor.text == lines
    assert editor.text[1] == "x = 1\x0cy = 2"
    assert len(editor.text) == 3


def test_new_buffer_save_then_reopen_keeps_lines(tmp_path: Path) -> None:
    target = tmp_path / "fresh.py"
    editor = make_editor()
    editor.text = list(PY_LINES)
    editor.filename = str(target)
    editor.encoding = "utf-8"
    editor._file_loaded_from_disk = False
    editor._file_had_final_newline = False
    editor.modified = True

    assert editor.save_file() is True

    reopened = make_editor()
    assert reopened.open_file(str(target)) is True
    assert reopened.text == PY_LINES
    assert len(reopened.text) == len(PY_LINES)
