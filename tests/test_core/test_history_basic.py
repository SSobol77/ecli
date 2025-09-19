# tests/core/test_history_basic.py
from types import SimpleNamespace

from ecli.core.History import History


def make_stub_editor():
    """Возвращает минимальный объект с полями,
    которые могут коснуться begin/end/add_action (их там нет).
    """
    return SimpleNamespace()

def test_add_and_clear():
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
    h = History(make_stub_editor())  # type: ignore[arg-type]

    h.begin_compound_action()
    h.add_action({"type": "insert", "text": "A", "position": (0, 0)})
    h.add_action({"type": "insert", "text": "B", "position": (0, 1)})
    h.end_compound_action()

    # после end_compound_action redo‑стек очищен
    assert len(h._action_history) == 2
    assert h._undone_actions == []

    # если добавить ещё один action – redo снова чистится
    h.add_action({"type": "insert", "text": "C", "position": (0, 2)})
    assert h._undone_actions == []
