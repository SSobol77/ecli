# tests/ui/test_keybinder.py

from typing import Union
from unittest.mock import MagicMock, patch

# Импортируем KeyBinder сразу
from ecli.ui.KeyBinder import KeyBinder


# Этот мок нам не нужен, так как мы будем патчить методы, которые его используют
# @pytest.fixture
# def mock_editor...

@patch("ecli.ui.KeyBinder.curses", MagicMock()) # Глобально мокаем curses для безопасности
def test_keybinder_lookup() -> None:
    """Тест: Проверяет работу метода lookup в полной изоляции.

    Мы достигаем изоляции, подменяя ("патча") сложные внутренние методы KeyBinder,
    от которых зависит lookup: _load_keybindings и _decode_keystring.
    Это позволяет нам не создавать сложнейший мок для всего Ecli.
    """
    # 1. Создаем минимально необходимую заглушку для editor.
    # Ему нужен только атрибут config, чтобы __init__ не упал.
    mock_editor = MagicMock()
    mock_editor.config = {}

    # 2. Определяем, что должны вернуть наши "подделанные" методы.

    # Этот словарь будет возвращен вместо реального выполнения _load_keybindings
    test_keybindings = {
        "save_file": [19],          # 'ctrl+s'
        "quit": [17, 27],           # 'ctrl+q', 'esc'
        "help": [-201]              # 'f1'
    }

    # Эта функция будет выполняться вместо реального _decode_keystring
    def simple_decoder(key_spec: str) -> str | int:
        """Простой декодер для нужд теста."""
        if key_spec == "ctrl+s":
            return 19
        if key_spec == "ctrl+q":
            return 17
        if key_spec == "esc":
            return 27
        if key_spec == "f1":
            return -201
        # Для неизвестных ключей вернем саму строку, чтобы проверить случай "не найдено"
        return key_spec

    # 3. Применяем патчи
    with patch.object(KeyBinder, "_load_keybindings", return_value=test_keybindings), \
         patch.object(KeyBinder, "_decode_keystring", side_effect=simple_decoder), \
         patch.object(KeyBinder, "_setup_action_map", return_value={}): # ⬅️ ВАЖНЕЙШИЙ ШАГ!

        # Мы также "выключаем" _setup_action_map, так как он не нужен для теста
        # метода lookup и именно он вызывает все ошибки __name__.

        # Теперь __init__ выполнится безопасно:
        # - _load_keybindings вернет наш словарь.
        # - _setup_action_map вернет пустой словарь и не будет падать.
        kb = KeyBinder(editor=mock_editor)

        # 4. Проверяем, что kb.keybindings содержит наши данные
        assert kb.keybindings == test_keybindings

        # 5. Проверяем сам метод lookup. Он будет использовать наш simple_decoder.
        assert kb.lookup("ctrl+s") == "save_file"
        assert kb.lookup("esc") == "quit"
        assert kb.lookup("ctrl+q") == "quit"
        assert kb.lookup("f1") == "help"

        # Проверяем случаи, когда ничего не должно быть найдено
        assert kb.lookup("f12") is None
        assert kb.lookup("несуществующая_клавиша") is None
