# tests/ui/test_draw_screen.py

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


# --- Глобальный мок для curses ---
@pytest.fixture(scope="module", autouse=True)
def mock_curses_module() -> Generator[None, None, None]:
    curses_mock = MagicMock()

    # curses.error должен быть настоящим исключением
    class CursesError(Exception):
        pass
    curses_mock.error = CursesError

    key_constants = {
        "A_REVERSE": 1, "A_BOLD": 2, "A_DIM": 3, "ACS_HLINE": ord("-"),
        "COLOR_WHITE": 7, "COLOR_BLACK": 0, "COLORS": 256,
        "KEY_UP": 259
    }
    for name, val in key_constants.items():
        setattr(curses_mock, name, val)
    curses_mock.color_pair.side_effect = lambda x: x

    with patch("ecli.ui.DrawScreen.curses", curses_mock):
        yield

from ecli.core.Ecli import Ecli
from ecli.ui.DrawScreen import DrawScreen


@pytest.fixture
def mock_editor() -> MagicMock:
    """Создает полнофункциональный мок для Ecli."""
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
    editor.config = {"keybindings": {},
                     "git": {"enabled": True},
                     "file_icons": {}
                     } # Добавил file_icons
    editor.colors = {}

    # Добавляем недостающий атрибут status_message
    editor.status_message = ""

    editor.stdscr = MagicMock()
    editor.stdscr.getmaxyx.return_value = (24, 80)

    mock_git = MagicMock()
    mock_git.info = ("main", "user", "123")
    editor.git = mock_git

    mock_lexer = MagicMock()
    mock_lexer.name = "Python"
    editor._lexer = mock_lexer

    editor.apply_syntax_highlighting_with_pygments.side_effect = \
        lambda lines, indices: [[(line, 100)] for line in lines]

    editor.get_string_width.side_effect = len
    editor.get_char_width.side_effect = lambda c: 1

    return editor

# ==================== Начало тестов ====================

class TestDrawScreenUtils:
    def test_safe_cut_left(self, mock_editor: MagicMock) -> None:
        ds = DrawScreen(mock_editor, mock_editor.config)
        assert ds._safe_cut_left("hello world", 6) == "world"

    def test_truncate_string(self, mock_editor: MagicMock) -> None:
        ds = DrawScreen(mock_editor, mock_editor.config)
        assert ds.truncate_string("long string", 5) == "long "

class TestDrawScreenComponents:
    def test_draw_status_bar(self, mock_editor: MagicMock) -> None:
        mock_editor.filename = "test.py"
        mock_editor.cursor_y = 1
        mock_editor.cursor_x = 4
        mock_editor.text = ["line one", "line two", "line three"]

        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._draw_status_bar()

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
        mock_editor.text = [""] * 100
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._draw_line_numbers()
        mock_editor.stdscr.addstr.assert_any_call(2, 0, "  3 ", 7)

    def test_draw_single_line_no_scroll(self, mock_editor: MagicMock) -> None:
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._text_start_x = 4
        line_data = (0, [("hello", 101)])
        ds._draw_single_line(0, line_data, 80, 4)
        mock_editor.stdscr.addstr.assert_called_with(0, 4, "hello", 101)

    def test_draw_single_line_with_horizontal_scroll(self,
                                                     mock_editor: MagicMock) -> None:
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._text_start_x = 4
        mock_editor.scroll_left = 10
        line_data = (0, [("a_very_long_line_of_text", 102)])
        ds._draw_single_line(0, line_data, 80, 4)
        expected_text = "g_line_of_text"
        mock_editor.stdscr.addstr.assert_called_with(0, 4, expected_text, 102)

class TestCursorAndScroll:
    def test_position_cursor_adjusts_vertical_scroll(self,
                                                     mock_editor: MagicMock) -> None:
        ds = DrawScreen(mock_editor, mock_editor.config)
        mock_editor.visible_lines = 10
        mock_editor.scroll_top = 0
        mock_editor.cursor_y = 15
        ds._position_cursor()
        assert mock_editor.scroll_top == 6
        mock_editor.cursor_y = 2
        ds._position_cursor()
        assert mock_editor.scroll_top == 2

    def test_position_cursor_adjusts_horizontal_scroll(self,
                                                       mock_editor: MagicMock) -> None:
        mock_editor.stdscr.getmaxyx.return_value = (24, 40)
        ds = DrawScreen(mock_editor, mock_editor.config)
        ds._text_start_x = 4
        mock_editor.scroll_left = 0
        mock_editor.text = ["this is a very long line for testing horizontal scroll"]
        mock_editor.cursor_y = 0
        mock_editor.cursor_x = 38
        ds._position_cursor()
        assert mock_editor.scroll_left == 3
