# tests/core/test_history_undo_redo.py
"""History Undo/Redo Tests
==========================

Unit tests for undo and redo functionality in the History class.

This module focuses on verifying that insert actions can be:
1. Undone — restoring the editor state to its prior content.
2. Redone — reapplying the action and restoring the text.
"""

from ecli.core.History import History
from tests.stubs import StubEditor


def test_insert_undo_redo_single_line():
    """Test: Insert action followed by undo and redo.

    This test simulates inserting the text `"hello"` into an empty editor.
    It then verifies that:
    - The action is recorded correctly in history.
    - Undo removes the inserted text and resets the cursor.
    - Redo re-applies the insertion, restoring the text and cursor position.
    """
    ed = StubEditor()
    hist = History(ed)  # type: ignore[arg-type]

    # Simulate inserting the string "hello" at the beginning of the buffer
    ed.insert_text_at_position("hello", 0, 0)
    action = {"type": "insert", "text": "hello", "position": (0, 0)}
    hist.add_action(action)

    assert ed.text == ["hello"]

    # ---- Undo the insert ----
    changed = hist.undo()
    assert changed is True
    assert ed.text == [""]
    assert ed.cursor_y == 0 and ed.cursor_x == 0
    assert hist._undone_actions[-1]["type"] == "insert"

    # ---- Redo the insert ----
    changed = hist.redo()
    assert changed is True
    assert ed.text == ["hello"]
    assert ed.cursor_y == 0 and ed.cursor_x == 5
    assert hist._action_history[-1]["type"] == "insert"
