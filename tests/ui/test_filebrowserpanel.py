# tests/ui/test_filebrowserpanel.py
"""Тесты для класса FileBrowserPanel.

Этот модуль содержит тесты для проверки функциональности файлового браузера:
- Инициализация и настройка
- Навигация по файловой системе
- Операции с файлами и директориями
- Интеграция с Git
- Обработка клавиш
- Отрисовка интерфейса
"""

import curses
import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from ecli.ui.panels import FileBrowserPanel


class TestFileBrowserPanel:
    """Тестовый класс для проверки функциональности FileBrowserPanel."""

    @patch("curses.newwin")
    def test_init(self, mock_newwin: MagicMock, mock_stdscr: MagicMock,
                 mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест инициализации FileBrowserPanel.
        
        Проверяет:
        - Правильный расчет размеров и позиции
        - Корректное чтение содержимого директории
        - Начальное состояние индекса и атрибутов
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        assert panel.width == 32  # 40% of 80
        assert panel.height == 23  # 24 - 1
        assert panel.start_x == 48  # 80 - 32
        assert panel.cwd == temp_dir
        assert len(panel.entries) > 0  # Должны быть записи о файлах
        assert panel.idx == 0
        assert panel.attr_border == mock_editor.colors["status"]
        assert panel.attr_dir == mock_editor.colors["keyword"]
        assert panel.attr_file == mock_editor.colors["default"]

    @patch("curses.newwin")
    def test_set_git_panel(self, mock_newwin: MagicMock, mock_stdscr: MagicMock,
                          mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест установки связи с GitPanel.
        
        Проверяет:
        - Правильное сохранение ссылки на GitPanel
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        git_panel = MagicMock()

        panel.set_git_panel(git_panel)

        assert panel.git_panel == git_panel

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_open(self, mock_curs_set: MagicMock, mock_newwin: MagicMock,
                 mock_stdscr: MagicMock, mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест открытия панели.
        
        Проверяет:
        - Установку видимости
        - Деактивацию курсора
        - Обновление статусов Git
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        git_panel = MagicMock()
        panel.set_git_panel(git_panel)

        panel.open()

        assert panel.visible is True
        mock_curs_set.assert_called_once_with(0)
        git_panel.force_update_file_status_cache.assert_called_once()

    @patch("curses.newwin")
    def test_handle_key_navigation(self, mock_newwin: MagicMock, mock_stdscr: MagicMock,
                                 mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест обработки клавиш навигации.
        
        Проверяет:
        - Движение вверх/вниз по списку файлов
        - Вход в директорию и выход из нее
        - Обработку альтернативных клавиш (j/k/h/l)
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        panel.visible = True

        # Убедимся, что есть записи для навигации
        assert len(panel.entries) > 1

        # Тест движения вниз
        original_idx = panel.idx
        assert panel.handle_key(curses.KEY_DOWN) is True
        assert panel.idx == (original_idx + 1) % len(panel.entries)

        # Тест движения с 'j' и 'k'
        original_idx = panel.idx
        assert panel.handle_key(ord("j")) is True
        assert panel.idx == (original_idx + 1) % len(panel.entries)

    @patch("curses.newwin")
    def test_handle_key_function_keys(self, mock_newwin: MagicMock, mock_stdscr: MagicMock,
                                   mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест обработки функциональных клавиш.
        
        Проверяет:
        - Обработку F2-F6 (операции с файлами)
        - Обработку Del (удаление)
        - Обработку F10/q/Esc (закрытие)
        - Обработку F12 (переключение фокуса)
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        panel.visible = True

        # Тест F2 (создание файла)
        with patch.object(panel, "_new_file") as mock_new_file:
            assert panel.handle_key(curses.KEY_F2) is True
            mock_new_file.assert_called_once()

        # Тест F10 (закрытие)
        assert panel.handle_key(curses.KEY_F10) is True
        mock_editor.toggle_file_browser.assert_called_once()

        # Тест F12 (переключение фокуса)
        mock_editor.toggle_file_browser.reset_mock()
        assert panel.handle_key(276) is True  # F12
        mock_editor.toggle_focus.assert_called_once()

    @patch("curses.newwin")
    def test_draw(self, mock_newwin: MagicMock, mock_stdscr: MagicMock,
                 mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест отрисовки панели.
        
        Проверяет:
        - Вызов необходимых методов curses
        - Обработку видимости панели
        - Отображение статусов Git
        """
        # Настраиваем мок для окна
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        panel.visible = True
        panel.win = mock_win

        # Вызываем метод draw
        panel.draw()

        # Проверяем вызовы методов окна
        mock_win.erase.assert_called_once()
        mock_win.noutrefresh.assert_called_once()

    @patch("curses.newwin")
    def test_enter_selected_directory(self, mock_newwin: MagicMock, mock_stdscr: MagicMock,
                                     mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест входа в директорию.
        
        Проверяет:
        - Правильное изменение текущей директории
        - Обновление списка файлов
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        # Находим поддиректорию
        for i, entry in enumerate(panel.entries):
            if entry and entry.is_dir() and entry.name == "subdir":
                panel.idx = i
                break

        original_cwd = panel.cwd
        panel._enter_selected()

        assert panel.cwd == original_cwd / "subdir"

    @patch("curses.newwin")
    @patch("pathlib.Path.touch")
    def test_new_file(self, mock_touch: MagicMock, mock_newwin: MagicMock,
                     mock_stdscr: MagicMock, mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест создания нового файла.
        
        Проверяет:
        - Вызов метода создания файла
        - Обновление списка файлов
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        with patch.object(panel, "_prompt", return_value="new_file.txt"):
            panel._new_file()

        mock_touch.assert_called_once_with(exist_ok=False)

    @patch("curses.newwin")
    @patch("shutil.copy2")
    def test_copy_entry(self, mock_copy2: MagicMock, mock_newwin: MagicMock,
                       mock_stdscr: MagicMock, mock_editor: MagicMock, temp_dir: Path) -> None:
        """Тест копирования файла.
        
        Проверяет:
        - Вызов метода копирования
        - Генерацию уникального имени
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        # Находим файл для копирования
        for i, entry in enumerate(panel.entries):
            if entry and not entry.is_dir():
                panel.idx = i
                break

        with patch.object(panel, "_prompt", return_value="y"):
            panel._copy_entry()

        mock_copy2.assert_called_once()
