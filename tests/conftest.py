# tests/conftest.py
"""Конфигурационный файл pytest с общими фикстурами для тестов редактора Ecli.

Совместимость: Python 3.13.5
Инструменты: Ruff, uv, SonarQube, Pylance
Требования: Обязательные аннотации типов, строгая типизация
"""

from __future__ import annotations

import queue
import tempfile
import threading
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, Mock, patch

import pytest

from ecli.core.Ecli import Ecli
from ecli.integrations.GitBridge import GitBridge
from ecli.integrations.LinterBridge import LinterBridge


# === Автоматическое мокирование функций curses ===
@pytest.fixture(autouse=True)
def mock_curses_functions() -> Generator[None, None, None]:
    """Автоматически применяемая фикстура для мокирования функций curses.

    Эта фикстура предотвращает ошибки при вызове функций curses в тестовой среде,
    где curses не инициализирован с помощью initscr().

    Yields:
        None: Генератор для контекстного менеджера
    """
    # Создаем полный мок модуля curses
    curses_mock = MagicMock()
    curses_mock.initscr.return_value = MagicMock()
    curses_mock.endwin.return_value = None
    curses_mock.curs_set.return_value = None
    curses_mock.init_pair.return_value = None
    curses_mock.color_pair.return_value = 1
    curses_mock.has_colors.return_value = True
    curses_mock.COLORS = 256
    curses_mock.COLOR_PAIRS = 256
    curses_mock.A_NORMAL = 0
    curses_mock.A_BOLD = 1
    curses_mock.A_DIM = 2
    curses_mock.ACS_HLINE = "-"
    curses_mock.ACS_VLINE = "|"

    # Заменяем весь модуль curses на наш мок
    with patch.dict("sys.modules", {"curses": curses_mock}):
        # Также заменяем curses в текущем модуле
        import sys

        if "curses" in sys.modules:
            del sys.modules["curses"]

        # Импортируем заново, чтобы использовать наш мок
        import curses

        curses.initscr = curses_mock.initscr
        curses.endwin = curses_mock.endwin
        curses.curs_set = curses_mock.curs_set
        curses.init_pair = curses_mock.init_pair
        curses.color_pair = curses_mock.color_pair
        curses.has_colors = curses_mock.has_colors
        curses.COLORS = curses_mock.COLORS
        curses.COLOR_PAIRS = curses_mock.COLOR_PAIRS
        curses.A_NORMAL = curses_mock.A_NORMAL
        curses.A_BOLD = curses_mock.A_BOLD
        curses.A_DIM = curses_mock.A_DIM
        curses.ACS_HLINE = curses_mock.ACS_HLINE
        curses.ACS_VLINE = curses_mock.ACS_VLINE

        yield


# === Базовые фикстуры для curses и конфигурации ===
@pytest.fixture
def mock_stdscr() -> MagicMock:
    """Создает мок объекта curses stdscr для тестирования UI-компонентов.

    Returns:
        MagicMock: Мок объекта curses stdscr с настроенными размерами терминала (24x80).
    """
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)  # Стандартные размеры терминала
    return stdscr


@pytest.fixture
def mock_config() -> dict[str, dict[str, Any]]:
    """Базовая конфигурация для тестов Ecli.

    Returns:
        dict[str, dict[str, Any]]: Словарь с базовой конфигурацией редактора.
    """
    return {
        "editor": {
            "use_system_clipboard": True,
            "tab_size": 4,
            "auto_indent": True,
            "show_line_numbers": True,
        },
        "settings": {
            "auto_save_interval": 1.0,
            "theme": "default",
        },
        "keybindings": {},
        "panels": {},
    }


# === Фикстуры для Ecli ===
@pytest.fixture
def mock_editor() -> Mock:
    """Создает комплексный мок основного редактора Ecli.

    Этот мок включает все необходимые атрибуты и методы, которые используются панелями:
    - Цветовые схемы
    - Конфигурация
    - Методы управления статусом, фокусом, буфером обмена и т.д.

    Returns:
        Mock: Настроенный мок объекта Ecli.
    """
    editor = Mock(spec=Ecli)

    # Цветовые схемы для панелей
    editor.colors = {
        "status": 1,  # curses.A_BOLD
        "keyword": 1,  # curses.A_BOLD
        "default": 0,  # curses.A_NORMAL
        "comment": 2,  # curses.A_DIM
        "git_dirty": 0,  # curses.A_NORMAL
        "git_info": 0,  # curses.A_NORMAL
        "git_deleted": 0,  # curses.A_NORMAL
        "git_added": 0,  # curses.A_NORMAL
        "function": 1,  # curses.A_BOLD
        "error": 0,  # curses.A_NORMAL
        "number": 0,  # curses.A_NORMAL
    }

    # Конфигурация редактора
    editor.config = {}
    editor.filename = "/path/to/test_file.py"
    editor.focus = "editor"

    # Основные атрибуты состояния
    editor.text = [""]
    editor.cursor_x = 0
    editor.cursor_y = 0
    editor.modified = False
    editor.insert_mode = True
    editor.status_message = "Ready"
    editor.lint_panel_message = ""
    editor.lint_panel_active = False
    editor.is_selecting = False
    editor.selection_start = None
    editor.selection_end = None
    editor.internal_clipboard = ""

    # Моки для менеджера панелей
    editor.panel_manager = MagicMock()
    editor.panel_manager.close_active_panel = MagicMock()
    editor.panel_manager.active_panel = None

    # Моки для буфера обмена и статуса
    editor._set_status_message = MagicMock()

    # Моки для файловых операций
    editor.open_file = MagicMock()
    editor.insert_text = MagicMock()
    editor.exit_editor = MagicMock()
    editor.toggle_file_browser = MagicMock()
    editor.toggle_focus = MagicMock()

    # Моки для UI
    editor.prompt = MagicMock()
    editor._force_full_redraw = MagicMock()
    editor.redraw = MagicMock()

    # Моки для интеграций
    editor.git = None
    editor.linter_bridge = None

    return editor


@pytest.fixture
def real_editor(mock_stdscr: MagicMock, mock_config: dict[str, dict[str, Any]]) -> Ecli:
    """Создает реальный экземпляр Ecli с мокированными зависимостями.

    Эта фикстура полезна для тестирования логики самого класса Ecli,
    а не его взаимодействия с другими компонентами.

    Args:
        mock_stdscr: Мок curses окна
        mock_config: Конфигурация для редактора

    Returns:
        Ecli: Реальный экземпляр класса с мокированными зависимостями.
    """
    with (
        patch("ecli.core.Ecli.DrawScreen"),
        patch("ecli.core.Ecli.KeyBinder"),
        patch("ecli.core.Ecli.History"),
        patch("ecli.core.Ecli.CodeCommenter"),
        patch("ecli.core.Ecli.PanelManager"),
        patch("ecli.core.Ecli.GitPanel"),
        patch("ecli.core.Ecli.FileBrowserPanel"),
        patch("ecli.core.Ecli.GitBridge"),
        patch("ecli.core.Ecli.LinterBridge"),
        patch("ecli.core.Ecli.AsyncEngine"),
        # Мокируем curses в самом модуле Ecli
        patch("ecli.core.Ecli.curses") as mock_curses,
    ):
        # Настраиваем мок curses
        mock_curses.initscr.return_value = mock_stdscr
        mock_curses.endwin.return_value = None
        mock_curses.curs_set.return_value = None
        mock_curses.init_pair.return_value = None
        mock_curses.color_pair.return_value = 1
        mock_curses.has_colors.return_value = True
        mock_curses.COLORS = 256
        mock_curses.COLOR_PAIRS = 256
        mock_curses.A_NORMAL = 0
        mock_curses.A_BOLD = 1
        mock_curses.A_DIM = 2
        mock_curses.ACS_HLINE = "-"
        mock_curses.ACS_VLINE = "|"

        # Создаем экземпляр с мокированными зависимостями
        editor = Ecli(mock_stdscr, mock_config, lightweight_mode=True)

        return editor


# === Фикстуры для интеграций ===
@pytest.fixture
def mock_git_bridge() -> Mock:
    """Создает мок GitBridge для тестирования GitPanel и интеграций с Git.

    Returns:
        Mock: Настроенный мок объекта GitBridge с тестовыми данными.
    """
    git_bridge = Mock(spec=GitBridge)
    git_bridge.info = ("* main", "user@example.com", "123")
    git_bridge.update_git_info = MagicMock()
    return git_bridge


@pytest.fixture
def mock_linter_bridge() -> Mock:
    """Создает мок LinterBridge для тестирования интеграций с линтерами/LSP.

    Returns:
        Mock: Настроенный мок объекта LinterBridge.
    """
    linter_bridge = Mock(spec=LinterBridge)
    linter_bridge.run_linter = MagicMock(return_value=True)
    linter_bridge.shutdown = MagicMock()
    linter_bridge.reload_devops_module = MagicMock(return_value=True)
    return linter_bridge


# === Фикстуры для файловой системы ===
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Создает временную директорию с тестовыми файлами и поддиректориями.

    Эта фикстура создает структуру:
    - file1.txt: Текстовый файл
    - file2.py: Python файл
    - subdir/: Поддиректория с файлом subfile.txt

    Yields:
        Path: Объект Path временной директории.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Создаем тестовые файлы
        (tmp_path / "file1.txt").write_text("Content of file1")
        (tmp_path / "file2.py").write_text("print('Hello, world!')")

        # Создаем поддиректорию с файлом
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("Content of subfile")

        yield tmp_path


# === Вспомогательные фикстуры ===
@pytest.fixture
def sample_text() -> list[str]:
    """Предоставляет пример текста для тестов.

    Returns:
        list[str]: Список строк с примером кода.
    """
    return [
        "def hello_world():",
        "    # This is a comment",
        "    print('Hello, world!')",
        "    return True",
        "",
    ]


@pytest.fixture
def mock_queue() -> Mock:
    """Создает мок очереди для асинхронных операций.

    Returns:
        Mock: Мок объекта queue.Queue.
    """
    return Mock(spec=queue.Queue)


@pytest.fixture
def mock_threading_event() -> Mock:
    """Создает мок события threading.Event.

    Returns:
        Mock: Мок объекта threading.Event.
    """
    return Mock(spec=threading.Event)


# === Фикстуры для тестовых данных ===
@pytest.fixture
def test_file_content() -> str:
    """Предоставляет тестовое содержимое файла.

    Returns:
        str: Содержимое тестового файла.
    """
    return """def test_function():
    \"\"\"This is a test function.\"\"\"
    return True
"""


@pytest.fixture
def test_file_path(temp_dir: Path) -> Path:
    """Создает тестовый файл во временной директории.

    Args:
        temp_dir: Временная директория

    Returns:
        Path: Путь к созданному тестовому файлу.
    """
    test_file = temp_dir / "test_file.py"
    test_file.write_text("print('Hello, world!')")
    return test_file


# === Фикстуры для тестовых сценариев ===
@pytest.fixture
def editor_with_text(real_editor: Ecli, sample_text: list[str]) -> Ecli:
    """Создает редактор с предварительно загруженным текстом.

    Args:
        real_editor: Экземпляр редактора
        sample_text: Текст для загрузки

    Returns:
        Ecli: Редактор с загруженным текстом.
    """
    real_editor.text = sample_text.copy()
    return real_editor


@pytest.fixture
def editor_with_selection(real_editor: Ecli, sample_text: list[str]) -> Ecli:
    """Создает редактор с выделенным текстом.

    Args:
        real_editor: Экземпляр редактора
        sample_text: Текст для загрузки

    Returns:
        Ecli: Редактор с выделенным текстом.
    """
    real_editor.text = sample_text.copy()
    real_editor.is_selecting = True
    real_editor.selection_start = (1, 4)  # Начало выделения
    real_editor.selection_end = (2, 10)  # Конец выделения
    return real_editor
