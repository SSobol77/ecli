# tests/ui/test_keybinder.py
"""Unit tests for the `KeyBinder` class.
========================================

Tests for the `KeyBinder` class.

This module isolates and verifies the `lookup` method behavior by patching
internal dependencies (`_load_keybindings`, `_decode_keystring`, and
`_setup_action_map`). By stubbing those internals, the test does not require
a fully mocked `Ecli` editor nor a real terminal/curses environment.
"""

from unittest.mock import MagicMock, patch

# Import KeyBinder directly for testing
from ecli.ui.KeyBinder import KeyBinder


@patch("ecli.ui.KeyBinder.curses", MagicMock())  # Globally mock `curses` for safety
def test_keybinder_lookup() -> None:
    """Validate `lookup` behavior in full isolation.

    Strategy:
    - Replace `_load_keybindings` to supply a deterministic in-memory mapping.
    - Replace `_decode_keystring` with a tiny decoder that returns known codes.
    - Replace `_setup_action_map` with a harmless noop to avoid side-effects.

    This allows us to test `lookup` without constructing a complex `Ecli` mock
    and without invoking unrelated initialization paths.
    """
    # 1. Minimal editor stub: only `config` is needed so `__init__` won't fail.
    mock_editor = MagicMock()
    mock_editor.config = {}

    # 2. Provide deterministic return values for the patched internals.

    # Returned instead of executing the real `_load_keybindings`.
    test_keybindings = {
        "save_file": [19],  # ctrl+s
        "quit": [17, 27],  # ctrl+q, esc
        "help": [-201],  # f1
    }

    # Minimal replacement for `_decode_keystring` used by `lookup`.
    def simple_decoder(key_spec: str) -> str | int:
        """Very small decoder that maps a few human-readable specs to codes.

        Unknown keys are returned as-is to exercise the "not found" branch.
        """
        if key_spec == "ctrl+s":
            return 19
        if key_spec == "ctrl+q":
            return 17
        if key_spec == "esc":
            return 27
        if key_spec == "f1":
            return -201
        # For unknown keys, return the original string to test the miss path
        return key_spec

    # 3. Apply patches.
    with (
        patch.object(KeyBinder, "_load_keybindings", return_value=test_keybindings),
        patch.object(KeyBinder, "_decode_keystring", side_effect=simple_decoder),
        patch.object(KeyBinder, "_setup_action_map", return_value={}),
    ):
        # NOTE: We also bypass `_setup_action_map` since it is irrelevant for this
        # test and can trigger unrelated errors inside complex initialization.
        # With the patches in place, `__init__` remains safe and deterministic.

        kb = KeyBinder(editor=mock_editor)

        # 4) Ensure the in-memory bindings were adopted.
        assert kb.keybindings == test_keybindings

        # 5) Verify `lookup` uses our `simple_decoder`-driven key specs.
        assert kb.lookup("ctrl+s") == "save_file"
        assert kb.lookup("esc") == "quit"
        assert kb.lookup("ctrl+q") == "quit"
        assert kb.lookup("f1") == "help"

        # Misses: unknown keys should return None
        assert kb.lookup("f12") is None
        assert kb.lookup("non-existent_key") is None
