# tests/core/test_history_undo_redo.py
from ecli.core.History import History
from tests.stubs import StubEditor


def test_insert_undo_redo_single_line():
    ed = StubEditor()
    hist = History(ed)   # type: ignore[arg-type]

    # симулируем вставку "hello"
    ed.insert_text_at_position("hello", 0, 0)
    action = {"type": "insert", "text": "hello", "position": (0, 0)}
    hist.add_action(action)

    assert ed.text == ["hello"]

    # ---- undo ----
    changed = hist.undo()
    assert changed is True
    assert ed.text == [""]
    assert ed.cursor_y == 0 and ed.cursor_x == 0
    assert hist._undone_actions[-1]["type"] == "insert"

    # ---- redo ----
    changed = hist.redo()
    assert changed is True
    assert ed.text == ["hello"]
    assert ed.cursor_y == 0 and ed.cursor_x == 5
    assert hist._action_history[-1]["type"] == "insert"
