# tests/core/test_history_basic.py
"""History Basic Tests
========================

Unit tests for the History class (basic functionality).

This test module verifies that the History class:

1. Correctly records and clears individual actions.
2. Supports compound actions through `begin_compound_action` and `end_compound_action`.
3. Clears the redo stack (`_undone_actions`) whenever new actions are added,
   ensuring consistent undo/redo behavior.
"""

from types import SimpleNamespace

from ecli.core.History import History


def make_stub_editor():
    """Return a minimal stub editor object.

    The stub provides only the attributes required by History,
    without implementing any editor-specific logic.
    """
    return SimpleNamespace()


def test_add_and_clear():
    """Test: Adding actions and clearing the history.

    Verifies that:
    - Actions are appended to `_action_history`.
    - The redo stack (`_undone_actions`) is empty after adding actions.
    - Calling `clear()` resets both history and redo stacks.
    """
    h = History(make_stub_editor())  # type: ignore[arg-type]

    action1 = {"type": "insert", "text": "hello", "position": (0, 0)}
    action2 = {"type": "delete_char", "text": "h", "position": (0, 0)}

    h.add_action(action1)
    h.add_action(action2)

    assert h._action_history == [action1, action2]
    assert h._undone_actions == []

    h.clear()
    assert h._action_history == []
    assert h._undone_actions == []


def test_compound_action_stacks():
    """Test: Compound actions correctly manage history and redo stacks.

    Verifies that:
    - Actions grouped between `begin_compound_action` and `end_compound_action`
      are recorded properly in `_action_history`.
    - The redo stack (`_undone_actions`) is cleared after a compound action ends.
    - Adding a new action after ending a compound action also clears the redo stack.
    """
    h = History(make_stub_editor())  # type: ignore[arg-type]

    h.begin_compound_action()
    h.add_action({"type": "insert", "text": "A", "position": (0, 0)})
    h.add_action({"type": "insert", "text": "B", "position": (0, 1)})
    h.end_compound_action()

    # After ending a compound action, redo stack should be cleared
    assert len(h._action_history) == 2
    assert h._undone_actions == []

    # Adding another action clears redo stack again
    h.add_action({"type": "insert", "text": "C", "position": (0, 2)})
    assert h._undone_actions == []
