# key_debugger.py
import curses
import time

# Создаем обратный словарь для имен констант curses
# Это нужно, чтобы показать имя клавиши (например, "KEY_UP") по ее коду (например, 259)
KEY_NAMES = {
    code: name
    for name, code in vars(curses).items()
    if name.startswith("KEY_")
}

def get_key_name(key_code: int) -> str:
    """Возвращает имя константы curses для данного кода клавиши."""
    return KEY_NAMES.get(key_code, "N/A")

def main(stdscr: "curses._CursesWindow"):
    """Основная функция, которая запускается в среде curses."""
    # --- Настройка Curses ---
    curses.curs_set(0)  # Скрыть курсор
    stdscr.nodelay(False)  # getch() будет ждать нажатия клавиши
    stdscr.timeout(-1)  # Ждать бесконечно

    # Включаем обработку спец. клавиш (F1, стрелки и т.д.)
    # Это заставляет curses пытаться самому парсить escape-последовательности
    stdscr.keypad(True)

    last_key_info = []

    while True:
        # --- Отрисовка интерфейса ---
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Заголовок
        title = "Curses Key Debugger"
        instructions = "Press any key to see its code. Press 'q' to quit."
        stdscr.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD)
        stdscr.addstr(2, (width - len(instructions)) // 2, instructions, curses.A_DIM)

        # Вывод информации о последнем нажатии
        if last_key_info:
            for i, line in enumerate(last_key_info):
                stdscr.addstr(5 + i, 4, line)

        stdscr.refresh()

        # --- Чтение и обработка ввода ---
        key = stdscr.getch()

        # Выход из программы
        if key == ord('q'):
            break

        # Пропускаем событие изменения размера окна, чтобы оно не мешало
        if key == curses.KEY_RESIZE:
            continue

        # Собираем информацию о нажатой клавише
        last_key_info = []
        key_type = type(key).__name__

        last_key_info.append(f"{'Key Type:':<20} {key_type}")
        last_key_info.append(f"{'Value (raw):':<20} {repr(key)}")

        if isinstance(key, int):
            last_key_info.append(f"{'Value (int):':<20} {key}")
            last_key_info.append(f"{'Value (hex):':<20} {hex(key)}")
            if 32 <= key <= 126:
                last_key_info.append(f"{'As char:':<20} '{chr(key)}'")

            key_name = get_key_name(key)
            last_key_info.append(f"{'curses.KEY_*:':<20} {key_name}")

        # --- Логика для захвата ПОЛНЫХ escape-последовательностей ---
        # Если мы получили ESC, быстро проверяем, не идет ли что-то следом
        if key == 27:
            sequence = ""
            stdscr.nodelay(True) # Не ждать следующую клавишу
            time.sleep(0.01) # Короткая пауза, чтобы дать буферу терминала заполниться
            try:
                while True:
                    next_key = stdscr.getch()
                    if next_key == curses.ERR:
                        break
                    sequence += chr(next_key)
            finally:
                stdscr.nodelay(False) # Вернуть в блокирующий режим

            if sequence:
                last_key_info.append("-" * 40)
                last_key_info.append("Detected Escape Sequence:")
                last_key_info.append(f"{'Sequence (raw):':<20} {repr(sequence)}")
                last_key_info.append(f"{'Full Sequence:':<20} ESC + {sequence}")


if __name__ == "__main__":
    print("Starting key debugger... Press 'q' to quit.")
    try:
        # curses.wrapper обеспечивает безопасный запуск и восстановление терминала
        curses.wrapper(main)
        print("Debugger finished.")
    except Exception as e:
        print(f"An error occurred: {e}")
