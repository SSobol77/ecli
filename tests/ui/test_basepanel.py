# tests/ui/test_basepanel.py
"""Test suite for the BasePanel class.
======================================

Tests for the `BasePanel` class.

This module verifies the base functionality common to all panels:
- Initialization and default state
- Visibility management via `open()` and `close()`
- Enforcement of abstract methods (`draw`, `handle_key`)
"""

from unittest.mock import MagicMock

import pytest

from ecli.ui.panels import BasePanel


class TestBasePanel:
    """Test suite for validating `BasePanel` behavior."""

    def test_init(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """Initialization of `BasePanel`.

        Verifies:
        - References to `stdscr` and `editor` are stored.
        - Initial visibility is `False`.
        - Terminal dimensions are read from `stdscr` (expected 24x80 in tests).
        - No curses window is created at construction time (`win is None`).
        """
        panel = BasePanel(mock_stdscr, mock_editor)

        assert panel.stdscr == mock_stdscr
        assert panel.editor == mock_editor
        assert panel.visible is False
        assert panel.term_height == 24
        assert panel.term_width == 80
        assert panel.win is None

    def test_open(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """`open()` sets the visibility flag to True."""
        panel = BasePanel(mock_stdscr, mock_editor)
        panel.open()

        assert panel.visible is True

    def test_close(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """`close()` sets the visibility flag to False."""
        panel = BasePanel(mock_stdscr, mock_editor)
        panel.visible = True
        panel.close()

        assert panel.visible is False

    def test_draw_not_implemented(
        self, mock_stdscr: MagicMock, mock_editor: MagicMock
    ) -> None:
        """Calling `draw()` on the base class raises `NotImplementedError`."""
        panel = BasePanel(mock_stdscr, mock_editor)

        with pytest.raises(
            NotImplementedError,
            match="The 'draw' method must be implemented in a child class.",
        ):
            panel.draw()

    def test_handle_key_not_implemented(
        self, mock_stdscr: MagicMock, mock_editor: MagicMock
    ) -> None:
        """Calling `handle_key()` on the base class raises `NotImplementedError`."""
        panel = BasePanel(mock_stdscr, mock_editor)

        with pytest.raises(
            NotImplementedError,
            match="The 'handle_key' method must be implemented in a child class.",
        ):
            panel.handle_key(ord("a"))
