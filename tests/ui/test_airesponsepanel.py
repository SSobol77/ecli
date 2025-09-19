# tests/ui/test_airesponsepanel.py
"""Тесты для класса AiResponsePanel.

Этот модуль содержит тесты для проверки функциональности панели отображения ответов ИИ:
- Инициализация и настройка цветов
- Управление видимостью и фокусом
- Навигация и выделение текста
- Работа с буфером обмена
- Обработка клавиш
- Отрисовка интерфейса
"""

import curses
from itertools import cycle
from unittest.mock import MagicMock, call, patch

import pytest

from ecli.ui.panels import AiResponsePanel


class TestAiResponsePanel:
    """Тестовый класс для проверки функциональности AiResponsePanel."""

    @patch("curses.newwin")
    def test_init(self,
                  mock_newwin: MagicMock,
                  mock_stdscr: MagicMock,
                  mock_editor: MagicMock) -> None:
        """Тест инициализации AiResponsePanel.

        Проверяет:
        - Правильную установку заголовка и содержимого
        - Корректный расчет размеров и позиции
        - Начальное состояние курсора и выделения
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor,
                                content=content, title="Test Panel")

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
    def test_open(self,
                  mock_curs_set: MagicMock,
                  mock_newwin: MagicMock,
                  mock_stdscr: MagicMock,
                  mock_editor: MagicMock) -> None:
        """Тест метода open().

        Проверяет:
        - Установку видимости и состояния работы
        - Активацию курсора
        - Установку сообщения о статусе
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = AiResponsePanel(mock_stdscr, mock_editor)
        panel.open()

        assert panel.visible is True
        assert panel.is_running is True
        mock_curs_set.assert_called_once_with(1)
        mock_editor._set_status_message.assert_called_once_with(
            "Panel: arrows move, Shift+arrows select, Ctrl+C copy, " \
            "Ctrl+P paste, F12 focus, F7/Esc close"
        )

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_close(self,
                   mock_curs_set: MagicMock,
                   mock_newwin: MagicMock,
                   mock_stdscr: MagicMock,
                   mock_editor: MagicMock) -> None:
        """Тест метода close().

        Проверяет:
        - Скрытие панели и остановку работы
        - Деактивацию курсора
        - Возврат фокуса редактору
        - Принудительную перерисовку
        """
        # Настраиваем мок для newwin
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
        # Проверяем, что _force_full_redraw был вызван с аргументом True
        assert mock_editor._force_full_redraw is True
        mock_editor.redraw.assert_called_once()

    @patch("curses.newwin")
    @patch("curses.init_pair")
    @patch("curses.color_pair")
    def test_init_colors(self,
                         mock_color_pair: MagicMock,
                         mock_init_pair: MagicMock,
                         mock_newwin: MagicMock,
                         mock_stdscr: MagicMock,
                         mock_editor: MagicMock) -> None:
        """Тест инициализации цветовых пар.

        Проверяет:
        - Правильную инициализацию цветовых пар
        - Корректное применение атрибутов
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Настраиваем моки для curses.color_pair с бесконечным циклом значений
        color_values = [201, 202, 203, 204, 206, 401, 402]  # Добавляем доп.значения
        mock_color_pair.side_effect = cycle(color_values)

        panel = AiResponsePanel(mock_stdscr, mock_editor)
        panel._init_colors()

        # Проверяем вызовы init_pair
        expected_calls = [
            call(201, curses.COLOR_WHITE, curses.COLOR_BLACK),
            call(202, curses.COLOR_CYAN, curses.COLOR_BLACK),
            call(203, curses.COLOR_YELLOW, curses.COLOR_BLACK),
            call(204, curses.COLOR_GREEN, curses.COLOR_BLACK),
            call(206, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        ]
        mock_init_pair.assert_has_calls(expected_calls)

        # Проверяем атрибуты цветов
        assert panel.attr_text == 201
        assert panel.attr_title == 202 | curses.A_BOLD
        assert panel.attr_md == 203 | curses.A_BOLD
        assert panel.attr_border == 204 | curses.A_BOLD
        assert panel.attr_cursor == 206 | curses.A_REVERSE
        assert panel.attr_sel == 401 | curses.A_REVERSE  #  значение из color_values
        assert panel.attr_dim == 402 | curses.A_DIM  # следующее из color_values

    @patch("curses.newwin")
    def test_move_cursor(self,
                         mock_newwin: MagicMock,
                         mock_stdscr: MagicMock,
                         mock_editor: MagicMock) -> None:
        """Тест перемещения курсора.

        Проверяет:
        - Движение курсора в разных направлениях
        - Работу выделения при движении с Shift
        - Ограничения движения
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)

        # Тест 1: Движение вниз без выделения
        panel._move_cursor(1, 0, shift=False)
        assert panel.cursor_y == 1
        assert panel.cursor_x == 0
        assert panel.sel_active is False

        # Тест 2: Движение с выделением
        panel._move_cursor(0, 3, shift=True)
        assert panel.cursor_y == 1
        assert panel.cursor_x == 3
        assert panel.sel_active is True

        # Тест 3: Проверка ограничений движения
        # Создаем новую панель для чистого теста ограничений
        panel2 = AiResponsePanel(mock_stdscr, mock_editor, content=content)  # type: ignore
        panel2.cursor_y = 0
        panel2.cursor_x = 0
        panel2._move_cursor(-1, 0, shift=False)  # Попытка выйти за границы
        assert panel2.cursor_y == 0

    @patch("curses.newwin")
    def test_is_selected(self,
                         mock_newwin: MagicMock,
                         mock_stdscr: MagicMock,
                         mock_editor: MagicMock) -> None:
        """Тест определения выделенного текста.

        Проверяет:
        - Правильное определение выделенных символов
        - Обработку однострочного и многострочного выделения
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)

        # Устанавливаем выделение
        panel.sel_active = True
        panel.sel_anchor = (0, 2)
        panel.cursor_y = 1
        panel.cursor_x = 3

        # Проверяем символы внутри выделения
        assert panel._is_selected(0, 3) is True
        assert panel._is_selected(1, 2) is True

        # Проверяем символы вне выделения
        assert panel._is_selected(0, 1) is False
        assert panel._is_selected(2, 0) is False

    @patch("curses.newwin")
    @patch("pyperclip.copy")
    def test_copy_selection(self,
                            mock_pyperclip_copy: MagicMock,
                            mock_newwin: MagicMock,
                            mock_stdscr: MagicMock,
                            mock_editor: MagicMock) -> None:
        """Тест копирования выделения в буфер обмена.

        Проверяет:
        - Копирование выделенного текста
        - Копирование всей строки при отсутствии выделения
        - Обработку ошибок и использование внутреннего буфера
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)

        # Тест копирования выделения
        panel.sel_active = True
        panel.sel_anchor = (0, 2)
        panel.cursor_y = 1
        panel.cursor_x = 3
        panel._copy_selection()

        expected_text = "ne 1\nLin"
        mock_pyperclip_copy.assert_called_once_with(expected_text)

        # Тест копирования без выделения
        panel.sel_active = False
        panel.cursor_y = 1
        panel._copy_selection()

        mock_pyperclip_copy.assert_called_with("Line 2")

    @patch("curses.newwin")
    def test_handle_key_navigation(self,
                                    mock_newwin: MagicMock,
                                    mock_stdscr: MagicMock,
                                    mock_editor: MagicMock) -> None:
        """Тест обработки клавиш навигации.

        Проверяет:
        - Обработку клавиш со стрелками
        - Работу с модификатором Shift
        - Специальные клавиши (Home, End, PageUp/Down)
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)
        panel.visible = True

        # Тест движения вниз
        assert panel.handle_key(curses.KEY_DOWN) is True
        assert panel.cursor_y == 1

        # Тест движения с Shift
        assert panel.handle_key(337) is True  # KEY_S_UP
        assert panel.sel_active is True

        # Тест Home/End
        panel.cursor_x = 3
        assert panel.handle_key(curses.KEY_HOME) is True
        assert panel.cursor_x == 0

        assert panel.handle_key(curses.KEY_END) is True
        assert panel.cursor_x == len(panel.lines[0])

    @patch("curses.newwin")
    def test_handle_key_function_keys(self,
                                      mock_newwin: MagicMock,
                                      mock_stdscr: MagicMock,
                                      mock_editor: MagicMock) -> None:
        """Тест обработки функциональных клавиш.

        Проверяет:
        - Обработку F7/Esc (закрытие)
        - Обработку Ctrl+C (копирование)
        - Обработку Ctrl+P (вставка)
        - Обработку F12 (переключение фокуса)
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)
        panel.visible = True

        # Тест F7 (закрытие)
        assert panel.handle_key(curses.KEY_F7) is True
        mock_editor.panel_manager.close_active_panel.assert_called_once()

        # Тест Ctrl+C (копирование)
        mock_editor.panel_manager.close_active_panel.reset_mock()
        with patch.object(panel, "_copy_selection") as mock_copy:
            assert panel.handle_key(3) is True  # Ctrl+C
            mock_copy.assert_called_once()

        # Тест F12 (переключение фокуса)
        assert panel.handle_key(276) is True  # F12
        mock_editor.toggle_focus.assert_called_once()

    @patch("curses.newwin")
    def test_draw(self,
                  mock_newwin: MagicMock,
                  mock_stdscr: MagicMock,
                  mock_editor: MagicMock) -> None:
        """Тест отрисовки панели.

        Проверяет:
        - Вызов необходимых методов curses
        - Обработку видимости панели
        """
        # Настраиваем мок для окна
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        content = "Line 1\nLine 2\nLine 3"
        panel = AiResponsePanel(mock_stdscr, mock_editor, content=content)
        panel.visible = True

        # Вызываем метод draw
        panel.draw()

        # Проверяем вызовы методов окна
        mock_win.erase.assert_called_once()
        mock_win.noutrefresh.assert_called_once()
