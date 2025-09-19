# tests/ui/test_basepanel.py
"""Тесты для базового класса BasePanel.

Этот модуль содержит тесты для проверки базовой функциональности всех панелей:
- Инициализация
- Управление видимостью
- Реализация абстрактных методов
"""

from unittest.mock import MagicMock

import pytest

from ecli.ui.panels import BasePanel


class TestBasePanel:
    """Тестовый класс для проверки функциональности BasePanel."""

    def test_init(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """Тест инициализации BasePanel.
        
        Проверяет:
        - Правильное сохранение ссылок на stdscr и редактор
        - Начальное состояние видимости
        - Корректное определение размеров терминала
        """
        panel = BasePanel(mock_stdscr, mock_editor)

        assert panel.stdscr == mock_stdscr
        assert panel.editor == mock_editor
        assert panel.visible is False
        assert panel.term_height == 24
        assert panel.term_width == 80
        assert panel.win is None

    def test_open(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """Тест метода open().
        
        Проверяет:
        - Установку флага видимости в True
        """
        panel = BasePanel(mock_stdscr, mock_editor)
        panel.open()

        assert panel.visible is True

    def test_close(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """Тест метода close().
        
        Проверяет:
        - Установку флага видимости в False
        """
        panel = BasePanel(mock_stdscr, mock_editor)
        panel.visible = True
        panel.close()

        assert panel.visible is False

    def test_draw_not_implemented(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """Тест метода draw() без реализации.
        
        Проверяет:
        - Вызов NotImplementedError при вызове нереализованного метода
        """
        panel = BasePanel(mock_stdscr, mock_editor)

        with pytest.raises(NotImplementedError, match="The 'draw' method must be implemented in a child class."):
            panel.draw()

    def test_handle_key_not_implemented(self, mock_stdscr: MagicMock, mock_editor: MagicMock) -> None:
        """Тест метода handle_key() без реализации.
        
        Проверяет:
        - Вызов NotImplementedError при вызове нереализованного метода
        """
        panel = BasePanel(mock_stdscr, mock_editor)

        with pytest.raises(NotImplementedError, match="The 'handle_key' method must be implemented in a child class."):
            panel.handle_key(ord("a"))
