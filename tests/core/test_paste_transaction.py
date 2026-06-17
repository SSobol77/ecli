# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_paste_transaction.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for bracketed-paste / clipboard insertion as a single transaction."""

from __future__ import annotations

import time
from threading import RLock
from typing import Any, cast

from ecli.core.Ecli import Ecli
from ecli.core.History import History


def make_editor(lines: list[str]) -> Ecli:
    editor = Ecli.__new__(Ecli)
    editor.text = list(lines)
    editor.cursor_x = 0
    editor.cursor_y = 0
    editor.scroll_top = 0
    editor.scroll_left = 0
    editor.modified = False
    editor.is_selecting = False
    editor.selection_start = None
    editor.selection_end = None
    editor.status_message = "Ready"
    editor.internal_clipboard = ""
    editor._state_lock = RLock()
    editor.history = History(cast(Any, editor))
    editor._set_status_message = lambda msg, *a, **k: setattr(  # type: ignore[method-assign]
        editor, "status_message", msg
    )
    return editor


def test_paste_inserts_multiple_lines_not_flattened() -> None:
    editor = make_editor([""])
    assert editor.insert_pasted_text("L1\nL2\nL3") is True
    assert editor.text[:3] == ["L1", "L2", "L3"]
    assert len(editor.text) >= 3  # not collapsed into one line


def test_paste_crlf_is_normalized() -> None:
    editor = make_editor([""])
    editor.insert_pasted_text("a\r\nb\r\nc")
    assert editor.text[:3] == ["a", "b", "c"]


def test_paste_bare_cr_is_normalized() -> None:
    editor = make_editor([""])
    editor.insert_pasted_text("a\rb\rc")
    assert editor.text[:3] == ["a", "b", "c"]


def test_paste_preserves_indentation_without_extra_auto_indent() -> None:
    editor = make_editor([""])
    editor.insert_pasted_text("def f():\n    return 1\n        deep = 2")
    assert editor.text[0] == "def f():"
    assert editor.text[1] == "    return 1"
    assert editor.text[2] == "        deep = 2"


def test_paste_is_single_undo_unit() -> None:
    editor = make_editor([""])
    editor.insert_pasted_text("a\nb\nc\nd")
    # Exactly one 'insert' action carrying the whole payload (one undo step).
    assert len(editor.history._action_history) == 1
    action = editor.history._action_history[0]
    assert action["type"] == "insert"
    assert action["text"] == "a\nb\nc\nd"


def test_paste_does_not_execute_shortcut_text() -> None:
    editor = make_editor([""])
    payload = "import os\nsave\nquit\nfind\nctrl+s"
    editor.insert_pasted_text(payload)
    # Shortcut-looking lines are inserted verbatim, never dispatched as actions.
    assert "save" in editor.text
    assert "quit" in editor.text
    assert "ctrl+s" in editor.text
    assert len(editor.history._action_history) == 1


def test_large_paste_completes_as_one_transaction() -> None:
    editor = make_editor([""])
    payload = "\n".join(f"line{i:03d}" for i in range(200))

    start = time.perf_counter()
    assert editor.insert_pasted_text(payload) is True
    elapsed = time.perf_counter() - start

    assert editor.text[:200] == [f"line{i:03d}" for i in range(200)]
    # One transaction, not 200 per-character/per-line actions.
    assert len(editor.history._action_history) == 1
    assert elapsed < 2.0


def test_empty_paste_is_noop() -> None:
    editor = make_editor(["x"])
    assert editor.insert_pasted_text("") is False
    assert editor.text == ["x"]
    assert len(editor.history._action_history) == 0
