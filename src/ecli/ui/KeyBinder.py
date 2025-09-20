# ecli/ui/KeyBinder.py
"""KeyBinder.py
==================
Description:
-----------------------
The KeyBinder class is responsible for translating user key presses into editor actions
within the ECLI text editor. It provides a flexible and extensible system for handling
keyboard input, supporting both standard and custom keybindings, including modifier keys
(Ctrl, Alt, Shift), function keys, and terminal-specific codes.

Key Features:
- Loads and parses keybinding configurations, supporting user overrides and terminal-specific quirks.
- Maps key codes and logical key strings to editor action methods.
- Handles printable character input and special key combinations.
- Provides diagnostic tools for debugging terminal input codes.
- Ensures robust and consistent input handling across different terminal environments.

Main Methods:
1. handle_input: Processes a single key event and dispatches it to the appropriate editor action.
2. _load_keybindings: Loads and parses keybinding configurations, resolving key codes and logical identifiers.
3. debug_tty_input: Diagnostic method for displaying raw terminal input codes for debugging.
4. _decode_keystring: Decodes key specification strings or integers into key codes or logical identifiers.
5. _setup_action_map: Constructs the mapping from key codes/logical keys to editor action methods.
6. get_key_input: Reads a single key or key sequence from the terminal, handling ESC/Alt sequences robustly.

Intended Usage:
---------------
Instantiate KeyBinder with a reference to the main Ecli instance. Use handle_input
to process key events, and get_key_input to read user input from the terminal. The class
ensures that all key events are mapped to the correct editor actions, supporting both
default and user-defined keybindings.
"""

import curses
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

# Importing a third-party library directly
from wcwidth import wcswidth


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


## ==================== KeyBinder Class ====================
class KeyBinder:
    """Class KeyBinder
    ====================
    KeyBinder manages keybindings, input handling, and action mapping for the ECLI editor.
    This class is responsible for translating user key presses into editor actions, supporting
    customizable keybindings, terminal-specific key code handling, and logical key mapping
    (including support for modifier keys such as Ctrl, Alt, and Shift). It provides methods
    for processing input events, loading and parsing keybinding configurations, mapping keys
    to editor actions, and debugging terminal input.

    Attributes:
        editor (Ecli): Reference to the main editor instance for accessing state and actions.
        history: Reference to the editor's history manager for undo/redo operations.
        config: Editor configuration, including user-defined keybindings.
        stdscr: The curses window object for terminal input/output.
        keybindings (dict): Mapping of action names to lists of key codes or key strings.
        action_map (dict): Mapping of key codes or logical key strings to editor action methods.
        handle_input(key): Processes a single key event and dispatches it to the appropriate editor action.
        _handle_printable_character(key): Handles insertion of printable characters into the editor buffer.
        _load_keybindings(): Loads and parses keybinding configuration, resolving key codes and modifiers.
        debug_tty_input(window): Diagnostic method for displaying raw terminal key codes for debugging.
        _decode_keystring(key_input): Decodes a key specification string or integer into a key code or logical key identifier.
        _setup_action_map(): Constructs the mapping from key codes or strings to editor action methods.
        get_key_input(window): Reads a key or key sequence from the terminal, handling ESC/Alt combinations robustly.
    """

    def __init__(self, editor: "Ecli"):
        """Initializes the KeyBinder instance.

            editor (Ecli): Reference to the main Ecli instance, used to access its
                configuration, standard screen (stdscr), and action methods.

        Attributes:
            editor (Ecli): The main editor instance.
            history: The editor's history object.
            config: The editor's configuration object.
            stdscr: The editor's standard screen object.
            keybindings (dict): Dictionary of loaded keybindings.
            action_map (dict): Mapping of actions to their corresponding methods.
        """
        logging.debug("KeyBinder initialized with editor: %s", editor)
        self.editor = editor
        self.history = editor.history
        self.config = editor.config
        self.stdscr = editor.stdscr

        # State that now belongs to KeyBinder
        self.keybindings = self._load_keybindings()
        self.action_map = self._setup_action_map()

    def _handle_printable_character(self, key: str | int) -> bool:
        """Handles insertion of a printable character into the buffer."""
        char_to_insert = ""
        if isinstance(key, str) and len(key) == 1:
            # Check that this isn't a control character that should have been processed earlier.
            # wcswidth > 0 is a good indicator that this is a visible character.
            if wcswidth(key) > 0:
                char_to_insert = key
        elif isinstance(key, int) and 32 <= key < 1114112:
            try:
                # Convert numeric code to character
                char_to_insert = chr(key)
                if wcswidth(char_to_insert) <= 0:
                    char_to_insert = ""  # Ignore invisible characters
            except ValueError:
                logging.warning(f"Invalid ordinal for chr(): {key}. Cannot convert.")
                self.editor._set_status_message(f"Invalid key code: {key}")
                return True

        if char_to_insert:
            logging.debug(
                f"handle_input: Treating '{repr(char_to_insert)}' as printable character for insertion."
            )
            return self.editor.insert_text(char_to_insert)

        return False

    # ---------------------- Handle Input --------------------
    def handle_input(self, key: str | int) -> bool:
        """Processes a single key event and triggers the corresponding editor action.
        This method handles different types of key inputs, including integers (such as key codes),
        'alt-...' string representations, and printable characters. It attempts to find a matching
        action in the action map, handles printable characters, or sets a status message for
        unhandled input. Visual changes are tracked and reported.

        Args:
            key (Union[str, int]): The logical key event to process. Can be an integer key code,
                a string representing a key (e.g., 'alt-x'), or a printable character.

        Returns:
            bool: True if the input caused a visual change in the editor, False otherwise.

        Raises:
            Exception: Any exception raised during input handling is caught, logged, and a status
                message is set. The exception is not propagated.
        """
        logging.debug(
            "handle_input: Received logical key event → %r (type: %s)",
            key,
            type(key).__name__,
        )

        original_status = self.editor.status_message
        action_caused_visual_change = False

        with self.editor._state_lock:
            try:
                # 1 Direct key lookup (numbers or 'alt-...')
                if key in self.action_map:
                    action = self.action_map[key]
                    logging.debug(
                        f"handle_input: Key '{key}' found in action_map. Calling: {action.__name__}"
                    )
                    if action():
                        action_caused_visual_change = True

                # 2 Handle printable characters
                # This branch will trigger if the key is, for example, 104 (ord('h')) or the string 'h'
                elif self._handle_printable_character(key):
                    action_caused_visual_change = True

                # 3 Unhandled input
                # This branch is for unassigned control characters or non-printable codes.
                else:
                    logging.debug(
                        "Unhandled input by primary logic: %r (type: %s)",
                        key,
                        type(key).__name__,
                    )
                    self.editor._set_status_message(
                        f"Ignored unhandled input: {repr(key)}"
                    )

                # Final check for status change
                if self.editor.status_message != original_status:
                    action_caused_visual_change = True

                return action_caused_visual_change

            except Exception as e_handler:
                logging.exception(
                    "Input handler critical error. This should be investigated."
                )
                self.editor._set_status_message(
                    f"Input handler error: {str(e_handler)[:50]}"
                )
                return True

    def _load_keybindings(self) -> dict[str, list[int | str]]:
        """Loads and returns the keybindings configuration for the editor.

        This method determines the correct key codes for various actions,
        taking into account terminal-specific differences (such as Backspace, Ctrl+Z, etc.).
        It returns a dictionary mapping action names to lists of key codes or key strings.

        Returns:
            dict[str, list[Union[int, str]]]: A dictionary where each key is an action name
            (e.g., "delete", "undo"), and the value is a list of key codes or key strings
            that trigger that action.
        """

        # Getting the correct key codes for TTY
        def get_backspace_code():
            """Determines the correct key codes for the Backspace key depending on the terminal.

            This helper function returns a list of integer codes that may represent the Backspace key
            in different terminal environments. It is useful for handling Backspace consistently
            across various platforms and terminal emulators.

            Returns:
                list[int]: A list of possible key codes for Backspace (e.g., [curses.KEY_BACKSPACE, 8, 127]).
            """
            return [curses.KEY_BACKSPACE, 8, 127]

        def get_ctrl_z_codes():
            """Returns all possible key codes for the Ctrl+Z key combination.

            This helper function provides a list of integer codes that may represent
            the Ctrl+Z (undo) key in different terminal environments. It includes
            the standard ASCII code, any available curses constant, and common
            alternative codes.

            Returns:
                list[int]: A list of possible key codes for Ctrl+Z (e.g., [26, curses.KEY_SUSPEND, 407]).
            """
            codes = [26]  # ASCII SUB (Ctrl+Z)
            if hasattr(curses, "KEY_SUSPEND"):
                codes.append(curses.KEY_SUSPEND)

            codes.append(407)  # Alternative code for undo
            return codes

        default_keybindings: dict[str, str | int | list[str | int]] = {
            "delete": ["del", curses.KEY_DC],
            "paste": ["ctrl+v", 22],
            "copy": ["ctrl+c", 3],
            "cut": ["ctrl+x", 24],
            "undo": ["ctrl+z"] + get_ctrl_z_codes(),
            "redo": ["ctrl+y", 558, 25],
            "new_file": ["f2", 266],
            "open_file": ["ctrl+o", 15],
            "save_file": ["ctrl+s", 19],
            "save_as": ["f5", 269],
            "select_all": ["ctrl+a", 1],
            "quit": ["ctrl+q", 17],
            "goto_line": ["ctrl+g", 7],
            "toggle_widget_panel": ["f7", 271],
            "git_menu": ["f9", 273],
            "help": ["f1", 265],
            "find": ["ctrl+f", 6],
            "find_next": ["f3", 267],
            "search_and_replace": ["f6", 270],
            "cancel_operation": ["esc", 27],
            "tab": ["tab", 9],
            "shift_tab": ["shift+tab", 353],
            "lint": ["f4", 268],
            "toggle_comment_block": ["ctrl+\\", 28],
            "handle_home": ["home", curses.KEY_HOME, 262],
            "handle_end": ["end", getattr(curses, "KEY_END", curses.KEY_LL), 360],
            "handle_page_up": ["pageup", curses.KEY_PPAGE, 339],
            "handle_page_down": ["pagedown", curses.KEY_NPAGE, 338],
            "toggle_insert_mode": ["insert", curses.KEY_IC, 331],
            "select_to_home": [curses.KEY_SHOME],
            "select_to_end": [curses.KEY_SEND],
            "handle_backspace": ["backspace"] + get_backspace_code(),
            "toggle_file_browser": ["f10", 274],
            "toggle_focus": ["f12", 276],
            # Improved Alt+HJKL support for TTYs
            "extend_selection_up": [
                "shift+up",
                "alt-k",
                getattr(curses, "KEY_SR", getattr(curses, "KEY_SPREVIOUS", 337)),
            ],
            "extend_selection_down": [
                "shift+down",
                "alt-j",
                getattr(curses, "KEY_SF", getattr(curses, "KEY_SNEXT", 336)),
            ],
            "extend_selection_left": [
                "shift+left",
                "alt-h",
                curses.KEY_SLEFT,
            ],
            "extend_selection_right": [
                "shift+right",
                "alt-l",
                curses.KEY_SRIGHT,
            ],
        }

        user_keybindings_config = self.config.get("keybindings", {})
        parsed_keybindings: dict[str, list[int | str]] = {}

        for action, default_value_spec in default_keybindings.items():
            key_value_spec_from_config = user_keybindings_config.get(
                action, default_value_spec
            )

            if not key_value_spec_from_config:
                logging.debug(f"Keybinding for action '{action}' is disabled or empty.")
                continue

            key_codes_for_action: list[int | str] = []
            specs_to_process: list[str | int]
            if isinstance(key_value_spec_from_config, list):
                specs_to_process = key_value_spec_from_config
            elif (
                isinstance(key_value_spec_from_config, str)
                and "|" in key_value_spec_from_config
            ):
                specs_to_process = [
                    s.strip() for s in key_value_spec_from_config.split("|")
                ]
            else:
                specs_to_process = [key_value_spec_from_config]

            for key_spec_item in specs_to_process:
                if not key_spec_item and key_spec_item != 0:
                    continue
                try:
                    key_code = self._decode_keystring(key_spec_item)
                    if key_code not in key_codes_for_action:
                        key_codes_for_action.append(key_code)
                except ValueError as e:
                    logging.error(
                        f"Error parsing keybinding item '{key_spec_item!r}' for action '{action}': {e}. "
                        f"This specific binding for the action will be ignored."
                    )
                except Exception as e_unhandled:
                    logging.error(
                        f"Unexpected error parsing keybinding item '{key_spec_item!r}' for action '{action}': {e_unhandled}",
                        exc_info=True,
                    )

            if action == "undo":  # Ctrl+Z / KEY_SUSPEND
                extra_codes: list[int] = [26, 407]  # 407 == curses.KEY_SUSPEND
                if hasattr(curses, "KEY_SUSPEND"):
                    extra_codes.append(curses.KEY_SUSPEND)
                for code in extra_codes:
                    if code not in key_codes_for_action:
                        key_codes_for_action.append(code)

            if key_codes_for_action:
                parsed_keybindings[action] = key_codes_for_action
            else:
                logging.warning(
                    f"No valid key codes found for action '{action}' after parsing. It will not be bound."
                )

        logging.debug(
            f"Loaded and parsed keybindings (action -> list of key_codes): {parsed_keybindings}"
        )
        return parsed_keybindings

    # Additional method for TTY diagnostics
    def debug_tty_input(self, window: Optional[curses.window] = None) -> None:
        """Diagnostic method for debugging keyboard input in TTY mode.
        Displays the raw key codes received from the terminal, allowing developers to inspect
        the exact input values as interpreted by curses. The method shows detailed information
        about each key press, including its representation, type, and code. Press ESC to exit
        the debug mode.

        Args:
            window (Optional[curses.window]): The curses window to read input from. If not provided,
                uses the default window (self.stdscr).

        Returns:
            None
        """
        logging.debug(
            "Entering TTY Debug Mode. Press keys to see their codes (ESC to exit)."
        )
        target = window or self.stdscr
        self.editor._set_status_message(
            "TTY Debug Mode: Press keys to see codes (ESC to exit)"
        )

        while True:
            try:
                key = target.get_wch()

                if key == 27:  # ESC for exit
                    logging.debug("Exiting TTY Debug Mode on ESC key.")
                    self.editor._set_status_message("Exiting TTY Debug Mode")
                    break

                # Show detailed information about the key
                key_info = f"Key: {key!r} (type: {type(key).__name__})"
                if isinstance(key, int):
                    key_info += f" decimal: {key}"
                    if 32 <= key <= 126:
                        key_info += f" char: '{chr(key)}'"
                elif isinstance(key, str):
                    key_info += f" ord: {ord(key) if len(key) == 1 else 'N/A'}"

                self.editor._set_status_message(key_info)
                self.editor.update_screen()

            except curses.error:
                continue
            except Exception as e:
                self.editor._set_status_message(f"Debug error: {e}")
                break

        self.editor._set_status_message("TTY Debug Mode ended")

    def _decode_keystring(self, key_input: str | int) -> int | str:
        """Decodes a key specification string or integer into a key code or logical key identifier.

        This method supports terminal-specific key codes, named keys, and modifier combinations
        (Ctrl, Alt, Shift). It normalizes and parses key strings, returning either an integer
        key code or a logical string for Alt-based bindings.

        Args:
            key_input (Union[str, int]): The key specification as a string (e.g., "ctrl+z", "alt-x")
                or an integer key code.

        Returns:
            Union[int, str]: The resolved key code (int) or logical key identifier (str).

        Raises:
            ValueError: If the key string is invalid or contains unknown modifiers.
        """
        if isinstance(key_input, int):
            return key_input

        if not isinstance(key_input, str):
            raise ValueError(
                f"Invalid key_input type: {type(key_input)}. Expected str or int."
            )

        original_key_string = key_input
        s = key_input.strip().lower()

        if not s:
            raise ValueError("Key string cannot be empty.")

        logging.debug(
            f"_decode_keystring: Parsing key_input: {original_key_string!r} (initial s: {s!r})"
        )

        # Normalize alt+key to alt-key
        if "alt" in s.split("+"):
            parts = s.split("+")
            if "alt" in parts:
                base_key_for_alt = parts[-1]
                other_mods = [m for m in parts[:-1] if m != "alt"]
                other_mods.sort()

                normalized_s_parts = ["alt-"]
                if other_mods:
                    normalized_s_parts.append("+".join(other_mods))
                    normalized_s_parts.append("+")
                normalized_s_parts.append(base_key_for_alt)

                s = "".join(normalized_s_parts)
                logging.debug(
                    f"_decode_keystring: Normalized '{original_key_string}' to '{s}' for Alt processing."
                )

        if s.startswith("alt-"):
            logging.debug(
                f"_decode_keystring: Interpreted as logical Alt-binding: {s!r}"
            )
            return s

        # Named keys map for terminal environments
        named_keys_map: dict[str, int] = {
            "f1": curses.KEY_F1,
            "f2": curses.KEY_F2,
            "f3": curses.KEY_F3,
            "f4": curses.KEY_F4,
            "f5": curses.KEY_F5,
            "f6": curses.KEY_F6,
            "f7": curses.KEY_F7,
            "f8": curses.KEY_F8,
            "f9": curses.KEY_F9,
            "f10": curses.KEY_F10,
            "f11": curses.KEY_F11,
            "f12": curses.KEY_F12,
            "left": curses.KEY_LEFT,
            "right": curses.KEY_RIGHT,
            "up": curses.KEY_UP,
            "down": curses.KEY_DOWN,
            "home": curses.KEY_HOME,
            "end": getattr(curses, "KEY_END", curses.KEY_LL),
            "pageup": curses.KEY_PPAGE,
            "pgup": curses.KEY_PPAGE,
            "pagedown": curses.KEY_NPAGE,
            "pgdn": curses.KEY_NPAGE,
            "delete": curses.KEY_DC,
            "del": curses.KEY_DC,
            "backspace": curses.KEY_BACKSPACE,
            "insert": curses.KEY_IC,
            "tab": 9,
            "enter": curses.KEY_ENTER,
            "return": curses.KEY_ENTER,
            "space": ord(" "),
            "esc": 27,
            "escape": 27,
            "shift+left": curses.KEY_SLEFT,
            "sleft": curses.KEY_SLEFT,
            "shift+right": curses.KEY_SRIGHT,
            "sright": curses.KEY_SRIGHT,
            "shift+up": getattr(
                curses, "KEY_SR", getattr(curses, "KEY_SPREVIOUS", 337)
            ),
            "sup": getattr(curses, "KEY_SR", getattr(curses, "KEY_SPREVIOUS", 337)),
            "shift+down": getattr(curses, "KEY_SF", getattr(curses, "KEY_SNEXT", 336)),
            "sdown": getattr(curses, "KEY_SF", getattr(curses, "KEY_SNEXT", 336)),
            "shift+home": curses.KEY_SHOME,
            "shift+end": curses.KEY_SEND,
            "shift+pageup": getattr(
                curses, "KEY_SPPAGE", getattr(curses, "KEY_SPREVIOUS", 337)
            ),
            "shift+pagedown": getattr(
                curses, "KEY_SNPAGE", getattr(curses, "KEY_SNEXT", 336)
            ),
            "shift+tab": getattr(curses, "KEY_BTAB", 353),
            "/": ord("/"),
            "?": ord("?"),
            "\\": ord("\\"),
        }

        # Add function keys F1-F12
        named_keys_map.update(
            {f"f{i}": getattr(curses, f"KEY_F{i}", 256 + i) for i in range(1, 13)}
        )

        if s in named_keys_map:
            code = named_keys_map[s]
            logging.debug(f"_decode_keystring: Named key {s!r} resolved to code {code}")
            return code

        # Parse modifiers
        parts = s.split("+")
        base_key_str = parts[-1].strip()
        modifiers = set(p.strip() for p in parts[:-1])

        if "alt" in modifiers:
            logging.error(
                f"_decode_keystring: 'alt' unexpectedly found in modifiers for '{s}' at a late stage."
            )
            modifiers.remove("alt")
            remaining_modifiers_part = ""
            if modifiers:
                sorted_remaining_modifiers = sorted(list(modifiers))
                remaining_modifiers_part = "+".join(sorted_remaining_modifiers) + "+"
            return f"alt-{remaining_modifiers_part}{base_key_str}"

        # Determine base key code
        base_code: int
        if base_key_str in named_keys_map:
            base_code = named_keys_map[base_key_str]
        elif len(base_key_str) == 1:
            base_code = ord(base_key_str)
        else:
            raise ValueError(
                f"Unknown base key '{base_key_str}' in '{original_key_string}'"
            )

        # Handle Ctrl modifier
        if "ctrl" in modifiers:
            modifiers.remove("ctrl")
            if "a" <= base_key_str <= "z" and len(base_key_str) == 1:
                base_code = ord(base_key_str) - ord("a") + 1
            elif base_key_str == "#":
                base_code = 51  # Ctrl+#
                logging.debug("_decode_keystring: Ctrl+# mapped to code 51")
            elif base_key_str == "/":
                base_code = 31  # Ctrl+/ = ASCII 31
                logging.debug("_decode_keystring: Ctrl+/ mapped to code 31")
            elif base_key_str == "\\":
                base_code = 28  # Ctrl+\\ = ASCII 28
            elif base_key_str == "[":
                base_code = 27  # Ctrl+[ = ESC
            elif base_key_str == "]":
                base_code = 29  # Ctrl+]
            elif base_key_str == "z":
                base_code = 26  # Ctrl+Z

        # Handle Shift modifier
        if "shift" in modifiers:
            modifiers.remove("shift")
            if (
                "a" <= base_key_str <= "z"
                and len(base_key_str) == 1
                and base_code == ord(base_key_str)
            ):
                base_code = ord(base_key_str.upper())

        if modifiers:
            raise ValueError(
                f"Unknown or unhandled modifiers {list(modifiers)} in '{original_key_string}'"
            )

        logging.debug(
            f"_decode_keystring: Final resolved integer key code for '{original_key_string}': {base_code}"
        )
        return base_code

    def _setup_action_map(self) -> dict[int | str, Callable[..., Any]]:
        """Constructs and returns a mapping from key codes (integers or strings) to their corresponding
        editor action methods.
        This method builds a dictionary that associates key codes (used for keyboard shortcuts)
        with callable methods that implement editor actions. The mapping is constructed from:
          - A predefined set of core editor actions and handlers.
          - Additional actions enabled by editor features (such as linting or AI widgets), depending
            on the editor's configuration.
          - Built-in key handlers for compatibility with TTY/curses environments.
          - User-defined or default keybindings from the editor's configuration.
        The method ensures that only valid actions and key codes are mapped, logs warnings for
        missing or conflicting bindings, and returns the final mapping for use in key event handling.

        Returns:
            Dict[Union[int, str], Callable[..., Any]]: A dictionary mapping key codes to their
            corresponding editor action methods.
        """
        logging.debug("Setting up action map for KeyBinder.")
        # This dictionary maps action names (from config) to the actual methods
        # on the Ecli instance.
        action_to_method_map: dict[str, Callable] = {
            # --- File and Edit Actions (Always available) ---
            "open_file": self.editor.open_file,
            "save_file": self.editor.save_file,
            "save_as": self.editor.save_file_as,
            "new_file": self.editor.new_file,
            "copy": self.editor.copy,
            "cut": self.editor.cut,
            "paste": self.editor.paste,
            "undo": self.history.undo,
            "redo": self.history.redo,
            "select_all": self.editor.select_all,
            "delete": self.editor.handle_delete,
            "quit": self.editor.exit_editor,
            # --- Navigation and Text Manipulation (Always available) ---
            "handle_home": self.editor.handle_home,
            "handle_end": self.editor.handle_end,
            "handle_page_up": self.editor.handle_page_up,
            "handle_page_down": self.editor.handle_page_down,
            "extend_selection_up": self.editor.extend_selection_up,
            "extend_selection_down": self.editor.extend_selection_down,
            "extend_selection_left": self.editor.extend_selection_left,
            "extend_selection_right": self.editor.extend_selection_right,
            "select_to_home": self.editor.select_to_home,
            "select_to_end": self.editor.select_to_end,
            "find": self.editor.find_prompt,
            "find_next": self.editor.find_next,
            "search_and_replace": self.editor.search_and_replace,
            "goto_line": self.editor.goto_line,
            "tab": self.editor.handle_smart_tab,
            "shift_tab": self.editor.handle_smart_unindent,
            "toggle_comment_block": self.editor.toggle_comment_block,
            "toggle_insert_mode": self.editor.toggle_insert_mode,
            # --- Core Handlers (Always available) ---
            "handle_up": self.editor.handle_up,
            "handle_down": self.editor.handle_down,
            "handle_left": self.editor.handle_left,
            "handle_right": self.editor.handle_right,
            "handle_backspace": self.editor.handle_backspace,
            "handle_enter": self.editor.handle_enter,
            "help": self.editor.show_help,
            "cancel_operation": self.editor.handle_escape,
            "toggle_file_browser": self.editor.toggle_file_browser,
            "toggle_focus": self.editor.toggle_focus,
            # --- Git ---
            "git_menu": self.editor.show_git_panel,
            # --- AI ---
            "request_ai_explanation": self.editor.toggle_widget_panel,
            # --- Debugging (Always available) ---
            "debug_show_lexer": lambda: self.editor._set_status_message(
                f"Current Lexer: {self.editor._lexer.name if self.editor._lexer else 'None'}"
            ),
        }

        if not self.editor.is_lightweight:
            if self.editor.linter_bridge:
                action_to_method_map["lint"] = self.editor.run_lint_async
                action_to_method_map["show_lint_panel"] = self.editor.show_lint_panel

            if self.editor.async_engine:
                action_to_method_map["toggle_widget_panel"] = (
                    self.editor.toggle_widget_panel
                )

        final_key_action_map: dict[int | str, Callable] = {}

        # --- Built-in key handlers for TTY/curses compatibility ---
        builtin_curses_key_handlers: dict[int, Callable] = {
            curses.KEY_UP: action_to_method_map["handle_up"],
            curses.KEY_DOWN: action_to_method_map["handle_down"],
            curses.KEY_LEFT: action_to_method_map["handle_left"],
            curses.KEY_RIGHT: action_to_method_map["handle_right"],
            curses.KEY_RESIZE: self.editor.handle_resize,
            curses.KEY_ENTER: action_to_method_map["handle_enter"],
            10: action_to_method_map["handle_enter"],  # LF
            13: action_to_method_map["handle_enter"],  # CR
        }

        for key_code, method_callable in builtin_curses_key_handlers.items():
            final_key_action_map[key_code] = method_callable

        # --- Map keybindings from config and defaults ---
        for action_name, key_code_list in self.keybindings.items():
            method_callable = action_to_method_map.get(action_name)
            if not method_callable:
                # It's normal for some actions to be unavailable in lightweight mode,
                # so we only log a warning if in full-featured mode.
                if not self.editor.is_lightweight:
                    logging.warning(
                        f"Action '{action_name}' in keybindings but no corresponding method. Ignored."
                    )
                continue

            for key_code in key_code_list:
                if not isinstance(key_code, (int, str)):
                    logging.error(
                        f"Invalid key code '{key_code}' for action '{action_name}'. Skipped."
                    )
                    continue

                if (
                    key_code in final_key_action_map
                    and final_key_action_map[key_code].__name__
                    != method_callable.__name__
                ):
                    logging.warning(
                        f"Keybinding for action '{action_name}' (key: {key_code}) is overwriting "
                        f"an existing mapping for method '{final_key_action_map[key_code].__name__}'."
                    )
                final_key_action_map[key_code] = method_callable

        # Log the final map for debugging.
        final_map_log_str = {k: v.__name__ for k, v in final_key_action_map.items()}
        logging.debug(f"Final constructed action map: {final_map_log_str}")
        return final_key_action_map

    def get_key_input(self, window: Optional[curses.window] = None) -> int | str:
        """Reads a single key or key sequence from the terminal, with robust handling of ESC sequences (e.g., for Alt+key) in TTY mode.

        Args:
            window (Optional[curses.window]): The curses window to read input from. If None, uses self.stdscr.

        Returns:
            Union[int, str]: The key code as an integer, or a string representing an Alt+key combination (e.g., "alt-a").
                - Returns 27 for the Escape key.
                - Returns curses.ERR on curses-related errors.
                - Returns -1 on unexpected exceptions.

        Raises:
            None: All exceptions are handled internally.
        """
        logging.debug("get_key_input: Waiting for key input from terminal.")
        if not window:
            logging.debug("get_key_input: No window provided, using stdscr.")
        else:
            logging.debug(f"get_key_input: Using provided window: {window}")
        target = window or self.stdscr
        try:
            # Use getch() for reliability; it returns an int
            key = target.getch()

            if key != 27:  # If this is not ESC, just return the code
                return key

            # If this is ESC, it might be the start of an Alt combination.
            # Make ONE non-blocking attempt to read the next character.
            target.nodelay(True)
            next_key = target.getch()
            target.nodelay(False)  # Immediately return to blocking mode

            if next_key == curses.ERR:
                # If nothing was read after ESC, it was just the Escape key
                return 27
            # We caught the sequence ESC + something else.
            # This is almost certainly an Alt combination.

            # Convert the second character to char if possible
            try:
                char_after_esc = chr(next_key)
                if "a" <= char_after_esc.lower() <= "z":
                    # This is the classic Alt + letter
                    alt_key_str = f"alt-{char_after_esc.lower()}"
                    logging.debug(
                        f"TTY: Parsed ESC sequence as logical key: {alt_key_str}"
                    )
                    return alt_key_str
            except ValueError:
                # next_key is not a valid character, ignoring
                pass

            # If this was not an Alt+letter (e.g., Alt+arrow),
            # curses often returns a special code by itself.
            # But if we got ESC + something_unexpected,
            # we return just ESC, and the second character goes back to the buffer for the next read.
            curses.ungetch(next_key)
            return 27

        except curses.error:
            # Error reading, e.g., due to window resizing
            return curses.ERR
        except Exception:
            logging.exception("get_key_input: unexpected error")
            return -1

    def lookup(self, key_spec: str | int) -> Optional[str]:
        """Finds the action name associated with a given key specification.
        This is the reverse of the main action map logic, useful for tests
        or displaying help.

        Args:
            key_spec: The key string (e.g., "ctrl+s") or integer code.

        Returns:
            The name of the action (e.g., "save_file") or None if not found.
        """
        try:
            # First, we decode the string/number into canonical form
            decoded_key = self._decode_keystring(key_spec)
        except ValueError:
            return None  # Invalid key string

        # Look up the action associated with this decoded key
        for action_name, key_list in self.keybindings.items():
            if decoded_key in key_list:
                return action_name

        return None
