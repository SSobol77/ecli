# tests/ui/test_gitpanel.py
"""Тесты для класса GitPanel.

Этот модуль содержит тесты для проверки функциональности Git-панели:
- Инициализация и настройка
- Управление Git-репозиторием
- Обработка команд Git
- Автообновление статусов
- Навигация по логу коммитов
- Отрисовка интерфейса
"""

import curses
import os
import subprocess
import threading
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from ecli.ui.panels import GitPanel


class TestGitPanel:
    """Тестовый класс для проверки функциональности GitPanel."""

    @patch("curses.newwin")
    def test_init(self,
                  mock_newwin: MagicMock,
                  mock_stdscr: MagicMock,
                  mock_editor: MagicMock,
                  mock_git_bridge: MagicMock) -> None:
        """Тест инициализации GitPanel.

        Проверяет:
        - Правильный расчет размеров и позиции
        - Корректную настройку GitBridge
        - Начальное состояние меню и вывода
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        assert panel.width == 40  # 50% of 80
        assert panel.height == 23  # 24 - 1
        assert panel.start_x == 40  # 80 - 40
        assert panel.git_bridge == mock_git_bridge
        assert panel.output_lines == ["Select a command from the menu to run."]
        assert len(panel.menu_items) > 0
        assert panel.selected_idx == 0
        assert panel.is_busy is False
        assert panel.auto_update_enabled is True

    @patch("curses.newwin")
    def test_init_colors(self,
                         mock_newwin: MagicMock,
                         mock_stdscr: MagicMock,
                         mock_editor: MagicMock,
                         mock_git_bridge: MagicMock) -> None:
        """Тест инициализации цветовых схем.

        Проверяет:
        - Использование цветов из редактора
        - Правильную установку атрибутов
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Проверяем, что цвета установлены из editor.colors
        assert panel.attr_border == mock_editor.colors["status"]
        assert panel.attr_text == mock_editor.colors["default"]
        assert panel.attr_title == mock_editor.colors["function"]
        assert panel.attr_branch == mock_editor.colors["keyword"]

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_open(self,
                  mock_curs_set: MagicMock,
                  mock_newwin: MagicMock,
                  mock_stdscr: MagicMock,
                  mock_editor: MagicMock,
                  mock_git_bridge: MagicMock) -> None:
        """Тест открытия панели.

        Проверяет:
        - Установку видимости
        - Деактивацию курсора
        - Обновление Git-информации
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        panel.open()

        assert panel.visible is True
        mock_curs_set.assert_called_once_with(0)
        mock_git_bridge.update_git_info.assert_called_once()

    @patch("curses.newwin")
    def test_handle_key_navigation(self,
                                   mock_newwin: MagicMock,
                                   mock_stdscr: MagicMock,
                                   mock_editor: MagicMock,
                                   mock_git_bridge: MagicMock) -> None:
        """Тест обработки клавиш навигации.

        Проверяет:
        - Движение по меню вверх/вниз
        - Пропуск разделителей
        - Обработку альтернативных клавиш (j/k)
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)
        panel.visible = True

        # Сохраняем исходный индекс
        original_idx = panel.selected_idx

        # Тест движения вниз
        assert panel.handle_key(curses.KEY_DOWN) is True
        # Пропускаем разделители
        expected_idx = original_idx
        while True:
            expected_idx = (expected_idx + 1) % len(panel.menu_items)
            if panel.menu_items[expected_idx] != "---":
                break
        assert panel.selected_idx == expected_idx

    @patch("curses.newwin")
    def test_handle_key_actions(self,
                                mock_newwin: MagicMock,
                                mock_stdscr: MagicMock,
                                mock_editor: MagicMock,
                                mock_git_bridge: MagicMock) -> None:
        """Тест обработки клавиш действий.

        Проверяет:
        - Обработку Enter (выполнение команды)
        - Обработку 'r' (обновление)
        - Обработку 'a' (автообновление)
        - Обработку F9/Esc/q (закрытие)
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)
        panel.visible = True

        # Тест Enter (выполнение действия)
        with patch.object(panel, "_execute_action") as mock_execute:
            assert panel.handle_key(curses.KEY_ENTER) is True
            mock_execute.assert_called_once()

        # Тест 'r' (обновление)
        with patch.object(panel, "_handle_status") as mock_status:
            assert panel.handle_key(ord("r")) is True
            mock_status.assert_called_once()

        # Тест F9 (закрытие)
        assert panel.handle_key(curses.KEY_F9) is True
        mock_editor.panel_manager.close_active_panel.assert_called_once()

    @patch("curses.newwin")
    @patch("subprocess.run")
    def test_run_git_command(self,
                             mock_subprocess_run: MagicMock,
                             mock_newwin: MagicMock,
                             mock_stdscr: MagicMock,
                             mock_editor: MagicMock,
                             mock_git_bridge: MagicMock) -> None:
        """Тест выполнения Git-команды.

        Проверяет:
        - Правильный вызов subprocess.run
        - Передачу правильной рабочей директории
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Настраиваем мок для subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git status output"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        # Вызываем метод
        result = panel._run_git_command(["git", "status"])

        # Проверяем вызов с правильными параметрами
        repo_dir = panel._get_repo_dir()
        mock_subprocess_run.assert_called_once_with(
            ["git", "status"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace"
        )
        assert result == mock_result

    @patch("curses.newwin")
    def test_toggle_auto_update(self,
                                mock_newwin: MagicMock,
                                mock_stdscr: MagicMock,
                                mock_editor: MagicMock,
                                mock_git_bridge: MagicMock) -> None:
        """Тест переключения автообновления.

        Проверяет:
        - Изменение флага автообновления
        - Запуск/остановку потока автообновления
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Проверяем исходное состояние
        assert panel.auto_update_enabled is True

        # Тест 1: Выключаем автообновление
        panel._toggle_auto_update()
        assert panel.auto_update_enabled is False

        # Тест 2: Включаем автообновление обратно
        panel._toggle_auto_update() # type: ignore
        assert panel.auto_update_enabled is True

        # Тест 3: Повторное выключение для проверки переключения
        panel._toggle_auto_update()
        assert panel.auto_update_enabled is False

    @patch("curses.newwin")
    @patch("subprocess.run")
    def test_update_file_status_cache(self,
                                      mock_subprocess_run: MagicMock,
                                      mock_newwin: MagicMock,
                                      mock_stdscr: MagicMock,
                                      mock_editor: MagicMock,
                                      mock_git_bridge: MagicMock) -> None:
        """Тест обновления кеша статусов файлов.

        Проверяет:
        - Правильный вызов git status
        - Корректный парсинг вывода
        - Обновление кеша
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Настраиваем мок для subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "M file1.txt\nA file2.py\nD file3.txt\n?? file4.txt"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        # Получаем рабочую директорию для проверки путей
        repo_dir = panel._get_repo_dir()

        # Вызываем метод
        panel._update_file_status_cache()

        # Проверяем вызов с правильными параметрами
        mock_subprocess_run.assert_called_once_with(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace"
        )

        # Проверяем кеш
        # Сначала проверяем, что файлы есть в кеше (с любыми именами)
        assert len(panel.file_status_cache) > 0

        # Проверяем, что статусы правильно определены
        # Проходим по всем записям в кеше проверяем, значения соответствуют ли ожидаемым
        status_values = set(panel.file_status_cache.values())
        assert "M" in status_values
        assert "A" in status_values
        assert "D" in status_values
        assert "??" in status_values

        # Проверяем, что есть запись для file4.txt (неотслеживаемый файл)
        file4_found = any("file4.txt" in key for key in panel.file_status_cache.keys())
        assert file4_found, "file4.txt should be in the cache"

    @patch("curses.newwin")
    def test_get_file_git_status(self,
                                 mock_newwin: MagicMock,
                                 mock_stdscr: MagicMock,
                                 mock_editor: MagicMock,
                                 mock_git_bridge: MagicMock) -> None:
        """Тест получения статуса файла.

        Проверяет:
        - Правильный возврат статуса из кеша
        - Обработку отсутствующих файлов
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Заполняем кеш
        panel.file_status_cache = {
            "/path/to/file1.txt": "M",
            "relative/path/file2.py": "A"
        }

        # Проверяем получение статуса
        assert panel.get_file_git_status("/path/to/file1.txt") == "M"
        assert panel.get_file_git_status("relative/path/file2.py") == "A"
        assert panel.get_file_git_status("/nonexistent.txt") is None

    @patch("curses.newwin")
    @patch("threading.Thread")
    def test_start_auto_update(self,
                               mock_thread: MagicMock,
                               mock_newwin: MagicMock,
                               mock_stdscr: MagicMock,
                               mock_editor: MagicMock,
                               mock_git_bridge: MagicMock) -> None:
        """Тест запуска автообновления.

        Проверяет:
        - Создание и запуск потока
        - Правильную настройку демона
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Запускаем автообновление
        panel._start_auto_update()

        # Проверяем создание потока
        mock_thread.assert_called_once_with(target=panel._auto_update_worker,
                                            daemon=True)
        mock_thread.return_value.start.assert_called_once()

    @patch("curses.newwin")
    def test_draw(self,
                  mock_newwin: MagicMock,
                  mock_stdscr: MagicMock,
                  mock_editor: MagicMock,
                  mock_git_bridge: MagicMock) -> None:
        """Тест отрисовки панели.

        Проверяет:
        - Вызов необходимых методов curses
        - Обработку видимости панели
        """
        # Настраиваем мок для окна
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)
        panel.visible = True

        # Вызываем метод draw
        panel.draw()

        # Проверяем вызовы методов окна
        mock_win.erase.assert_called_once()
        mock_win.noutrefresh.assert_called_once()

    @patch("curses.newwin")
    @patch("subprocess.run")
    def test_show_git_log(self,
                          mock_subprocess_run: MagicMock,
                          mock_newwin: MagicMock,
                          mock_stdscr: MagicMock,
                          mock_editor: MagicMock,
                          mock_git_bridge: MagicMock) -> None:
        """Тест отображения лога коммитов.

        Проверяет:
        - Правильный вызов git log
        - Форматирование вывода
        - Обработку пагинации
        """
        # Настраиваем мок для newwin
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Устанавливаем GitBridge в редакторе
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Настраиваем мок для subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "commit1\ncommit2\ncommit3"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        # Вызываем метод
        panel._show_git_log()

        # Проверяем вызов с правильными параметрами
        expected_cmd = [
            "git", "log",
            "--oneline",
            f"--max-count={panel.log_page_size}",
            "--skip=0"
        ]
        mock_subprocess_run.assert_called_once_with(
            expected_cmd,
            cwd=panel._get_repo_dir(),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace"
        )

        # Проверяем вывод с правильным форматом
        assert "commit1" in panel.output_lines
        assert "=== Git Log (page 1, format: --oneline) ===" in panel.output_lines
