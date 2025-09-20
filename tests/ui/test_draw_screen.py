# tests/ui/test_draw_screen.py
"""Unit and integration tests for the `DrawScreen` UI renderer.
=================================================================

Tests for the `DrawScreen` UI renderer.

This module validates utility helpers and rendering behaviors used by
the editor screen layer, including:

- Safe substring operations and truncation helpers.
- Status bar composition and rendering.
- Line number column rendering.
- Single-line drawing with and without horizontal scroll.
- Cursor positioning logic that adjusts vertical and horizontal scroll offsets.

The suite relies on a module-scoped autouse fixture that mocks `curses`
symbols used inside `ecli.ui.DrawScreen` to ensure tests are hermetic and
do not require a real terminal.
"""

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


# --- Global `curses` mock -----------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def mock_curses_module() -> Generator[None, None, None]:
    """Provide a module-level mock of `curses` for DrawScreen.

    We patch the `curses` module as imported by `ecli.ui.DrawScreen`, defining:
    - A concrete `curses.error` exception type.
    - A minimal set of attributes/constants accessed by the renderer.
    - `color_pair()` that returns the pair index as-is (sufficient for tests).

    Yields:
        None: Ensures the patch remains active for the entire module scope.
    """
    curses_mock = MagicMock()

    # `curses.error` must be a real exception subclass
    class CursesError(Exception):
        """Minimal replacement for `curses.error` used in tests."""

    curses_mock.error = CursesError

    # Provide a subset of constants that DrawScreen expects
    key_constants = {
        "A_REVERSE": 1,
        "A_BOLD": 2,
        "A_DIM": 3,
        "ACS_HLINE": ord("-"),
        "COLOR_WHITE": 7,
        "COLOR_BLACK": 0,
        "COLORS": 256,
        "KEY_UP": 259,
    }
    for name, val in key_constants.items():
        setattr(curses_mock, name, val)

    # Simplified color pair resolution (identity)
    curses_mock.color_pair.side_effect = lambda x: x

    # Patch the `curses` module inside DrawScreen only
    with patch("ecli.ui.DrawScreen.curses", curses_mock):
        yield


# Import after the patch above so DrawScreen sees the mocked `curses`
from ecli.core.Ecli import Ecli  # noqa: E402
from ecli.ui.DrawScreen import DrawScreen  # noqa: E402


@pytest.fixture
def mock_editor() -> MagicMock:
    """Create a fully-featured mock `Ecli` editor used by DrawScreen tests.

    The mock includes:
    - Minimal text buffer and file metadata.
    - Cursor and scroll positions.
    - Display-related flags (line numbers, insert mode).
    - Git and lexer stubs.
    - Width/char helpers and a simplified syntax highlighter hook.

    Returns:
        MagicMock: A mock adhering to the `Ecli` interface as used by DrawScreen.
    """
    editor = MagicMock(spec=Ecli)
    editor.text = ["line 1", "line 2 with more text", "line 3"]
    editor.filename = "/path/to/file.py"
    editor.modified = False
    editor.encoding = "utf-8"
    editor.cursor_y = 0
    editor.cursor_x = 0
    editor.scroll_top = 0
    editor.scroll_left = 0
    editor.visible_lines = 10
    editor.is_selecting = False
    editor.show_line_numbers = True
    editor.insert_mode = True
    editor.is_lightweight = False
    editor.config = {
        "keybindings": {},
        "git": {"enabled": True},
        "file_icons": {},  # Add file_icons to satisfy DrawScreen references
    }
    editor.colors = {}

    # Add the missing attribute used by the status bar
    editor.status_message = ""

    # stdscr mock with fixed terminal size
    editor.stdscr = MagicMock()
    editor.stdscr.getmaxyx.return_value = (24, 80)

    # Git info stub for status bar rendering
    mock_git = MagicMock()
    mock_git.info = ("main", "user", "123")
    editor.git = mock_git

    # Lexer stub
    mock_lexer = MagicMock()
    mock_lexer.name = "Python"
    editor._lexer = mock_lexer

    # Simplified syntax highlighter: returns a single token per line
    editor.apply_syntax_highlighting_with_pygments.side_effect = (
        lambda lines, indices: [[(line, 100)] for line in lines]
    )

    # Width helpers
    editor.get_string_width.side_effect = len
    editor.get_char_width.side_effect = lambda c: 1

    return editor


# ============================== Tests =========================================


class TestDrawScreenUtils:
    """Unit tests for DrawScreen's small utility helpers."""

    def test_safe_cut_left(self, mock_editor: MagicMock) -> None:
        """`_safe_cut_left` removes N leading characters safely."""
        ds = DrawScreen(mock_editor, mock_editor.config)
        assert ds._safe_cut_left("hello world", 6) == "world"

    def test_truncate_string(self, mock_editor: MagicMock) -> None:
        """`truncate_string` truncates to width, preserving exact width via padding."""
        ds = DrawScreen(mock_editor, mock_editor.config)
        assert ds.truncate_string("long string", 5) == "long "


class TestDrawScreenComponents:
    """Rendering-related tests for status bar, line numbers, and lines."""

    def test_draw_status_bar(self, mock_editor: MagicMock) -> None:
        """Status bar includes filename, lexer name, position, mode, and Git info."""
        mock_editor.filename = "test.py"
        mock_editor.cursor_y = 1
        mock_editor.cursor_x = 4
        mock_editor.text = ["line one", "line two", "line three"]

        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._draw_status_bar()

        # Extract the actual drawn string from stdscr.addstr call
        call_args = mock_editor.stdscr.addstr.call_args
        assert call_args is not None
        drawn_string = call_args[0][2]

        assert "test.py" in drawn_string
        assert "Python" in drawn_string
        assert "Ln 2/3" in drawn_string
        assert "Col 5" in drawn_string
        assert "INS" in drawn_string
        assert "Git: user, main, 123" in drawn_string

    def test_draw_line_numbers(self, mock_editor: MagicMock) -> None:
        """Line number gutter renders expected formatted numbers."""
        mock_editor.text = [""] * 100
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._draw_line_numbers()
        # Expect to have printed "  3 " at row=2 (3rd line), col=0 with attr=7
        mock_editor.stdscr.addstr.assert_any_call(2, 0, "  3 ", 7)

    def test_draw_single_line_no_scroll(self, mock_editor: MagicMock) -> None:
        """Single-line draw without horizontal scrolling draws from col `_text_start_x`."""
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._text_start_x = 4
        line_data = (0, [("hello", 101)])
        ds._draw_single_line(0, line_data, 80, 4)
        mock_editor.stdscr.addstr.assert_called_with(0, 4, "hello", 101)

    def test_draw_single_line_with_horizontal_scroll(
        self, mock_editor: MagicMock
    ) -> None:
        """Single-line draw with horizontal scroll cuts content from the left side."""
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._text_start_x = 4
        mock_editor.scroll_left = 10
        line_data = (0, [("a_very_long_line_of_text", 102)])
        ds._draw_single_line(0, line_data, 80, 4)
        expected_text = "g_line_of_text"  # left-cut result after scroll_left=10
        mock_editor.stdscr.addstr.assert_called_with(0, 4, expected_text, 102)


class TestCursorAndScroll:
    """Tests for cursor positioning and automatic scroll adjustments."""

    def test_position_cursor_adjusts_vertical_scroll(
        self, mock_editor: MagicMock
    ) -> None:
        """Cursor below/above viewport should adjust `scroll_top` appropriately."""
        ds = DrawScreen(mock_editor, mock_editor.config)
        mock_editor.visible_lines = 10
        mock_editor.scroll_top = 0

        # Move cursor below current viewport -> scroll down
        mock_editor.cursor_y = 15
        ds._position_cursor()
        assert mock_editor.scroll_top == 6

        # Move cursor near top -> scroll to show it
        mock_editor.cursor_y = 2
        ds._position_cursor()
        assert mock_editor.scroll_top == 2

    def test_position_cursor_adjusts_horizontal_scroll(
        self, mock_editor: MagicMock
    ) -> None:
        """Long lines and far-right cursor positions should adjust `scroll_left`."""
        # Narrower terminal to force horizontal scroll logic
        mock_editor.stdscr.getmaxyx.return_value = (24, 40)
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._text_start_x = 4

        mock_editor.scroll_left = 0
        mock_editor.text = ["this is a very long line for testing horizontal scroll"]
        mock_editor.cursor_y = 0
        mock_editor.cursor_x = 38

        ds._position_cursor()
        assert mock_editor.scroll_left == 3
