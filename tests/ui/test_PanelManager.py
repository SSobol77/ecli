# tests/ui/test_PanelManager.py
import curses
from typing import Any, Dict, Optional, Type, Union, cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from ecli.ui.PanelManager import PanelManager
from ecli.ui.panels import AiResponsePanel, BasePanel, FileBrowserPanel


# Фиктивный класс панели для тестов
class DummyPanel(BasePanel):
    """Тестовая панель для юнит-тестов"""

    def __init__(self, stdscr: Any, editor: Any, **kwargs: Any) -> None:
        """Инициализация тестовой панели"""
        super().__init__(stdscr, editor)
        self.visible = True
        # Мокируем getmaxyx чтобы избежать ошибки
        self.stdscr.getmaxyx = MagicMock(return_value=(24, 80))

    def open(self) -> None:
        """Открытие панели"""
        self.visible = True

    def close(self) -> None:
        """Закрытие панели"""
        self.visible = False

    def handle_key(self, key: int | str) -> bool:
        """Обработка нажатия клавиши"""
        return False

    def draw(self) -> None:
        """Отрисовка панели"""
        pass

# Фикстуры для моков
@pytest.fixture
def mock_editor() -> Mock:
    """Мок для Ecli"""
    editor = Mock()
    editor.stdscr = Mock()
    editor.stdscr.getmaxyx = MagicMock(return_value=(24, 80))
    editor.focus = "editor"
    editor._force_full_redraw = False
    editor._set_status_message = Mock()
    return editor

@pytest.fixture
def panel_manager(mock_editor: Mock) -> PanelManager:
    """Создание PanelManager с мокированным редактором и логированием"""
    with patch("ecli.ui.PanelManager.logging"):
        return PanelManager(mock_editor)

@pytest.fixture
def mock_panel() -> Mock:
    """Базовый мок для панели"""
    panel = Mock(spec=BasePanel)
    panel.visible = True
    return panel

# Мокирование curses.curs_set
@pytest.fixture(autouse=True)
def mock_curses() -> Any:
    """Мокирование curses.curs_set для всех тестов"""
    with patch("curses.curs_set"):
        yield

# Тесты инициализации
def test_panel_manager_initialization(mock_editor: Mock) -> None:
    """Тест инициализации PanelManager"""
    with patch("ecli.ui.PanelManager.logging") as mock_logging:
        manager = PanelManager(mock_editor)
        assert manager.editor == mock_editor
        assert manager.active_panel is None
        assert "ai_response" in manager.registered_panels
        assert "file_browser" in manager.registered_panels
        mock_logging.info.assert_called_once()

# Тесты is_panel_active
def test_is_panel_active_no_panel(panel_manager: PanelManager) -> None:
    """Тест is_panel_active без активной панели"""
    assert not panel_manager.is_panel_active()

def test_is_panel_active_with_panel(panel_manager: PanelManager,
                                    mock_panel: Mock) -> None:
    """Тест is_panel_active с активной видимой панелью"""
    panel_manager.active_panel = mock_panel
    assert panel_manager.is_panel_active()

def test_is_panel_active_invisible_panel(panel_manager: PanelManager,
                                         mock_panel: Mock) -> None:
    """Тест is_panel_active с активной невидимой панелью"""
    mock_panel.visible = False
    panel_manager.active_panel = mock_panel
    assert not panel_manager.is_panel_active()

# Тесты show_panel
def test_show_panel_unknown_name(panel_manager: PanelManager) -> None:
    """Тест show_panel с неизвестным именем панели"""
    panel_manager.show_panel("unknown")

    # Явное приведение типа для mypy
    status_mock = cast(Mock, panel_manager.editor._set_status_message)
    status_mock.assert_called_once_with(
        "Error: Unknown panel name 'unknown'"
    )

def test_show_panel_toggle_active(panel_manager: PanelManager,
                                  mock_panel: Mock) -> None:
    """Тест show_panel с переключением активной панели"""
    panel_manager.active_panel = mock_panel
    panel_manager.registered_panels["test"] = DummyPanel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel("test")
        mock_close.assert_called_once()

def test_show_panel_replace_active(panel_manager: PanelManager,
                                   mock_panel: Mock) -> None:
    """Тест show_panel с заменой активной панели"""
    old_panel = Mock()
    panel_manager.active_panel = old_panel
    panel_manager.registered_panels["new"] = DummyPanel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel("new")
        mock_close.assert_called_once()
        assert isinstance(panel_manager.active_panel, DummyPanel)

def test_show_panel_success(panel_manager: PanelManager) -> None:
    """Тест успешного show_panel"""
    panel_manager.registered_panels["test"] = DummyPanel

    panel_manager.show_panel("test")

    # Проверяем, что панель создана и видима
    assert panel_manager.active_panel is not None
    assert panel_manager.active_panel.visible
    assert panel_manager.editor.focus == "panel"
    assert panel_manager.editor._force_full_redraw

def test_show_panel_exception(panel_manager: PanelManager) -> None:
    """Тест show_panel с исключением при создании панели"""
    # Создаем класс панели, который наследуется от BasePanel и вызывает исключение
    class FailingPanel(BasePanel):
        def __init__(self, stdscr: Any, editor: Any, **kwargs: Any) -> None:
            # Вызываем конструктор базового класса
            super().__init__(stdscr, editor)
            # Используем конкретное исключение вместо общего Exception
            raise RuntimeError("Test error")

    panel_manager.registered_panels["test"] = FailingPanel

    panel_manager.show_panel("test")

    # Явное приведение типа для mypy
    status_mock = cast(Mock, panel_manager.editor._set_status_message)
    status_mock.assert_called_once()

    assert panel_manager.active_panel is None
    assert panel_manager.editor.focus == "editor"

# Тесты show_panel_instance
def test_show_panel_instance_none(panel_manager: PanelManager) -> None:
    """Тест show_panel_instance с None"""
    # Игнорируем ошибку типа, так как метод в PanelManager.py обрабатывает None
    panel_manager.show_panel_instance(None)  # type: ignore[arg-type]
    assert panel_manager.active_panel is None

def test_show_panel_instance_toggle(panel_manager: PanelManager,
                                    mock_panel: Mock) -> None:
    """Тест show_panel_instance с переключением активной панели"""
    panel_manager.active_panel = mock_panel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel_instance(mock_panel)
        mock_close.assert_called_once()

def test_show_panel_instance_replace(panel_manager: PanelManager,
                                     mock_panel: Mock) -> None:
    """Тест show_panel_instance с заменой активной панели"""
    old_panel = Mock()
    panel_manager.active_panel = old_panel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel_instance(mock_panel)
        mock_close.assert_called_once()
        assert panel_manager.active_panel == mock_panel

def test_show_panel_instance_success(panel_manager: PanelManager,
                                     mock_panel: Mock) -> None:
    """Тест успешного show_panel_instance"""
    panel_manager.show_panel_instance(mock_panel)
    mock_panel.open.assert_called_once()
    assert panel_manager.editor.focus == "panel"
    assert panel_manager.editor._force_full_redraw

def test_show_panel_instance_exception(panel_manager: PanelManager,
                                       mock_panel: Mock) -> None:
    """Тест show_panel_instance с исключением при открытии панели"""
    mock_panel.open.side_effect = RuntimeError("Test error")

    panel_manager.show_panel_instance(mock_panel)
    assert panel_manager.active_panel is None
    assert panel_manager.editor.focus == "editor"

# Тесты close_active_panel
def test_close_active_panel_no_panel(panel_manager: PanelManager) -> None:
    """Тест close_active_panel без активной панели"""
    panel_manager.close_active_panel()
    assert panel_manager.editor.focus == "editor"

def test_close_active_panel_with_panel(panel_manager: PanelManager,
                                       mock_panel: Mock) -> None:
    """Тест close_active_panel с активной панелью"""
    panel_manager.active_panel = mock_panel
    # Устанавливаем начальное значение фокуса, отличное от "editor"
    panel_manager.editor.focus = "panel"

    # Вызываем закрытие панели
    panel_manager.close_active_panel()

    # Проверяем, что метод close панели был вызван
    mock_panel.close.assert_called_once()

    # Проверяем, что активная панель сброшена
    assert panel_manager.active_panel is None

    # Проверяем, что фокус вернулся в редактор
    assert panel_manager.editor.focus == "editor"   # type: ignore[unreachable]

def test_close_active_panel_exception(panel_manager: PanelManager,
                                       mock_panel: Mock) -> None:
    """Тест close_active_panel с исключением при закрытии панели"""
    mock_panel.close.side_effect = RuntimeError("Test error")
    panel_manager.active_panel = mock_panel

    # Используем глобальный патчинг logging.exception
    with patch("logging.exception") as mock_exception:
        panel_manager.close_active_panel()
        mock_exception.assert_called_once_with("Exception while closing panel")

    assert panel_manager.active_panel is None

# Тесты handle_key
def test_handle_key_no_panel(panel_manager: PanelManager) -> None:
    """Тест handle_key без активной панели"""
    assert not panel_manager.handle_key("test")

def test_handle_key_with_panel(panel_manager: PanelManager, mock_panel: Mock) -> None:
    """Тест handle_key с активной панелью, обрабатывающей ключ"""
    panel_manager.active_panel = mock_panel
    mock_panel.handle_key.return_value = True

    assert panel_manager.handle_key("test")
    mock_panel.handle_key.assert_called_once_with("test")

def test_handle_key_panel_not_handled(panel_manager: PanelManager,
                                      mock_panel: Mock) -> None:
    """Тест handle_key с активной панелью, не обрабатывающей ключ"""
    panel_manager.active_panel = mock_panel
    mock_panel.handle_key.return_value = False

    assert not panel_manager.handle_key("test")

def test_handle_key_exception(panel_manager: PanelManager, mock_panel: Mock) -> None:
    """Тест handle_key с исключением в обработчике панели"""
    panel_manager.active_panel = mock_panel
    mock_panel.handle_key.side_effect = RuntimeError("Test error")

    with patch("ecli.ui.PanelManager.logging") as mock_logging:
        assert not panel_manager.handle_key("test")
        mock_logging.exception.assert_called_once()

# Тесты draw_active_panel
def test_draw_active_panel_no_panel(panel_manager: PanelManager) -> None:
    """Тест draw_active_panel без активной панели"""
    panel_manager.draw_active_panel()  # Не должно вызывать ошибок

def test_draw_active_panel_with_panel(panel_manager: PanelManager,
                                      mock_panel: Mock) -> None:
    """Тест draw_active_panel с активной панелью"""
    panel_manager.active_panel = mock_panel

    panel_manager.draw_active_panel()
    mock_panel.draw.assert_called_once()

def test_draw_active_panel_exception(panel_manager: PanelManager,
                                      mock_panel: Mock) -> None:
    """Тест draw_active_panel с исключением при отрисовке панели"""
    panel_manager.active_panel = mock_panel
    mock_panel.draw.side_effect = RuntimeError("Test error")

    with patch("ecli.ui.PanelManager.logging") as mock_logging:
        panel_manager.draw_active_panel()
        mock_logging.exception.assert_called_once()
