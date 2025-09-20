# tests/ui/test_airesponsepanel.py
"""Unit tests for the `AiResponsePanel` class in `ecli.ui.panels`.
==================================================================

Tests for the `AiResponsePanel` class.

This module verifies the panel responsible for displaying AI responses:
- Initialization and color setup
- Visibility and focus management
- Navigation and text selection
- Clipboard interactions
- Key handling
- UI drawing/rendering
"""

import curses
from itertools import cycle
from unittest.mock import MagicMock, call, patch

import pytest

from ecli.ui.panels import AiResponsePanel


# pylint: disable=protected-access
# pylint: disable=too-many-public-methods
class TestAiResponsePanel:
    """Test suite for `AiResponsePanel` behavior."""

    @patch("curses.newwin")
    def test_init(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Initialization of `AiResponsePanel`.

        Verifies:
        - Proper title and content are set.
        - Window geometry (width, height, position) is computed correctly.
        - Initial cursor, scroll, and selection states are defaulted.
        """
        # Configure a mock window to be returned by curses.newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(
            mock_stdscr, mock_editor, content=content, title="Test Panel"
        )

        assert panel.title == "Test Panel"
        assert panel.lines == ["Line 1", "Line 2", "Line 3"]
        assert panel.width == 32  # 40% of 80
        assert panel.height == 23  # 24 - 1
        assert panel.start_x == 48  # 80 - 32
        assert panel.start_y == 0
        assert panel.cursor_y == 0
        assert panel.cursor_x == 0
        assert panel.scroll == 0
        assert panel.visual_scroll == 0
        assert panel.sel_anchor is None
        assert panel.sel_active is False
        assert panel.visible is False
        assert panel.is_running is False

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_open(
        self,
        mock_curs_set: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """`open()` sets visibility, running state, and cursor, and shows help hint."""
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = AiResponsePanel(mock_stdscr, mock_editor)
        panel.open()

        assert panel.visible is True
        assert panel.is_running is True
        mock_curs_set.assert_called_once_with(1)
        mock_editor._set_status_message.assert_called_once_with(
            "Panel: arrows move, Shift+arrows select, Ctrl+C copy, "
            "Ctrl+P paste, F12 focus, F7/Esc close"
        )

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_close(
        self,
        mock_curs_set: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """`close()` hides the panel, returns focus, and triggers a redraw."""
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = AiResponsePanel(mock_stdscr, mock_editor)
        panel.visible = True
        panel.is_running = True
        panel.close()

        assert panel.visible is False
        assert panel.is_running is False
        mock_curs_set.assert_called_once_with(1)
        assert mock_editor.panel_manager.active_panel is None
        assert mock_editor.focus == "editor"
        # Ensure a full redraw was requested and performed
        assert mock_editor._force_full_redraw is True
        mock_editor.redraw.assert_called_once()

    @patch("curses.newwin")
    @patch("curses.init_pair")
    @patch("curses.color_pair")
    def test_init_colors(
        self,
        mock_color_pair: MagicMock,
        mock_init_pair: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Initialization of color pairs and their attributes.

        Verifies:
        - Correct initialization of curses color pairs.
        - Attributes are composed with bold/reverse/dim as expected.
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Cycle through deterministic color values for color_pair
        color_values = [201, 202, 203, 204, 206, 401, 402]
        mock_color_pair.side_effect = cycle(color_values)

        panel = AiResponsePanel(mock_stdscr, mock_editor)
        panel._init_colors()

        # Validate init_pair calls
        expected_calls = [
            call(201, curses.COLOR_WHITE, curses.COLOR_BLACK),
            call(202, curses.COLOR_CYAN, curses.COLOR_BLACK),
            call(203, curses.COLOR_YELLOW, curses.COLOR_BLACK),
            call(204, curses.COLOR_GREEN, curses.COLOR_BLACK),
            call(206, curses.COLOR_MAGENTA, curses.COLOR_BLACK),
        ]
        mock_init_pair.assert_has_calls(expected_calls)

        # Validate computed attributes
        assert panel.attr_text == 201
        assert panel.attr_title == (202 | curses.A_BOLD)
        assert panel.attr_md == (203 | curses.A_BOLD)
        assert panel.attr_border == (204 | curses.A_BOLD)
        assert panel.attr_cursor == (206 | curses.A_REVERSE)
        assert panel.attr_sel == (
            401 | curses.A_REVERSE
        )  # next value from color_values
        assert panel.attr_dim == (402 | curses.A_DIM)  # next value from color_values

    @patch("curses.newwin")
    def test_move_cursor(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Cursor movement behavior.

        Verifies:
        - Movement in multiple directions.
        - Selection anchoring when Shift is used.
        - Boundary constraints (no movement outside valid range).
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)

        # 1) Move down without selection
        panel._move_cursor(1, 0, shift=False)
        assert panel.cursor_y == 1
        assert panel.cursor_x == 0
        assert panel.sel_active is False

        # 2) Move with selection (Shift)
        panel._move_cursor(0, 3, shift=True)
        assert panel.cursor_y == 1
        assert panel.cursor_x == 3
        assert panel.sel_active is True

        # 3) Boundary constraints: attempt to move above the first line
        panel2 = AiResponsePanel(mock_stdscr, mock_editor, content=content)  # type: ignore
        panel2.cursor_y = 0
        panel2.cursor_x = 0
        panel2._move_cursor(-1, 0, shift=False)
        assert panel2.cursor_y == 0

    @patch("curses.newwin")
    def test_is_selected(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Selection range detection.

        Verifies:
        - Correct identification of selected characters.
        - Handling of single-line and multi-line selections.
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)

        # Establish a selection: anchor at (0,2) and cursor at (1,3)
        panel.sel_active = True
        panel.sel_anchor = (0, 2)
        panel.cursor_y = 1
        panel.cursor_x = 3

        # Characters inside selection
        assert panel._is_selected(0, 3) is True
        assert panel._is_selected(1, 2) is True

        # Characters outside selection
        assert panel._is_selected(0, 1) is False
        assert panel._is_selected(2, 0) is False

    @patch("curses.newwin")
    @patch("pyperclip.copy")
    def test_copy_selection(
        self,
        mock_pyperclip_copy: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Copying selected text (or current line) to the clipboard.

        Verifies:
        - Copy of the selected multi-line range.
        - Copy of the current line when no selection exists.
        - Clipboard integration via `pyperclip.copy`.
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)

        # Copy a multi-line selection
        panel.sel_active = True
        panel.sel_anchor = (0, 2)
        panel.cursor_y = 1
        panel.cursor_x = 3
        panel._copy_selection()
        expected_text = "ne 1\nLin"
        mock_pyperclip_copy.assert_called_once_with(expected_text)

        # Copy when there is no active selection -> copy entire current line
        panel.sel_active = False
        panel.cursor_y = 1
        panel._copy_selection()
        mock_pyperclip_copy.assert_called_with("Line 2")

    @patch("curses.newwin")
    def test_handle_key_navigation(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Navigation key handling.

        Verifies:
        - Arrow keys movement.
        - Shift-modified navigation (selection).
        - Home/End/PageUp/PageDown special keys.
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)
        panel.visible = True

        # Down arrow
        assert panel.handle_key(curses.KEY_DOWN) is True
        assert panel.cursor_y == 1

        # Shift + Up (emulated key code 337)
        assert panel.handle_key(337) is True  # KEY_S_UP
        assert panel.sel_active is True

        # Home / End on current line
        panel.cursor_x = 3
        assert panel.handle_key(curses.KEY_HOME) is True
        assert panel.cursor_x == 0

        assert panel.handle_key(curses.KEY_END) is True
        assert panel.cursor_x == len(panel.lines[0])

    @patch("curses.newwin")
    def test_handle_key_function_keys(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Function key handling.

        Verifies:
        - F7/Esc (close panel).
        - Ctrl+C (copy selection).
        - Ctrl+P (paste; if implemented).
        - F12 (toggle focus).
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)
        panel.visible = True

        # F7 closes the panel
        assert panel.handle_key(curses.KEY_F7) is True
        mock_editor.panel_manager.close_active_panel.assert_called_once()

        # Ctrl+C triggers copy
        mock_editor.panel_manager.close_active_panel.reset_mock()
        with patch.object(panel, "_copy_selection") as mock_copy:
            assert panel.handle_key(3) is True  # Ctrl+C
            mock_copy.assert_called_once()

        # F12 toggles focus between panel and editor
        assert panel.handle_key(276) is True  # F12
        mock_editor.toggle_focus.assert_called_once()

    @patch("curses.newwin")
    def test_draw(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
    ) -> None:
        """Rendering the panel via curses APIs.

        Verifies:
        - Core curses window methods are called.
        - Behavior when the panel is visible.
        """
        # Configure a mock window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)
        panel.visible = True

        # Trigger drawing
        panel.draw()

        # Ensure drawing methods were called
        mock_win.erase.assert_called_once()
        mock_win.noutrefresh.assert_called_once()
