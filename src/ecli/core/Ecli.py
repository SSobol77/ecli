# ecli/core/Ecli.py
# ruff: noqa: E501
"""ecli.core.Ecli.py
============================
Ecli: Main Module for the ECLI Terminal-Based Text Editor

This module defines the core Ecli class, which serves as the central
controller for the ECLI terminal text editor application. It manages all
primary editor functionality, including:

- File operations (open, save, revert, new file)
- Text editing, selection, and navigation
- Syntax highlighting (Pygments and custom regex-based)
- Clipboard integration (internal and system)
- Undo/redo history management
- Block operations (indent, unindent, comment, uncomment)
- Search, find/replace, and search highlighting
- Git integration and linter/LSP diagnostics
- Panel management (file browser, Git panel, AI assistant, etc.)
- Auto-save and background task handling
- User interface rendering and keybinding delegation
- Robust error handling and status messaging

The Ecli class is designed for extensibility and modularity,
delegating specialized tasks to dedicated components (e.g., History,
CodeCommenter, GitBridge, LinterBridge, PanelManager).
It provides a curses-based UI and supports advanced features such as multi-line
selection, bracket matching, and asynchronous shell command execution.

This module is intended to be the main entry point for the ECLI editor's core
logic and should be imported and instantiated by the application's main script.
"""

import curses
import functools
import logging
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
    Literal,
    Optional,
    TextIO,
    cast,
    overload,
)
from unittest.mock import Mock

import chardet
import pyperclip

# Imports of third party libraries that are USED in the class
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_for_filename, guess_lexer
from pygments.token import Token
from wcwidth import wcswidth, wcwidth

from ecli.core.AsyncEngine import AsyncEngine
from ecli.core.CodeCommenter import CodeCommenter

# Imports from ecli package
from ecli.core.History import History
from ecli.integrations.GitBridge import GitBridge
from ecli.integrations.LinterBridge import LinterBridge
from ecli.ui.DrawScreen import DrawScreen
from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.PanelManager import PanelManager
from ecli.ui.panels import FileBrowserPanel, GitPanel
from ecli.utils.logging_config import logger
from ecli.utils.utils import hex_to_xterm


# --- CONDITIONAL IMPORT FOR UNIX SYSTEMS ---
if sys.platform != "win32":
    import termios


## ==================== Ecli Class ====================
class Ecli:
    """Class Ecli
    =========================
    Ecli is the main class for the ECLI terminal-based text editor.
    This class encapsulates the core logic, state management, and user interface for
    the ECLI editor.It provides functionality for file operations, text editing,
    syntax highlighting, keybindings, clipboard actions, selection handling,
    Git integration, Language Server Protocol (LSP) support,and interaction with
    the curses-based terminal UI.

    Attributes:
        stdscr (curses.window): The main curses window object for terminal display.
        is_lightweight (bool): Whether the editor is running in
                               lightweight mode (reduced features).
        show_line_numbers (bool): Whether to display line numbers in the editor.
        original_termios_attrs (Any): Stores original terminal attributes
                                      for restoration.
        config (dict): The configuration dictionary loaded from the user's config file.
        user_colors (dict): User-defined color settings.
        colors (dict): Mapping of semantic color names to curses color pairs.
        text (list[str]): The text buffer, where each element is a line.
        cursor_x (int): The current cursor column position.
        cursor_y (int): The current cursor row position.
        scroll_top (int): The topmost visible line in the editor window.
        scroll_left (int): The leftmost visible column in the editor window.
        modified (bool): Indicates if the buffer has unsaved changes.
        encoding (str): The file encoding used for reading/writing files.
        filename (Optional[str]): The name of the currently open file.
        insert_mode (bool): Whether the editor is in insert mode.
        status_message (str): The current status message displayed in the status bar.
        lint_panel_message (Optional[str]): The message displayed in the linter panel.
        lint_panel_active (bool): Whether the linter panel is currently visible.
        visible_lines (int): Number of text lines visible in the editor window.
        last_window_size (tuple[int, int]): The last known terminal window size.
        _force_full_redraw (bool): Flag to force a complete redraw of the UI.
        focus (str): Indicates the current focus ("editor" or "panel").
        selection_start (Optional[tuple[int, int]]): Start coordinates of the current selection.
        selection_end (Optional[tuple[int, int]]): End coordinates of the current selection.
        is_selecting (bool): Whether a text selection is currently active.
        search_term (str): The current search term.
        search_matches (list[tuple[int, int, int]]): List of search match positions.
        current_match_idx (int): Index of the current search match.
        highlighted_matches (list[tuple[int, int, int]]): List of highlighted search matches.
        current_language (Optional[str]): The detected language of the current file.
        _lexer (Optional[TextLexer]): The current Pygments lexer for syntax highlighting.
        custom_syntax_patterns (list): List of custom regex patterns for syntax highlighting.
        _state_lock (threading.RLock): Lock for thread-safe state changes.
        _shell_cmd_q (queue.Queue): Queue for shell command execution.
        _git_q (queue.Queue): Queue for Git operations.
        _git_cmd_q (queue.Queue): Queue for Git command strings.
        _async_results_q (queue.Queue): Queue for asynchronous operation results.
        internal_clipboard (str): Internal clipboard buffer for copy/cut/paste.
        git (Optional[GitBridge]): Git integration component.
        linter_bridge (Optional[LinterBridge]): Linter/LSP integration component.
        async_engine (Optional[AsyncEngine]): Asynchronous task engine.
        panel_manager (Optional[PanelManager]): Manages UI panels.
        git_panel_instance (Optional[GitPanel]): Persistent instance of the Git panel.
        file_browser_instance (Optional[FileBrowserPanel]): Persistent instance of the file browser panel.
        history (History): Undo/redo history manager.
        commenter (CodeCommenter): Code commenting/uncommenting helper.
        drawer (DrawScreen): Responsible for drawing the editor UI.
        keybinder (KeyBinder): Handles keybindings and input dispatch.
        running (bool): Main loop control flag.
        use_system_clipboard (bool): Whether to use the system clipboard if available.
        pyclip_available (bool): Whether pyperclip/system clipboard is available.
        _auto_save_thread (Optional[threading.Thread]): Background auto-save thread.
        _auto_save_enabled (bool): Whether auto-save is enabled.
        _auto_save_stop_event (threading.Event): Event to signal auto-save thread to stop.  # noqa: E501
        _auto_save_interval (float): Interval (in seconds) for auto-save.
        _exit_in_progress (bool): Flag to prevent multiple exit sequences.

    Methods:
        __init__(stdscr, config, lightweight_mode=False, show_line_numbers=True):
            Initializes the Ecli instance and all components.
        close():
        toggle_focus():
            Switches the focus between the main editor and the active panel.
        show_git_panel():
            Shows the Git panel using its persistent instance.
        toggle_widget_panel():
            Shows the AI widget panel.
        toggle_file_browser():
            Shows the file browser panel using its persistent instance.
        toggle_comment_block():
            Toggles commenting for the selected block or current line.
        reload_devops_module():
            Hot-reloads the DevOps linter module.
        run_lint_async(code=None):
        show_lint_panel():
        _check_pyclip_availability():
            Checks the availability of the pyperclip library and system clipboard.
        get_selected_text():
            Returns the currently selected text from the editor buffer.
        copy():
            Copies the selected text to the clipboard.
        _clamp_scroll_and_check_change(original_scroll_tuple):
            Clamps scroll and checks if it changed.
        _get_normalized_selection_range():
            Returns normalized selection coordinates.
        delete_text_internal(start_row, start_col, end_row, end_col):
            Deletes text in the specified range.
        handle_smart_unindent():
            Handles smart unindentation (Shift+Tab).
        _get_tokenized_line(line_content, lexer_id, custom_rules_exist):
            Tokenizes a single line for syntax highlighting.
        apply_syntax_highlighting_with_pygments(lines, line_indices):
        _detect_color_capabilities():
        exit_editor():
            Gracefully saves, shuts down background services, restores the terminal, and exits.
        detect_language():
            Detects the file's language and sets the syntax highlighter.
        apply_custom_highlighting(line):
            Applies syntax highlighting using custom regex patterns.
        delete_char_internal(row, col):
            Deletes a single character at the specified position.
        handle_resize():
        get_display_width(text):
            Returns the printable width of text in terminal cells.
        handle_up(), handle_down(), handle_left(), handle_right():
            Cursor navigation methods.
        handle_home(), handle_end(), handle_page_up(), handle_page_down():
            Cursor movement and scrolling methods.
        goto_line():
            Moves the cursor to a specified line number.
        _goto_match(match_index):
            Moves the cursor to the specified search match.
        set_initial_cursor_position():
            Sets the initial cursor position and scrolling offsets.
        _clamp_scroll():
            Ensures scroll offsets keep the cursor visible.
        _ensure_cursor_in_bounds():
            Clamps cursor position to valid buffer positions.
        handle_backspace(), handle_delete():
            Handles backspace and delete key actions.
        handle_smart_tab(), handle_tab(), handle_enter():
            Handles tabbing and newline insertion.
        insert_text(text), insert_text_at_position(text, row, col):
            Inserts text at the current or specified position.
        delete_selected_text_internal(start_y, start_x, end_y, end_x):
            Deletes text between the specified coordinates.
        paste():
            Pastes text from the clipboard.
        delete_selected_text():
            Deletes the currently selected text and records it in history.
        cut():
            Cuts the selected text to the clipboard.
        undo(), redo():
            Undo and redo actions.
        _cancel_selection_if_not_extending():
        extend_selection_right(), extend_selection_left(), extend_selection_up(), extend_selection_down():  # noqa: E501
            Methods for extending the selection in various directions.
        select_to_home(), select_to_end(), select_all():
            Methods for selecting to line start, end, or the entire buffer.
        handle_block_indent(), handle_block_unindent(), unindent_current_line():
            Methods for block indentation and unindentation.
        comment_lines(), uncomment_lines():
            Methods for commenting and uncommenting lines.
    """

    # --- Status message and lint panel management ---
    def _set_status_message(
        self,
        message_for_statusbar: str,
        is_lint_status: bool = False,
        full_lint_output: Optional[str] = None,
        activate_lint_panel_if_issues: bool = False,
    ) -> None:
        """Sets the status message and, if applicable, delegates linter panel management."""
        try:
            message_for_statusbar = str(message_for_statusbar)

            if self.status_message != message_for_statusbar:
                self.status_message = message_for_statusbar
                logging.debug(
                    f"Status message set directly to: '{self.status_message}'"
                )  # noqa: E501

            # Delegate all complex lint panel logic to a helper method
            if is_lint_status:
                self._handle_lint_status(
                    full_lint_output, activate_lint_panel_if_issues
                )  # noqa: E501

        except Exception as e:
            logging.error(
                f"Unexpected error in _set_status_message: {e}", exc_info=True
            )  # noqa: E501
            try:
                self.status_message = f"Status update error: {str(e)[:50]}"
            except Exception as e_fallback:
                logging.critical(f"Failed to set fallback status message: {e_fallback}")

    # Helper for lint panel management
    def _handle_lint_status(
        self, full_lint_output: Optional[str], activate_lint_panel_if_issues: bool
    ) -> None:
        """Manages the state and content of the linter panel based on lint results.
        This helper is called by _set_status_message.
        """
        panel_state_or_content_changed = False

        if full_lint_output is not None:
            new_panel_message_str = str(full_lint_output)
            if self.lint_panel_message != new_panel_message_str:
                self.lint_panel_message = new_panel_message_str
                panel_state_or_content_changed = True

        if activate_lint_panel_if_issues and self.lint_panel_message:
            no_issues_substrings = ["no issues found", "no linting issues"]
            panel_message_lower = self.lint_panel_message.strip().lower()
            has_actual_issues = not any(
                sub in panel_message_lower for sub in no_issues_substrings
            )

            if has_actual_issues and not self.lint_panel_active:
                self.lint_panel_active = True
                panel_state_or_content_changed = True

        if panel_state_or_content_changed and self.lint_panel_active:
            self._force_full_redraw = True

    # -- Initialization and Setup ---
    def __init__(
        self,
        stdscr: "curses.window",
        config: dict[str, Any],
        lightweight_mode: bool = False,
        show_line_numbers: bool = True,
    ) -> None:
        """Creates and fully initializes a `Ecli` instance.
        Delegates complex setup to private helper methods to reduce complexity.
        """
        # Basic setup
        self.stdscr = stdscr
        self.config: dict[str, Any] = config
        self.is_lightweight: bool = lightweight_mode
        self.show_line_numbers: bool = show_line_numbers

        # Initialize all state attributes
        self._initialize_state()

        # Initialize components
        self._initialize_components()

        # Setup environment (terminal, clipboard, etc.)
        self._setup_environment()

        # Final setup steps
        self.set_initial_cursor_position()
        self._ensure_trailing_newline()
        self.handle_resize()
        logging.info(
            f"Ecli initialized successfully. \
                Lightweight: {self.is_lightweight}"
        )

    # --- State Initialization ---
    def _initialize_state(self) -> None:
        """Initializes all editor state attributes to their default values."""
        self.text: list[str] = [""]
        self.cursor_x: int = 0
        self.cursor_y: int = 0
        self.scroll_top: int = 0
        self.scroll_left: int = 0
        self.modified: bool = False
        self.encoding: str = "UTF-8"
        self.filename: Optional[str] = None
        self.insert_mode: bool = True
        self.status_message: str = "Ready"
        self._last_status_msg_sent: Optional[str] = None
        self.lint_panel_message: str = ""
        self.lint_panel_active: bool = False
        self.visible_lines: int = 0
        self.last_window_size: tuple[int, int] = (0, 0)
        self._force_full_redraw: bool = False
        self.focus: str = "editor"
        self.selection_start: Optional[tuple[int, int]] = None
        self.selection_end: Optional[tuple[int, int]] = None
        self.is_selecting: bool = False
        self.search_term: str = ""
        self.search_matches: list[tuple[int, int, int]] = []
        self.current_match_idx: int = -1
        self.highlighted_matches: list[tuple[int, int, int]] = []
        self.current_language: Optional[str] = None
        self._lexer: Optional[TextLexer] = None
        self.custom_syntax_patterns: list[tuple[re.Pattern, str]] = []
        self._state_lock: threading.RLock = threading.RLock()
        self._shell_cmd_q: queue.Queue[str] = queue.Queue()
        self._git_q: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._git_cmd_q: queue.Queue[str] = queue.Queue()
        self._async_results_q: queue.Queue[dict[str, Any]] = queue.Queue()
        self.internal_clipboard: str = ""

    # --- Component Initialization ---
    def _initialize_components(self) -> None:
        """Initializes all editor components like History, Drawer, Git, etc."""
        self.colors: dict[str, int] = {}
        self.init_colors()

        # Initialize components that are always needed
        self.history: History = History(self)
        self.commenter: CodeCommenter = CodeCommenter(self)
        self.drawer: DrawScreen = DrawScreen(self, self.config)

        # Initialize optional components to None first
        self.git: Optional[GitBridge] = None
        self.linter_bridge: Optional[LinterBridge] = None
        self.async_engine: Optional[AsyncEngine] = None
        self.panel_manager: Optional[PanelManager] = None
        self.git_panel_instance: Optional[GitPanel] = None
        self.file_browser_instance: Optional[FileBrowserPanel] = None

        if not self.is_lightweight:
            self.git = GitBridge(self)
            self.linter_bridge = LinterBridge(self)
            self.async_engine = AsyncEngine(
                to_ui_queue=self._async_results_q, config=self.config
            )
            self.async_engine.start()
            self.panel_manager = PanelManager(self)
            self.git_panel_instance = GitPanel(self.stdscr, self)
            self.file_browser_instance = FileBrowserPanel(self.stdscr, self)

            if self.file_browser_instance and self.git_panel_instance:
                self.file_browser_instance.set_git_panel(self.git_panel_instance)
            if self.panel_manager:
                self.panel_manager.registered_panels["git"] = GitPanel
        else:
            # Use Mocks for lightweight mode to avoid AttributeError
            self.git = Mock()
            self.linter_bridge = Mock()
            self.panel_manager = Mock()

        # KeyBinder is initialized last as it may depend on other components
        self.keybinder: KeyBinder = KeyBinder(self)
        self.handle_input = self.keybinder.handle_input

    # --- Environment Setup ---
    def _setup_environment(self) -> None:
        """Configures terminal settings, clipboard, and auto-save."""
        self.stdscr.keypad(True)
        curses.curs_set(1)
        self.original_termios_attrs: Optional[list[Any]] = None

        if self.is_lightweight:
            return

        # Setup termios for Unix-like systems
        if sys.platform != "win32":
            try:
                fd = sys.stdin.fileno()
                self.original_termios_attrs = termios.tcgetattr(fd)
                attrs = list(self.original_termios_attrs)
                attrs[0] &= ~(termios.IXON | termios.IXOFF)
                attrs[3] &= ~(termios.ICANON | termios.ISIG)
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
            except Exception as exc:
                logging.warning("Could not set Unix terminal attributes: %s", exc)

        curses.raw()
        curses.noecho()

        # Setup clipboard
        self.use_system_clipboard: bool = self.config.get("editor", {}).get(
            "use_system_clipboard", True
        )  # noqa: E501
        self.pyclip_available: bool = self._check_pyclip_availability()
        if not self.pyclip_available:
            self.use_system_clipboard = False
        # Setup auto-save
        self._auto_save_thread: Optional[threading.Thread] = None
        self._auto_save_enabled: bool = False
        self._auto_save_stop_event: threading.Event = threading.Event()
        try:
            self._auto_save_interval: float = float(
                self.config.get("settings", {}).get("auto_save_interval", 1.0)
            )  # noqa: E501
            if self._auto_save_interval <= 0:
                raise ValueError
        except (ValueError, TypeError):
            self._auto_save_interval = 1.0

        if self.git:
            self.git.update_git_info()

    # --- Clipboard Availability Check ---
    def close(self) -> None:
        """Gracefully shuts down the editor and releases all associated resources.

        This method stops background services (like auto-save) and delegates the
        shutdown of any running linter processes (such as the LSP server) to the
        `LinterBridge` component.

        This ensures a clean exit by properly terminating child processes and
        joining their associated threads.

        Notes:
            This method is idempotent: repeated calls are safe and will not raise
            exceptions if background services are already stopped.
        """
        logging.info(
            "Ecli.close() called, preparing \
                     to shut down all components."
        )

        # Stop background tasks (like auto-save) if they exist
        # This logic remains the same, assuming you have an auto-save mechanism.
        try:
            # Check if the auto-save thread exists and signal it to stop.
            if hasattr(self, "_auto_save_stop_event"):
                self._auto_save_stop_event.set()
                logging.debug("Signaled auto-save thread to stop.")
            # Your original code called a method; this is a more direct way if
            # you have a stop event. Adapt as needed.
            # self._stop_auto_save_thread()
        except AttributeError:
            # It's okay if auto-save attributes don't exist (e.g., disabled).
            pass
        except Exception as e:
            # Log any other errors during task shutdown.
            logging.warning(f"Exception while stopping background tasks: {e}")

        # Delegate LSP/linter shutdown to the LinterBridge component
        # Instead of handling the process and messages directly here, we just call
        # the shutdown method on our dedicated component. LinterBridge now
        # encapsulates all the details of stopping the LSP process and its threads.
        logging.debug("Delegating linter/LSP shutdown to LinterBridge.")

        if self.linter_bridge:
            self.linter_bridge.shutdown()

        logging.info("Ecli components have been shut down.")

    # ---- Switch focus panel ----
    def toggle_focus(self) -> bool:
        """Switches the input focus between the main editor and the active panel."""
        if not self.panel_manager or not self.panel_manager.is_panel_active():
            self._set_status_message("No active panel to switch focus to.")
        else:
            if self.focus == "editor":
                self.focus = "panel"
                self._set_status_message("Focus: Panel")
            else:
                self.focus = "editor"
                self._set_status_message("Focus: Editor")

            # Update cursor visibility based on the new focus
            curses.curs_set(1 if self.focus == "editor" else 0)
            logging.info(f"Focus switched to '{self.focus}'.")

        # Toggling focus or displaying a message always requires a redraw.
        return True

    # ---- Git panel show ----
    def show_git_panel(self) -> bool:
        """Shows the Git panel using its persistent instance."""
        # Add None checks for mypy
        if self.git_panel_instance and self.panel_manager:
            if not self.git:
                self._set_status_message("Git integration is not available.")
            else:
                repo_dir = (
                    Path(self.filename).parent
                    if self.filename and os.path.exists(self.filename)
                    else Path.cwd()
                )  # noqa: E501
                if not (repo_dir / ".git").is_dir():
                    self._set_status_message("Not a Git repository.")
                else:
                    # Use new method to show prepared instance
                    self.panel_manager.show_panel_instance(self.git_panel_instance)
        else:
            self._set_status_message("Git panel not available.")

        # This action always results in a UI change (panel opens or status
        # message appears), so a redraw is always required.
        return True

    # --- Comment/Uncomment Block - Ecli ---
    def _determine_lines_to_toggle_comment(self) -> Optional[tuple[int, int]]:
        """Determines the line range affected by comment or uncomment actions.

        With an active selection, returns the range from the first to the last
        selected line,excluding the last line if the selection ends at column 0
        (to match common IDE behavior).
        Without a selection, returns the current cursor row as both start and end.

        Returns:
            Optional[tuple[int, int]]: (start_row, end_row) indices, or None if
            selection is invalid.
        """
        if self.is_selecting and self.selection_start and self.selection_end:
            norm_range = self._get_normalized_selection_range()
            if not norm_range:
                return None
            start_coords, end_coords = norm_range

            start_y = start_coords[0]
            end_y = end_coords[0]

            # Exclude the last line if selection ends at column 0
            # and spans multiple lines
            if end_coords[1] == 0 and end_y > start_y:
                end_y -= 1
            return start_y, end_y
        return self.cursor_y, self.cursor_y

    # --- Panel toggles ---
    def toggle_widget_panel(self) -> bool:
        """Keeps original AI widget behaviour (bound to F7).
        Shows widget selection menu and launches the selected one.
        """
        # This function now simply calls select_ai_provider_and_ask,
        # which in turn will call the non-blocking panel.
        logging.debug("toggle_widget_panel -> AI panel request.")
        return self.select_ai_provider_and_ask()

    # --- File Browser Panel ---
    def toggle_file_browser(self) -> bool:
        """Shows the file browser panel using its persistent instance."""
        if self.file_browser_instance and self.panel_manager:
            # Use new method to show prepared instance
            self.panel_manager.show_panel_instance(self.file_browser_instance)
        else:
            self._set_status_message("File browser not available.")
        # No need to return anything here, as the panel manager handles the redraw.
        # This action always changes the UI state (shows a panel or a message),
        # so a redraw is always required.
        return True

    # --- Comment/Uncomment Block ---
    def toggle_comment_block(self) -> bool:
        """Determines the line range and delegates the commenting operation
        to the CodeCommenter helper class.
        """
        line_range = self._determine_lines_to_toggle_comment()

        if line_range is None:
            self._set_status_message("No lines selected to comment/uncomment.")
            # Set the message and let it go to the end
        else:
            start_y, end_y = line_range
            # Delegate the call to our new object
            self.commenter.perform_toggle(start_y, end_y)

        # The operation always changes something (status message or text),
        # so we always consider that a redraw is needed.
        return True

    # --- LSP --- DevOps module reload ---
    def reload_devops_module(self) -> bool:
        """Delegates the request to hot-reload the DevOps linter module.

        The actual implementation is handled by the LinterBridge component.
        This method provides a clean access point from the editor's keybindings.

        Returns:
            bool: The result from the LinterBridge's reload attempt, or False
                  if the linter bridge is not available.
        """
        if self.linter_bridge:
            # Delegate the call to the component responsible for linters.
            return self.linter_bridge.reload_devops_module()

        # If linter_bridge does not exist, reload is not possible.
        self._set_status_message("Linter component is not active.")
        return False

    # --- Linting and Linter Panel Management ---
    # Linting is now fully delegated to the LinterBridge component.
    # This keeps the Ecli class cleaner and separates concerns.
    # The LinterBridge handles tool selection (LSP vs. external),
    # execution, and result processing.
    # Ecli just provides a simple interface to trigger linting and
    # manage the panel visibility.
    def run_lint_async(self, code: Optional[str] = None) -> bool:
        """Initiates a linting operation for the current buffer.

        This method delegates the entire linting process—including tool selection
        (LSP vs. external), execution, and result handling—to the LinterBridge
        component.

        Args:
            code (Optional[str]): The source code to lint. If None, the current
                                editor buffer content is used.

        Returns:
            bool: True if the operation changed the editor's status message,
                indicating a redraw is needed. Returns False if the linter
                component is not available.
        """
        if self.linter_bridge:
            return self.linter_bridge.run_linter(code)

        # If linter_bridge does not exist, linting is not possible.
        self._set_status_message("Linter component is not active.")
        return True  # Return True, as we changed the status message

    def show_lint_panel(self) -> bool:
        """Toggles the visibility of the linter panel.

        This method acts as a user-driven toggle for the panel that displays
        detailed linter output. Its behavior is as follows:
        - If the panel is currently active, it will be hidden.
        - If the panel is inactive but there is a lint message to show, it
        will be activated and displayed.
        - If the panel is inactive and there is no lint message, it informs
        the user and remains hidden.

        This provides an intuitive toggle action for the user, typically bound
        to a key like F4 (which might be shared with `run_lint_async`).

        Returns:
            bool: True if the panel's visibility state (`self.lint_panel_active`)
                or the status message changed, indicating a redraw is needed.
                False otherwise.
        """
        logging.debug(
            f"show_lint_panel called. Current state: panel_active={self.lint_panel_active}, "
            f"message_exists={bool(self.lint_panel_message)}"
        )

        original_panel_state = self.lint_panel_active
        original_status = self.status_message

        # Logic for toggling the panel
        if self.lint_panel_active:
            # If the panel is currently visible, hide it.
            self.lint_panel_active = False
            self._set_status_message("Lint panel hidden")
            logging.debug("show_lint_panel: Panel was active, now hidden.")
        elif self.lint_panel_message:
            # If the panel is hidden but there is a message to show, activate it.
            self.lint_panel_active = True
            # No need to set a status message here, as the panel appearing is the feedback.
            logging.debug(
                "show_lint_panel: Panel was inactive, now activated to show message."
            )
        else:
            # If the panel is hidden and there is no message, inform the user.
            self._set_status_message("No linting information to display.")
            logging.debug("show_lint_panel: No lint message available to show.")

        # A change occurred if the panel's state flipped or the status message was updated.
        state_changed = (
            self.lint_panel_active != original_panel_state
            or self.status_message != original_status
        )

        if state_changed:
            logging.debug(
                f"show_lint_panel: State changed. Panel active: {self.lint_panel_active}. "
                f"Status: '{self.status_message}'"
            )

        return state_changed

    # ----- Clipboard Handling -------
    def _check_pyclip_availability(self) -> bool:  # Added return type hint
        """Checks the availability of the pyperclip library and underlying
        system clipboard utilities.
        This is typically called once during editor initialization.
        """
        # First, check if system clipboard usage is enabled in the configuration.
        if not self.config.get("editor", {}).get("use_system_clipboard", True):
            logging.debug("System clipboard usage is disabled by editor configuration.")
            return False  # Not available because it's turned off by config

        # Try to import and perform a basic operation with pyperclip.
        try:
            # Attempt a benign copy operation to check if pyperclip and its
            # dependencies are functional.
            # An empty string copy should not affect the actual clipboard
            # content significantly but will trigger exceptions if pyperclip
            # cannot access the clipboard.
            pyperclip.copy("")

            # pyperclip.paste() can sometimes be problematic or require user interaction
            # (e.g., on Wayland or due to terminal security policies), so a successful
            # copy("") is often a sufficient check for basic availability.
            # If paste() is also critical for your definition of "available", you might
            # add it, but be prepared for more potential PyperclipException scenarios.
            logging.debug(
                "pyperclip and system clipboard utilities appear to be available."
            )
            return True
        except pyperclip.PyperclipException as e:
            # This exception is raised by pyperclip if it encounters issues specific
            # to clipboard access (required utilities like xclip/xsel on Linux not found).
            logging.warning(
                f"System clipboard unavailable via pyperclip: {str(e)}. "
                f"Falling back to internal clipboard. Ensure clipboard utilities "
                f"(e.g., xclip, xsel, wl-copy, pbcopy) are installed."
            )
            return False
        except ImportError:  # Should not happen if pyperclip is a listed dependency
            logging.warning(
                "pyperclip library not found. System clipboard integration disabled. "
                "Please install it (e.g., 'pip install pyperclip')."
            )
            return False
        except Exception as e:
            # Catch any other unexpected errors during the check.
            logging.warning(
                f"An unexpected error occurred while checking system clipboard availability: {e}. "
                f"Falling back to internal clipboard.",
                exc_info=True,
            )  # Include stack trace for unexpected errors
            return False

    def get_selected_text(self) -> str:
        """Returns the currently selected text from the editor buffer, precisely
        respecting the start and end character positions.
        """
        if (
            not self.is_selecting
            or self.selection_start is None
            or self.selection_end is None
        ):
            return ""

        norm_range = self._get_normalized_selection_range()
        if not norm_range:
            return ""

        start_coords, end_coords = norm_range
        start_row, start_col = start_coords
        end_row, end_col = end_coords

        if start_row == end_row:
            # Single-line selection
            return self.text[start_row][start_col:end_col]
        # Multi-line selection
        selected_parts = []
        # Part of the first line
        selected_parts.append(self.text[start_row][start_col:])
        # Full middle lines
        for i in range(start_row + 1, end_row):
            selected_parts.append(self.text[i])
        # Part of the last line
        selected_parts.append(self.text[end_row][:end_col])

        return "\n".join(selected_parts)

    # --- Copy selected text ---
    def copy(self) -> bool:
        """Copies the selected text to the internal clipboard and, if enabled/available,
        to the system clipboard. This action does not modify the document.

        Returns:
            bool: True, as this action always updates the status message,
                  requiring a UI redraw.
        """
        selected_text = self.get_selected_text()

        if not selected_text:
            self._set_status_message("Nothing to copy")
        else:
            # Always copy to the internal clipboard as a reliable fallback
            self.internal_clipboard = selected_text
            logging.info(f"Copied {len(selected_text)} chars to internal clipboard.")

            status_update = "Copied to internal clipboard"

            if self.use_system_clipboard and self.pyclip_available:
                try:
                    pyperclip.copy(selected_text)
                    status_update = "Copied to system clipboard"
                    logging.info("Successfully copied text to system clipboard.")
                except Exception as e:
                    status_update = "Copied to internal (system clipboard error)"
                    logging.error(
                        f"Failed to copy to system clipboard: {e}", exc_info=True
                    )

            self._set_status_message(status_update)

        # The copy action (or attempting to copy) always results in a status message
        # update, so a redraw is always necessary.
        return True

    # auxiliary method
    def _clamp_scroll_and_check_change(
        self, original_scroll_tuple: tuple[int, int]
    ) -> bool:
        """Calls _clamp_scroll and returns True if scroll_top or scroll_left changed
        from the provided original_scroll_tuple.
        """
        old_st, old_sl = original_scroll_tuple
        self._clamp_scroll()  # This method updates self.scroll_top and self.scroll_left
        return self.scroll_top != old_st or self.scroll_left != old_sl

    # This is a helper method - a function that only reads the selection state
    # (self.is_selecting, self.selection_start, self.selection_end) and does not change any editor state.
    # Its job is to return normalized coordinates or None.
    def _get_normalized_selection_range(
        self,
    ) -> Optional[tuple[tuple[int, int], tuple[int, int]]]:
        """Helper method. Returns normalized selection coordinates (start_pos, end_pos),
        where start_pos is always logically before or at the same position as end_pos
        (i.e., start_row < end_row, or start_row == end_row and start_col <= end_col).

        Returns:
            Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
                A tuple containing two tuples: ((start_row, start_col), (end_row, end_col))
                representing the normalized selection range.
                Returns None if there is no active selection or if selection boundaries are not set.
        """
        if (
            not self.is_selecting
            or self.selection_start is None
            or self.selection_end is None
        ):
            logging.debug(
                "_get_normalized_selection_range: No active or valid selection."
            )
            return None

        # Unpack current selection start and end points
        # These are (row, col) tuples
        sy1, sx1 = self.selection_start
        sy2, sx2 = self.selection_end

        # Normalize the coordinates: (norm_start_y, norm_start_x) should be <= (norm_end_y, norm_end_x)
        if (sy1 > sy2) or (sy1 == sy2 and sx1 > sx2):
            # If the original start is after the original end, swap them
            norm_start_y, norm_start_x = sy2, sx2
            norm_end_y, norm_end_x = sy1, sx1
            logging.debug(
                f"_get_normalized_selection_range: Swapped selection points. Original: (({sy1},{sx1}), ({sy2},{sx2})), Normalized: (({norm_start_y},{norm_start_x}), ({norm_end_y},{norm_end_x}))"
            )
        else:
            # Original order is already normalized
            norm_start_y, norm_start_x = sy1, sx1
            norm_end_y, norm_end_x = sy2, sx2
            logging.debug(
                f"_get_normalized_selection_range: Selection points already normalized: (({norm_start_y},{norm_start_x}), ({norm_end_y},{norm_end_x}))"
            )

        return ((norm_start_y, norm_start_x), (norm_end_y, norm_end_x))

    def delete_text_internal(
        self, start_row: int, start_col: int, end_row: int, end_col: int
    ) -> None:
        """Removes text in the range [start_row, start_col) .. [end_row, end_col)."""
        # Normalization
        if (start_row > end_row) or (start_row == end_row and start_col > end_col):
            start_row, start_col, end_row, end_col = (
                end_row,
                end_col,
                start_row,
                start_col,
            )

        # Validation
        if not (0 <= start_row < len(self.text)) or not (0 <= end_row < len(self.text)):
            logging.error(
                "delete_text_internal: row index out of bounds (%s..%s)",
                start_row,
                end_row,
            )
            return

        # Correcting columns — cannot go beyond the limits of the corresponding lines
        start_col = max(0, min(start_col, len(self.text[start_row])))
        end_col = max(0, min(end_col, len(self.text[end_row])))

        if start_row == end_row:
            self.text[start_row] = (
                self.text[start_row][:start_col] + self.text[start_row][end_col:]
            )
        else:
            # Part of the first line up to start_col + part of the last line after end_col
            new_first = self.text[start_row][:start_col] + self.text[end_row][end_col:]
            # Remove all middle lines and the last one
            del self.text[start_row + 1 : end_row + 1]
            # Update the first line
            self.text[start_row] = new_first

        self.modified = True  # Update modification status

    def handle_smart_unindent(self) -> bool:
        """Handles smart unindentation (typically Shift+Tab).
        - If text is selected, unindents all lines in the selected block.
        - If no text is selected, unindents the current line.
        Returns True if any change occurred that requires a redraw, False otherwise.
        """
        if self.is_selecting:
            return self.handle_block_unindent()  # This method now returns bool
        return self.unindent_current_line()  # This method now returns bool

    @functools.lru_cache(maxsize=20000)
    def _get_tokenized_line(
        self, line_content: str, lexer_id: int, custom_rules_exist: bool
    ) -> list[tuple[str, int]]:
        """Tokenizes a single line of text for syntax highlighting.

        This method acts as a dispatcher:
        1. If `custom_rules_exist` is True, it uses the editor's custom regex-based
        highlighter (`apply_custom_highlighting`).
        2. Otherwise, it falls back to using the currently set Pygments lexer.

        The results are memoized using `@lru_cache` to significantly improve
        performance by avoiding re-tokenization of identical lines. The `lexer_id`
        and `custom_rules_exist` parameters are part of the cache key to ensure
        that changes to the lexer or rules invalidate the cache correctly.

        Args:
            line_content (str): The text content of the line to tokenize.
            lexer_id (int): The ID of the current Pygments lexer object.
            custom_rules_exist (bool): A flag indicating if custom syntax rules
                                    should be used instead of Pygments.

        Returns:
            A list of (substring, curses_attribute) tuples representing the
            colorized segments of the line.
        """
        """
        Tokenizes a single line of text for syntax highlighting.
        """
        if custom_rules_exist:
            return self.apply_custom_highlighting(line_content)

        if self._lexer is None:
            return [(line_content, self.colors.get("default", curses.A_NORMAL))]

        # --- Create two different palettes ---

        # Palette for modern terminals
        # uses semantic colors from self.colors
        semantic_color_map = {
            Token.Keyword: self.colors.get("keyword"),
            Token.Name.Function: self.colors.get("function"),
            Token.Name.Class: self.colors.get("class", self.colors.get("type")),
            Token.Name.Decorator: self.colors.get("decorator"),
            Token.Literal.String: self.colors.get("string"),
            Token.Literal.String.Doc: self.colors.get("comment"),
            Token.Literal.Number: self.colors.get("number"),
            Token.Comment: self.colors.get("comment"),
            Token.Operator: self.colors.get("operator"),
            Token.Punctuation: self.colors.get("default"),
            Token.Name.Builtin: self.colors.get("builtin"),
            Token.Name.Tag: self.colors.get("tag"),
            Token.Name.Attribute: self.colors.get("attribute"),
            Token.Error: self.colors.get("error"),
        }

        # Palette for legacy TTY terminals (hardcoded colors)
        tty_color_map = {
            Token.Keyword: curses.color_pair(2),
            Token.Keyword.Constant: curses.color_pair(2),
            Token.Keyword.Declaration: curses.color_pair(2),
            Token.Keyword.Namespace: curses.color_pair(2),
            Token.Keyword.Pseudo: curses.color_pair(2),
            Token.Keyword.Reserved: curses.color_pair(2),
            Token.Keyword.Type: curses.color_pair(2),
            Token.Name.Builtin: curses.color_pair(7),
            Token.Name.Function: curses.color_pair(3),
            Token.Name.Class: curses.color_pair(4),
            Token.Name.Decorator: curses.color_pair(5),
            Token.Name.Exception: curses.color_pair(8) | curses.A_BOLD,
            Token.Name.Variable: curses.color_pair(6),
            Token.Name.Attribute: curses.color_pair(6),
            Token.Name.Tag: curses.color_pair(5),
            Token.Literal.String: curses.color_pair(3),
            Token.Literal.String.Doc: curses.color_pair(1),
            Token.Literal.String.Interpol: curses.color_pair(3),
            Token.Literal.String.Escape: curses.color_pair(5),
            Token.Literal.String.Backtick: curses.color_pair(3),
            Token.Literal.String.Delimiter: curses.color_pair(3),
            Token.Literal.Number: curses.color_pair(4),
            Token.Literal.Number.Float: curses.color_pair(4),
            Token.Literal.Number.Hex: curses.color_pair(4),
            Token.Literal.Number.Integer: curses.color_pair(4),
            Token.Literal.Number.Oct: curses.color_pair(4),
            Token.Comment: curses.color_pair(1),
            Token.Comment.Multiline: curses.color_pair(1),
            Token.Comment.Preproc: curses.color_pair(1),
            Token.Comment.Special: curses.color_pair(1) | curses.A_BOLD,
            Token.Operator: curses.color_pair(6),
            Token.Operator.Word: curses.color_pair(2),
            Token.Punctuation: curses.color_pair(6),
            Token.Text: curses.color_pair(0),
            Token.Text.Whitespace: curses.color_pair(0),
            Token.Error: curses.color_pair(8) | curses.A_BOLD,
            Token.Generic.Heading: curses.color_pair(5) | curses.A_BOLD,
            Token.Generic.Subheading: curses.color_pair(5),
            Token.Generic.Deleted: curses.color_pair(8),
            Token.Generic.Inserted: curses.color_pair(4),
            Token.Generic.Emph: curses.color_pair(3) | curses.A_BOLD,
            Token.Generic.Strong: curses.color_pair(2) | curses.A_BOLD,
            Token.Generic.Prompt: curses.color_pair(7),
            Token.Generic.Output: curses.color_pair(0),
        }

        # --- Choose which palette to use ---
        token_color_map = (
            semantic_color_map if self.is_256_color_terminal else tty_color_map
        )

        default_color = self.colors.get("default", curses.A_NORMAL)

        tokenized_segments = []
        try:
            raw_tokens = list(lex(line_content, self._lexer))
            if not raw_tokens and line_content:
                return [(line_content, default_color)]

            for token_type, text_value in raw_tokens:
                color_attr = default_color
                # Traverse up the token tree to find a matching color.
                # E.g., Token.Keyword.Constant will match Token.Keyword if not defined itself.
                current_type = token_type
                while current_type:
                    if current_type in token_color_map:
                        color_attr = token_color_map[current_type]
                        break
                    current_type = current_type.parent
                tokenized_segments.append((text_value, color_attr or default_color))

        except Exception as e:
            logging.error(
                f"Pygments tokenization error for line '{line_content[:70]}...': {e}"
            )
            return [(line_content, default_color)]

        return tokenized_segments

    # --- Syntax-highlighting helper ------------------------------
    def apply_syntax_highlighting_with_pygments(
        self,
        lines: list[str],
        _line_indices: list[int],
    ) -> list[list[tuple[str, int]]]:
        """Returns a colorized representation of the requested lines.

        This method dispatches to the appropriate tokenizer for each line,
        either the custom regex-based highlighter or the Pygments lexer,
        based on whether custom rules are defined for the current language.

        Args:
            lines: A list of raw string content for each line to be highlighted.
            line_indices: The original buffer indices of the lines (unused here,
                        but maintained for API consistency).

        Returns:
            A list of lists, where each inner list contains (substring,
            curses_attribute) tuples for a single line.
        """
        # Ensure a lexer is set, even if it's just TextLexer.
        if self._lexer is None:
            self.detect_language()

        highlighted: list[list[tuple[str, int]]] = []
        lexer_id = id(self._lexer) if self._lexer else 0

        # Determine once if custom rules should be used for this language.
        has_custom_rules = bool(getattr(self, "custom_syntax_patterns", []))

        if has_custom_rules:
            logging.debug("Applying custom syntax highlighting rules.")
        else:
            logging.debug(
                f"Applying Pygments highlighting with lexer: '{self._lexer.name if self._lexer else 'None'}'"
            )

        for raw_line in lines:
            # Pass all three required arguments to the cached function.
            segments = self._get_tokenized_line(raw_line, lexer_id, has_custom_rules)
            highlighted.append(segments)

        return highlighted

    # --- Colour-initialisation helper -----------------------------
    def _detect_color_capabilities(self) -> tuple[bool, bool, int]:
        """Detects the terminal's color support capabilities.

        Returns:
            tuple[bool, bool, int]: A tuple of the form:
                - have_color (bool): Whether the terminal supports at least 8 colors.
                - use_extended (bool): Whether extended color modes (256+) are supported.
                - max_colors (int): The number of colors supported by the terminal.

        Notes:
            This function queries the terminal's color capabilities using `curses.tigetnum("colors")`
            and applies thresholds for interpreting the result:
                - Fewer than 8 colors: considered no usable color support.
                - 8–15 colors: basic ANSI palette.
                - 16–255 colors: normal extended mode.
                - 256 or more: full extended color mode is assumed.
        """
        max_colors = curses.tigetnum("colors")

        if max_colors < 8:
            return False, False, max_colors  # Not enough colors for meaningful display
        if max_colors < 16:
            return True, False, max_colors  # Basic 8-color palette
        if max_colors < 256:
            return True, False, max_colors  # 16-color mode (with bright variants)
        return True, True, max_colors  # 256-color mode or better

    def exit_editor(self) -> None:
        """Gracefully handles the editor exit sequence.

        This method orchestrates a clean shutdown. It first checks for unsaved
        changes and prompts the user to save them. If the user cancels, the exit
        is aborted.

        Crucially, this method does NOT call `sys.exit()` directly. Instead, it
        signals the main `run()` loop to terminate by setting `self.running = False`.
        This allows the `curses.wrapper` (which invoked the `run` method) to
        handle the restoration of the terminal state (e.g., calling `curses.endwin()`),
        preventing terminal corruption and `endwin() returned ERR` errors.

        It also ensures background services like the AsyncEngine and auto-save
        are properly shut down before the application terminates.
        """
        # 1. Lightweight Instance Protection
        # Panels and other lightweight instances should not be able to close the entire application.
        if self.is_lightweight:
            logging.warning(
                "exit_editor called on a lightweight instance. This is not allowed."
            )
            self._set_status_message("Exit action is disabled in this context.")
            return

        # 2. Re-entrancy Guard
        # Prevents the exit sequence from being triggered multiple times if the user
        # presses the exit key rapidly.
        if hasattr(self, "_exit_in_progress") and self._exit_in_progress:
            return
        self._exit_in_progress = True
        logger.info("--- EXIT SEQUENCE INITIATED ---")

        # 3. Handle Unsaved Changes
        # Prompt the user to save if the buffer has been modified.
        if self.modified:
            ans = self.prompt("Save changes before exiting? (y/n): ")
            if ans and ans.lower().startswith("y"):
                # If user chooses to save, attempt the save operation.
                if not self.save_file():
                    # If saving fails or is cancelled, abort the exit sequence.
                    self._set_status_message(
                        "Save failed or was cancelled. Exit aborted."
                    )
                    logging.warning(
                        "Exit aborted: user chose to save, but save_file() failed."
                    )
                    self._exit_in_progress = (
                        False  # Reset the flag to allow another exit attempt.
                    )
                    return
            elif not (ans and ans.lower().startswith("n")):
                # If the user cancels the prompt (e.g., presses Esc) or enters anything but 'n',
                # abort the exit.
                self._set_status_message("Exit cancelled by user.")
                logging.info("User cancelled exit at the save prompt.")
                self._exit_in_progress = False  # Reset the flag.
                return

        # 4. Signal Main Loop to Terminate
        # This is the correct way to exit the application. The `run` loop will see
        # this flag and break, allowing `curses.wrapper` to clean up.
        self.running = False
        logging.info("Main loop stop signaled. The application will exit cleanly.")

        # 5. Shut Down Background Services
        # Stop any running threads before the program fully exits.
        logging.info("Shutting down background services...")
        if hasattr(self, "_auto_save_stop_event"):
            self._auto_save_stop_event.set()
        if self.async_engine:
            self.async_engine.stop()

    # -------------  Sets Pygments lexer - 4 methods:  ------------
    def detect_language(self) -> None:
        """Detects the language, sets the lexer, loads custom patterns, and clears cache if needed.

        This method orchestrates the entire language detection and syntax highlighting
        configuration process by delegating tasks to specialized helper methods. It ensures
        that the editor is always configured with the correct syntax highlighter for the

        The process is as follows:
        1.  Determine Lexer (`_determine_lexer`): It first attempts to find a suitable
            Pygments lexer. The detection follows a strict priority:
            a.  By Filename: Tries to find a lexer based on the file's extension
                (e.g., `.py` -> Python lexer). This is the most reliable method.
            b.  By Content: If filename detection fails (e.g., for a new buffer or
                an unknown extension), it guesses the language by analyzing a sample
                of the file's content.
            c.  Fallback: If both methods fail, it defaults to a plain `TextLexer`,
                which provides no special highlighting.

        2.  Load Custom Patterns (`_load_custom_syntax_patterns`): After a lexer is
            determined and `self.current_language` is set, this method checks the
            editor's configuration (`config.toml`) for a `[syntax_highlighting.<language>]`
            section. It loads any custom regex patterns defined there, compiling them
            for performance. These custom rules can augment or override the default
            Pygments highlighting.

        3.  Clear Cache if Changed (`_clear_cache_if_changed`): Finally, it compares
            the newly determined lexer and custom patterns against their previous state.
            If there is any change, it invalidates and clears the `lru_cache` for the
            `_get_tokenized_line` method. This ensures that any subsequent screen redraws
            will use the new highlighting rules.
        """
        old_lexer_id = id(self._lexer) if self._lexer else None
        old_custom_patterns = tuple(self.custom_syntax_patterns)

        # Determine the new Pygments lexer
        new_lexer = self._determine_lexer()
        self._lexer = new_lexer
        self.current_language = new_lexer.name.lower()

        # Load custom syntax patterns for the detected language
        self.custom_syntax_patterns = self._load_custom_syntax_patterns()

        # Clear tokenization cache if the lexer or patterns have changed
        self._clear_cache_if_changed(old_lexer_id, old_custom_patterns)

    def _determine_lexer(self) -> TextLexer:
        """Determines the appropriate Pygments lexer based on filename and content.
        Follows a priority: filename > content > fallback to TextLexer.
        """
        # Detect by filename
        if self.filename and self.filename != "noname":
            try:
                lexer = get_lexer_for_filename(self.filename, stripall=True)
                logging.debug(f"Pygments: Detected '{lexer.name}' by filename.")
                return lexer
            except Exception:
                logging.debug(f"Pygments: No lexer for filename '{self.filename}'.")

        # Guess from content
        content_sample = "\n".join(self.text[:200])[:10000]
        if content_sample.strip():
            try:
                lexer = guess_lexer(content_sample, stripall=True)
                logging.debug(f"Pygments: Guessed '{lexer.name}' by content.")
                return lexer
            except Exception:
                logging.debug("Pygments: Content guess failed.")

        # Fallback
        logging.debug("Pygments: Falling back to TextLexer.")
        return TextLexer()

    def _load_custom_syntax_patterns(self) -> list[tuple[re.Pattern, str]]:
        """Loads and compiles custom regex syntax patterns from the config for the current language."""
        if not self.current_language or not self._lexer:
            return []

        patterns = []
        syntax_config = self.config.get("syntax_highlighting", {})
        lang_keys_to_check = [self.current_language] + self._lexer.aliases

        for lang_key in lang_keys_to_check:
            if lang_key in syntax_config:
                patterns_from_config = syntax_config[lang_key].get("patterns", [])
                if patterns_from_config:
                    logging.info(
                        f"Loading {len(patterns_from_config)} custom syntax rules for '{lang_key}'."
                    )
                    for rule in patterns_from_config:
                        try:
                            compiled_pattern = re.compile(rule["pattern"])
                            color_name = rule["color"]
                            patterns.append((compiled_pattern, color_name))
                        except (re.error, KeyError, TypeError) as e:
                            logging.warning(
                                f"Skipping invalid syntax rule for '{lang_key}': {rule}. Error: {e}"
                            )
                    break  # Stop after finding the first matching language key
        return patterns

    # --- Cache management ---
    def _clear_cache_if_changed(
        self, old_lexer_id: Optional[int], old_custom_patterns: tuple
    ) -> None:
        """Clears the tokenization cache if the lexer or custom patterns have changed."""
        new_lexer_id = id(self._lexer)
        new_custom_patterns_tuple = tuple(self.custom_syntax_patterns)

        if (new_lexer_id != old_lexer_id) or (
            new_custom_patterns_tuple != old_custom_patterns
        ):
            lexer_name = self._lexer.name if self._lexer else "None"
            logging.info(
                f"Lexer or custom rules changed to '{lexer_name}'. Clearing tokenization cache."
            )

            # Safely access and clear the cache
            get_tokenized_line_func = getattr(self, "_get_tokenized_line", None)
            if get_tokenized_line_func and hasattr(
                get_tokenized_line_func, "cache_clear"
            ):
                get_tokenized_line_func.cache_clear()

    def apply_custom_highlighting(self, line: str) -> list[tuple[str, int]]:
        """Applies syntax highlighting to a line using custom regex patterns from config."""
        # Map for converting color names from config to curses attributes
        color_map = self.colors

        # Create a "map" of colors for each character in the line
        # Initially, all characters have the default color
        line_len = len(line)
        char_colors = [color_map.get("default", curses.A_NORMAL)] * line_len

        # Apply each rule
        for pattern, color_name in self.custom_syntax_patterns:
            color_attr = color_map.get(color_name, color_map["default"])
            for match in pattern.finditer(line):
                start, end = match.span()
                # "Paint" the characters that matched
                for i in range(start, end):
                    if i < line_len:
                        char_colors[i] = color_attr

        # Assemble the line back into segments with the same color
        if not line:
            return [("", color_map["default"])]

        segments = []
        current_segment_text = line[0]
        current_segment_color = char_colors[0]

        for i in range(1, line_len):
            if char_colors[i] == current_segment_color:
                current_segment_text += line[i]
            else:
                segments.append((current_segment_text, current_segment_color))
                current_segment_text = line[i]
                current_segment_color = char_colors[i]

        segments.append((current_segment_text, current_segment_color))

        return segments

    def delete_char_internal(self, row: int, col: int) -> str:
        """Deletes one character at (row, col) without writing to history.
        Returns the deleted character (or '').
        """
        if not (0 <= row < len(self.text)):
            return ""
        line = self.text[row]
        if not (0 <= col < len(line)):
            return ""
        removed = line[col]
        self.text[row] = line[:col] + line[col + 1 :]
        self.modified = True
        logging.debug("delete_char_internal: removed %r at (%s,%s)", removed, row, col)
        return removed

    def handle_resize(self) -> bool:
        """Handles window resize events.
        Updates editor's understanding of window dimensions and visible lines,
        adjusts scroll and cursor, notifies the active panel, and crucially,
        forces a full screen redraw to prevent visual artifacts.
        """
        logging.debug("handle_resize called")
        try:
            self._force_full_redraw = True
            new_height, new_width = self.stdscr.getmaxyx()

            # The calculation is correct, but let's log it.
            self.visible_lines = max(1, new_height - 2)
            self.last_window_size = (new_height, new_width)
            self.scroll_left = 0
            logging.debug(
                f"Window resized to {new_width}x{new_height}. "
                f"Visible text lines: {self.visible_lines}. Horizontal scroll reset."
            )

            if self.panel_manager and self.panel_manager.is_panel_active():
                active_panel = self.panel_manager.active_panel
                if active_panel and hasattr(active_panel, "resize"):
                    active_panel.resize()

            self._ensure_cursor_in_bounds()
            self._clamp_scroll()
            self._set_status_message(f"Resized to {new_width}x{new_height}")
            return True

        except Exception as e:
            logging.error(f"Error in handle_resize: {e}", exc_info=True)
            self._set_status_message("Resize error (see log)")
            return True

    def get_display_width(self, text: str) -> int:
        """Return the printable width of *text* in terminal cells.

        * Uses wcwidth / wcswidth to honour full‑width CJK.
        * Treats non‑printable characters (wcwidth == ‑1) as width 0.
        """
        # Fast‑path for ASCII
        if text.isascii():
            return len(text)

        width = cast(int, wcswidth(text))
        if width < 0:
            width = 0
            for ch in text:
                w = wcwidth(ch)
                width += max(w, 0)
        return width

    # ---------------- Cursor and its methods ------------------------
    # I. Direct control of cursor position (navigation):
    # handle_up(self)
    # handle_down(self)
    # handle_left(self)
    # handle_right(self)
    # handle_home(self)
    # handle_end(self)
    # handle_page_up(self)
    # handle_page_down(self)
    # goto_line(self)
    # _goto_match(self, match_index: int) (helper for searching)
    # set_initial_cursor_position(self) (reset position)
    #
    # Helper methods for cursor and scrolling:
    # _ensure_cursor_in_bounds(self)
    # _clamp_scroll(self)
    # _cancel_selection_if_not_extending(self)

    # --- `array up` ---
    def handle_up(self) -> bool:  # noqa: python:S3516
        """Move cursor one line up.
        Returns True if cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        old_y, old_x = self.cursor_y, self.cursor_x
        old_scroll_top = self.scroll_top
        changed = False

        if self.cursor_y > 0:
            self.cursor_y -= 1
            self.cursor_x = min(self.cursor_x, len(self.text[self.cursor_y]))
            # _clamp_scroll will be called and it can change scroll_top

        self._clamp_scroll()  # Always call to ensure scroll is correct

        if (
            old_y != self.cursor_y
            or old_x != self.cursor_x
            or old_scroll_top != self.scroll_top
        ):
            changed = True
            logging.debug(
                "cursor ↑ (%d,%d), scroll_top: %d",
                self.cursor_y,
                self.cursor_x,
                self.scroll_top,
            )
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                msg_lower = self.status_message.lower()
                if (
                    "inserted" in msg_lower
                    or "deleted" in msg_lower
                    or "copied" in msg_lower
                    or "pasted" in msg_lower
                    or "cut" in msg_lower
                    or "undone" in msg_lower
                    or "redone" in msg_lower
                    or "cancelled" in msg_lower
                    or "commented" in msg_lower
                    or "uncommented" in msg_lower
                ):
                    self._set_status_message("Ready")
        else:
            logging.debug(
                "cursor ↑ already at top or no change (%d,%d)",
                self.cursor_y,
                self.cursor_x,
            )
            # Clear status even if no move, if it was an action message
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                msg_lower = self.status_message.lower()
                if (
                    "inserted" in msg_lower
                    or "deleted" in msg_lower
                    or "copied" in msg_lower
                    or "pasted" in msg_lower
                    or "cut" in msg_lower
                    or "undone" in msg_lower
                    or "redone" in msg_lower
                    or "cancelled" in msg_lower
                    or "commented" in msg_lower
                    or "uncommented" in msg_lower
                ):
                    self._set_status_message("Ready")
                    changed = True  # Status changed, so redraw needed

        return changed

    # --- `array down` ---
    def handle_down(self) -> bool:
        """Moves the cursor one line down.
        Correctly handles moving between text lines and onto the final empty line.
        Returns True if the cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        # Save the initial state for subsequent comparison
        original_y, original_x = self.cursor_y, self.cursor_x
        original_scroll_top = self.scroll_top

        # Check if we can move down.
        # self.text always has an empty string at the end, so len(self.text) - 1
        # is the index of the last (empty) line we can still move to.
        if self.cursor_y < len(self.text) - 1:
            self.cursor_y += 1
            # Adjust self.cursor_x to the length of the new line.
            self.cursor_x = min(self.cursor_x, len(self.text[self.cursor_y]))
            self._clamp_scroll()  # Adjust scroll to the new position

        # Determine if anything changed as a result
        position_changed = (self.cursor_y, self.cursor_x) != (original_y, original_x)
        scroll_changed = self.scroll_top != original_scroll_top

        if position_changed:
            logging.debug(
                "cursor ↓ (%d,%d), scroll_top: %d",
                self.cursor_y,
                self.cursor_x,
                self.scroll_top,
            )
            # Reset temporary status messages if there was movement
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                self._set_status_message("Ready")
                return True  # Status changed, so redraw needed
        else:
            logging.debug("cursor ↓ already at the last line.")

        # Return True if the cursor position OR scroll position changed
        return position_changed or scroll_changed

    # --- `array left (<-)` ---
    def handle_left(self) -> bool:  # noqa: python:S3516
        """Move cursor one position to the left.
        Returns True if cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        old_y, old_x = self.cursor_y, self.cursor_x
        old_scroll_left = self.scroll_left
        old_scroll_top = self.scroll_top  # For line jumps
        changed = False

        if self.cursor_x > 0:
            self.cursor_x -= 1
        elif self.cursor_y > 0:
            self.cursor_y -= 1
            self.cursor_x = len(self.text[self.cursor_y])

        self._clamp_scroll()

        if (
            old_y != self.cursor_y
            or old_x != self.cursor_x
            or old_scroll_left != self.scroll_left
            or old_scroll_top != self.scroll_top
        ):
            changed = True
            logging.debug(
                "cursor ← (%d,%d), scroll: (%d,%d)",
                self.cursor_y,
                self.cursor_x,
                self.scroll_top,
                self.scroll_left,
            )
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                msg_lower = self.status_message.lower()
                if (
                    "inserted" in msg_lower
                    or "deleted" in msg_lower
                    or "copied" in msg_lower
                    or "pasted" in msg_lower
                    or "cut" in msg_lower
                    or "undone" in msg_lower
                    or "redone" in msg_lower
                    or "cancelled" in msg_lower
                    or "commented" in msg_lower
                    or "uncommented" in msg_lower
                ):
                    self._set_status_message("Ready")
        else:
            logging.debug(
                "cursor ← no change or at boundary (%d,%d)",
                self.cursor_y,
                self.cursor_x,
            )
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                msg_lower = self.status_message.lower()
                if (
                    "inserted" in msg_lower
                    or "deleted" in msg_lower
                    or "copied" in msg_lower
                    or "pasted" in msg_lower
                    or "cut" in msg_lower
                    or "undone" in msg_lower
                    or "redone" in msg_lower
                    or "cancelled" in msg_lower
                    or "commented" in msg_lower
                    or "uncommented" in msg_lower
                ):
                    self._set_status_message("Ready")
                    changed = True
        return changed

    # --- `array right (->)` ---
    def handle_right(self) -> bool:  # noqa: python:S3516
        """Move cursor one position to the right.
        Returns True if cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        old_y, old_x = self.cursor_y, self.cursor_x
        old_scroll_left = self.scroll_left
        old_scroll_top = self.scroll_top
        changed = False

        try:
            line_len = len(self.text[self.cursor_y])
            if self.cursor_x < line_len:
                self.cursor_x += 1
                while (
                    self.cursor_x < line_len
                    and wcswidth(self.text[self.cursor_y][self.cursor_x]) == 0
                ):
                    self.cursor_x += 1
            elif self.cursor_y < len(self.text) - 1:
                self.cursor_y += 1
                self.cursor_x = 0

            self._clamp_scroll()

            if (
                old_y != self.cursor_y
                or old_x != self.cursor_x
                or old_scroll_left != self.scroll_left
                or old_scroll_top != self.scroll_top
            ):
                changed = True
                logging.debug(
                    "cursor → (%d,%d), scroll: (%d,%d)",
                    self.cursor_y,
                    self.cursor_x,
                    self.scroll_top,
                    self.scroll_left,
                )
                if self.status_message not in [
                    "Ready",
                    "",
                ] and not self.status_message.lower().startswith("error"):
                    self._set_status_message("Ready")
            else:
                logging.debug(
                    "cursor → no change or at boundary (%d,%d)",
                    self.cursor_y,
                    self.cursor_x,
                )
                if self.status_message not in [
                    "Ready",
                    "",
                ] and not self.status_message.lower().startswith("error"):
                    self._set_status_message("Ready")
                    changed = True
            return changed
        except IndexError:
            logging.exception("Error in handle_right (IndexError)")
            self._set_status_message("Cursor error (see log)")
            return True
        except Exception as e:
            logging.exception(f"Unexpected error in handle_right: {e}")
            self._set_status_message("Cursor error (see log)")
            return True

    # --- key HOME ---
    def handle_home(self) -> bool:
        """Moves the cursor to the beginning of the current line.
        Implements "smart home" behavior:
        - First press: moves to the first non-whitespace character (or column 0 if no indent).
        - Second press (if already at indent): moves to absolute column 0.
        Returns True if the cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        original_cursor_x = self.cursor_x
        original_scroll_left = self.scroll_left  # To check if _clamp_scroll changes it
        changed_state = False

        with self._state_lock:
            # Ensure cursor_y is valid, though it shouldn't change here
            if self.cursor_y >= len(self.text):
                logging.warning(f"handle_home: cursor_y {self.cursor_y} out of bounds.")
                return False  # No change possible

            current_line_content = self.text[self.cursor_y]

            # Find the end of the leading whitespace (indentation)
            match = re.match(r"^(\s*)", current_line_content)
            indentation_end_column = match.end() if match else 0

            if self.cursor_x != indentation_end_column:
                # Cursor is not at the indentation point yet, move to it.
                self.cursor_x = indentation_end_column
            else:
                # Cursor is already at the indentation point (or col 0 if no indent),
                # so move to the absolute beginning of the line (column 0).
                self.cursor_x = 0

            # After cursor_x is set, adjust horizontal scroll if needed.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            self.cursor_x != original_cursor_x
            or self.scroll_left != original_scroll_left
        ):
            changed_state = True
            logging.debug(
                f"handle_home: New cursor_x: {self.cursor_x}, scroll_left: {self.scroll_left}. Changed: {changed_state}"
            )
        else:
            logging.debug("handle_home: No change in cursor_x or scroll_left.")

        # Clear transient status messages if a move occurred or was attempted
        if self.status_message not in [
            "Ready",
            "",
        ] and not self.status_message.lower().startswith("error"):
            msg_lower = self.status_message.lower()
            if (
                "inserted" in msg_lower
                or "deleted" in msg_lower
                or "copied" in msg_lower
                or "pasted" in msg_lower
                or "cut" in msg_lower
                or "undone" in msg_lower
                or "redone" in msg_lower
                or "cancelled" in msg_lower
                or "commented" in msg_lower
                or "uncommented" in msg_lower
            ):
                self._set_status_message("Ready")
                changed_state = True  # Status message change also implies redraw

        return changed_state

    # --- key END ---
    def handle_end(self) -> bool:
        """Moves the cursor to the end of the current line.
        Returns True if the cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        original_cursor_x = self.cursor_x
        original_scroll_left = self.scroll_left  # To check if _clamp_scroll changes it
        changed_state = False

        with self._state_lock:
            if self.cursor_y >= len(self.text):
                logging.warning(f"handle_end: cursor_y {self.cursor_y} out of bounds.")
                return False  # No change possible

            self.cursor_x = len(self.text[self.cursor_y])
            # After cursor_x is set, adjust horizontal scroll if needed.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            self.cursor_x != original_cursor_x
            or self.scroll_left != original_scroll_left
        ):
            changed_state = True
            logging.debug(
                f"handle_end: New cursor_x: {self.cursor_x}, scroll_left: {self.scroll_left}. Changed: {changed_state}"
            )
        else:
            logging.debug("handle_end: No change in cursor_x or scroll_left.")

        # Clear transient status messages if a move occurred or was attempted
        if self.status_message not in [
            "Ready",
            "",
        ] and not self.status_message.lower().startswith("error"):
            msg_lower = self.status_message.lower()
            if (
                "inserted" in msg_lower
                or "deleted" in msg_lower
                or "copied" in msg_lower
                or "pasted" in msg_lower
                or "cut" in msg_lower
                or "undone" in msg_lower
                or "redone" in msg_lower
                or "cancelled" in msg_lower
                or "commented" in msg_lower
                or "uncommented" in msg_lower
            ):
                self._set_status_message("Ready")
                # If only status changed, and cursor/scroll didn't, ensure changed_state reflects this.
                if not changed_state:
                    changed_state = True

        return changed_state

    # --- key Page-Up ---
    def handle_page_up(self) -> bool:
        """Moves the cursor and view up by approximately one screen height.

        This method scrolls the view upwards by the number of currently visible
        text lines (`self.visible_lines`). The cursor's vertical position is
        adjusted accordingly, and its horizontal position (column) is preserved
        if possible, clamped by the length of the new line. If the cursor moves
        or the scroll position changes, this method returns True.

        It also clears transient status messages (e.g., "Text inserted") if
        a movement occurs, resetting the status to "Ready" unless it's an
        error message.

        Args:
            None

        Returns:
            bool: True if the cursor position, scroll position, or status message
                  changed, indicating a redraw might be needed. False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_status = self.status_message
        changed_state = False

        with self._state_lock:
            if self.visible_lines <= 0:
                logging.warning(
                    "handle_page_up: visible_lines is not positive, cannot page."
                )
                return False

            page_height = self.visible_lines  # Number of text lines visible on screen

            # Move cursor by one page height upwards.
            new_cursor_y_candidate = max(0, self.cursor_y - page_height)
            self.cursor_y = new_cursor_y_candidate

            # Ensure cursor_x is valid for the new line, maintaining the desired column.
            if self.cursor_y < len(self.text):
                self.cursor_x = min(self.cursor_x, len(self.text[self.cursor_y]))
            else:  # Should not happen if self.text always has at least [""]
                self.cursor_x = 0

            # _clamp_scroll will adjust scroll_top and scroll_left to ensure
            # the new cursor_y and cursor_x are visible.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (self.cursor_y, self.cursor_x) != original_cursor_pos or (
            self.scroll_top,
            self.scroll_left,
        ) != original_scroll_pos:
            changed_state = True
            logging.debug(
                f"handle_page_up: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"scroll ({self.scroll_top},{self.scroll_left}). Changed: {changed_state}"
            )
        else:
            logging.debug("handle_page_up: No change in cursor or scroll state.")

        # Clear transient status messages if a move occurred.
        # (Remaining logic for status message clearing stays the same)
        if changed_state and self.status_message != original_status:
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                msg_lower = self.status_message.lower()
                # Check if the current status message is one of the transient action messages
                transient_action_keywords = [
                    "inserted",
                    "deleted",
                    "copied",
                    "pasted",
                    "cut",
                    "undone",
                    "redone",
                    "cancelled",
                    "commented",
                    "uncommented",
                ]
                if any(keyword in msg_lower for keyword in transient_action_keywords):
                    self._set_status_message("Ready")
                    # If status changed back to Ready, it's still a change from original_status
                    # if original_status wasn't Ready.
                    if self.status_message != original_status and not changed_state:
                        # This part of 'if' ensures changed_state is True if only status changed.
                        # However, changed_state is already True if we are in this block.
                        # The important part is that self._set_status_message("Ready") might have occurred.
                        pass  # Redraw will be triggered by changed_state = True or status changing

        # The method returns True if 'changed_state' is True (cursor/scroll moved)
        # OR if the status message itself is different from what it was at the start.
        return changed_state or (self.status_message != original_status)

    # --- key Page-Down ---
    def handle_page_down(self) -> bool:  # noqa: python:S3516
        """Moves the cursor and view down by approximately one screen height of text.
        The cursor attempts to maintain its horizontal column, clamped by line length.
        Returns True if the cursor or scroll position changed, False otherwise.
        """
        if self._cancel_selection_if_not_extending():
            return True

        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_status = self.status_message
        changed_state = False

        with self._state_lock:
            if self.visible_lines <= 0:
                logging.warning(
                    "handle_page_down: visible_lines is not positive, cannot page."
                )
                return False

            page_height = self.visible_lines
            max_y_idx = len(self.text) - 1
            max_y_idx = max(max_y_idx, 0)  # Handle empty text [""] case

            # Calculate new cursor_y candidate
            new_cursor_y_candidate = min(max_y_idx, self.cursor_y + page_height)

            if new_cursor_y_candidate != self.cursor_y:
                self.cursor_y = new_cursor_y_candidate

            # Ensure cursor_x is valid for the new line
            if self.cursor_y < len(self.text):
                self.cursor_x = min(self.cursor_x, len(self.text[self.cursor_y]))
            else:
                self.cursor_x = 0

            # _clamp_scroll will ensure cursor_y is visible and adjust scroll_top and scroll_left
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (self.cursor_y, self.cursor_x) != original_cursor_pos or (
            self.scroll_top,
            self.scroll_left,
        ) != original_scroll_pos:
            changed_state = True
            logging.debug(
                f"handle_page_down: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"scroll ({self.scroll_top},{self.scroll_left}). Changed: {changed_state}"
            )
        else:
            logging.debug("handle_page_down: No change in cursor or scroll state.")

        # Clear transient status messages if a move occurred
        if changed_state and self.status_message != original_status:
            if self.status_message not in [
                "Ready",
                "",
            ] and not self.status_message.lower().startswith("error"):
                msg_lower = self.status_message.lower()
                if (
                    "inserted" in msg_lower
                    or "deleted" in msg_lower
                    or "copied" in msg_lower
                    or "pasted" in msg_lower
                    or "cut" in msg_lower
                    or "undone" in msg_lower
                    or "redone" in msg_lower
                    or "cancelled" in msg_lower
                    or "commented" in msg_lower
                    or "uncommented" in msg_lower
                ):
                    self._set_status_message("Ready")
                    if self.status_message != original_status and not changed_state:
                        changed_state = True

        return changed_state

    # --- GOTO LINE ---
    def goto_line(self) -> bool:  # noqa: python:S3516
        """Moves the cursor to a specified line number. Supports absolute numbers,
        relative numbers (+N, -N), and percentages (N%).
        Returns True if the cursor, scroll position, or status message changed,
        False otherwise (e.g., invalid input but status didn't change from original).
        """
        original_status = self.status_message
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_top = self.scroll_top

        # The prompt itself will temporarily change the status bar.
        # We need to capture the status *after* the prompt to see if the prompt interaction
        # itself should be considered the "final" status change for this operation if parsing fails.
        prompt_text = f"Go to line (1-{len(self.text)}, ±N, %): "
        raw_input_str = self.prompt(prompt_text)

        status_after_prompt = (
            self.status_message
        )  # Status might have been restored by prompt's finally block

        if (
            not raw_input_str
        ):  # User cancelled the prompt (e.g., pressed Esc or Enter on empty input)
            # If the prompt itself set a new status (e.g. "Prompt timeout"), that's a change.
            # If prompt restored original_status, but user cancelled, set "Goto cancelled".
            if status_after_prompt == original_status:
                self._set_status_message("Goto cancelled")
            # Return True if status message is different from what it was *before* the prompt.
            return self.status_message != original_status

        target_line_num_one_based: Optional[int] = None
        total_lines = len(self.text)
        if total_lines == 0:  # Should not happen if self.text always has at least [""]
            self._set_status_message("Cannot go to line: buffer is empty")
            return self.status_message != original_status

        try:
            if raw_input_str.endswith("%"):
                percentage_str = raw_input_str.rstrip("%")
                if not percentage_str:  # Just '%' was entered
                    raise ValueError("Percentage value missing.")
                percentage = float(percentage_str)
                if not (0 <= percentage <= 100):
                    self._set_status_message("Percentage out of range (0-100)")
                    return True  # Status changed
                # Calculate target line (1-based), ensuring it's within [1, total_lines]
                # round() handles .5 by rounding to the nearest even number in Python 3.
                # int(val + 0.5) is a common way to round half up for positive numbers.
                # For percentages, simple rounding is usually fine.
                target_line_num_one_based = max(
                    1, min(total_lines, round(total_lines * percentage / 100.0))
                )
                if target_line_num_one_based == 0 and total_lines > 0:
                    target_line_num_one_based = 1  # Ensure at least line 1
                logging.debug(
                    f"Goto: Percentage {percentage}%, target line {target_line_num_one_based}"
                )
            elif raw_input_str.startswith(("+", "-")):
                if len(raw_input_str) == 1:  # Just '+' or '-' was entered
                    raise ValueError("Relative offset value missing.")
                relative_offset = int(raw_input_str)
                # Current line is 0-based (self.cursor_y), target is 1-based
                target_line_num_one_based = (self.cursor_y + 1) + relative_offset
                logging.debug(
                    f"Goto: Relative offset {relative_offset}, from line {self.cursor_y + 1}, target line {target_line_num_one_based}"
                )
            else:
                target_line_num_one_based = int(raw_input_str)
                logging.debug(f"Goto: Absolute target line {target_line_num_one_based}")

            # Validate the calculated target_line_num_one_based
            if (
                target_line_num_one_based is None
            ):  # Should not happen if parsing logic is complete
                raise ValueError("Line number could not be determined.")
            if not (1 <= target_line_num_one_based <= total_lines):
                self._set_status_message(f"Line number out of range (1–{total_lines})")
                return True  # Status changed

            # Convert 1-based target to 0-based for internal use
            target_y_zero_based = target_line_num_one_based - 1

            # Only proceed if the target is different from the current line
            if target_y_zero_based == self.cursor_y and self.cursor_x == min(
                self.cursor_x, len(self.text[target_y_zero_based])
            ):
                # If already on the target line and x is valid for it (or will be clamped to valid)
                # No actual cursor line change, but check if x needs clamping or status needs update.
                self.cursor_x = min(
                    self.cursor_x, len(self.text[target_y_zero_based])
                )  # Ensure x is valid
                self._clamp_scroll()  # Ensure scroll is correct for current position
                if (
                    self.cursor_y,
                    self.cursor_x,
                ) != original_cursor_pos or self.scroll_top != original_scroll_top:
                    self._set_status_message(
                        f"Moved to line {target_line_num_one_based}, column adjusted"
                    )
                    return True
                self._set_status_message(f"Already at line {target_line_num_one_based}")
                return self.status_message != original_status

            # Move cursor
            self.cursor_y = target_y_zero_based
            # Try to maintain horizontal cursor position, clamped to new line length
            self.cursor_x = min(original_cursor_pos[1], len(self.text[self.cursor_y]))

            self._clamp_scroll()  # Adjust scroll to make the new cursor position visible

            # Check if cursor or scroll actually changed
            if (
                self.cursor_y,
                self.cursor_x,
            ) != original_cursor_pos or self.scroll_top != original_scroll_top:
                self._set_status_message(f"Moved to line {target_line_num_one_based}")
                return True
            # This case should be rare if logic above for "already at line" is correct.
            # It means target was same as current, and clamp_scroll did nothing.
            # However, the prompt was shown.
            if (
                status_after_prompt != original_status
            ):  # If prompt itself set a lasting status
                return True
                # If prompt restored status, but we set a new one (e.g. "already at line")
            self._set_status_message(f"At line {target_line_num_one_based} (no change)")
            return self.status_message != original_status

        except ValueError as ve:  # Handles errors from int(), float(), or custom raises
            logging.warning(f"Goto: Invalid input format '{raw_input_str}': {ve}")
            self._set_status_message(f"Invalid format: {raw_input_str[:30]}")
            return True  # Status changed due to error message
        except Exception as e:  # Catch any other unexpected errors
            logging.error(
                f"Unexpected error in goto_line for input '{raw_input_str}': {e}",
                exc_info=True,
            )
            self._set_status_message(f"Goto error: {str(e)[:60]}...")
            return True  # Status changed due to error message

    # --- Auxiliary method for searching ---
    def _goto_match(
        self, match_index: int
    ) -> None:  # Added type hint and English docstring
        """Moves the cursor and adjusts the scroll view to the search match
        specified by `match_index`.

        This method assumes `self.search_matches` is populated and `match_index` is valid.
        It updates `self.cursor_y`, `self.cursor_x`, `self.scroll_top`, and `self.scroll_left`
        as necessary to make the match visible, ideally near the center of the screen.

        Args:
            match_index (int): The index of the desired match in `self.search_matches`.
        """
        # Validate the match_index and ensure search_matches is populated.
        if not self.search_matches or not (0 <= match_index < len(self.search_matches)):
            logging.warning(
                f"_goto_match called with invalid index {match_index} for "
                f"{len(self.search_matches)} available matches. No action taken."
            )
            return  # Invalid index or no matches to go to

        # Get the coordinates of the target match.
        # search_matches stores tuples: (row_index, column_start_index, column_end_index)
        target_row, target_col_start, _ = self.search_matches[
            match_index
        ]  # We only need start for cursor

        logging.debug(
            f"_goto_match: Navigating to match {match_index + 1}/{len(self.search_matches)} "
            f"at (row:{target_row}, col:{target_col_start})."
        )

        # Move the logical cursor to the start of the match.
        # Ensure target_row and target_col_start are valid within the current text buffer.
        # This is a safeguard; _collect_matches should provide valid indices.
        if target_row >= len(self.text):
            logging.error(
                f"_goto_match: Match row {target_row} is out of bounds for text length {len(self.text)}."
            )
            return
        if target_col_start > len(
            self.text[target_row]
        ):  # Allow being at the end of the line
            logging.error(
                f"_goto_match: Match col_start {target_col_start} is out of bounds for line {target_row} (len {len(self.text[target_row])})."
            )
            # Optionally clamp target_col_start or return
            # target_col_start = len(self.text[target_row]) # Clamp to end of line
            return

        self.cursor_y = target_row
        self.cursor_x = target_col_start

        # Adjust scroll to ensure the new cursor position is visible.
        # self._clamp_scroll() handles both vertical and horizontal scrolling
        # to bring self.cursor_y and self.cursor_x into view.
        # It also attempts to center the cursor line if it's far off-screen.

        # The previous logic for adjusting scroll_top was a simplified centering.
        # _clamp_scroll provides a more comprehensive adjustment.
        # Let's review _clamp_scroll's behavior for centering.
        # Current _clamp_scroll:
        #   if self.cursor_y < self.scroll_top: self.scroll_top = self.cursor_y
        #   elif self.cursor_y >= self.scroll_top + text_height: self.scroll_top = self.cursor_y - text_height + 1
        # This ensures visibility but doesn't explicitly center.
        # To achieve better centering for _goto_match, we can pre-adjust scroll_top here.

        if (
            self.visible_lines > 0
        ):  # visible_lines should be height - 2 (status/number bars)
            text_area_height = self.visible_lines

            # Desired scroll_top to center the cursor_y, or bring it into view if near edges.
            # Try to place the target line roughly in the middle third of the screen.
            desired_scroll_top = self.cursor_y - (text_area_height // 3)

            # Clamp desired_scroll_top to valid range: [0, max_scroll_possible]
            max_scroll_possible = max(0, len(self.text) - text_area_height)
            self.scroll_top = max(0, min(desired_scroll_top, max_scroll_possible))

            logging.debug(
                f"_goto_match: Tentative scroll_top set to {self.scroll_top} to center line {self.cursor_y}."
            )

        # Now, call _clamp_scroll() to finalize both vertical and horizontal scroll based on
        # the new cursor_y, cursor_x, and the tentative scroll_top.
        # _clamp_scroll will also handle horizontal scrolling for cursor_x.
        self._clamp_scroll()

        logging.debug(
            f"_goto_match: Final state after _clamp_scroll: "
            f"Cursor=({self.cursor_y},{self.cursor_x}), Scroll=({self.scroll_top},{self.scroll_left})"
        )
        # This method modifies editor state (cursor, scroll) but does not directly
        # return a bool for redraw; the caller (find_prompt or find_next) handles that.

    # --- Reset position ---
    def set_initial_cursor_position(self) -> None:
        """Sets the initial cursor position and scrolling offsets."""
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_top = 0
        self.scroll_left = 0
        # When you reset the cursor position, you also reset the selection.
        self.is_selecting = False
        self.selection_start = None
        self.selection_end = None
        self.highlighted_matches = []  # Reset search highlights
        self.search_matches = []
        self.search_term = ""
        self.current_match_idx = -1

    def _clamp_scroll(self) -> None:
        """Ensures that scroll_top and scroll_left are adjusted to keep the cursor
        within the visible text area of the screen.

        This method is crucial for editor navigation and is called after any
        cursor movement. It performs two main functions:

        1.  **Vertical Scrolling:** If the cursor moves above the top visible line or
            below the bottom visible line, `self.scroll_top` is adjusted to bring
            the cursor's line back into view.
        2.  **Horizontal Scrolling:** If the cursor's horizontal position (calculated
            by its visual width) moves off the left or right edge of the text
            area, `self.scroll_left` is adjusted accordingly.

        It correctly handles the virtual line after the last line of text and
        calculates the available text area width by accounting for the line
        number gutter.

        Side Effects:
            - Modifies `self.scroll_top`.
            - Modifies `self.scroll_left`.
        """
        # Get current terminal dimensions.
        height, width = self.stdscr.getmaxyx()

        # --- Vertical Scrolling ---

        # Calculate the height of the text viewport (total terminal height minus chrome).
        # This is the number of lines that can be displayed in the text area.
        text_area_height = max(1, height - 2)

        # Scroll up if the cursor is now above the current viewport.
        if self.cursor_y < self.scroll_top:
            self.scroll_top = self.cursor_y
        # Scroll down if the cursor is now below the current viewport.
        elif self.cursor_y >= self.scroll_top + text_area_height:
            self.scroll_top = self.cursor_y - text_area_height + 1

        # --- Horizontal Scrolling ---

        # Handle the special case where the cursor is on the virtual line
        # after the last line of content. In this state, cursor_x is always 0,
        # and no horizontal scrolling logic is needed.
        if self.cursor_y >= len(self.text):
            logging.debug(
                "_clamp_scroll: Cursor on virtual line, skipping horizontal scroll clamp."
            )
            # We still need to ensure scroll values are non-negative before returning.
            self.scroll_top = max(0, self.scroll_top)
            self.scroll_left = max(0, self.scroll_left)
            return

        # Calculate the available width for the text area, accounting for the line number gutter.
        # `self.drawer._text_start_x` holds the column where the text begins.
        text_area_start_x = self.drawer._text_start_x
        text_area_width = max(1, width - text_area_start_x)

        # Get the visual display width of the line content up to the cursor position.
        line_content_before_cursor = self.text[self.cursor_y][: self.cursor_x]
        cursor_display_x = self.get_display_width(line_content_before_cursor)

        # Scroll left if the cursor is now to the left of the viewport.
        if cursor_display_x < self.scroll_left:
            self.scroll_left = cursor_display_x

        # Scroll right if the cursor is at or past the right edge.
        # The original code incorrectly compared against the full terminal `width`
        # instead of the `text_area_width`, causing delayed scrolling.
        elif cursor_display_x >= self.scroll_left + text_area_width:
            self.scroll_left = cursor_display_x - text_area_width + 1

        # --- Final Safeguards ---
        # Ensure scroll values are never negative.
        self.scroll_top = max(0, self.scroll_top)
        self.scroll_left = max(0, self.scroll_left)

    # --- Helper method ---
    def _ensure_cursor_in_bounds(self) -> None:
        """Clamps `cursor_y` and `cursor_x` to valid positions.
        Crucially, allows `cursor_y` to be at `len(self.text)`, which represents
        the position *after* the last line, enabling full file selection.
        """
        if not self.text:
            self.text.append("")

        # Allow cursor to be one position AFTER the last line
        max_y = len(self.text)
        self.cursor_y = max(0, min(self.cursor_y, max_y))

        # If cursor is on the virtual line, X should be 0.
        if self.cursor_y == len(self.text):
            self.cursor_x = 0
        else:
            # Otherwise, clamp X to the length of the real line.
            max_x = len(self.text[self.cursor_y])
            self.cursor_x = max(0, min(self.cursor_x, max_x))

        logging.debug("Cursor clamped → (%d,%d)", self.cursor_y, self.cursor_x)

    # ---------- Text modification affecting the cursor: ------------------
    # handle_backspace(self)
    # handle_delete(self)
    # handle_tab(self) (via insert_text)
    # handle_smart_tab(self) (via insert_text or handle_block_indent)
    # handle_enter(self) (via insert_text)
    # insert_text(self, text: str) (main insertion method)
    # insert_text_at_position(self, text: str, row: int, col: int) (low-level insertion)
    # delete_selected_text_internal(self, start_y: int, start_x: int, end_y: int, end_x: int) (low-level deletion)
    # paste(self) (includes deletion of selection and insertion)
    # cut(self) (includes deletion of selection)
    # search_and_replace(self) (resets cursor)

    # ----------------- Cursor: Backspace and Delete ------------------

    # --- key Backspace ---
    def handle_backspace(self) -> bool:  # noqa: python:S3516
        """Handles the Backspace key with clear, sequential logic.
        1. If a selection is active, deletes the selection.
        2. If cursor is not at the start of a line, deletes the character to the left.
        3. If cursor is at the start of a line (but not the first), merges it with the previous line.
        """
        logging.debug("handle_backspace triggered.")
        with self._state_lock:
            # Deleting selection
            if self.is_selecting:
                logging.debug(
                    "handle_backspace: Active selection found. Deleting selection."
                )
                # delete_selected_text() will handle history and modified flag
                self.delete_selected_text()
                return True

            # Deleting char to the left
            if self.cursor_x > 0:
                logging.debug(
                    f"handle_backspace: Deleting char at ({self.cursor_y}, {self.cursor_x - 1})."
                )
                y, x = self.cursor_y, self.cursor_x

                char_to_delete = self.text[y][x - 1]
                self.text[y] = self.text[y][: x - 1] + self.text[y][x:]
                self.cursor_x -= 1
                self.modified = True

                self.history.add_action(
                    {
                        "type": "delete_char",
                        "text": char_to_delete,
                        "position": (y, self.cursor_x),
                    }
                )
                self._set_status_message("Character deleted")
                return True

            # Merging lines
            if self.cursor_y > 0:
                logging.debug(
                    f"handle_backspace: Merging line {self.cursor_y} with {self.cursor_y - 1}."
                )

                current_line_content = self.text.pop(self.cursor_y)
                prev_line_idx = self.cursor_y - 1
                new_cursor_x = len(self.text[prev_line_idx])

                self.text[prev_line_idx] += current_line_content
                self.cursor_y = prev_line_idx
                self.cursor_x = new_cursor_x
                self.modified = True

                self.history.add_action(
                    {
                        "type": "delete_newline",
                        "text": current_line_content,
                        "position": (self.cursor_y, self.cursor_x),
                    }
                )
                self._set_status_message("Newline deleted (lines merged)")
                return True

            # No action (cursor at the very beginning of the file)
            logging.debug("handle_backspace: At beginning of file. No action.")
            self._set_status_message("Beginning of file")
            return True

    # --- key Delete ----
    def handle_delete(self) -> bool:
        """Handles the Delete key. Deletes selection, char under cursor, or merges lines."""
        with self._state_lock:
            if self.is_selecting:
                self.delete_selected_text()
                return True

            y, x = self.cursor_y, self.cursor_x
            if y >= len(self.text):
                return False

            current_line_len = len(self.text[y])
            if x < current_line_len:
                deleted_char = self.text[y][x]
                self.text[y] = self.text[y][:x] + self.text[y][x + 1 :]
                self.modified = True
                self.history.add_action(
                    {"type": "delete_char", "text": deleted_char, "position": (y, x)}
                )
                self._set_status_message("Character deleted")
                return True

            if y < len(self.text) - 1:
                next_line_content = self.text[y + 1]
                self.text[y] += self.text.pop(y + 1)
                self.modified = True
                self.history.add_action(
                    {
                        "type": "delete_newline",
                        "text": next_line_content,
                        "position": (y, x),
                    }
                )
                self._set_status_message("Newline deleted (lines merged)")
                return True

            self._set_status_message("End of file")
            return True

    # ---- Cursor: smart tab ----
    def handle_smart_tab(self) -> bool:
        """Handles smart tabbing behavior.
        - If text is selected, indents the selected block.
        - If cursor is not at the beginning of the line, inserts a standard tab/spaces.
        - If cursor is at the beginning of the line, copies indentation from the previous line
          or inserts a standard tab/spaces if no previous indentation to copy.
        Returns True if any change (text, selection, cursor, scroll, status) occurred, False otherwise.
        """
        if self.is_selecting:
            # handle_block_indent is expected to return bool indicating if a change occurred
            return self.handle_block_indent()

        # If not selecting, and cursor is not at the absolute beginning of the line
        if self.cursor_x > 0:
            # handle_tab calls insert_text, which returns bool
            return self.handle_tab()

        # Cursor is at the beginning of the line (self.cursor_x == 0) and no selection
        indentation_to_copy = ""
        if self.cursor_y > 0:  # Check if there's a previous line
            prev_line_idx = self.cursor_y - 1
            # Ensure prev_line_idx is valid (should be, if self.cursor_y > 0)
            if 0 <= prev_line_idx < len(self.text):
                prev_line_content = self.text[prev_line_idx]
                # Use regex to find leading whitespace
                match_result = re.match(r"^(\s*)", prev_line_content)
                if match_result:
                    indentation_to_copy = match_result.group(1)
            else:  # Should not happen if self.cursor_y > 0
                logging.warning(
                    f"handle_smart_tab: Invalid prev_line_idx {prev_line_idx} when cursor_y is {self.cursor_y}"
                )

        text_to_insert = indentation_to_copy  # Use copied indentation by default

        if (
            not indentation_to_copy
        ):  # If no indentation to copy (e.g., first line, or prev line had no indent)
            tab_size = self.config.get("editor", {}).get("tab_size", 4)
            use_spaces = self.config.get("editor", {}).get("use_spaces", True)
            text_to_insert = " " * tab_size if use_spaces else "\t"

        if not text_to_insert:  # If, for some reason, text_to_insert is still empty (e.g. prev line was empty)
            # then insert_text("") will return False, which is correct.
            logging.debug(
                "handle_smart_tab: No text to insert for smart indent (e.g. previous line empty and no default tab configured)."
            )
            return False  # No change will be made

        # insert_text handles history, self.modified, and returns True if text was inserted.
        return self.insert_text(text_to_insert)

    # --- for the TAB key helper method ---
    def handle_tab(self) -> bool:
        """Inserts standard tab characters (spaces or a tab char) at the current cursor position.
        Deletes selection if active before inserting.
        Returns True if text was inserted (always true if not an empty tab string), False otherwise.
        """
        tab_size = self.config.get("editor", {}).get("tab_size", 4)
        use_spaces = self.config.get("editor", {}).get("use_spaces", True)

        text_to_insert_val = " " * tab_size if use_spaces else "\t"

        if not text_to_insert_val:  # Should not happen with default config
            logging.warning("handle_tab: Tab string is empty, nothing to insert.")
            return False

        # self.insert_text handles active selection, history, and returns True if changes were made.
        return self.insert_text(text_to_insert_val)

    # ---- key Enter ----
    def handle_enter(self) -> bool:
        """Inserts a newline with smart auto-indentation.
        If a selection is active, it is deleted before the newline is inserted.
        Correctly handles adding a new line when at the end of the buffer.
        """
        with self._state_lock:
            # Check that the cursor is within the existing rows.
            # This will prevent errors if the state becomes invalid for some reason.
            if self.cursor_y >= len(self.text):
                logging.error(
                    f"handle_enter: cursor_y ({self.cursor_y}) is out of bounds. Appending a new line as a fallback."
                )
                self.text.append("")  # Append a new line to avoid crashing
                # After this, cursor_y becomes a valid index.

            current_line_content = self.text[self.cursor_y]
            line_before_cursor = current_line_content[: self.cursor_x]

            # Determine indentation for the new line
            indent_match = re.match(r"^\s*", current_line_content)
            indent = indent_match.group(0) if indent_match else ""

            tab_size = self.config.get("editor", {}).get("tab_size", 4)
            use_spaces = self.config.get("editor", {}).get("use_spaces", True)
            extra_indent = " " * tab_size if use_spaces else "\t"

            stripped_line_before_cursor = line_before_cursor.rstrip()

            # Logic for "smart" indentation
            if (
                self.current_language == "python"
                and stripped_line_before_cursor.endswith(":")
            ):
                indent += extra_indent
            elif self.current_language in {
                "java",
                "c",
                "cpp",
                "c++",
                "rust",
                "javascript",
                "typescript",
                "csharp",
                "go",
                "php",
            } and stripped_line_before_cursor.endswith("{"):
                indent += extra_indent

            # Form the text to insert: newline + indentation
            text_to_insert = "\n" + indent

            # Delegate the insertion to the insert_text method, which will handle selection, history, etc.
            # insert_text, in turn, will call _ensure_trailing_newline,
            # which implements your logic for adding an empty line at the end.
            return self.insert_text(text_to_insert)

    # ---- Insert text at position ----
    def insert_text(self, text: str) -> bool:
        """Main public method for text insertion.
        Handles active selection by deleting it first. If so, the deletion and
        insertion are grouped as one compound action for undo/redo purposes.
        Cursor is set after the inserted text.
        Returns True if text was inserted or selection was modified, False otherwise.
        """
        if not text and not self.is_selecting:
            logging.debug("insert_text: empty text and no selection, no change.")
            return False

        made_change_overall = False
        with self._state_lock:
            effective_insert_y, effective_insert_x = self.cursor_y, self.cursor_x
            original_status = self.status_message

            # Start a compound action to group deletion and insertion
            self.history.begin_compound_action()
            try:
                # Handle active selection by deleting it first
                if self.is_selecting:
                    normalized_selection = self._get_normalized_selection_range()
                    if normalized_selection:
                        norm_start_coords, norm_end_coords = normalized_selection
                        logging.debug(
                            f"insert_text: Deleting active selection from {norm_start_coords} to {norm_end_coords} before insertion."
                        )

                        deleted_segments = self.delete_selected_text_internal(
                            norm_start_coords[0],
                            norm_start_coords[1],
                            norm_end_coords[0],
                            norm_end_coords[1],
                        )

                        # Record deletion action if something was actually deleted
                        if deleted_segments or (norm_start_coords != norm_end_coords):
                            self.history.add_action(
                                {
                                    "type": "delete_selection",
                                    "text": deleted_segments,
                                    "start": norm_start_coords,
                                    "end": norm_end_coords,
                                }
                            )
                            made_change_overall = True

                        # delete_selected_text_internal sets the new cursor position
                        effective_insert_y, effective_insert_x = (
                            self.cursor_y,
                            self.cursor_x,
                        )

                        self.is_selecting = False
                        self.selection_start = None
                        self.selection_end = None
                        logging.debug(
                            f"insert_text: Selection processed. Cursor at ({self.cursor_y}, {self.cursor_x})."
                        )

                # Insert the new text (if there is any)
                if text:
                    insert_pos_for_history = (effective_insert_y, effective_insert_x)

                    try:
                        if self.insert_text_at_position(
                            text, effective_insert_y, effective_insert_x
                        ):
                            made_change_overall = True
                    except IndexError as e:
                        logging.error(
                            f"insert_text: Error during insert_text_at_position: {e}",
                            exc_info=True,
                        )
                        self._set_status_message(f"Insertion error: {e}")
                        # It is important to commit the transaction even if there is an error to clear the redo stack.
                        return True

                    # Add "insert" action to history
                    self.history.add_action(
                        {
                            "type": "insert",
                            "text": text,
                            "position": insert_pos_for_history,
                        }
                    )

            finally:
                # End the compound action. This will clear the redo stack once for the whole operation.
                self.history.end_compound_action()
                self._ensure_trailing_newline()

            # Final status update and logging
            if made_change_overall:
                if self.status_message == original_status:
                    self._set_status_message(
                        "Text inserted" if text else "Selection deleted"
                    )
                logging.debug(
                    f"insert_text: Completed. Text '{text!r}' processed. Final cursor ({self.cursor_y}, {self.cursor_x})."
                )
            else:
                logging.debug(
                    f"insert_text: No effective change made for text '{text!r}'."
                )

        return made_change_overall

    def insert_text_at_position(self, text: str, row: int, col: int) -> bool:
        """Low-level insertion of `text` at the logical position (row, col).
        This is the definitive, corrected version that handles both single
        and multi-line pastes without data loss.

        It does NOT add to action history; the caller is responsible for that.
        The cursor is set immediately after the inserted text.

        Args:
            text (str): The text to insert.
            row (int): The 0-based row index for insertion.
            col (int): The 0-based column index for insertion.

        Returns:
            bool: True if text was non-empty and thus inserted, False otherwise.

        Raises:
            IndexError: If the `row` index is out of bounds.
        """
        if not text:
            logging.debug(
                "insert_text_at_position: empty text -> no action, returning False"
            )
            return False

        if not (0 <= row < len(self.text)):
            msg = f"insert_text_at_position: invalid row index {row} (buffer size {len(self.text)})"
            logging.error(msg)
            raise IndexError(msg)

        current_line_len = len(self.text[row])
        if not (0 <= col <= current_line_len):
            logging.warning(
                f"insert_text_at_position: column {col} out of bounds for line {row} (len {current_line_len}). Clamping."
            )
            col = max(0, min(col, current_line_len))

        logging.debug(
            f"insert_text_at_position: text='{text[:50].replace(chr(10), r' ')}...' at row={row}, col={col}"
        )

        lines_to_insert = text.split("\n")

        # Split the current line into two parts
        original_line_prefix = self.text[row][:col]
        original_line_suffix = self.text[row][col:]

        if len(lines_to_insert) == 1:
            # Single-line insertion
            # Reconstruct the line: prefix + insertion + suffix
            self.text[row] = (
                original_line_prefix + lines_to_insert[0] + original_line_suffix
            )
            self.cursor_y = row
            self.cursor_x = col + len(text)
        else:
            # Multi-line insertion
            # First line: prefix + first part of the inserted text
            self.text[row] = original_line_prefix + lines_to_insert[0]

            # Last line: last part of the inserted text + suffix
            last_new_line = lines_to_insert[-1] + original_line_suffix

            # Last line: last part of the inserted text + suffix
            last_new_line = lines_to_insert[-1] + original_line_suffix

            # Insert all new lines (middle + last)
            # Start with inserting the last line to avoid shifting indices for the middle ones
            self.text.insert(row + 1, last_new_line)
            # Now insert the middle lines in reverse order
            for line_content in reversed(lines_to_insert[1:-1]):
                self.text.insert(row + 1, line_content)

            # Update cursor position
            self.cursor_y = row + len(lines_to_insert) - 1
            self.cursor_x = len(lines_to_insert[-1])

        self.modified = True
        logging.debug(
            f"insert_text_at_position: cursor now at (y={self.cursor_y}, x={self.cursor_x})"
        )
        return True

    # ------------- Delete selected text ---------------------
    def delete_selected_text_internal(
        self, start_y: int, start_x: int, end_y: int, end_x: int
    ) -> list[str]:  # noqa: python:S3516
        """Low-level method: deletes text between normalized (start_y, start_x) and (end_y, end_x).
        Returns the deleted text as a list of strings (segments).
        Sets the cursor to (start_y, start_x).
        DOES NOT record an action in history. Sets self.modified = True.
        Assumes coordinates are normalized (start_y, start_x) <= (end_y, end_x).
        """
        logging.debug(
            f"delete_selected_text_internal: Deleting from ({start_y},{start_x}) to ({end_y},{end_x})"
        )

        # Basic coordinate validation
        # Ensure start_y and end_y are within the bounds of self.text
        if not (0 <= start_y < len(self.text) and 0 <= end_y < len(self.text)):
            logging.error(
                f"delete_selected_text_internal: Invalid row indices for deletion: "
                f"start_y={start_y}, end_y={end_y} with text length {len(self.text)}"
            )
            return []  # Return empty if rows are out of bounds

        # Ensure start_x and end_x are within the bounds of their respective lines
        if not (
            0 <= start_x <= len(self.text[start_y])
            and 0 <= end_x <= len(self.text[end_y])
        ):
            logging.error(
                f"delete_selected_text_internal: Invalid column indices for deletion: "
                f"start_x={start_x} (line len {len(self.text[start_y])}), "
                f"end_x={end_x} (line len {len(self.text[end_y])})"
            )
            return []

        deleted_segments = []
        if start_y == end_y:
            # Deletion within a single line
            line_content = self.text[start_y]
            actual_start_x = min(start_x, end_x)
            actual_end_x = max(start_x, end_x)

            actual_start_x = min(actual_start_x, len(line_content))
            actual_end_x = min(actual_end_x, len(line_content))

            if actual_start_x < actual_end_x:
                deleted_segments.append(line_content[actual_start_x:actual_end_x])
                self.text[start_y] = (
                    line_content[:actual_start_x] + line_content[actual_end_x:]
                )
            else:
                logging.debug(
                    "delete_selected_text_internal: Single line selection, but start_x >= end_x. No characters deleted."
                )
        else:
            # Multi-line deletion
            line_start_content = self.text[start_y]
            actual_start_x_on_first_line = min(start_x, len(line_start_content))
            deleted_segments.append(line_start_content[actual_start_x_on_first_line:])

            remaining_prefix_on_start_line = line_start_content[
                :actual_start_x_on_first_line
            ]

            if end_y > start_y + 1:
                deleted_segments.extend(self.text[start_y + 1 : end_y])

            line_end_content = self.text[end_y]
            actual_end_x_on_last_line = min(end_x, len(line_end_content))
            deleted_segments.append(line_end_content[:actual_end_x_on_last_line])

            remaining_suffix_on_end_line = line_end_content[actual_end_x_on_last_line:]

            self.text[start_y] = (
                remaining_prefix_on_start_line + remaining_suffix_on_end_line
            )
            del self.text[start_y + 1 : end_y + 1]

        self.cursor_y = start_y
        self.cursor_x = start_x

        self.modified = True

        if not deleted_segments and start_y == end_y and start_x == end_x:
            logging.debug(
                f"delete_selected_text_internal: No actual characters deleted (empty selection \
                    at a point). Cursor at ({self.cursor_y},{self.cursor_x})."
            )
        else:
            logging.debug(
                f"delete_selected_text_internal: Deletion complete. Cursor at ({self.cursor_y},{self.cursor_x})."
                f"Deleted segments count: {len(deleted_segments)}. \
                    First segment preview: '{deleted_segments[0][:50] if deleted_segments else ''}'"
            )
        return deleted_segments

    # ------- Paste ---------------
    def paste(self) -> bool:
        """Pastes text from the clipboard at the current cursor position.
        If a selection is active, it is cancelled before pasting, and the text
        is inserted at the current cursor location.
        """
        # First, we get the text that we will insert
        text_to_paste = ""
        source_of_paste = "internal"

        if self.use_system_clipboard and self.pyclip_available:
            try:
                system_text = pyperclip.paste()
                if system_text:
                    text_to_paste = system_text
                    self.internal_clipboard = system_text
                    source_of_paste = "system"
                    logging.info(
                        f"Retrieved {len(text_to_paste)} chars from system clipboard."
                    )
            except Exception as e:
                logging.warning(
                    f"Could not read from system clipboard, falling back to internal. Error: {e}"
                )

        if not text_to_paste:
            text_to_paste = self.internal_clipboard
            source_of_paste = "internal"
            if text_to_paste:
                logging.info(
                    f"Using {len(text_to_paste)} chars from internal clipboard."
                )

        if not text_to_paste:
            self._set_status_message("Clipboard is empty")
            return True

        # If there is a selection, we do not delete it, but simply cancel it.
        # Insertion always occurs at the current cursor position.
        if self.is_selecting:
            self.is_selecting = False
            self.selection_start = None
            self.selection_end = None
            logging.debug("Paste cancelled active selection before inserting.")

        # Now that the selection is cancelled, we simply insert the text.
        # The insert_text method will no longer see an active selection.
        text_to_paste = text_to_paste.replace("\r\n", "\n").replace("\r", "\n")

        if self.insert_text(text_to_paste):
            self._set_status_message(f"Pasted from {source_of_paste} clipboard")
            return True
        return False

    def delete_selected_text(self) -> None:
        """High-level action to delete the currently selected text and record
        it in the undo/redo history.
        """
        if not self.is_selecting:
            return

        with self._state_lock:
            norm_range = self._get_normalized_selection_range()
            if not norm_range:
                logging.warning(
                    "delete_selected_text: Called with active selection but no valid range."
                )
                return

            start_coords, end_coords = norm_range

            # Used internal method for actual deletion
            deleted_segments = self.delete_selected_text_internal(
                start_coords[0], start_coords[1], end_coords[0], end_coords[1]
            )

            # Record action in history
            if deleted_segments or (start_coords != end_coords):
                self.history.add_action(
                    {
                        "type": "delete_selection",
                        "text": deleted_segments,
                        "start": start_coords,
                        "end": end_coords,
                    }
                )

            # Clear selection
            self.is_selecting = False
            self.selection_start = None
            self.selection_end = None

            self._set_status_message("Selection deleted")

    # --------- Cut -----------
    def cut(self) -> bool:
        """Cuts the selected text to the internal and (if enabled) system clipboard.
        The selected text is removed from the document.
        Manages action history for the deletion.

        Returns:
            bool: True if the text, selection, cursor, scroll, or status message changed,
                  False otherwise (e.g., if trying to cut with no selection and status didn't change).
        """
        with self._state_lock:
            # Store initial state for comparison
            original_cursor_pos = (self.cursor_y, self.cursor_x)
            original_scroll_pos = (self.scroll_top, self.scroll_left)
            original_selection_state = (
                self.is_selecting,
                self.selection_start,
                self.selection_end,
            )
            original_modified_flag = self.modified
            original_status = self.status_message

            action_made_change_to_content = (
                False  # Tracks if text content actually changed
            )

            if not self.is_selecting:
                self._set_status_message("Nothing to cut (no selection)")
                return (
                    self.status_message != original_status
                )  # Redraw if status message changed

            # Selection exists, proceed with cutting
            normalized_range = self._get_normalized_selection_range()
            if (
                not normalized_range
            ):  # Should ideally not happen if self.is_selecting is True
                logging.warning(
                    "cut: is_selecting=True, but no valid normalized range."
                )
                self.is_selecting = False  # Attempt to recover
                self.selection_start = None
                self.selection_end = None
                self._set_status_message("Cut error: Invalid selection state")
                return True  # Status changed

            norm_start_coords, norm_end_coords = normalized_range

            # delete_selected_text_internal sets self.modified and new cursor position
            deleted_text_segments = self.delete_selected_text_internal(
                norm_start_coords[0],
                norm_start_coords[1],
                norm_end_coords[0],
                norm_end_coords[1],
            )

            # Check if anything was actually deleted
            if not deleted_text_segments and norm_start_coords == norm_end_coords:
                # This means the selection was effectively a point (start == end)
                self._set_status_message("Nothing to cut (empty selection)")
                self.is_selecting = False  # Clear selection state
                self.selection_start = None
                self.selection_end = None
                # Return True if status message changed or selection state changed
                return (
                    self.status_message != original_status
                    or (self.is_selecting, self.selection_start, self.selection_end)
                    != original_selection_state
                )

            action_made_change_to_content = True  # Text was removed

            text_for_clipboard = "\n".join(deleted_text_segments)

            # Always copy to internal clipboard
            self.internal_clipboard = text_for_clipboard
            status_message_for_cut = "Cut to internal clipboard"  # Default message

            # Attempt to copy to system clipboard if enabled and available
            if self.use_system_clipboard and self.pyclip_available:
                try:
                    pyperclip.copy(text_for_clipboard)
                    status_message_for_cut = "Cut to system clipboard"
                    logging.debug(
                        "Text cut and copied to system clipboard successfully."
                    )
                except pyperclip.PyperclipException as e:
                    logging.error(
                        f"Failed to copy cut text to system clipboard: {str(e)}"
                    )
                    status_message_for_cut = (
                        "Cut to internal clipboard (system clipboard error)"
                    )
                except Exception as e:  # Catch any other unexpected error
                    logging.error(
                        f"Unexpected error copying cut text to system clipboard: {e}",
                        exc_info=True,
                    )
                    status_message_for_cut = (
                        "Cut to internal clipboard (unexpected system clipboard error)"
                    )

            # Add the deletion action to history
            self.history.add_action(
                {
                    "type": "delete_selection",
                    "text": deleted_text_segments,
                    "start": norm_start_coords,
                    "end": norm_end_coords,
                }
            )

            # self.modified is already set to True by delete_selected_text_internal
            # Cursor position is also set by delete_selected_text_internal to norm_start_coords
            self.is_selecting = False  # Selection is gone after cut
            self.selection_start = None
            self.selection_end = None

            self._set_status_message(status_message_for_cut)

            # Ensure cursor and scroll are valid after the operation
            # Although delete_selected_text_internal sets cursor, _ensure_cursor_in_bounds is a good safeguard
            self._ensure_cursor_in_bounds()
            self._clamp_scroll()  # Scroll might need adjustment if cursor position changed significantly

            # Determine if a redraw is needed by comparing overall state
            # Since cut always involves text deletion and status change, it should always return True if successful.
            if (
                action_made_change_to_content
                or (self.cursor_y, self.cursor_x) != original_cursor_pos
                or (self.scroll_top, self.scroll_left) != original_scroll_pos
                or (self.is_selecting, self.selection_start, self.selection_end)
                != original_selection_state
                or self.modified
                != original_modified_flag  # Check if modified flag state actually flipped
                or self.status_message != original_status
            ):
                return True

            return False  # Should not be reached if cut was successful

    # ---- Undo ----
    def undo(self) -> bool:
        """Delegates the undo action to the History component."""
        return self.history.undo()

    # ---- Redo ----
    def redo(self) -> bool:
        """Delegates the redo action to the History component."""
        return self.history.redo()

    # ---- Cancel Selection ----
    def _cancel_selection_if_not_extending(self) -> bool:
        """Cancels the current selection if it exists.
        This is called by navigation methods to ensure that a simple
        cursor movement stops the selection mode.
        Returns True if a selection was cancelled, False otherwise.
        """
        if self.is_selecting:
            self.is_selecting = False
            self.selection_start = None
            self.selection_end = None
            logging.debug("Selection cancelled by cursor movement.")
            self._set_status_message("Selection cancelled")  # Add feedback
            return True
        return False

    # -------------- Selection Management ---------------------
    # (indirectly related to the visible cursor, which is usually at the end of the selection):
    # extend_selection_right(self)
    # extend_selection_left(self)
    # extend_selection_up(self)
    # extend_selection_down(self)
    # select_to_home(self)
    # select_to_end(self)
    # select_all(self)

    # ---- Selection Right -----
    def extend_selection_right(self) -> bool:
        """Extends the selection one character to the right.
        If no selection is active, starts a new selection from the current cursor position.
        Moves the cursor to the new end of the selection.
        Adjusts scroll if necessary.

        Returns:
            bool: True if the cursor position, selection state/boundaries, or scroll position changed,
                  False otherwise.
        """
        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_selection_start = self.selection_start
        original_selection_end = self.selection_end
        original_is_selecting_flag = self.is_selecting
        # No status message is typically set by this kind of fine-grained action

        changed_state = False

        with self._state_lock:
            current_line_idx = self.cursor_y
            if current_line_idx >= len(
                self.text
            ):  # Should not happen with valid cursor
                logging.warning(
                    f"extend_selection_right: cursor_y {current_line_idx} out of bounds."
                )
                return False  # No change possible

            current_line_content = self.text[current_line_idx]
            current_line_length = len(current_line_content)

            # If selection is not active, start it from the current cursor position.
            if not self.is_selecting:
                self.selection_start = (self.cursor_y, self.cursor_x)
                self.is_selecting = True
                # This itself is a state change if original_is_selecting_flag was False

            # Move the cursor logically one character to the right, if not at the end of the line.
            # This also becomes the new end of the selection.
            if self.cursor_x < current_line_length:
                self.cursor_x += 1
                # Skip over zero-width characters if any (though less common for simple right extension)
                while (
                    self.cursor_x < current_line_length
                    and wcwidth(current_line_content[self.cursor_x]) == 0
                ):
                    self.cursor_x += 1
            # If at the end of the line, cursor_x does not move further right on this line.
            # Extending selection to the next line is typically handled by extend_selection_down then extend_selection_left/right.
            # This method focuses on extending right on the *current* line or starting selection.

            # Update the end of the selection to the new cursor position.
            self.selection_end = (self.cursor_y, self.cursor_x)

            # Ensure scrolling is adjusted if the cursor moved out of view.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left) != original_scroll_pos
            or self.is_selecting != original_is_selecting_flag
            or self.selection_start != original_selection_start
            or self.selection_end != original_selection_end
        ):
            changed_state = True
            logging.debug(
                f"extend_selection_right: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"selection_end ({self.selection_end}). Changed: {changed_state}"
            )
        else:
            logging.debug(
                "extend_selection_right: No change in cursor, scroll, or selection state."
            )

        return changed_state

    # ------------ Selection Left ------------
    def extend_selection_left(self) -> bool:
        """Extends the selection one character to the left.
        If no selection is active, starts a new selection from the current cursor position.
        Moves the cursor to the new end of the selection (which is to the left).
        Adjusts scroll if necessary.

        Returns:
            bool: True if the cursor position, selection state/boundaries, or scroll position changed,
                  False otherwise.
        """
        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_selection_start = self.selection_start
        original_selection_end = self.selection_end
        original_is_selecting_flag = self.is_selecting

        changed_state = False

        with self._state_lock:
            current_line_idx = self.cursor_y
            if current_line_idx >= len(
                self.text
            ):  # Should not happen with valid cursor
                logging.warning(
                    f"extend_selection_left: cursor_y {current_line_idx} out of bounds."
                )
                return False  # No change possible

            # If selection is not active, start it from the current cursor position.
            # When extending left, the initial cursor position becomes the 'anchor' or 'selection_start'
            # if we consider selection_end to be the moving part.
            # Or, if self.selection_start is the fixed point and self.selection_end moves with cursor:
            if not self.is_selecting:
                self.selection_start = (self.cursor_y, self.cursor_x)  # Anchor point
                self.is_selecting = True

            # Move the cursor logically one character to the left.
            if self.cursor_x > 0:
                self.cursor_x -= 1
                # If moving left lands on a zero-width character, keep moving left
                # until a non-zero-width character is found or beginning of line.
                # This ensures the selection "jumps over" combining characters.
                current_line_content = self.text[current_line_idx]
                while (
                    self.cursor_x > 0
                    and wcwidth(current_line_content[self.cursor_x]) == 0
                ):
                    self.cursor_x -= 1
            # If at the beginning of the current line (self.cursor_x == 0),
            # this method does not currently extend to the previous line.
            # That would typically be handled by extend_selection_up then extend_selection_right/end.

            # Update the end of the selection to the new cursor position.
            # If selection_start was (y, X) and cursor moves to (y, X-1),
            # selection_end becomes (y, X-1).
            self.selection_end = (self.cursor_y, self.cursor_x)

            # Ensure scrolling is adjusted if the cursor moved out of view.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left) != original_scroll_pos
            or self.is_selecting != original_is_selecting_flag
            or self.selection_start
            != original_selection_start  # Could change if is_selecting was false
            or self.selection_end != original_selection_end
        ):  # Will always change if cursor_x changed
            changed_state = True
            logging.debug(
                f"extend_selection_left: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"selection_end ({self.selection_end}). Changed: {changed_state}"
            )
        else:
            logging.debug(
                "extend_selection_left: No change in cursor, scroll, or selection state."
            )

        return changed_state

    # --- Selection Up ----
    def extend_selection_up(self) -> bool:
        """Extends the selection one line upwards.
        If no selection is active, starts a new selection from the current cursor position.
        The cursor moves to the corresponding column in the line above, clamped by line length.
        The new cursor position becomes the (moving) end of the selection.

        Returns:
            bool: True if the cursor position, selection state/boundaries, or scroll position changed,
                  False otherwise.
        """
        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_selection_start = self.selection_start
        original_selection_end = self.selection_end
        original_is_selecting_flag = self.is_selecting

        changed_state = False

        with self._state_lock:
            # If selection is not active, start it from the current cursor position.
            # This current position becomes the 'anchor' (selection_start).
            if not self.is_selecting:
                self.selection_start = (self.cursor_y, self.cursor_x)
                self.is_selecting = True

            # Move the cursor logically one line up, if not already at the first line.
            if self.cursor_y > 0:
                self.cursor_y -= 1
                # Maintain the horizontal cursor column if possible, clamping to the new line's length.
                # self.cursor_x (the "desired" column) is preserved from the previous line.
                self.cursor_x = min(self.cursor_x, len(self.text[self.cursor_y]))
            # If at the first line (self.cursor_y == 0), no further upward movement is possible.

            # Update the end of the selection to the new cursor position.
            self.selection_end = (self.cursor_y, self.cursor_x)

            # Adjust scroll if necessary.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left) != original_scroll_pos
            or self.is_selecting != original_is_selecting_flag
            or self.selection_start
            != original_selection_start  # Could change if is_selecting was false
            or self.selection_end != original_selection_end
        ):  # Will change if cursor_y or cursor_x changed
            changed_state = True
            logging.debug(
                f"extend_selection_up: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"selection_end ({self.selection_end}). Changed: {changed_state}"
            )
        else:
            logging.debug(
                "extend_selection_up: No change in cursor, scroll, or selection state."
            )

        return changed_state

    # ----- Selection Down -----
    def extend_selection_down(self) -> bool:
        """Extends the selection one line downwards. Correctly handles extending
        onto the virtual line after the last line of text.
        """
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_selection_state = (
            self.is_selecting,
            self.selection_start,
            self.selection_end,
        )
        changed_state = False

        with self._state_lock:
            if not self.is_selecting:
                self.selection_start = (self.cursor_y, self.cursor_x)
                self.is_selecting = True

            # Allow the cursor to move up to and including len(self.text)
            if self.cursor_y < len(self.text):
                self.cursor_y += 1

            # _ensure_cursor_in_bounds is now critically important. It will set
            # cursor_x to 0 if cursor_y has become equal to len(self.text).
            self._ensure_cursor_in_bounds()

            self.selection_end = (self.cursor_y, self.cursor_x)
            self._clamp_scroll()  # _clamp_scroll is now safe

        # Check if anything has changed
        if (self.cursor_y, self.cursor_x) != original_cursor_pos or (
            self.is_selecting,
            self.selection_start,
            self.selection_end,
        ) != original_selection_state:
            changed_state = True

        if changed_state:
            logging.debug(
                f"extend_selection_down: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"selection_end ({self.selection_end}). Changed: True"
            )
        return changed_state

    # ------------ Selection Home ---------------
    def select_to_home(self) -> bool:
        """Extends the selection from the current cursor position to the beginning of the current line.
        If no selection is active, starts a new selection.
        The cursor moves to the beginning of the line (column 0).

        Returns:
            bool: True if the cursor position, selection state/boundaries, or scroll position changed,
                  False otherwise.
        """
        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (
            self.scroll_top,
            self.scroll_left,
        )  # Specifically scroll_left
        original_selection_start = self.selection_start
        original_selection_end = self.selection_end
        original_is_selecting_flag = self.is_selecting

        changed_state = False

        with self._state_lock:
            current_line_idx = self.cursor_y
            if current_line_idx >= len(
                self.text
            ):  # Should not happen with valid cursor
                logging.warning(
                    f"select_to_home: cursor_y {current_line_idx} out of bounds."
                )
                return False  # No change possible

            # If selection is not active, start it from the current cursor position.
            # This current position becomes the 'anchor' (selection_start).
            if not self.is_selecting:
                self.selection_start = (self.cursor_y, self.cursor_x)
                self.is_selecting = True

            # Move the cursor to the beginning of the current line (column 0).
            self.cursor_x = 0

            # Update the end of the selection to the new cursor position (beginning of the line).
            self.selection_end = (self.cursor_y, self.cursor_x)

            # Adjust horizontal scroll if necessary, as cursor moved to column 0.
            # _clamp_scroll will handle if self.cursor_x (now 0) is less than self.scroll_left.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left)
            != original_scroll_pos  # Check both scroll dimensions
            or self.is_selecting != original_is_selecting_flag
            or self.selection_start != original_selection_start
            or self.selection_end != original_selection_end
        ):
            changed_state = True
            logging.debug(
                f"select_to_home: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"selection_end ({self.selection_end}). Changed: {changed_state}"
            )
        else:
            logging.debug(
                "select_to_home: No change in cursor, scroll, or selection state."
            )

        return changed_state

    # ------ Selection End --------------
    def select_to_end(self) -> bool:
        """Extends the selection from the current cursor position to the end of the current line.
        If no selection is active, starts a new selection.
        The cursor moves to the end of the line.

        Returns:
            bool: True if the cursor position, selection state/boundaries, or scroll position changed,
                  False otherwise.
        """
        # Store initial state for comparison
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_selection_start = self.selection_start
        original_selection_end = self.selection_end
        original_is_selecting_flag = self.is_selecting

        changed_state = False

        with self._state_lock:
            current_line_idx = self.cursor_y
            if current_line_idx >= len(
                self.text
            ):  # Should not happen with valid cursor
                logging.warning(
                    f"select_to_end: cursor_y {current_line_idx} out of bounds."
                )
                return False  # No change possible

            current_line_content = self.text[current_line_idx]
            current_line_length = len(current_line_content)

            # If selection is not active, start it from the current cursor position.
            # This current position becomes the 'anchor' (selection_start).
            if not self.is_selecting:
                self.selection_start = (self.cursor_y, self.cursor_x)
                self.is_selecting = True

            # Move the cursor to the end of the current line.
            self.cursor_x = current_line_length

            # Update the end of the selection to the new cursor position (end of the line).
            self.selection_end = (self.cursor_y, self.cursor_x)

            # Adjust scroll if necessary, as cursor may have moved far right.
            self._clamp_scroll()

        # Determine if any relevant state actually changed.
        if (
            (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left) != original_scroll_pos
            or self.is_selecting != original_is_selecting_flag
            or self.selection_start != original_selection_start
            or self.selection_end != original_selection_end
        ):
            changed_state = True
            logging.debug(
                f"select_to_end: New cursor ({self.cursor_y},{self.cursor_x}), "
                f"selection_end ({self.selection_end}). Changed: {changed_state}"
            )
        else:
            logging.debug(
                "select_to_end: No change in cursor, scroll, or selection state."
            )

        return changed_state

    # ----- Selection ALL -----
    def select_all(self) -> bool:
        """Selects all text in the document.
        Moves the cursor to the end of the selection.
        Sets a status message.
        Adjusts scroll to ensure the end of the selection (and cursor) is visible.

        Returns:
            bool: True, as this action always changes the selection state,
                  cursor position, potentially scroll, and status message,
                  thus requiring a redraw.
        """
        logging.debug("select_all called")

        # Store original state for comparison, though this action almost always changes it
        original_selection_state = (
            self.is_selecting,
            self.selection_start,
            self.selection_end,
        )
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        original_status = self.status_message

        with self._state_lock:  # Ensure atomicity of state changes
            if not self.text:  # Should not happen if text is always at least [""]
                self.text = [""]  # Ensure there's at least one line
                logging.warning(
                    "select_all: Text buffer was unexpectedly empty, initialized to ['']."
                )

            # Set selection start to the beginning of the document
            self.selection_start = (0, 0)

            # Determine the end of the document
            # If the buffer is [""] (one empty line), last_line_idx is 0, len(self.text[0]) is 0.
            # So selection_end will be (0,0).
            # If buffer has content, e.g. ["abc", "de"], last_line_idx is 1, len(self.text[1]) is 2.
            # So selection_end will be (1,2).
            last_line_idx = max(0, len(self.text) - 1)
            self.selection_end = (last_line_idx, len(self.text[last_line_idx]))

            self.is_selecting = True  # Mark that selection is active

            # Move the cursor to the end of the new selection
            self.cursor_y, self.cursor_x = self.selection_end

            self._set_status_message("All text selected")

            # Adjust scroll to make the new cursor position (end of selection) visible
            self._clamp_scroll()

            # Determine if a redraw is needed by comparing relevant state aspects
        # For select_all, it's virtually guaranteed to change state.
        if (
            self.is_selecting != original_selection_state[0]
            or self.selection_start != original_selection_state[1]
            or self.selection_end != original_selection_state[2]
            or (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left) != original_scroll_pos
            or self.status_message != original_status
        ):
            return True

        return False  # Should technically not be reached if "All text selected" is always set.

    # -------------------- Block Indentation/Commenting Methods --------------------
    # (also affects self.cursor_x/y after changing the selection)
    # handle_block_indent(self)
    # handle_block_unindent(self)
    # unindent_current_line(self)
    # comment_lines(self, ...)
    # uncomment_lines(self, ...)

    def handle_block_indent(self) -> bool:
        """Increases indentation for all lines within the current selection.
        Updates selection, cursor, modified status, and action history.

        Returns:
            bool: True if any lines were indented or if the status
                  message changed, indicating a redraw is needed.
                  False if no selection was active.
        """
        if not self.is_selecting or not self.selection_start or not self.selection_end:
            self._set_status_message("No selection to indent.")
            return True  # Status message changed

        original_status = self.status_message
        original_selection_tuple = (
            self.is_selecting,
            self.selection_start,
            self.selection_end,
        )

        made_actual_text_change = False

        with self._state_lock:
            norm_range = self._get_normalized_selection_range()
            if not norm_range:
                logging.warning(
                    "handle_block_indent: Could not get normalized selection \
                        range despite active selection."
                )
                self._set_status_message("Selection error during indent.")
                return True

            start_coords, end_coords = norm_range
            start_y_idx, start_x_in_line_sel = start_coords
            end_y_idx, end_x_in_line_sel = end_coords

            tab_size = self.config.get("editor", {}).get("tab_size", 4)
            use_spaces = self.config.get("editor", {}).get("use_spaces", True)
            indent_string = " " * tab_size if use_spaces else "\t"
            indent_char_length = len(indent_string)

            undo_changes_list: list[dict[str, Any]] = []
            indented_line_count = 0

            for current_y in range(start_y_idx, end_y_idx + 1):
                if current_y >= len(self.text):
                    continue

                original_line_content = self.text[current_y]
                self.text[current_y] = indent_string + original_line_content

                undo_changes_list.append(
                    {
                        "line_index": current_y,
                        "original_text": original_line_content,
                        "new_text": self.text[current_y],
                    }
                )
                indented_line_count += 1
                made_actual_text_change = True

            if made_actual_text_change:
                self.modified = True

                new_selection_start_x = start_x_in_line_sel + indent_char_length
                new_selection_end_x = end_x_in_line_sel + indent_char_length

                self.selection_start = (start_y_idx, new_selection_start_x)
                self.selection_end = (end_y_idx, new_selection_end_x)

                self.cursor_y, self.cursor_x = self.selection_end

                self.history.add_action(
                    {
                        "type": "block_indent",
                        "changes": undo_changes_list,
                        "indent_str_used": indent_string,
                        "start_y": start_y_idx,
                        "end_y": end_y_idx,
                        "selection_before": original_selection_tuple[
                            1:
                        ],  # Save (start_coords, end_coords)
                        "cursor_before_no_selection": None,  # Since there is always a selection
                        "selection_after": (
                            self.is_selecting,
                            self.selection_start,
                            self.selection_end,
                        ),
                        "cursor_after_no_selection": None,  # Since the selection remains
                    }
                )
                self._set_status_message(f"Indented {indented_line_count} line(s)")
                logging.debug(
                    f"Block indent: {indented_line_count} lines from {start_y_idx}-{end_y_idx} "
                    f"indented by '{indent_string}'. New selection: {self.selection_start} -> {self.selection_end}"
                )
                return True
            if self.status_message == original_status:
                self._set_status_message(
                    "No lines selected for indent operation."
                )  # Or "Nothing to indent in selection"
            return self.status_message != original_status
        # Default return if somehow lock isn't acquired or other paths missed
        return False

    def handle_block_unindent(self) -> bool:  # noqa: python:S3516
        """Decreases indentation for all lines within the current selection.
        Updates selection, cursor, modified status, and action history.

        Returns:
            bool: True if any lines were unindented or if the status message changed,
                  False otherwise (e.g., no selection or nothing to unindent).
        """
        if not self.is_selecting or not self.selection_start or not self.selection_end:
            self._set_status_message("No selection to unindent.")
            return True  # Status message changed

        original_status = self.status_message
        original_selection_tuple = (
            self.is_selecting,
            self.selection_start,
            self.selection_end,
        )

        made_actual_text_change = False

        with self._state_lock:
            norm_range = self._get_normalized_selection_range()
            if not norm_range:
                logging.warning(
                    "handle_block_unindent: Could not get normalized selection range despite active selection."
                )
                self._set_status_message("Selection error during unindent.")
                return True

            start_coords, end_coords = norm_range
            start_y_idx, start_x_in_line_sel = start_coords
            end_y_idx, end_x_in_line_sel = end_coords

            tab_size = self.config.get("editor", {}).get("tab_size", 4)
            use_spaces = self.config.get("editor", {}).get("use_spaces", True)
            # Number of characters to attempt to remove for unindentation
            unindent_char_count_to_try = tab_size if use_spaces else 1

            undo_changes_list: list[dict[str, Any]] = []
            unindented_line_count = 0

            # Store characters actually removed per line for accurate cursor/selection adjustment
            chars_removed_from_sel_start_line = 0
            chars_removed_from_sel_end_line = 0

            for current_y in range(start_y_idx, end_y_idx + 1):
                if current_y >= len(self.text):
                    continue

                original_line_content = self.text[current_y]
                line_to_modify = self.text[current_y]
                prefix_that_was_removed = ""

                if use_spaces:
                    actual_spaces_to_remove = 0
                    for i in range(
                        min(len(line_to_modify), unindent_char_count_to_try)
                    ):
                        if line_to_modify[i] == " ":
                            actual_spaces_to_remove += 1
                        else:
                            break
                    if actual_spaces_to_remove > 0:
                        prefix_that_was_removed = line_to_modify[
                            :actual_spaces_to_remove
                        ]
                        self.text[current_y] = line_to_modify[actual_spaces_to_remove:]
                elif line_to_modify.startswith("\t"):
                    prefix_that_was_removed = "\t"
                    self.text[current_y] = line_to_modify[1:]

                if prefix_that_was_removed:
                    undo_changes_list.append(
                        {
                            "line_index": current_y,
                            "original_text": original_line_content,
                            "new_text": self.text[current_y],
                        }
                    )
                    unindented_line_count += 1
                    made_actual_text_change = True
                    if current_y == start_y_idx:
                        chars_removed_from_sel_start_line = len(prefix_that_was_removed)
                    if current_y == end_y_idx:  # Could be same as start_y_idx
                        chars_removed_from_sel_end_line = len(prefix_that_was_removed)

            if made_actual_text_change:
                self.modified = True

                new_selection_start_x = max(
                    0, start_x_in_line_sel - chars_removed_from_sel_start_line
                )
                new_selection_end_x = max(
                    0, end_x_in_line_sel - chars_removed_from_sel_end_line
                )

                self.selection_start = (start_y_idx, new_selection_start_x)
                self.selection_end = (end_y_idx, new_selection_end_x)

                self.cursor_y, self.cursor_x = self.selection_end

                self.history.add_action(
                    {
                        "type": "block_unindent",  # Specific type for undo/redo
                        "changes": undo_changes_list,
                        "start_y": start_y_idx,
                        "end_y": end_y_idx,
                        "selection_before": original_selection_tuple[1:],
                        "cursor_before_no_selection": None,
                        "selection_after": (
                            self.is_selecting,
                            self.selection_start,
                            self.selection_end,
                        ),
                        "cursor_after_no_selection": None,
                    }
                )
                self._set_status_message(f"Unindented {unindented_line_count} line(s)")
                logging.debug(
                    f"Block unindent: {unindented_line_count} lines from {start_y_idx}-{end_y_idx} unindented. "
                    f"New selection: {self.selection_start} -> {self.selection_end}"
                )
                return True
            if self.status_message == original_status:
                self._set_status_message("Nothing to unindent in selection.")
            return self.status_message != original_status

    def unindent_current_line(self) -> bool:
        """Decreases the indentation of the current line if there is no active selection.

        This method attempts to unindent the current line by removing either a configured
        number of leading spaces or a single tab character, depending on editor settings.
        If successful, the change is recorded in the undo history, the modified flag is set,
        and the status message is updated. If no unindentation is possible, an appropriate
        status message is set. This operation does nothing if there is an active selection.

        Returns:
            bool: True if the line was unindented or the status message changed (requiring a redraw),
                False otherwise.

        Side Effects:
            - Modifies the text buffer if unindentation occurs.
            - Updates cursor position and editor modified state.
            - Records the change in the undo history.
            - Updates the status message.

        Notes:
            This method is intended for single-line unindent only. For block unindent, see
            handle_smart_unindent or handle_block_unindent.
        """
        if self.is_selecting:
            # This action is intended for when there's no selection.
            # Block unindent is handled by handle_smart_unindent -> handle_block_unindent.
            return False

        original_status = self.status_message
        original_line_content = ""
        original_cursor_pos = (
            self.cursor_y,
            self.cursor_x,
        )  # For history and change detection

        with self._state_lock:
            current_y = self.cursor_y
            if current_y >= len(self.text):
                logging.warning(
                    f"unindent_current_line: cursor_y {current_y} out of bounds."
                )
                return False

            original_line_content = self.text[current_y]  # Save for undo
            line_to_modify = self.text[current_y]

            if not line_to_modify or not (
                line_to_modify.startswith(" ") or line_to_modify.startswith("\t")
            ):
                self._set_status_message("Nothing to unindent at line start.")
                return self.status_message != original_status

            tab_size = self.config.get("editor", {}).get("tab_size", 4)
            use_spaces = self.config.get("editor", {}).get("use_spaces", True)
            unindent_char_count_to_try = tab_size if use_spaces else 1

            chars_removed_from_line = 0

            if use_spaces:
                actual_spaces_to_remove = 0
                for i in range(min(len(line_to_modify), unindent_char_count_to_try)):
                    if line_to_modify[i] == " ":
                        actual_spaces_to_remove += 1
                    else:
                        break
                if actual_spaces_to_remove > 0:
                    self.text[current_y] = line_to_modify[actual_spaces_to_remove:]
                    chars_removed_from_line = actual_spaces_to_remove
            elif line_to_modify.startswith("\t"):
                self.text[current_y] = line_to_modify[1:]
                chars_removed_from_line = 1

            if chars_removed_from_line > 0:
                self.modified = True
                # Adjust cursor: move left by the number of characters removed, but not before column 0
                self.cursor_x = max(0, self.cursor_x - chars_removed_from_line)

                self.history.add_action(
                    {
                        "type": "block_unindent",  # Re-use for consistency with undo/redo logic
                        "changes": [
                            {
                                "line_index": current_y,
                                "original_text": original_line_content,
                                "new_text": self.text[current_y],
                            }
                        ],
                        "selection_before": None,  # No selection was active
                        "cursor_before_no_selection": original_cursor_pos,
                        "selection_after": None,
                        "cursor_after_no_selection": (self.cursor_y, self.cursor_x),
                    }
                )
                self._set_status_message("Line unindented.")
                logging.debug(
                    f"Unindented line {current_y}. Removed {chars_removed_from_line} char(s). Cursor at {self.cursor_x}"
                )
                return True
            if self.status_message == original_status:
                self._set_status_message(
                    "Nothing effectively unindented on current line."
                )
            return self.status_message != original_status

    # ----------------------- Commenting lines -----------------------
    def comment_lines(self, start_y: int, end_y: int, comment_prefix: str) -> bool:
        """Comments a range of lines by prepending a language-specific prefix.

        This high-level method orchestrates the block commenting process. It is designed
        to be intelligent, avoiding double-commenting and respecting the block's
        existing indentation. The core logic is decomposed into helper methods
        for clarity and maintainability.

        The process is as follows:
        1.  Find Minimum Indent (`_find_min_indent_for_commenting`): It first scans
            all non-empty lines within the specified range (`start_y` to `end_y`) to
            determine the shallowest indentation level. This ensures that the
            comment prefix is inserted consistently at the start of the code block,
            not at the beginning of each line.

        2.  Determine Insert Position (`_determine_comment_insert_pos`): For each
            line in the range, it calculates the precise column to insert the
            `comment_prefix`. For code lines, this is the minimum indent found in
            step 1. For blank or whitespace-only lines, it inserts the prefix at
            the start of the line's content to preserve alignment.

        3.  Apply Commenting: It iterates through each line, prepending the
            `comment_prefix` at the calculated position. It skips any line that
            is already commented with the same prefix at that position to prevent
            double-commenting (e.g., `## comment`).

        4.  Update State: If any lines were modified, it updates the editor's
            state:
            - Sets the `modified` flag to True.
            - Adjusts the cursor and selection boundaries to account for the newly
              inserted prefix characters using `_adjust_selection_after_commenting`.
            - Records the entire operation in the undo/redo history.
            - Sets a status message indicating how many lines were commented.

        Args:
            start_y (int): The starting line index (0-based) of the block to comment.
            end_y (int): The ending line index (0-based) of the block.
            comment_prefix (str): The string to prepend as a comment (e.g., "# ", "// ").

        Returns:
            bool: True, as this operation always results in a UI update (either the
                  text is changed or a status message is set), requiring a redraw.
        """
        with self._state_lock:
            min_indent = self._find_min_indent_for_commenting(start_y, end_y)

            undo_changes = []
            lines_commented_count = 0

            original_texts = {
                y: self.text[y] for y in range(start_y, end_y + 1) if y < len(self.text)
            }

            for y in range(start_y, end_y + 1):
                if y >= len(self.text):
                    continue

                line = self.text[y]
                insert_pos = self._determine_comment_insert_pos(line, min_indent)

                is_already_commented = line[insert_pos:].startswith(comment_prefix)
                if is_already_commented:
                    logging.debug(f"Line {y + 1} already commented, skipping.")
                    continue

                self.text[y] = line[:insert_pos] + comment_prefix + line[insert_pos:]
                undo_changes.append(
                    {
                        "line_index": y,
                        "original_text": original_texts.get(y, line),
                        "new_text": self.text[y],
                    }
                )
                lines_commented_count += 1

            if undo_changes:
                # If changes were made, update state and history
                self.modified = True
                self._adjust_selection_after_commenting(
                    start_y, end_y, len(comment_prefix), min_indent
                )

                self.history.add_action(
                    {
                        "type": "comment_block",
                        "changes": undo_changes,
                        "comment_prefix": comment_prefix,
                    }
                )
                self._set_status_message(f"Commented {lines_commented_count} line(s)")
            else:
                # No lines were actually commented
                self._set_status_message("Selected lines already commented.")

        # This operation always results in a UI change (text is modified or status message is set),
        # so a redraw is always required.
        return True

    def _find_min_indent_for_commenting(self, start_y: int, end_y: int) -> int:
        """Finds the minimum indentation level for non-empty lines in a range."""
        min_indent = float("inf")
        found_non_empty_line = False

        for y in range(start_y, end_y + 1):
            if y >= len(self.text):
                continue
            line = self.text[y]
            if line.strip():
                indent_len = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent_len)
                found_non_empty_line = True

        return int(min_indent) if found_non_empty_line else 0

    def _determine_comment_insert_pos(self, line: str, min_indent: int) -> int:
        """Determines the column where the comment prefix should be inserted."""
        if not line.strip():  # For blank or whitespace-only lines
            # Find first non-space char (like a tab) or end of string
            for i, char in enumerate(line):
                if char != " ":
                    return i
            return len(line)
        # For non-blank lines
        return min_indent

    def _adjust_selection_after_commenting(
        self, start_y: int, end_y: int, prefix_len: int, min_indent: int
    ) -> None:
        """Adjusts cursor and selection after adding comments."""
        if self.is_selecting and self.selection_start and self.selection_end:
            s_y, s_x = self.selection_start
            e_y, e_x = self.selection_end

            # A simple shift if the comment was added at or before the selection start
            new_s_x = (
                s_x + prefix_len
                if s_y >= start_y and s_y <= end_y and min_indent <= s_x
                else s_x
            )
            new_e_x = (
                e_x + prefix_len
                if e_y >= start_y and e_y <= end_y and min_indent <= e_x
                else e_x
            )

            self.selection_start = (s_y, new_s_x)
            self.selection_end = (e_y, new_e_x)
            self.cursor_y, self.cursor_x = self.selection_end
        elif not self.is_selecting:  # Single line comment at cursor_y
            if (
                self.cursor_y >= start_y
                and self.cursor_y <= end_y
                and min_indent <= self.cursor_x
            ):
                self.cursor_x += prefix_len

    # -------------- Uncommenting  lines ----------------------
    def uncomment_lines(self, start_y: int, end_y: int, comment_prefix: str) -> bool:
        """Uncomments a range of lines by removing a language-specific prefix.

        This high-level method orchestrates the block uncommenting process. It is
        designed to be robust, correctly handling various commenting styles and
        updating the editor state accordingly. The core logic is decomposed into
        helper methods for clarity and maintainability.

        The process is as follows:
        1.  Uncomment Each Line (`_uncomment_single_line`): The method iterates
            through each line in the specified range (`start_y` to `end_y`). For each
            line, it delegates the actual uncommenting logic to the
            `_uncomment_single_line` helper. This helper intelligently removes
            the `comment_prefix` from the start of the line's content (after any
            leading whitespace). It correctly handles prefixes with and without
            trailing spaces (e.g., removing both "# " and "#" from a line).
            It returns the modified line and the number of characters removed.

        2.  Update State and History: If any lines were successfully uncommented,
            this method updates the editor's state:
            - Sets the `modified` flag to True.
            - Adjusts the cursor and selection boundaries to account for the
              removed characters using `_adjust_selection_after_uncommenting`.
              This ensures the selection and cursor remain in a logical position.
            - Records the entire operation in the undo/redo history as a single,
              atomic action.
            - Sets a status message indicating how many lines were uncommented.

        3.  Handle No Changes: If no lines in the selection were uncommented
            (e.g., they were not commented with the specified prefix), it sets an
            informative status message.

        Args:
            start_y (int): The starting line index (0-based) of the block.
            end_y (int): The ending line index (0-based) of the block.
            comment_prefix (str): The comment prefix to remove (e.g., "# ", "// ").

        Returns:
            bool: True, as this operation always results in a UI update (either the
                  text is changed or a status message is set), requiring a redraw.
        """
        with self._state_lock:
            undo_changes = []
            chars_removed_map = {}  # {line_index: count}

            for y in range(start_y, end_y + 1):
                if y >= len(self.text):
                    continue

                original_line = self.text[y]
                new_line, chars_removed = self._uncomment_single_line(
                    original_line, comment_prefix
                )

                if chars_removed > 0:
                    self.text[y] = new_line
                    undo_changes.append(
                        {
                            "line_index": y,
                            "original_text": original_line,
                            "new_text": new_line,
                        }
                    )
                    chars_removed_map[y] = chars_removed

            if undo_changes:
                # If changes were made, update state and history
                self.modified = True
                self._adjust_selection_after_uncommenting(chars_removed_map)

                self.history.add_action(
                    {
                        "type": "uncomment_block",
                        "changes": undo_changes,
                        "comment_prefix": comment_prefix,
                    }
                )
                self._set_status_message(f"Uncommented {len(undo_changes)} line(s)")
            else:
                # No lines were actually uncommented
                self._set_status_message(
                    f"Nothing to uncomment with prefix '{comment_prefix}'"
                )

        # This operation always results in a UI change (text is modified or status message is set),
        # so a redraw is always required.
        return True

    def _uncomment_single_line(self, line: str, comment_prefix: str) -> tuple[str, int]:
        """Attempts to uncomment a single line.

        Returns:
            A tuple of (new_line_content, number_of_chars_removed).
        """
        prefix_stripped = comment_prefix.strip()
        leading_whitespace = line[: len(line) - len(line.lstrip())]
        content_after_indent = line.lstrip()

        # Case 1: Exact prefix match (e.g., "# " for "# comment")
        if content_after_indent.startswith(comment_prefix):
            new_line = leading_whitespace + content_after_indent[len(comment_prefix) :]
            return new_line, len(comment_prefix)

        # Case 2: Stripped prefix match (e.g., "#" for "#comment")
        if content_after_indent.startswith(prefix_stripped):
            len_stripped = len(prefix_stripped)
            # Check if a space should also be removed
            if (
                comment_prefix.endswith(" ")
                and len(content_after_indent) > len_stripped
                and content_after_indent[len_stripped] == " "
            ):
                new_line = leading_whitespace + content_after_indent[len_stripped + 1 :]
                return new_line, len_stripped + 1
            new_line = leading_whitespace + content_after_indent[len_stripped:]
            return new_line, len_stripped

        return line, 0  # No changes made

    def _adjust_selection_after_uncommenting(
        self, chars_removed_map: dict[int, int]
    ) -> None:
        """Adjusts cursor and selection after removing comments."""
        if self.is_selecting and self.selection_start and self.selection_end:
            s_y, s_x = self.selection_start
            e_y, e_x = self.selection_end

            chars_removed_start = chars_removed_map.get(s_y, 0)
            chars_removed_end = chars_removed_map.get(e_y, 0)

            self.selection_start = (s_y, max(0, s_x - chars_removed_start))
            self.selection_end = (e_y, max(0, e_x - chars_removed_end))
            self.cursor_y, self.cursor_x = self.selection_end
        elif not self.is_selecting:
            chars_removed = chars_removed_map.get(self.cursor_y, 0)
            self.cursor_x = max(0, self.cursor_x - chars_removed)

    def get_char_width(self, char: str) -> int:
        """Calculates the display width of a character using wcwidth.
        Returns 1 for control characters or characters with ambiguous width (-1).
        Uses unicodedata to check if it's a control character.
        """
        if not isinstance(char, str) or len(char) != 1:
            return 1  # Unexpected input, counting width 1

        # Check for control characters (except known types like Tab, Enter)
        if unicodedata.category(char) in ("Cc", "Cf"):  # Cc: Control, Cf: Format
            # Here we can add exceptions for characters we want to display (e.g., '\t')
            if char == "\t":
                # Tab width depends on cursor position and tab_size,
                # but wcwidth('\t') is usually 0 or 1.
                # For rendering Pygments tokens, it's better to return wcwidth or 1.
                # Actual tab rendering happens in DrawScreen.
                width = wcwidth(char)
                return width if width >= 0 else 1
            return 0  # Control characters are usually not displayed and have 0 width
        # Check for zero-width characters (e.g., diacritics)
        if unicodedata.combining(char):
            return 0  # Combining characters have zero width

        width = wcwidth(char)
        # wcwidth returns -1 for characters with undefined width,
        # or 0 for zero-width characters (which we've already handled).
        # For -1 or 0 (if not combining), we return 1 to move the cursor.
        # If wcwidth returned >=0, we return it.
        return width if width >= 0 else 1

    def get_string_width(self, text: str) -> int:
        """Calculates the display width of a string using wcswidth.
        Handles potential errors by summing individual character widths.
        """
        if not isinstance(text, str):
            logging.warning(f"get_string_width received non-string input: {type(text)}")
            return 0

        try:
            width = cast(int, wcswidth(text))
            # If wcswidth returned -1 (non-printable characters),
            # we do NOT return this value, but move on to fallback.
            if width != -1:
                return width
        except Exception as e:
            # If wcswidth raised an error, log it and fall back.
            logging.warning(
                f"wcswidth failed for '{text[:20]}...': {e}. Falling back to char sum."
            )

        # Fallback: sum the width of each character
        total_width = 0
        for char in text:
            total_width += self.get_char_width(char)
        return total_width

    # Signature #1: for binary mode.
    @overload
    def safe_open(
        self,
        filename: str,
        mode: Literal["rb", "wb", "ab", "xb", "r+b", "w+b", "a+b", "x+b"],
        encoding: None = None,
        errors: None = None,
    ) -> BinaryIO: ...

    # Signature #2: for text mode.
    @overload
    def safe_open(
        self,
        filename: str,
        mode: Literal[
            "r", "w", "a", "x", "r+", "w+", "a+", "x+", "rt", "wt", "at", "xt"
        ] = "r",
        encoding: str | None = None,
        errors: str = "replace",
    ) -> TextIO: ...

    # Implementation covering both signatures.
    # Note: The mode parameter is a union of both signatures.
    # The encoding and errors types have been made more general to accommodate both signatures.
    def safe_open(
        self,
        filename: str,
        mode: str = "r",
        encoding: str | None = None,
        errors: str | None = "replace",
    ) -> TextIO | BinaryIO:
        """Safely open a file in the given mode."""
        try:
            if "b" in mode:
                # Here we return BinaryIO.
                return cast(BinaryIO, open(filename, mode))
            # Here we also use `cast` for TextIO.
            return cast(
                TextIO,
                open(
                    filename,
                    mode,
                    encoding=encoding or self.encoding,
                    errors=errors,
                ),
            )
        except Exception as e:
            logging.error(
                f"Failed to safe_open file {filename!r} in mode {mode!r}: {e}"
            )
            raise

    # =============== Open file ============================
    def open_file(self, filename_to_open: Optional[str] = None) -> bool:  # noqa: python:S3516
        """Opens a specified file or prompts for one.
        Handles unsaved changes in the current buffer before proceeding.
        Detects file encoding, loads content, and updates editor state.

        Args:
            filename_to_open (Optional[str]): The path to the file to open.
                                             If None, the user will be prompted.

        Returns:
            bool: True if the editor's state changed significantly (new file loaded,
                  status message updated, prompt interaction occurred) requiring a redraw,
                  False otherwise (e.g., operation fully cancelled without status change).
        """
        logging.debug(f"open_file called. Requested filename: '{filename_to_open}'")

        # Store initial states to determine if a redraw is ultimately needed
        original_status = self.status_message
        original_filename_for_revert = self.filename
        original_text_tuple_for_revert = tuple(self.text)
        original_modified_flag_for_revert = self.modified

        status_changed_by_interaction = False

        try:
            # Handle unsaved changes in the current buffer
            if self.modified:
                status_before_save_prompt = self.status_message
                ans = self.prompt("Current file has unsaved changes. Save now? (y/n): ")
                if self.status_message != status_before_save_prompt:
                    status_changed_by_interaction = True

                if ans and ans.lower().startswith("y"):
                    self.save_file()
                    if self.modified:
                        self._set_status_message(
                            "Open file cancelled: current file changes were not saved."
                        )
                        logging.warning(
                            "Open file aborted: User chose to save, but 'save_file' did not clear 'modified' flag."
                        )
                        return True
                elif ans and ans.lower().startswith("n"):
                    logging.info(
                        "Open file: User chose NOT to save current changes. Discarding them."
                    )
                    self.modified = False
                else:
                    if (
                        not status_changed_by_interaction
                        and self.status_message == original_status
                    ):
                        self._set_status_message(
                            "Open file cancelled by user at save prompt."
                        )
                    logging.debug(
                        "Open file cancelled by user at 'save changes' prompt."
                    )
                    return (
                        self.status_message != original_status
                        or status_changed_by_interaction
                    )

            # Determine the filename to open
            actual_filename_to_open = filename_to_open
            if not actual_filename_to_open:
                status_before_open_prompt = self.status_message
                actual_filename_to_open = self.prompt("Enter file name to open: ")
                if self.status_message != status_before_open_prompt:
                    status_changed_by_interaction = True

            if not actual_filename_to_open:
                if (
                    not status_changed_by_interaction
                    and self.status_message == original_status
                ):
                    self._set_status_message(
                        "Open file cancelled: no filename provided."
                    )
                logging.debug("Open file cancelled: no filename provided by user.")
                return (
                    self.status_message != original_status
                    or status_changed_by_interaction
                )

            if not os.path.exists(actual_filename_to_open):
                self.text = [""]
                self.filename = None
                self.modified = False
                self.encoding = "utf-8"
                self.history.clear()
                self.history.add_action(
                    {
                        "type": "open_file_missing",
                        "attempted_path": actual_filename_to_open,
                        "content": [""],
                        "encoding": "utf-8",
                    }
                )
                self.set_initial_cursor_position()
                self._set_status_message(
                    f"Error: File not found '{os.path.basename(actual_filename_to_open)}'"
                )
                logging.warning(
                    f"Open file failed: file not found at '{actual_filename_to_open}'"
                )
                return True

            if os.path.isdir(actual_filename_to_open):
                self._set_status_message(
                    f"Error: '{os.path.basename(actual_filename_to_open)}' is a directory."
                )
                logging.warning(
                    f"Open file failed: path '{actual_filename_to_open}' is a directory."
                )
                return True

            if not os.access(actual_filename_to_open, os.R_OK):
                self._set_status_message(
                    f"Error: No read permissions for '{os.path.basename(actual_filename_to_open)}'."
                )
                logging.warning(
                    f"Open file failed: no read permissions for '{actual_filename_to_open}'."
                )
                return True

            # 4. Detect file encoding and read content
            lines: Optional[list[str]] = None
            final_encoding_used: str = "utf-8"  # Default if all else fails

            try:
                sample_size_for_chardet = 1024 * 20
                raw_data_sample: bytes
                with self.safe_open(actual_filename_to_open, mode="rb") as f_binary:
                    raw_data_sample = f_binary.read(sample_size_for_chardet)

                if not raw_data_sample:
                    logging.info(
                        f"File '{actual_filename_to_open}' is empty or could not be read for chardet."
                    )
                    lines = [""]
                    final_encoding_used = self.encoding
                else:
                    chardet_result = chardet.detect(raw_data_sample)
                    encoding_guess = chardet_result.get("encoding")
                    confidence = chardet_result.get("confidence", 0.0)
                    logging.debug(
                        f"Chardet detected encoding '{encoding_guess}' with confidence {confidence:.2f} "
                        f"for '{actual_filename_to_open}'."
                    )

                    encodings_to_try_ordered: list[tuple[Optional[str], str]] = []
                    if encoding_guess and confidence >= 0.75:
                        encodings_to_try_ordered.append((encoding_guess, "strict"))

                    # Add common fallbacks, ensuring UTF-8 is prominent
                    common_fallbacks = [("utf-8", "strict"), ("latin-1", "strict")]
                    if (
                        encoding_guess
                        and (encoding_guess, "replace") not in encodings_to_try_ordered
                    ):
                        # Try detected encoding with 'replace' if strict fails for it or if confidence was low
                        if not (encoding_guess and confidence >= 0.75):
                            encodings_to_try_ordered.append((encoding_guess, "replace"))

                    for enc_fb, err_fb in common_fallbacks:
                        if (enc_fb, err_fb) not in encodings_to_try_ordered:
                            encodings_to_try_ordered.append((enc_fb, err_fb))

                    # Final absolute fallback
                    if ("utf-8", "replace") not in encodings_to_try_ordered:
                        encodings_to_try_ordered.append(("utf-8", "replace"))

                    seen_enc_err_pairs = set()
                    unique_encodings_to_try = []
                    for enc, err_handling in encodings_to_try_ordered:
                        if (
                            enc and (enc, err_handling) not in seen_enc_err_pairs
                        ):  # Ensure enc is not None
                            unique_encodings_to_try.append((enc, err_handling))
                            seen_enc_err_pairs.add((enc, err_handling))
                        elif (
                            not enc
                            and ("utf-8", err_handling) not in seen_enc_err_pairs
                        ):  # If chardet returns None for encoding
                            unique_encodings_to_try.append(
                                ("utf-8", err_handling)
                            )  # Default to utf-8
                            seen_enc_err_pairs.add(("utf-8", err_handling))

                    for enc_attempt, error_policy in unique_encodings_to_try:
                        try:
                            logging.debug(
                                f"Attempting to read '{actual_filename_to_open}' with encoding '{enc_attempt}' \
                                    (errors='{error_policy}')"
                            )
                            with self.safe_open(
                                actual_filename_to_open,
                                "r",
                                encoding=enc_attempt,
                                errors=error_policy,
                            ) as f_text:
                                lines = f_text.read().splitlines()
                            final_encoding_used = (
                                enc_attempt if enc_attempt else "utf-8"
                            )
                            logging.info(
                                f"Successfully read '{actual_filename_to_open}' using encoding '{final_encoding_used}' \
                                    with errors='{error_policy}'."
                            )
                            break
                        except (UnicodeDecodeError, OSError, LookupError) as e_read:
                            logging.warning(
                                f"Failed to read '{actual_filename_to_open}' with encoding '{enc_attempt}' \
                                    (errors='{error_policy}'): {e_read}"
                            )

                if lines is None:
                    self._set_status_message(
                        f"Error reading '{os.path.basename(actual_filename_to_open)}': Could not decode content."
                    )
                    logging.error(
                        f"All attempts to read and decode '{actual_filename_to_open}' failed."
                    )
                    return True

            except Exception as e_detect_read:
                self._set_status_message(
                    f"Error during file processing for '{os.path.basename(actual_filename_to_open)}': {e_detect_read}"
                )
                logging.exception(
                    f"Failed during encoding detection or initial read for '{actual_filename_to_open}'"
                )
                return True

            self.text = lines if lines is not None else [""]
            self.filename = actual_filename_to_open
            self.modified = False
            self.encoding = final_encoding_used

            self.set_initial_cursor_position()
            self.history.clear()
            self._ensure_trailing_newline()
            self._set_status_message(
                f"Opened '{os.path.basename(self.filename)}' (enc: {self.encoding}, {len(self.text)} lines)"
            )
            logging.info(
                f"File opened successfully: '{self.filename}', Encoding: {self.encoding}, Lines: {len(self.text)}"
            )

            self._lexer = None
            self.detect_language()
            if self.git:
                self.git.update_git_info()
            self._force_full_redraw = True
            return True

        except Exception as e_outer:
            self._set_status_message(f"Error opening file: {str(e_outer)[:70]}...")
            logging.exception(
                f"Unexpected error during open_file process for: {filename_to_open}"
            )
            # Attempt to restore some semblance of original state if open failed badly
            self.filename = original_filename_for_revert
            self.text = list(original_text_tuple_for_revert)
            self.modified = original_modified_flag_for_revert
            # Could also try to restore lexer, cursor, scroll but it gets complex.
            # A full redraw with the error message is the main goal.
            return True

    # --- save file ------------------
    def save_file(self) -> bool:
        """Saves the current document to its existing filename.
        If the filename is not set (e.g., for a new, unsaved buffer),
        this method invokes `save_file_as()` to prompt the user for a name.
        Updates editor state (modified status, potentially Git info, language detection).

        Returns:
            bool: True if the operation resulted in a change to the editor's state
                  (e.g., modified status changed, status message updated, or if
                  `save_file_as` was called and made changes), False otherwise.
        """
        logging.debug("save_file called")

        # Store initial state for comparison
        original_status = self.status_message
        original_modified_flag = self.modified
        # Filename should not change in a direct save, unless save_file_as is called
        original_filename = self.filename

        redraw_is_needed = False

        # If no filename is set, delegate to save_file_as()
        if not self.filename or self.filename == "noname":
            logging.debug("save_file: Filename not set, invoking save_file_as().")
            # save_file_as() returns True if it made changes requiring a redraw
            return self.save_file_as()

            # Validate existing filename and permissions (precautionary)
        # These checks are more critical for save_file_as, but good for robustness here too.
        if not self.validate_filename(self.filename):
            # validate_filename calls _set_status_message
            return True  # Status changed by validate_filename

        if os.path.isdir(self.filename):
            self._set_status_message(
                f"Cannot save: '{os.path.basename(self.filename)}' is a directory."
            )
            return True  # Status changed

        # Check for write permissions on the file itself if it exists,
        # or on its parent directory if it doesn't (though save usually implies it exists or can be created).
        target_path_exists = os.path.exists(self.filename)
        can_write = False
        if target_path_exists:
            if os.access(self.filename, os.W_OK):
                can_write = True
        else:  # File doesn't exist yet, check parent directory
            parent_dir = (
                os.path.dirname(self.filename) or "."
            )  # Use current dir if no path part
            if os.access(parent_dir, os.W_OK):
                can_write = True

        if not can_write:
            self._set_status_message(
                f"No write permissions for '{os.path.basename(self.filename)}' or its directory."
            )
            return True  # Status changed

        # Attempt to write the file to the existing path
        try:
            # _write_file is the low-level write operation.
            # It updates self.modified to False and calls detect_language/update_git_info.
            # It does not set a "Saved" status message itself.
            self._write_file(self.filename)

            # After successful _write_file:
            # self.filename is unchanged (unless _write_file unexpectedly changes it, which it shouldn't for 'save')
            # self.modified should be False

            self._set_status_message(f"Saved to {os.path.basename(self.filename)}")

            # Determine if a redraw is needed based on actual state changes
            if (
                self.modified != original_modified_flag  # Typically True -> False
                or self.status_message != original_status  # "Saved to..." is new
                or self.filename != original_filename
            ):  # Should not change here but check
                redraw_is_needed = True

            return redraw_is_needed

        except Exception as e_write:  # Catch errors specifically from _write_file
            self._set_status_message(
                f"Error saving file '{os.path.basename(self.filename)}': {str(e_write)[:60]}..."
            )
            logging.error(
                f"Failed to write file during Save '{self.filename}': {e_write}",
                exc_info=True,
            )
            # self.modified might remain True if save failed
            return True  # Status message changed due to error

    def save_file_as(self) -> bool:  # noqa: python:S3516
        """Saves the current document content to a new file name specified by the user.
        Handles prompts for the new filename and overwrite confirmation if the file exists.
        Updates editor state (filename, modified status, language detection, Git info).

        Returns:
            bool: True if the operation resulted in a change to the editor's state
                  (e.g., filename changed, modified status changed, status message updated,
                  or a redraw is needed due to prompt interactions), False otherwise
                  (e.g., if the operation was cancelled very early without any status change).
        """
        logging.debug("save_file_as called")

        # Store initial state for comparison to determine if a redraw is truly needed
        original_status = self.status_message
        original_filename = self.filename
        original_modified_flag = self.modified
        # Other states like cursor/scroll usually don't change directly from save_as,
        # but filename and modified status will.

        redraw_is_needed = False  # Accumulator for redraw reasons

        # Determine a default name for the prompt
        default_name_for_prompt = (
            self.filename
            if self.filename and self.filename != "noname"
            else self.config.get("editor", {}).get(
                "default_new_filename", "new_file.txt"
            )
        )

        # Prompt for the new filename
        status_before_filename_prompt = self.status_message
        new_filename_input = self.prompt(f"Save file as ({default_name_for_prompt}): ")
        if self.status_message != status_before_filename_prompt:
            redraw_is_needed = True  # Prompt interaction itself changed the status line

        if not new_filename_input:  # User cancelled (Esc or empty Enter)
            if (
                not redraw_is_needed and self.status_message == original_status
            ):  # Only set if prompt didn't change status
                self._set_status_message("Save as cancelled")
            return True  # Status changed by prompt or by this cancellation message

        # Use provided name or default if input was just whitespace
        new_filename_processed = new_filename_input.strip() or default_name_for_prompt

        # Validate the new filename
        if not self.validate_filename(new_filename_processed):
            # validate_filename already calls _set_status_message with error
            return True  # Status was changed by validate_filename

        if os.path.isdir(new_filename_processed):
            self._set_status_message(
                f"Cannot save: '{os.path.basename(new_filename_processed)}' is a directory."
            )
            return True  # Status changed

        # Handle existing file and permissions
        if os.path.exists(new_filename_processed):
            if not os.access(new_filename_processed, os.W_OK):
                self._set_status_message(
                    f"No write permissions for existing file: '{os.path.basename(new_filename_processed)}'"
                )
                return True  # Status changed

            status_before_overwrite_prompt = self.status_message
            overwrite_choice = self.prompt(
                f"File '{os.path.basename(new_filename_processed)}' already exists. Overwrite? (y/n): "
            )
            if self.status_message != status_before_overwrite_prompt:
                redraw_is_needed = True

            if not overwrite_choice or overwrite_choice.lower() != "y":
                if not redraw_is_needed and self.status_message == original_status:
                    self._set_status_message(
                        "Save as cancelled (file exists, not overwritten)."
                    )
                return True  # Status changed by prompt or cancellation
        else:
            # File does not exist, check if directory needs to be created
            target_dir = os.path.dirname(new_filename_processed)
            if target_dir and not os.path.exists(
                target_dir
            ):  # If target_dir is empty, it's the current dir
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    logging.info(f"Created missing directory for save as: {target_dir}")
                except Exception as e_mkdir:
                    self._set_status_message(
                        f"Cannot create directory '{target_dir}': {e_mkdir}"
                    )
                    logging.error(
                        f"Failed to create directory '{target_dir}': {e_mkdir}"
                    )
                    return True  # Status changed

            # Check write permissions for the target directory (or current if target_dir is empty)
            effective_target_dir = target_dir if target_dir else "."
            if not os.access(effective_target_dir, os.W_OK):
                self._set_status_message(
                    f"No write permissions for directory: '{effective_target_dir}'"
                )
                return True  # Status changed

        # Attempt to write the file
        try:
            # _write_file updates self.filename, self.modified, calls detect_language, update_git_info.
            # It does not set a status message itself, allowing this method to do so.
            self._write_file(new_filename_processed)

            # After successful _write_file:
            # self.filename is new_filename_processed
            # self.modified is False
            # self._lexer might have changed

            # toggle_auto_save might be called here if it's relevant after a save_as
            # If so, it might change status and redraw_is_needed should be True.
            # self.toggle_auto_save()

            self._set_status_message(
                f"Saved as {os.path.basename(new_filename_processed)}"
            )

            # Check if any key state changed that would require a redraw beyond just status.
            # Filename change is significant. Modified flag change is also significant.
            if (
                self.filename != original_filename
                or self.modified != original_modified_flag
                or self.status_message != original_status
            ):  # This will always be true due to set_status_message above
                redraw_is_needed = True

            return True  # Always true because status message is set and state changes.

        except Exception as e_write:  # Catch errors from _write_file
            self._set_status_message(
                f"Error saving file as '{os.path.basename(new_filename_processed)}': {str(e_write)[:60]}..."
            )
            logging.error(
                f"Failed to write file during Save As '{new_filename_processed}': {e_write}",
                exc_info=True,
            )
            # Restore original filename and modified status if save_as failed mid-way
            # (e.g., if _write_file partially updated them before failing)
            # This is tricky, _write_file should ideally be atomic or handle its own partial failure state.
            # For now, we assume if _write_file fails, self.filename might not have been updated yet.
            if (
                self.filename == new_filename_processed
            ):  # If _write_file updated filename before error
                self.filename = original_filename  # Try to revert
                self.modified = original_modified_flag  # Revert modified status
            return True  # Status message changed due to error

    # The _write_file method is a low-level operation designed to actually write
    # the contents of a file and update the associated editor state.
    def _write_file(self, target_filename: str) -> None:
        """Low-level method to write the current buffer content to the specified target file.
        This method updates the editor's internal state related to the file
        (filename, modified status, language detection, Git info).
        It does NOT set a user-facing status message like "File saved"; that's the
        caller's responsibility (e.g., save_file, save_file_as).

        Args:
            target_filename (str): The absolute or relative path to the file to write.

        Raises:
            Exception: Propagates exceptions that occur during file writing (e.g., IOError, OSError).
        """
        logging.debug(
            f"_write_file: Writing to '{target_filename}' with encoding '{self.encoding}'"
        )

        content_to_write = ""
        # Create a copy for safe modification
        lines_to_save = list(self.text)

        # If the last line is empty and the second-to-last is not, remove it for saving
        if len(lines_to_save) > 1 and not lines_to_save[-1] and lines_to_save[-2]:
            lines_to_save.pop()
        elif len(lines_to_save) == 1 and not lines_to_save[0]:
            # If the file contains only one empty line (our technical one)
            lines_to_save = []  # Save as an empty file
        content_to_write = os.linesep.join(lines_to_save)

        try:
            with self.safe_open(
                target_filename, "w", encoding=self.encoding, errors="replace"
            ) as f:
                text_f = cast(TextIO, f)
                text_f.write(content_to_write)
                if content_to_write:
                    text_f.write(os.linesep)

            logging.debug(f"Successfully wrote to '{target_filename}'")

            # Update editor state after successful write
            if self.filename != target_filename:
                self.filename = target_filename
                if self.git:
                    self.git.update_git_info()

            self.modified = False
            self.detect_language()

            # Update Git information as file state on disk has changed
            if self.git:
                self.git.update_git_info()

            # Update Git status cache for the file browser panel
            if self.git_panel_instance:
                logging.debug(
                    f"Updating Git status cache after saving {target_filename}"
                )
                self.git_panel_instance.update_file_status(target_filename)

            # Asynchronously run linter if the file is a Python file
            if self._lexer and self._lexer.name.lower() in ["python", "python3", "py"]:
                logging.debug(
                    f"_write_file: Python file saved, queueing async lint for '{target_filename}'"
                )
                threading.Thread(
                    target=self.run_lint_async,
                    args=(content_to_write,),
                    daemon=True,
                    name=f"LintThread-{os.path.basename(target_filename)}",
                ).start()

        except Exception as e:
            logging.error(
                f"Failed to write file '{target_filename}': {e}", exc_info=True
            )
            raise

    def revert_changes(self) -> bool:  # noqa: python:S3516
        """Reverts unsaved changes by reloading the content from the last(f"User confirmed.
        Attempting to revert changes for '{self.filename}' by reloading.")
        """
        logging.debug("revert_changes called")

        original_status = self.status_message
        original_modified_flag_for_comparison = self.modified

        redraw_is_needed_due_to_interaction = False

        if not self.filename or self.filename == "noname":
            self._set_status_message(
                "Cannot revert: file has not been saved yet (no filename)."
            )
            logging.debug(
                "Revert failed: current buffer is unnamed or has never been saved to disk."
            )
            return self.status_message != original_status

        if not os.path.exists(self.filename):
            self._set_status_message(
                f"Cannot revert: '{os.path.basename(self.filename)}' does not exist on disk."
            )
            logging.warning(f"Revert failed: File '{self.filename}' not found on disk.")
            return self.status_message != original_status

        if not self.modified:
            self._set_status_message(
                f"No unsaved changes to revert for '{os.path.basename(self.filename)}'."
            )
            logging.debug(
                f"Revert skipped: No modifications to revert for '{self.filename}'."
            )
            return self.status_message != original_status

        status_before_prompt = self.status_message
        confirmation = self.prompt(
            f"Revert all unsaved changes to '{os.path.basename(self.filename)}'? (y/n): "
        )

        if self.status_message != status_before_prompt:
            redraw_is_needed_due_to_interaction = True

        if not confirmation or confirmation.lower() != "y":
            if (
                not redraw_is_needed_due_to_interaction
                and self.status_message == original_status
            ):
                self._set_status_message("Revert cancelled by user.")
            logging.debug("Revert operation cancelled by user or prompt timeout.")
            return (
                self.status_message != original_status
                or redraw_is_needed_due_to_interaction
            )

        logging.info(
            f"User confirmed. Attempting to revert changes for '{self.filename}' by reloading."
        )
        self.modified = False

        try:
            reloaded_successfully = self.open_file(self.filename)

            if reloaded_successfully:
                if not self.modified:
                    self._set_status_message(
                        f"Successfully reverted to saved version of '{os.path.basename(self.filename)}'."
                    )
                    logging.info(
                        f"Changes for '{self.filename}' reverted successfully."
                    )
                else:
                    self._set_status_message(
                        f"Reverted '{os.path.basename(self.filename)}', but file still marked modified."
                    )
                    logging.warning(
                        f"Reverted '{self.filename}', but it's still marked as modified post-open."
                    )
                return True
            self.modified = original_modified_flag_for_comparison
            logging.warning(
                f"Revert: self.open_file call for '{self.filename}' returned False. Status: {self.status_message}"
            )
            return (
                self.status_message != original_status
                or redraw_is_needed_due_to_interaction
            )

        except Exception as e:
            self._set_status_message(
                f"Error during revert operation for '{os.path.basename(self.filename)}': {str(e)[:70]}..."
            )
            logging.exception(
                f"Unexpected error during revert process for file: {self.filename}"
            )
            self.modified = original_modified_flag_for_comparison
            return True

    # -------------- Auto-save ------------------------------
    def toggle_auto_save(self) -> bool:
        """Toggles the auto-save feature on or off.
        The auto-save interval (in minutes) is read from `self.config` or defaults.
        Auto-save only occurs if a filename is set and there are modifications (`self.modified`).
        A background thread handles the periodic saving.

        This method itself primarily manages the `_auto_save_enabled` flag and the
        auto-save thread. It always sets a status message indicating the new state
        of auto-save, thus it usually implies a redraw is needed.

        Returns:
            bool: True, as this action always changes the status message to reflect
                  the new auto-save state, requiring a status bar update.
        """
        logging.debug(
            f"toggle_auto_save called. Current auto_save_enabled: {getattr(self, '_auto_save_enabled', False)}"
        )
        original_status = self.status_message

        # Ensure attributes exist (usually set in __init__)
        if not hasattr(self, "_auto_save_enabled"):
            self._auto_save_enabled = False
        if not hasattr(
            self, "_auto_save_thread"
        ):  # Thread object for the auto-save task
            self._auto_save_thread = None
        if not hasattr(self, "_auto_save_stop_event"):  # Event to signal thread to stop
            self._auto_save_stop_event = threading.Event()

        # Get the auto-save interval from config, defaulting if not found or invalid
        try:
            # Ensure interval is a positive number, representing minutes
            interval_minutes = float(
                self.config.get("settings", {}).get("auto_save_interval", 1.0)
            )  # Default 1 min
            if interval_minutes <= 0:
                logging.warning(
                    f"Invalid auto_save_interval ({interval_minutes} min) in config, defaulting to 1 min."
                )
                interval_minutes = 1.0
        except (ValueError, TypeError):
            logging.warning(
                "Could not parse auto_save_interval from config, defaulting to 1 min."
            )
            interval_minutes = 1.0

        self._auto_save_interval = (
            interval_minutes  # Store the current interval in minutes
        )

        # Toggle the auto-save state
        self._auto_save_enabled = not self._auto_save_enabled

        if self._auto_save_enabled:
            # Auto-save is being enabled
            self._auto_save_stop_event.clear()  # Clear the stop signal for the new thread

            # Start the auto-save thread if it's not already running or if it died
            if self._auto_save_thread is None or not self._auto_save_thread.is_alive():

                def auto_save_task_runner() -> None:
                    """The actual task performed by the auto-save thread."""
                    logging.info(
                        f"Auto-save thread started. Interval: {self._auto_save_interval} min."
                    )
                    last_saved_text_hash = (
                        None  # Store hash of last saved content to detect changes
                    )

                    while (
                        not self._auto_save_stop_event.is_set()
                    ):  # Loop until stop event is set
                        try:
                            # Wait for the specified interval or until stop event is set
                            # Convert interval from minutes to seconds for time.sleep
                            sleep_duration_seconds = max(
                                1, int(self._auto_save_interval * 60)
                            )

                            # Wait in smaller chunks to be more responsive to stop_event
                            interrupted = self._auto_save_stop_event.wait(
                                timeout=sleep_duration_seconds
                            )
                            if interrupted:  # Stop event was set
                                logging.info(
                                    "Auto-save thread received stop signal during wait."
                                )
                                break

                                # Check again after sleep, in case state changed while sleeping
                            if (
                                not self._auto_save_enabled
                                or self._auto_save_stop_event.is_set()
                            ):
                                break

                            # Conditions for auto-saving:
                            # - Filename must be set (i.e., not a new, unsaved buffer)
                            # - Document must be modified
                            if not self.filename or self.filename == "noname":
                                logging.debug("Auto-save: Skipped, no filename set.")
                                continue

                            # Acquire lock to safely read self.text and self.modified
                            with self._state_lock:
                                if not self.modified:
                                    logging.debug(
                                        "Auto-save: Skipped, no modifications."
                                    )
                                    continue

                                # Get current text and its hash
                                current_text_content = os.linesep.join(self.text)
                                current_text_hash = hash(current_text_content)

                                # Only save if content has actually changed since last auto-save
                                if current_text_hash == last_saved_text_hash:
                                    logging.debug(
                                        "Auto-save: Skipped, content unchanged since last auto-save."
                                    )
                                    continue

                                # File is named, modified, and content has changed
                                temp_filename = (
                                    self.filename
                                )  # Store before releasing lock for write
                                temp_encoding = self.encoding
                                temp_text_to_save = current_text_content
                                _temp_modified_flag_before_save = self.modified

                            # Perform file writing outside the main state lock if possible,
                            # though _write_file might acquire it again internally if it modifies shared state
                            # like self.modified. For simplicity here, direct write.
                            try:
                                logging.info(f"Auto-saving '{temp_filename}'...")
                                # Use safe_open directly or call a simplified _write_file_content
                                with self.safe_open(
                                    temp_filename,
                                    "w",
                                    encoding=temp_encoding,
                                    errors="replace",
                                ) as f:
                                    text_f = cast(TextIO, f)
                                    text_f.write(temp_text_to_save)

                                # Update state after successful save
                                with self._state_lock:
                                    # Verify that the file saved is still the current one and text hasn't changed
                                    # during the write operation (unlikely for this simple model).
                                    if (
                                        self.filename == temp_filename
                                        and hash(os.linesep.join(self.text))
                                        == current_text_hash
                                    ):
                                        self.modified = (
                                            False  # Mark as no longer modified
                                        )
                                        last_saved_text_hash = current_text_hash  # Update hash of saved content
                                        self._set_status_message(
                                            f"Auto-saved: {os.path.basename(temp_filename)}"
                                        )
                                        logging.info(
                                            f"Auto-saved '{temp_filename}' successfully."
                                        )
                                    else:
                                        logging.warning(
                                            f"Auto-save: File context changed during write of '{temp_filename}'. Save may be stale."
                                        )
                                        # Don't change modified flag or last_saved_text_hash if context changed.

                            except Exception as e_write:
                                self._set_status_message(
                                    f"Auto-save error for '{temp_filename}': {e_write}"
                                )
                                logging.exception(
                                    f"Auto-save failed for '{temp_filename}'"
                                )
                                # Consider if _auto_save_enabled should be set to False on error

                        except Exception as e_thread_loop:
                            # Catch any other unexpected errors within the thread's loop
                            logging.exception(
                                f"Unexpected error in auto-save thread loop: {e_thread_loop}"
                            )
                            # Potentially disable auto-save to prevent repeated errors
                            self._auto_save_enabled = False
                            self._auto_save_stop_event.set()  # Signal thread to terminate
                            self._set_status_message(
                                "Auto-save disabled due to an internal error."
                            )
                            break  # Exit the loop

                    logging.info("Auto-save thread finished.")

                # Create and start the daemon thread for auto-saving
                self._auto_save_thread = threading.Thread(
                    target=auto_save_task_runner,
                    daemon=True,  # Thread will exit when the main program exits
                    name="AutoSaveThread",
                )
                self._auto_save_thread.start()

            # Set status message to indicate auto-save is now enabled
            self._set_status_message(
                f"Auto-save enabled (every {self._auto_save_interval:.1f} min)"
            )
            logging.info(
                f"Auto-save feature has been enabled. Interval: {self._auto_save_interval:.1f} minutes."
            )
        else:
            # Auto-save is being disabled
            if self._auto_save_thread and self._auto_save_thread.is_alive():
                logging.debug("toggle_auto_save: Signaling auto-save thread to stop.")
                self._auto_save_stop_event.set()  # Signal the thread to stop
                # Optionally, wait for the thread to finish with a timeout
                # self._auto_save_thread.join(timeout=2.0)
                # if self._auto_save_thread.is_alive():
                #    logging.warning("Auto-save thread did not stop in time.")
            self._auto_save_thread = None  # Discard thread object

            self._set_status_message("Auto-save disabled")
            logging.info("Auto-save feature has been disabled.")

        # This method always changes the status message, so a redraw is needed.
        return (
            self.status_message != original_status or True
        )  # Force True because state change is significant

    # ------- New File ---------
    def new_file(self) -> bool:
        """Creates a new, empty buffer, prompting to save unsaved changes first.

        This high-level method orchestrates the entire process of creating a new
        document. It ensures a safe workflow by handling unsaved changes before
        resetting the editor's state. The core logic is decomposed into helper
        methods for clarity and maintainability.

        The process is as follows:
        1.  Handle Unsaved Changes (`_handle_unsaved_changes_before_new_file`):
            - If the current buffer has no modifications, this step is skipped.
            - If there are unsaved changes, it prompts the user with a "Save changes?"
              dialog (y/n/cancel).
            - If the user chooses to save, it calls `self.save_file()`. If saving
              fails, the entire `new_file` operation is aborted.
            - If the user chooses not to save, the changes are discarded.
            - If the user cancels the prompt, the operation is aborted.
            - This helper method returns a boolean indicating whether to proceed.

        2.  Reset Editor State (`_reset_state_for_new_file`): If the previous
            step allows proceeding, this method performs a complete reset of the
            editor's state to a clean slate:
            - The text buffer is cleared (`self.text = [""]`).
            - `filename`, `encoding`, and `modified` status are reset.
            - The syntax lexer (`self._lexer`) and Git state (`self.git`) are reset.
            - The cursor, scroll, selection, and undo/redo history are cleared by
              calling `set_initial_cursor_position()` and `history.clear()`.
            - Auto-save is disabled for the new, untitled buffer.
            - A "New file created" message is set in the status bar.
            - A full screen redraw is forced.

        Returns:
            bool: True, as this operation always results in a significant UI change
                  (either a state reset or a status message update), requiring a redraw.
        """
        logging.debug("new_file called")

        # Step 1: Handle unsaved changes.
        # The helper method returns True to proceed, False to abort.
        can_proceed = self._handle_unsaved_changes_before_new_file()
        # Step 2: If we can proceed, reset the editor state for a new file.
        if can_proceed:
            self._reset_state_for_new_file()
        # This action, whether it completes or is cancelled by the user,
        # always results in a status message change, requiring a redraw.
        return True

    def _handle_unsaved_changes_before_new_file(self) -> bool:
        """If the current buffer is modified, prompts the user to save.

        Returns:
            bool: True if the `new_file` operation should proceed, False if it should be cancelled.
        """
        if not self.modified:
            return True  # No changes to handle, proceed.

        ans = self.prompt("Save changes before creating new file? (y/n): ")

        if ans and ans.lower().startswith("y"):
            self.save_file()
            if self.modified:  # If saving failed or was cancelled
                self._set_status_message(
                    "New file creation cancelled: unsaved changes were not saved."
                )
                return False  # Cancel the operation
        elif not (ans and ans.lower().startswith("n")):
            # User cancelled the prompt (pressed Esc, etc.)
            self._set_status_message("New file creation cancelled.")
            return False  # Cancel the operation
        # If user pressed 'n', we just proceed, changes will be discarded.
        return True

    def _reset_state_for_new_file(self) -> None:
        """Resets all relevant editor state for a new, empty buffer."""
        logging.debug("Proceeding to reset editor state for a new file.")

        self.text = [""]
        self.filename = None
        self.encoding = "UTF-8"
        self.modified = False
        self._lexer = None

        if self.git:
            self.git.reset_state()

        self.set_initial_cursor_position()
        self.history.clear()
        self.history.add_action(
            {
                "type": "new_file",
                "content": [""],
                "encoding": "UTF-8",
            }
        )

        if self._auto_save_enabled:
            self._auto_save_enabled = False
            logging.debug("Auto-save disabled for new untitled file.")

        self.detect_language()
        self._set_status_message("New file created")
        self._force_full_redraw = True

    # ---- Cancel operation -----
    def cancel_operation(self) -> bool:
        """Handles cancellation of specific ongoing states like an active lint panel,
        text selection, or search highlighting.
        Sets an appropriate status message if an operation was cancelled.

        Returns:
            bool: True if any specific state (lint panel visibility, selection active,
                  search highlights present) was actively cancelled AND the status message
                  was consequently updated. False if no such specific state was active to be
                  cancelled by this method call.
        """
        logging.debug(
            f"cancel_operation called. Panel: {self.lint_panel_active}, "
            f"Selecting: {self.is_selecting}, Highlights: {bool(self.highlighted_matches)}"
        )

        original_status = self.status_message
        action_cancelled_a_specific_state = False

        if self.lint_panel_active:
            self.lint_panel_active = False
            self.lint_panel_message = (
                ""  # Clear the message when panel is explicitly closed
            )
            self._set_status_message("Lint panel closed")
            logging.debug("cancel_operation: Lint panel closed.")
            action_cancelled_a_specific_state = True
        elif self.is_selecting:
            self.is_selecting = False
            self.selection_start = None
            self.selection_end = None
            self._set_status_message("Selection cancelled")
            logging.debug("cancel_operation: Selection cancelled.")
            action_cancelled_a_specific_state = True
        elif self.highlighted_matches:
            self.highlighted_matches = []

            self._set_status_message("Search highlighting cleared")
            logging.debug("cancel_operation: Search highlighting cleared.")
            action_cancelled_a_specific_state = True

        # Returns True if a specific state was cancelled AND status message changed as a result.
        # If only status changes without a specific state change (e.g. from "Ready" to "Nothing to cancel"),
        # that will be caught by the caller (handle_escape) if needed.
        # This method focuses on *cancelling an operation*.
        if action_cancelled_a_specific_state:
            logging.debug(
                f"Status changed from '{original_status}' to '{self.status_message}'"
            )
        return action_cancelled_a_specific_state

    def handle_escape(self) -> bool:
        """Handles the Esc key press.
        Primarily attempts to cancel active states (lint panel, selection, search highlights)
        by calling self.cancel_operation().
        If no specific operation was cancelled, it may set a generic "Nothing to cancel" message
        or do nothing if a more relevant status is already present.

        The timestamp logic for double-press exit is removed from this version
        to align with standard Esc behavior (cancel only, no exit).

        Returns:
            bool: True if any state relevant for redraw changed (panel visibility, selection,
                  highlights, or status message), False otherwise.
        """
        original_status = (
            self.status_message
        )  # To check if status message actually changes
        action_taken_requiring_redraw = False

        logging.debug("handle_escape called.")

        # Attempt to cancel any ongoing specific operation.
        # cancel_operation() returns True if it cancelled something and set a status.
        if self.cancel_operation():
            action_taken_requiring_redraw = True
            logging.debug(
                "handle_escape: cancel_operation handled the Esc press and indicated a change."
            )
        else:
            # cancel_operation() returned False, meaning no specific panel, selection,
            # or highlight was active to be cancelled by it.
            # In this case, a single Esc press with no active operation
            # should typically do nothing or, at most, clear a transient status message.
            # We will set a "Nothing to cancel" message only if no other important message is present.
            if (
                self.status_message == original_status
                or self.status_message == "Ready"
                or not self.status_message
            ):
                # If status was default or unchanged by cancel_operation (which it shouldn't be if it returned false),
                # then set a "nothing to cancel" message.
                # We could also choose to do absolutely nothing visually if there's nothing to cancel.
                # For now, let's set a message.
                self._set_status_message(
                    "Nothing to cancel"
                )  # Or simply don't change status
                if self.status_message != original_status:
                    action_taken_requiring_redraw = True
            # Some other status message was already present (e.g. an error), leave it.
            # Redraw might still be needed if that status is new compared to before handle_escape.
            elif self.status_message != original_status:
                action_taken_requiring_redraw = True

            logging.debug(
                "handle_escape: No specific operation to cancel. Status might be updated."
            )

        # The _last_esc_time attribute is no longer needed for double-press exit logic here.
        # If you still want to track it for other purposes, it can be updated:
        # setattr(self, "_last_esc_time", time.monotonic())

        return action_taken_requiring_redraw

    def _ensure_trailing_newline(self) -> None:
        """Ensures that there is always one blank line at the end of the buffer.
        This is necessary to correctly select the last line.
        """
        if (
            not self.text or self.text[-1]
        ):  # If the list is empty or the last line is not empty
            self.text.append("")

    # ------------------ Prompting for Input ------------------
    def prompt(
        self,
        message: str,
        initial: str = "",
        is_yes_no_prompt: bool = False,
        max_len: int = 1024,
        timeout_seconds: int = 60,
    ) -> Optional[str]:  # noqa: python:S3516
        """Displays a single-line input prompt, taking full control of the screen."""
        logging.debug(f"Prompt called. Message: '{message}', Initial: '{initial}'")

        original_cursor_visibility = curses.curs_set(1)

        # Setting up blocking mode with a timeout
        self.stdscr.nodelay(False)
        self.stdscr.timeout(timeout_seconds * 1000 if timeout_seconds > 0 else -1)

        input_buffer = list(initial)
        cursor_pos = len(input_buffer)

        try:
            while True:
                h, w = self.stdscr.getmaxyx()
                prompt_y = h - 1

                # --- Drawing the prompt line ---
                # Forming the full line for output
                prompt_line = f"{message}{''.join(input_buffer)}"

                # Clearing the line and outputting
                self.stdscr.move(prompt_y, 0)
                self.stdscr.clrtoeol()
                self.stdscr.addstr(
                    prompt_y, 0, prompt_line, self.colors.get("status", curses.A_NORMAL)
                )

                # Setting the cursor
                self.stdscr.move(prompt_y, len(message) + cursor_pos)
                self.stdscr.refresh()  # Refresh the screen immediately

                try:
                    key = self.stdscr.getch()
                except curses.error:  # Timeout
                    return None

                if key == curses.KEY_ENTER or key in (10, 13):
                    return "".join(input_buffer).strip()
                if key == 27:  # ESC
                    return None
                if key in (curses.KEY_BACKSPACE, 127, 8):
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        input_buffer.pop(cursor_pos)
                elif key == curses.KEY_LEFT:
                    cursor_pos = max(0, cursor_pos - 1)
                elif key == curses.KEY_RIGHT:
                    cursor_pos = min(len(input_buffer), cursor_pos + 1)
                elif 32 <= key < 256:  # Printable characters
                    char = chr(key)
                    if is_yes_no_prompt:
                        if char.lower() in ("y", "n"):
                            return char.lower()
                    elif len(input_buffer) < max_len:
                        input_buffer.insert(cursor_pos, char)
                        cursor_pos += 1
        finally:
            # Restoring non-blocking mode and cursor visibility
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)  # Returning timeout for the main loop
            curses.curs_set(original_cursor_visibility)

            # Requesting a full redraw after exiting the prompt,
            # to erase its traces and restore the editor's appearance.
            self._force_full_redraw = True

    # 2 ========== Search/Replace and Find ======================
    def search_and_replace(self) -> bool:  # noqa: python:S3516
        """Searches for text using a regular expression and replaces occurrences.
        Prompts for search pattern and replacement text.
        This operation is not added to the undo/redo history; instead, the history is cleared.
        Returns True if any interaction (prompts, status change) or modification occurred,
        indicating a redraw is needed.
        """
        logging.debug("search_and_replace called")

        original_status = self.status_message
        status_changed_by_prompts = (
            False  # Track if prompts themselves alter final status view
        )
        # Clear previous search state immediately
        self.highlighted_matches = []
        self.search_matches = []
        self.search_term = ""  # Clear the term so F3 won't use the old one
        self.current_match_idx = -1
        # Initial redraw might be good here if clearing highlights should be immediate
        # but we'll rely on the return value for the main loop.

        # Prompt for search pattern
        status_before_search_prompt = self.status_message
        search_pattern_str = self.prompt("Search for (regex): ")
        if self.status_message != status_before_search_prompt:
            status_changed_by_prompts = True

        if not search_pattern_str:  # User cancelled (Esc or empty Enter)
            if not status_changed_by_prompts and self.status_message == original_status:
                self._set_status_message("Search/Replace cancelled")
            # Return True if status changed by prompt or by cancellation message
            return self.status_message != original_status

            # Prompt for replacement string
        # An empty replacement string is valid (means delete the matched pattern).
        status_before_replace_prompt = self.status_message
        replace_with_str = self.prompt(
            "Replace with: "
        )  # `prompt` can return None if cancelled
        if self.status_message != status_before_replace_prompt:
            status_changed_by_prompts = True

        if replace_with_str is None:  # User cancelled the replacement prompt
            if not status_changed_by_prompts and self.status_message == original_status:
                self._set_status_message(
                    "Search/Replace cancelled (no replacement text)"
                )
            return self.status_message != original_status

        # Compile the regex pattern
        compiled_regex_pattern: Optional[re.Pattern] = None
        try:
            # re.IGNORECASE is a common default, can be made configurable
            compiled_regex_pattern = re.compile(search_pattern_str, re.IGNORECASE)
            logging.debug(
                f"Compiled regex pattern: '{search_pattern_str}' with IGNORECASE"
            )
        except re.error as e:
            error_msg = f"Regex error: {str(e)[:70]}"
            self._set_status_message(error_msg)
            logging.warning(f"Search/Replace failed due to regex error: {e}")
            return True  # Status changed due to error message

        # --- Perform replacement ---
        new_text_lines: list[str] = []
        total_replacements_count = 0
        line_processing_error_occurred = False

        # It's safer to operate on a copy if iterating and modifying
        # or build a new list directly as done here.
        # Lock is needed for reading self.text if it could be modified by another thread,
        # but here we are in the main thread of action.

        with self._state_lock:  # Access self.text safely
            current_text_snapshot = list(self.text)  # Work on a snapshot

        for line_idx, current_line in enumerate(current_text_snapshot):
            try:
                # Perform substitution on the current line
                # subn returns a tuple: (new_string, number_of_subs_made)
                new_line_content, num_subs_on_line = compiled_regex_pattern.subn(
                    replace_with_str, current_line
                )
                new_text_lines.append(new_line_content)
                if num_subs_on_line > 0:
                    total_replacements_count += num_subs_on_line
            except Exception as e_sub:  # Catch errors during re.subn (e.g., complex regex on specific line)
                logging.error(
                    f"Error replacing in line {line_idx + 1} ('{current_line[:50]}...'): {e_sub}"
                )
                new_text_lines.append(
                    current_line
                )  # Append original line in case of error on this line
                line_processing_error_occurred = True

        # --- Update editor state if replacements were made or errors occurred ---
        if total_replacements_count > 0 or line_processing_error_occurred:
            with self._state_lock:
                self.text = new_text_lines
                self.modified = True  # Document has been modified
                # Search and Replace is a major change, typically clears undo/redo history
                self.history.clear()
                self.history.add_action(
                    {"type": "bulk_replace", "replacements": total_replacements_count}
                )
                logging.debug("Cleared undo/redo history after search/replace.")
                # Cursor position might be invalidated, reset to start of document or last known good pos.
                # For simplicity, let's move to the beginning of the file.
                self.cursor_y = 0
                self.cursor_x = 0
                self._ensure_cursor_in_bounds()  # Ensure it's valid
                self._clamp_scroll()  # Adjust scroll

            if line_processing_error_occurred:
                self._set_status_message(
                    f"Replaced {total_replacements_count} occurrences with errors on some lines."
                )
                logging.warning("Search/Replace completed with errors on some lines.")
            else:
                self._set_status_message(
                    f"Replaced {total_replacements_count} occurrence(s)."
                )
                logging.info(
                    f"Search/Replace successful: {total_replacements_count} replacements."
                )
            return True  # Text changed, status changed, cursor moved
        # No replacements made and no errors
        self._set_status_message("No occurrences found to replace.")
        logging.info("Search/Replace: No occurrences found.")
        return True  # Status message changed

        # Fallback, should not be reached if logic is complete
        # return status_changed_by_prompts

    def _collect_matches(self, term: str) -> list[tuple[int, int, int]]:
        """Finds all occurrences of `term` (case-insensitive) in `self.text`.
        Uses a state lock for safe access to `self.text`.

        Args:
            term (str): The search term.

        Returns:
            List[Tuple[int, int, int]]: A list of tuples, where each tuple is
                                         (row_index, column_start_index, column_end_index)
                                         for a match.
        """
        matches: list[tuple[int, int, int]] = []
        if not term:  # If the search term is empty, no matches can be found.
            return matches

        # Perform a case-insensitive search
        search_term_lower = term.lower()
        term_length = len(term)  # Original term length for calculating end index

        # Use a lock only for accessing self.text to get a snapshot.
        # This minimizes the time the lock is held.
        text_snapshot: list[str]
        with self._state_lock:
            # Create a shallow copy of the list of lines.
            # The strings themselves are immutable, so this is safe.
            text_snapshot = list(self.text)

            # Perform the search on the snapshot without holding the lock for the entire loop.
        for row_index, line_content in enumerate(text_snapshot):
            current_search_start_column = 0
            line_content_lower = (
                line_content.lower()
            )  # Compare against the lowercased version of the line

            while True:
                # Find the next occurrence in line_content_lower,
                # but record indices based on the original line_content.
                found_at_index = line_content_lower.find(
                    search_term_lower, current_search_start_column
                )

                if found_at_index == -1:  # No more matches in this line
                    break

                match_end_index = found_at_index + term_length  # End index is exclusive
                matches.append((row_index, found_at_index, match_end_index))

                # Advance the search position to after the current match to find subsequent matches.
                # If term_length is 0 (empty search term, though handled above),
                # this prevents an infinite loop by advancing by at least first step
                current_search_start_column = (
                    match_end_index if term_length > 0 else found_at_index + 1
                )

        if matches:
            logging.debug(
                f"Found {len(matches)} match(es) for search term '{term}'. First match at: {matches[0]}"
            )
        else:
            logging.debug(f"No matches found for search term '{term}'.")

        return matches

    def find_prompt(self) -> bool:
        """Prompts the user for a search term, collects all matches,
        updates highlights, and navigates to the first match if found.
        Clears any previous search state before starting a new search.

        Returns:
            bool: True if the editor's visual state (cursor, scroll, highlights, status)
                  changed as a result of the find operation or user interaction
                  with the prompt, False otherwise (though unlikely for this method).
        """
        logging.debug("find_prompt called")

        # Store initial state to compare against for determining if a redraw is needed.
        original_status = self.status_message
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        # Highlights will be cleared, so that's always a potential change.

        # Clear previous search state and highlights.
        # This is a visual change if there were previous highlights.
        had_previous_highlights = bool(self.highlighted_matches)
        self.highlighted_matches = []
        self.search_matches = []
        self.search_term = ""  # Reset search term for a new search
        self.current_match_idx = -1

        redraw_needed_due_to_clearing = (
            had_previous_highlights  # If highlights were cleared, redraw
        )

        # Prompt for the search term.
        # The prompt itself temporarily changes the status bar.
        status_before_prompt = (
            self.status_message
        )  # Could have been changed if highlights were cleared and status set

        # Prompting the user for input
        term_to_search = self.prompt(
            "Find: "
        )  # self.prompt handles its own status line updates during input

        # Check if status message was altered by the prompt itself (e.g., timeout, or internal prompt messages)
        # or if it was restored to its state before the prompt.
        status_changed_by_prompt_interaction = (
            self.status_message != status_before_prompt
        )

        if (
            not term_to_search
        ):  # User cancelled the prompt (e.g., Esc) or entered nothing
            # If status after prompt is same as original status (before clearing highlights and prompt),
            # but user cancelled, set "Search cancelled".
            if (
                not status_changed_by_prompt_interaction
                and self.status_message == original_status
            ):
                self._set_status_message("Search cancelled")
            # A redraw is needed if highlights were cleared, or if status message changed.
            return redraw_needed_due_to_clearing or (
                self.status_message != original_status
            )

        # A search term was entered.
        self.search_term = term_to_search  # Store the new search term

        # Collect all matches for the new term.
        # _collect_matches reads self.text, so no direct visual change from this call itself.
        self.search_matches = self._collect_matches(self.search_term)

        # Update highlights to show the new matches.
        # This is a visual change if new matches are found or if previous highlights are now gone.
        self.highlighted_matches = list(
            self.search_matches
        )  # Make a copy for highlighting

        # Navigate and set status based on whether matches were found.
        if not self.search_matches:
            self._set_status_message(f"'{self.search_term}' not found")
            # Even if no matches, highlights were cleared/updated (to empty), so redraw likely.
            # And status message changed.
        else:
            self.current_match_idx = 0  # Go to the first match
            # _goto_match will update cursor_y, cursor_x, scroll_top, scroll_left
            self._goto_match(self.current_match_idx)
            self._set_status_message(
                f"Found {len(self.search_matches)} match(es) for '{self.search_term}'. Press F3 for next."
            )

        # Determine if overall state change warrants a redraw.
        # Changes could be: highlights changed, cursor/scroll changed by _goto_match, status message changed.
        if (
            redraw_needed_due_to_clearing  # Highlights were cleared
            or bool(self.highlighted_matches)  # New highlights were added
            or (self.cursor_y, self.cursor_x) != original_cursor_pos
            or (self.scroll_top, self.scroll_left) != original_scroll_pos
            or self.status_message != original_status
        ):
            return True

        return False  # Should rarely be False, as status or highlights usually change.

    def find_next(self) -> bool:
        """Moves the cursor and view to the next search match in the current search results.
        If no search has been performed or no matches were found, it sets an appropriate status message.
        The list of highlighted matches (`self.highlighted_matches`) is not changed by this method;
        it's assumed to be managed by `find_prompt` or when the search term changes.

        Returns:
            bool: True if the cursor position, scroll, or status message changed, False otherwise.
        """
        original_status = self.status_message
        original_cursor_pos = (self.cursor_y, self.cursor_x)
        original_scroll_pos = (self.scroll_top, self.scroll_left)
        changed_state = False

        if not self.search_matches:
            # This means either no search was performed (self.search_term is empty)
            # or the last search yielded no results (self.search_term is set, but search_matches is empty).
            if not self.search_term:
                self._set_status_message(
                    "No search term. Use Find (e.g., Ctrl+F) first."
                )
            else:  # search_term exists, but no matches were found for it
                self._set_status_message(f"No matches found for '{self.search_term}'.")

            # Ensure no stale highlights if we reach here
            if (
                self.highlighted_matches
            ):  # If there were highlights from a previous successful search
                self.highlighted_matches = []
                changed_state = True  # Highlight state changed

            self.current_match_idx = -1  # Reset current match index

            if self.status_message != original_status:
                changed_state = True
            return changed_state

        # Proceed if there are matches
        # Increment current_match_idx, wrapping around if necessary
        self.current_match_idx = (self.current_match_idx + 1) % len(self.search_matches)

        # The _goto_match method should handle cursor and scroll adjustment
        # It does not return a flag, so we check changes after its call.
        self._goto_match(self.current_match_idx)

        self._set_status_message(
            f"Match {self.current_match_idx + 1} of {len(self.search_matches)} for '{self.search_term}'"
        )

        # Determine if a redraw is needed by comparing state
        if (
            self.cursor_y != original_cursor_pos[0]
            or self.cursor_x != original_cursor_pos[1]
            or self.scroll_top != original_scroll_pos[0]
            or self.scroll_left != original_scroll_pos[1]
            or self.status_message != original_status
        ):
            changed_state = True

        return changed_state

    def validate_filename(self, filename: str) -> bool:
        """Validates the provided filename for basic correctness, length, and path restrictions.
        - Checks for empty or excessively long filenames.
        - Checks for invalid characters commonly disallowed in filenames.
        - Checks for reserved system names on Windows.
        - Performs basic path traversal security check for '..'.
        """
        if not filename:
            self._set_status_message("Filename cannot be empty.")
            logging.warning("Validation failed: Filename is empty.")
            return False

        MAX_FILENAME_LEN = 255
        if len(filename) > MAX_FILENAME_LEN:
            self._set_status_message(
                f"Filename too long (max {MAX_FILENAME_LEN} chars)."
            )
            logging.warning(
                f"Validation failed: Filename too long ({len(filename)} chars): '{filename[:50]}...'"
            )
            return False

        stripped_filename = filename.strip()
        if not stripped_filename:
            self._set_status_message("Filename cannot consist only of whitespace.")
            logging.warning(
                "Validation failed: Filename is composed entirely of whitespace."
            )
            return False

        basename_to_check = os.path.basename(filename)
        invalid_chars_regex = r'[<>:"/\\|?*\x00-\x1F]'
        if re.search(invalid_chars_regex, basename_to_check):
            self._set_status_message(
                f"Filename '{basename_to_check}' contains invalid characters."
            )
            logging.warning(
                f"Validation failed: Filename part '{basename_to_check}' contains invalid characters."
            )
            return False

        if os.name == "nt":
            windows_reserved_names = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "COM1",
                "COM2",
                "COM3",
                "COM4",
                "COM5",
                "COM6",
                "COM7",
                "COM8",
                "COM9",
                "LPT1",
                "LPT2",
                "LPT3",
                "LPT4",
                "LPT5",
                "LPT6",
                "LPT7",
                "LPT8",
                "LPT9",
            }
            name_part_without_ext = os.path.splitext(basename_to_check)[0].upper()
            if name_part_without_ext in windows_reserved_names:
                self._set_status_message(
                    f"Filename '{name_part_without_ext}' is a reserved system name on Windows."
                )
                logging.warning(
                    f"Validation failed: Filename '{filename}' is a reserved system name."
                )
                return False

        try:
            # Normalizing the path for reliable verification
            absolute_target_path = os.path.normpath(os.path.abspath(filename))

            # Leaving only the basic check for attempts to go up directories,
            # which is a reasonable security measure.
            if ".." in absolute_target_path.split(os.sep):
                self._set_status_message(
                    f"Path appears to traverse upwards ('..'): '{filename}'"
                )
                logging.warning(
                    f"Validation failed: Path '{absolute_target_path}' contains '..'."
                )
                return False

            logging.debug(
                f"Filename '{filename}' validated successfully. Resolved path: '{absolute_target_path}'"
            )
            return True

        except Exception as e_path:
            self._set_status_message(
                f"Error validating file path: {str(e_path)[:70]}..."
            )
            logging.error(
                f"Error validating filename path \
                            for '{filename}': {e_path}",
                exc_info=True,
            )
            return False

    # ============= execute shell commands ===============================
    def _execute_shell_command_async(self, cmd_list: list[str]) -> None:
        """Executes a shell command in a separate thread and sends the result
        to the self._shell_cmd_q queue in a thread-safe manner.
        The result is a single string message summarizing the outcome.

        Args:
            cmd_list (List[str]): The command and its arguments as a list of strings.
        """
        # Initialize result variables for this execution
        captured_stdout: str = ""
        captured_stderr: str = ""
        result_message: str = ""  # This will be the final message sent to the queue
        exit_code: int = -1  # Default/unknown exit code

        process_handle: Optional[subprocess.Popen] = (
            None  # To store Popen object for terminate/kill
        )

        try:
            command_str_for_log = " ".join(shlex.quote(c) for c in cmd_list)
            logging.debug(
                f"Async shell command: Preparing to \
                            execute: {command_str_for_log}"
            )

            # Determine current working directory for the command
            # Prefer directory of the current file, fallback to os.getcwd()
            # Ensure self.filename is valid and exists if used for cwd
            cwd_path: str
            if self.filename and os.path.isfile(
                self.filename
            ):  # Check if it's a file, not just exists
                cwd_path = os.path.dirname(os.path.abspath(self.filename))
            else:
                cwd_path = os.getcwd()
            logging.debug(f"Async shell command: Effective CWD: {cwd_path}")

            # Use subprocess.Popen for better control, especially for timeouts and stream handling
            process_handle = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,  # Capture standard output
                stderr=subprocess.PIPE,  # Capture standard error
                text=True,  # Decode output as text (uses locale's encoding by default or specified)
                encoding="utf-8",  # Explicitly specify UTF-8 for decoding
                errors="replace",  # Replace undecodable characters
                cwd=cwd_path,  # Set the current working directory for the command
                universal_newlines=True,  # Deprecated but often used with text=True for line ending normalization
                # For Python 3.7+, text=True implies universal_newlines=True effectively.
            )

            # Wait for the command to complete, with a timeout.
            # communicate() reads all output/error until EOF and waits for process to terminate.
            # Timeout is configurable via editor settings (e.g., self.config['shell']['timeout'])
            shell_timeout = self.config.get("shell", {}).get("timeout_seconds", 30)
            try:
                captured_stdout, captured_stderr = process_handle.communicate(
                    timeout=shell_timeout
                )
                exit_code = process_handle.returncode
            except subprocess.TimeoutExpired:
                logging.warning(
                    f"Async shell command '{command_str_for_log}' timed out after {shell_timeout}s. Terminating."
                )
                result_message = f"Command timed out ({shell_timeout}s). Terminating."

                # Attempt to terminate and then kill the process
                try:
                    process_handle.terminate()  # Send SIGTERM
                    # Wait a bit for termination
                    try:
                        outs, errs = process_handle.communicate(
                            timeout=5
                        )  # Collect any final output
                        captured_stdout += outs if outs else ""
                        captured_stderr += errs if errs else ""
                    except subprocess.TimeoutExpired:  # Still didn't terminate
                        logging.warning(
                            f"Process '{command_str_for_log}' did not \
                              terminate gracefully, attempting kill."
                        )
                        process_handle.kill()  # Send SIGKILL
                        # Try one last communicate to drain pipes after kill
                        try:
                            outs, errs = process_handle.communicate(timeout=1)
                            captured_stdout += outs if outs else ""
                            captured_stderr += errs if errs else ""
                        except Exception:
                            pass  # Ignore errors on communicate after kill
                except Exception as e_term:
                    logging.error(
                        f"Error during termination/kill of \
                          timed-out process '{command_str_for_log}': {e_term}"
                    )

                exit_code = (
                    process_handle.returncode
                    if process_handle.returncode is not None
                    else -2
                )  # Indicate timeout/kill
                # Prepend to existing output/error if any was captured before timeout signal
                captured_stdout = f"(Output after timeout signal)\n{captured_stdout}"
                captured_stderr = f"(Error after timeout signal)\n{captured_stderr}"

            logging.debug(
                f"Async shell command '{command_str_for_log}' finished. "
                f"Exit code: {exit_code}. Stdout len: {len(captured_stdout)}. Stderr len: {len(captured_stderr)}."
            )

        except FileNotFoundError:
            # This occurs if the command executable itself is not found in PATH.
            result_message = f"Error: Executable not found: '{cmd_list[0]}'"
            logging.error(result_message)
            exit_code = -3  # Custom code for FileNotFoundError
        except Exception as e_exec:
            # Catch any other exceptions during Popen or initial setup.
            command_str_for_log_err = (
                " ".join(shlex.quote(c) for c in cmd_list)
                if "cmd_list" in locals()
                else "Unknown command"
            )
            logging.exception(
                f"Error executing shell command '{command_str_for_log_err}'"
            )
            result_message = f"Execution error: {str(e_exec)[:80]}..."
            exit_code = -4  # Custom code for other execution errors

        finally:
            # Construct the final message based on outcome,
            # if not already set by a major error.
            if not result_message:  # If no message was set by FileNotFoundError, Timeout, or general Exception
                if exit_code != 0:
                    # Command finished with a non-zero exit code (an error).
                    err_summary = (
                        captured_stderr.strip().splitlines()[0]
                        if captured_stderr.strip()
                        else "(no stderr)"
                    )
                    result_message = (
                        f"Command failed (code {exit_code}): {err_summary[:100]}"
                    )
                    if (
                        len(captured_stderr.strip().splitlines()) > 1
                        or len(err_summary) > 100
                    ):
                        result_message += "..."
                elif captured_stdout.strip():
                    # Command was successful (exit code 0) and produced output.
                    out_summary = captured_stdout.strip().splitlines()[0]
                    result_message = f"Command successful: {out_summary[:100]}"
                    if (
                        len(captured_stdout.strip().splitlines()) > 1
                        or len(out_summary) > 100
                    ):
                        result_message += "..."
                else:
                    # Command was successful (exit code 0) but produced no output.
                    result_message = "Command executed successfully (no output)."

            # Send the final result message to the queue for the main thread.
            try:
                self._shell_cmd_q.put(result_message)
                logging.debug(f"Async shell command result queued: '{result_message}'")
            except Exception as e_queue:
                logging.error(
                    f"Failed to put shell command result \
                                into queue: {e_queue}",
                    exc_info=True,
                )

    def execute_shell_command(self) -> bool:
        """Prompts the user for a shell command, then executes it asynchronously.
        An initial status message "Running command..." is set.
        The actual result of the command will be displayed in the status bar later
        when processed from the _shell_cmd_q by the main loop.

        Returns:
            bool:True if the user provided a command and the process was initiated
                 (which involves setting a status message, thus needing a redraw).
                 False if the user cancelled the command prompt without entering a
                 command and the status message did not change from its original state.
        """
        logging.debug("execute_shell_command called")
        original_status = self.status_message
        status_changed_by_interaction = False

        # Prompt for the command
        # self.prompt handles its own temporary status line drawing.
        status_before_prompt = self.status_message
        command_str = self.prompt("Enter shell command: ")
        if (
            self.status_message != status_before_prompt
        ):  # If prompt itself changed status
            status_changed_by_interaction = True

        if not command_str:  # User cancelled or entered empty command at prompt
            if (
                not status_changed_by_interaction
                and self.status_message == original_status
            ):
                self._set_status_message("Shell command cancelled by user.")
            logging.debug("Shell command input cancelled by user or empty.")
            return (
                self.status_message != original_status or status_changed_by_interaction
            )

        # Parse the command string into a list of arguments
        cmd_list_args: list[str]
        try:
            cmd_list_args = shlex.split(command_str)
            if (
                not cmd_list_args
            ):  # Empty command after shlex.split (e.g., if input was only whitespace)
                self._set_status_message("Empty command entered.")
                logging.warning(
                    "Shell command execution failed: command was empty after parsing."
                )
                return True  # Status message changed
        except (
            ValueError
        ) as e_shlex:  # Error during shlex.split (e.g., unmatched quotes)
            self._set_status_message(f"Command parse error: {e_shlex}")
            logging.error(f"Shell command parse error for '{command_str}': {e_shlex}")
            return True  # Status message changed

        # --- Set status to "Running command..." and start the thread ---
        # This message will be displayed while the command runs in the background.
        display_command_str = " ".join(shlex.quote(c) for c in cmd_list_args)
        if len(display_command_str) > 60:  # Truncate for status bar
            display_command_str = display_command_str[:57] + "..."

        self._set_status_message(f"Running: {display_command_str}")

        # Start the command execution in a separate thread
        thread_name = f"ShellExecThread-{cmd_list_args[0]}-{int(time.time())}"
        command_execution_thread = threading.Thread(
            target=self._execute_shell_command_async,
            args=(cmd_list_args,),
            daemon=True,  # Thread will exit when the main program exits
            name=thread_name,
        )
        command_execution_thread.start()

        logging.debug(
            f"Started shell command execution \
                      thread: {thread_name} for command: {cmd_list_args}"
        )

        # The method has initiated an async action and set a status message.
        return True  # Status message changed, redraw needed.

    def toggle_insert_mode(self) -> bool:
        """Toggles between Insert and Replace (Overwrite) modes for text input.

        - Insert Mode (default): Characters are inserted at the cursor position,
          shifting existing characters to the right.
        - Replace Mode: Characters typed replace the character currently under
          the cursor. If at the end of the line, characters are appended.

        This method updates the `self.insert_mode` flag and sets a status message
        indicating the new mode.

        Returns:
            bool: True, as this action always changes the editor's mode and
                  updates the status message, thus requiring a redraw of the status bar.
        """
        original_status = self.status_message  # For robust True/False return
        original_insert_mode = self.insert_mode

        self.insert_mode = not self.insert_mode  # Toggle the mode

        mode_text_indicator = "Insert" if self.insert_mode else "Replace"

        logging.debug(f"Insert mode toggled. New mode: {mode_text_indicator}")
        self._set_status_message(f"Mode: {mode_text_indicator}")

        # Return True if the mode actually changed or if the status message changed.
        # Since _set_status_message is always called with a new mode indicator,
        # the status message will almost certainly change unless it was already displaying
        # the exact same "Mode: ..." message (highly unlikely for a toggle).
        if (
            self.insert_mode != original_insert_mode
            or self.status_message != original_status
        ):
            return True

        return False  # Should be rare, e.g. if status somehow didn't update to the new mode text

    # ==================== bracket =======================
    # this method designed to search for a matching bracket across multiple lines
    def find_matching_bracket_multiline(
        self, initial_char_y: int, initial_char_x: int
    ) -> Optional[tuple[int, int]]:  # noqa: python:S3516
        """Searches for the matching bracket for the one at
        (initial_char_y, initial_char_x) across multiple lines.
        This is a simplified version and does NOT consider string literals
        or comments,which can lead to incorrect matches in source code.

        Args:
            initial_char_y (int): The row of the bracket to start searching from.
            initial_char_x (int): The column of the bracket to start searching from.

        Returns:
            Optional[Tuple[int, int]]: (row, col) of the matching bracket,
            or None if not found.
        """
        if not (
            0 <= initial_char_y < len(self.text)
            and 0 <= initial_char_x < len(self.text[initial_char_y])
        ):
            return None  # Initial position is out of bounds

        char_at_cursor = self.text[initial_char_y][initial_char_x]

        brackets_map = {
            "(": ")",
            "{": "}",
            "[": "]",
            "<": ">",
            ")": "(",
            "}": "{",
            "]": "[",
            ">": "<",
        }
        open_brackets = "({[<"

        if char_at_cursor not in brackets_map:
            return None  # Character at cursor is not a bracket we handle

        target_match_char = brackets_map[char_at_cursor]
        level = 1  # Start at level 1, looking for the char that brings it to 0

        if char_at_cursor in open_brackets:
            # Search forward for the closing bracket
            current_y, current_x = initial_char_y, initial_char_x + 1
            while current_y < len(self.text):
                line = self.text[current_y]
                while current_x < len(line):
                    char = line[current_x]
                    if (
                        char == char_at_cursor
                    ):  # Found another opening bracket of the same type
                        level += 1
                    elif (
                        char == target_match_char
                    ):  # Found a potential matching closing bracket
                        level -= 1
                        if level == 0:
                            return (current_y, current_x)  # Match found
                    current_x += 1
                current_y += 1
                current_x = 0  # Reset column for the new line
        else:  # char_at_cursor is a closing bracket, search backward for the opening one
            current_y, current_x = initial_char_y, initial_char_x - 1
            while current_y >= 0:
                line = self.text[current_y]
                while current_x >= 0:
                    char = line[current_x]
                    if char == char_at_cursor:
                        level += 1
                    elif char == target_match_char:
                        level -= 1
                        if level == 0:
                            return (current_y, current_x)
                    current_x -= 1
                current_y -= 1
                if current_y >= 0:
                    current_x = len(self.text[current_y]) - 1

        return None  # No match found

    def highlight_matching_brackets(self) -> None:
        """Highlights the bracket at the cursor and its matching pair.

        This method searches for a bracket character at or immediately to the
        left of the current cursor position. If a bracket is found, it uses
        `find_matching_bracket_multiline` to locate its corresponding pair.
        If both brackets are found and are visible on the screen, they are
        highlighted using `curses.A_REVERSE`.

        The method accounts for:
            - Cursor position being at the end of a line or on an empty line.
            - Vertical and horizontal scrolling to determine visibility.
            - Display widths of characters (via `self.get_char_width` and `self.get_string_width`).

        This method is typically called as part of the main drawing cycle and
        modifies the screen directly using `self.stdscr.chgat()`. It does not
        perform `self.stdscr.refresh()` itself.

        Note:
            This implementation does NOT currently ignore brackets found within
            string literals or comments, which can lead to incorrect matches in
            source code.

        Args:
            None

        Returns:
            None
        """
        # Get terminal dimensions and ensure basic conditions are met.
        _term_height, term_width = self.stdscr.getmaxyx()
        # Bounds check for cursor position
        if not (0 <= self.cursor_y < len(self.text)):
            logging.debug(
                "highlight_matching_brackets: Cursor Y (%d) is out of text bounds (0-%d).",
                self.cursor_y,
                len(self.text) - 1,
            )
            return

        # Check if cursor's line is visible on the screen
        if not (
            self.scroll_top <= self.cursor_y < self.scroll_top + self.visible_lines
        ):
            logging.debug(
                "highlight_matching_brackets: Cursor's line (%d) is not currently visible \
                    on screen (scroll_top: %d, visible_lines: %d).",
                self.cursor_y,
                self.scroll_top,
                self.visible_lines,
            )
            return

        current_line_text = self.text[self.cursor_y]
        if not current_line_text and self.cursor_x == 0:
            logging.debug(
                "highlight_matching_brackets: Cursor is on an empty line at column 0."
            )
            return

        # Find the bracket at or near the cursor
        brackets_map_chars = "(){}[]<>"
        bracket_pos = None

        if (
            0 <= self.cursor_x < len(current_line_text)
            and current_line_text[self.cursor_x] in brackets_map_chars
        ):
            bracket_pos = (self.cursor_y, self.cursor_x)
            logging.debug(
                f"highlight_matching_brackets: Candidate bracket '{current_line_text[self.cursor_x]}' \
                    AT cursor ({self.cursor_y},{self.cursor_x})."
            )
        elif (
            self.cursor_x > 0
            and current_line_text[self.cursor_x - 1] in brackets_map_chars
        ):
            bracket_pos = (self.cursor_y, self.cursor_x - 1)
            logging.debug(
                f"highlight_matching_brackets: Candidate bracket '{current_line_text[self.cursor_x - 1]}' LEFT \
                    of cursor ({self.cursor_y},{self.cursor_x - 1})."
            )
        else:
            logging.debug(
                f"highlight_matching_brackets: No suitable bracket found \
                    near cursor ({self.cursor_y},{self.cursor_x}) for matching."
            )
            return

        # Find the matching bracket using the determined position
        bracket_char = self.text[bracket_pos[0]][bracket_pos[1]]
        match_coords = self.find_matching_bracket_multiline(
            bracket_pos[0], bracket_pos[1]
        )

        if not match_coords:
            logging.debug(
                f"highlight_matching_brackets: No matching bracket found \
                    for '{bracket_char}' at ({bracket_pos[0]},{bracket_pos[1]})."
            )
            return

        match_y, match_x = match_coords
        if not (
            0 <= match_y < len(self.text) and 0 <= match_x < len(self.text[match_y])
        ):
            logging.warning(
                f"highlight_matching_brackets: Matching bracket \
                    coords ({match_y},{match_x}) are out of text bounds."
            )
            return

        # Calculate the display width of the line number column
        line_num_display_width = len(str(max(1, len(self.text)))) + 1
        if (
            hasattr(self.drawer, "_text_start_x")
            and isinstance(self.drawer._text_start_x, int)
            and self.drawer._text_start_x >= 0
        ):
            line_num_display_width = self.drawer._text_start_x
        else:
            logging.debug(
                "highlight_matching_brackets: self.drawer._text_start_x not available or invalid, \
                    calculating line_num_display_width locally."
            )

        def get_screen_coords_for_highlight(
            text_row_idx: int, text_col_idx: int
        ) -> Optional[tuple[int, int]]:
            """Calculates screen (y, x) for a text coordinate.

            Args:
                text_row_idx (int): The 0-based row index in the text buffer.
                text_col_idx (int): The 0-based character column index in the line.

            Returns:
                Optional[Tuple[int, int]]: The screen coordinates if visible, otherwise None.
            """
            if not (
                self.scroll_top <= text_row_idx < self.scroll_top + self.visible_lines
            ):
                return None
            screen_y_coord = text_row_idx - self.scroll_top
            try:
                if not (0 <= text_row_idx < len(self.text)):
                    logging.warning(
                        f"get_screen_coords_for_highlight: text_row_idx {text_row_idx} out of bounds for self.text."
                    )
                    return None
                clamped_text_col_idx = max(
                    0, min(text_col_idx, len(self.text[text_row_idx]))
                )
                prefix_width_unscrolled = self.get_string_width(
                    self.text[text_row_idx][:clamped_text_col_idx]
                )
            except IndexError:
                logging.warning(
                    f"get_screen_coords_for_highlight: IndexError accessing text for ({text_row_idx},{text_col_idx})."
                )
                return None
            screen_x_coord = (
                line_num_display_width + prefix_width_unscrolled - self.scroll_left
            )
            if text_col_idx >= len(self.text[text_row_idx]):
                logging.warning(
                    f"get_screen_coords_for_highlight: text_col_idx {text_col_idx} is at or past EOL for line {text_row_idx} (len {len(self.text[text_row_idx])}). Cannot get char width for highlighting."
                )
                return None
            char_display_width_at_coord = self.get_char_width(
                self.text[text_row_idx][text_col_idx]
            )
            if char_display_width_at_coord <= 0:
                logging.debug(
                    f"get_screen_coords_for_highlight: Character at ({text_row_idx},{text_col_idx}) has width {char_display_width_at_coord}, not highlighting directly."
                )
                return None
            if (
                screen_x_coord >= term_width
                or (screen_x_coord + char_display_width_at_coord)
                <= line_num_display_width
            ):
                return None
            return screen_y_coord, max(line_num_display_width, screen_x_coord)

        # 4. Calculate screen coordinates for both brackets
        coords1_on_screen = get_screen_coords_for_highlight(
            bracket_pos[0], bracket_pos[1]
        )
        coords2_on_screen = get_screen_coords_for_highlight(match_y, match_x)

        # 5. Highlight brackets if visible on screen
        highlight_attr = curses.A_REVERSE

        if coords1_on_screen:
            scr_y1, scr_x1 = coords1_on_screen
            char1_width = self.get_char_width(self.text[bracket_pos[0]][bracket_pos[1]])
            if scr_x1 < term_width and char1_width > 0:
                visible_cells_of_char1 = min(char1_width, term_width - scr_x1)
                if visible_cells_of_char1 > 0:
                    try:
                        self.stdscr.chgat(
                            scr_y1, scr_x1, visible_cells_of_char1, highlight_attr
                        )
                        logging.debug(
                            f"Highlighted bracket 1 ('{bracket_char}') at screen ({scr_y1},{scr_x1}) for {visible_cells_of_char1} cells, "
                            f"text ({bracket_pos[0]},{bracket_pos[1]})"
                        )
                    except curses.error as e:
                        logging.warning(
                            f"Curses error highlighting bracket 1 at screen ({scr_y1},{scr_x1}): {e}"
                        )

        if coords2_on_screen:
            scr_y2, scr_x2 = coords2_on_screen
            char2_width = self.get_char_width(self.text[match_y][match_x])
            if scr_x2 < term_width and char2_width > 0:
                visible_cells_of_char2 = min(char2_width, term_width - scr_x2)
                if visible_cells_of_char2 > 0:
                    try:
                        self.stdscr.chgat(
                            scr_y2, scr_x2, visible_cells_of_char2, highlight_attr
                        )
                        logging.debug(
                            f"Highlighted bracket 2 ('{self.text[match_y][match_x]}') at screen ({scr_y2},{scr_x2}) for {visible_cells_of_char2} cells, "
                            f"text ({match_y},{match_x})"
                        )
                    except curses.error as e:
                        logging.warning(
                            f"Curses error highlighting bracket 2 at screen ({scr_y2},{scr_x2}): {e}"
                        )

    def init_colors(self) -> None:
        """Initializes curses color pairs with graceful degradation."""
        self.is_256_color_terminal: bool = False
        self.colors = {}  # Start fresh

        if not curses.has_colors() or curses.COLORS < 8:
            logging.warning(
                "Terminal has no or limited color support (< 8). Using monochrome attributes."
            )
            self.colors = {
                "default": curses.A_NORMAL,
                "comment": curses.A_DIM,
                "keyword": curses.A_BOLD,
                "string": curses.A_NORMAL,
                "number": curses.A_NORMAL,
                "function": curses.A_BOLD,
                "constant": curses.A_BOLD,
                "type": curses.A_NORMAL,
                "operator": curses.A_NORMAL,
                "decorator": curses.A_BOLD,
                "variable": curses.A_NORMAL,
                "tag": curses.A_NORMAL,
                "attribute": curses.A_NORMAL,
                "error": curses.A_REVERSE | curses.A_BOLD,
                "status": curses.A_REVERSE,
                "status_error": curses.A_REVERSE | curses.A_BOLD,
                "line_number": curses.A_DIM,
                # --- Adding Git colors even to monochrome mode---
                "git_info": curses.A_NORMAL,
                "git_dirty": curses.A_BOLD,
                "git_added": curses.A_NORMAL,
                "git_deleted": curses.A_DIM,
                # -----------------------------------------------------------------
                "search_highlight": curses.A_REVERSE,
            }
            return

        curses.start_color()
        curses.use_default_colors()

        # --- Adding new semantic names for Git ---
        color_definitions = {
            # Syntax Highlighting
            "default": ("#C9D1D9", curses.COLOR_WHITE, curses.A_NORMAL),
            "comment": ("#8B949E", curses.COLOR_WHITE, curses.A_DIM),
            "keyword": ("#FF7B72", curses.COLOR_MAGENTA, curses.A_NORMAL),
            "string": ("#A5D6FF", curses.COLOR_CYAN, curses.A_NORMAL),
            "number": ("#79C0FF", curses.COLOR_BLUE, curses.A_NORMAL),
            "function": ("#D2A8FF", curses.COLOR_YELLOW, curses.A_BOLD),
            "constant": ("#79C0FF", curses.COLOR_CYAN, curses.A_BOLD),
            "type": ("#F2CC60", curses.COLOR_YELLOW, curses.A_NORMAL),
            "operator": ("#FF7B72", curses.COLOR_RED, curses.A_NORMAL),
            "decorator": ("#D2A8FF", curses.COLOR_MAGENTA, curses.A_BOLD),
            "variable": ("#C9D1D9", curses.COLOR_WHITE, curses.A_NORMAL),
            "tag": ("#7EE787", curses.COLOR_GREEN, curses.A_NORMAL),
            "attribute": ("#79C0FF", curses.COLOR_CYAN, curses.A_NORMAL),
            # UI Elements
            "error": ("#F85149", curses.COLOR_RED, curses.A_BOLD),
            "status": ("#C9D1D9", curses.COLOR_WHITE, curses.A_REVERSE),
            "status_error": (
                "#F85149",
                curses.COLOR_RED,
                curses.A_REVERSE | curses.A_BOLD,
            ),
            "line_number": ("#817248", curses.COLOR_YELLOW, curses.A_DIM),
            # --- Colors for Git statuses ---
            "git_info": (
                "#34913C",
                curses.COLOR_GREEN,
                curses.A_NORMAL,
            ),  # Untracked, Clean
            "git_dirty": ("#F2CC60", curses.COLOR_YELLOW, curses.A_NORMAL),  # Modified
            "git_added": ("#A5D6FF", curses.COLOR_CYAN, curses.A_NORMAL),  # Added
            "git_deleted": ("#F85149", curses.COLOR_RED, curses.A_DIM),  # Deleted
            # -----------------------------------------
            "search_highlight": ("#000000", curses.COLOR_BLACK, curses.A_NORMAL),
        }

        user_colors = self.config.get("colors", {})
        pair_id_counter = 1
        can_use_256_colors = curses.COLORS >= 256
        self.is_256_color_terminal = can_use_256_colors

        for name, (default_hex, default_8_color, attr) in color_definitions.items():
            if pair_id_counter >= curses.COLOR_PAIRS:
                logging.warning(
                    f"Ran out of color pairs. Cannot initialize '{name}' \
                                    and subsequent colors."
                )
                self.colors[name] = attr
                continue

            fg, bg = -1, -1

            if can_use_256_colors:
                hex_code = user_colors.get(name, default_hex)
                try:
                    fg = hex_to_xterm(hex_code)
                except Exception:
                    fg = hex_to_xterm(default_hex)
            else:
                fg = default_8_color

            if name == "search_highlight":
                bg_hex = user_colors.get("search_highlight_bg", "#FFAB70")
                if can_use_256_colors:
                    try:
                        bg = hex_to_xterm(bg_hex)
                    except Exception:
                        bg = 215
                else:
                    bg = curses.COLOR_YELLOW

            try:
                curses.init_pair(pair_id_counter, fg, bg)
                self.colors[name] = curses.color_pair(pair_id_counter) | attr
                pair_id_counter += 1
            except curses.error as e:
                logging.error(f"Failed to initialize curses pair for '{name}': {e}")
                self.colors[name] = attr

    # ==================== HELP ==================================
    def _build_help_lines(self) -> list[str]:  # noqa: python:S3516
        # This method seems correct as is, based on your provided code.
        # It uses self.config to get keybindings.
        def _kb(action: str, default: str) -> str:
            """Return a prettified key‑binding string for *action*."""
            # Ensure self.config is accessed correctly
            raw = self.config.get("keybindings", {}).get(action, default)
            if isinstance(
                raw, int
            ):  # If the binding is a direct int (curses code), use default string
                raw = default
            elif isinstance(
                raw, list
            ):  # If it's a list, take the first string representation or default
                str_bindings = [item for item in raw if isinstance(item, str)]
                raw = str_bindings[0] if str_bindings else default

            parts = str(raw).strip().lower().split("+")
            formatted = []
            for part in parts:
                if part in {"ctrl", "alt", "shift"}:
                    formatted.append(part.capitalize())
                elif len(part) == 1 and part.isalpha():
                    formatted.append(part.upper())
                elif part.startswith("f") and part[1:].isdigit():
                    formatted.append(part.upper())
                else:
                    # Capitalize if fully alphabetic, otherwise use as is
                    formatted.append(part.capitalize() if part.isalpha() else part)
            return "+".join(formatted)

        defaults = {
            "new_file": "F2",
            "open_file": "Ctrl+O",
            "save_file": "Ctrl+S",
            "save_as": "F5",
            "quit": "Ctrl+Q",
            "undo": "Ctrl+Z",
            "redo": "Ctrl+Y",
            "copy": "Ctrl+C",
            "cut": "Ctrl+X",
            "paste": "Ctrl+V",
            "select_all": "Ctrl+A",
            "delete": "Del",
            "goto_line": "Ctrl+G",
            "find": "Ctrl+F",
            "find_next": "F3",
            "search_and_replace": "F6",
            "lint": "F4",
            "git_menu": "F9",
            "help": "F1",
            "cancel_operation": "Esc",
            "tab": "Tab",
            "shift_tab": "Shift+Tab",
            "toggle_comment_block": "Ctrl+\\",
            "ai_assist": "F7",
            "file_manager": "F10",
        }
        return [
            "                 ──  Ecli Help  ──  ",
            "",
            "  Tools & Features:",
            f"    {_kb('file_manager', defaults['file_manager']):<22}: File Manager",
            f"    {_kb('lint', defaults['lint']):<22}: Diagnostics (LSP/Linters)",
            f"    {_kb('git_menu', defaults['git_menu']):<22}: Git menu",
            f"    {_kb('help', defaults['help']):<22}: This help screen",
            f"    {_kb('ai_assist', defaults['ai_assist']):<22}: AI Code Assistant",
            f"    {_kb('cancel_operation', defaults['cancel_operation']):<22}: Cancel / Close Panel",
            "    Insert Key            : Toggle Insert/Replace mode",
            "",
            "  File Operations:",
            f"    {_kb('new_file', defaults['new_file']):<22}: New file",
            f"    {_kb('open_file', defaults['open_file']):<22}: Open file",
            f"    {_kb('save_file', defaults['save_file']):<22}: Save",
            f"    {_kb('save_as', defaults['save_as']):<22}: Save as…",
            f"    {_kb('quit', defaults['quit']):<22}: Quit editor",
            "",
            "  Editing:",
            f"    {_kb('copy', defaults['copy']):<22}: Copy",
            f"    {_kb('cut', defaults['cut']):<22}: Cut",
            f"    {_kb('paste', defaults['paste']):<22}: Paste",
            f"    {_kb('select_all', defaults['select_all']):<22}: Select all",
            f"    {_kb('undo', defaults['undo']):<22}: Undo",
            f"    {_kb('redo', defaults['redo']):<22}: Redo",
            f"    {_kb('delete', defaults['delete']):<22}: Delete char/selection",
            "    Backspace             : Delete char left / selection",
            f"    {_kb('tab', defaults['tab']):<22}: Smart Tab / Indent block",
            f"    {_kb('shift_tab', defaults['shift_tab']):<22}: Smart Unindent / Unindent block",
            f"    {_kb('toggle_comment_block', defaults['toggle_comment_block']):<22}: Comment/Uncomment block/line",
            "",
            "  Navigation & Search:",
            f"    {_kb('goto_line', defaults['goto_line']):<22}: Go to line",
            f"    {_kb('find', defaults['find']):<22}: Find (prompt)",
            f"    {_kb('find_next', defaults['find_next']):<22}: Find next occurrence",
            f"    {_kb('search_and_replace', defaults['search_and_replace']):<22}: Search & Replace (regex)",
            "    Arrows, Home, End     : Cursor movement",
            "    PageUp, PageDown      : Scroll by page",
            "    Shift+Nav Keys        : Extend selection",
            "",
            "   ────────────────────────────────────────────────────",
            "",
            "              Press any key to close help",  # Changed
            "",
            "               Licensed under the Apache-2.0 ",
            "",
            "               © 2025 Siergej Sobolewski",
        ]

    def show_help(self) -> bool:  # noqa: python:S3516
        """Displays a centered, scrollable help window.
        Uses textual indicators for scrolling and adapts colors based
        on terminal capabilities.
        """
        lines = self._build_help_lines()

        if not lines:  # Should not happen if _build_help_lines is robust
            self._set_status_message("Error: Help content is empty.")
            return True

        term_h, term_w = self.stdscr.getmaxyx()

        # Calculate window dimensions for the help panel
        # Ensure some padding and that it doesn't exceed terminal dimensions
        text_max_width = 0
        if lines:  # Avoid error if lines is empty, though we check above
            text_max_width = max(len(line) for line in lines)

        # Add padding for borders and internal margins
        view_w = min(
            text_max_width + 6, term_w - 4
        )  # +2 for side borders, +4 for side margins
        view_h = min(
            len(lines) + 4, term_h - 4
        )  # +2 for top/bottom borders, +2 for top/bottom margins

        # Ensure minimum dimensions
        view_w = max(20, view_w)  # Minimum width for readability
        view_h = max(8, view_h)  # Minimum height

        # Center the help window
        view_y = max(0, (term_h - view_h) // 2)
        view_x = max(0, (term_w - view_w) // 2)

        # Re-check if dimensions are too small even after adjustments
        if view_h <= 4 or view_w <= 4:  # Need space for border and content
            self._set_status_message("Terminal too small for help.")
            return True

        original_cursor_visibility = curses.curs_set(0)  # Hide cursor for help screen

        # --- Color Attributes ---
        # Defaults for monochrome or very limited color terminals
        default_text_attr = curses.A_NORMAL
        default_bg_attr = curses.A_NORMAL  # Will be background of the help window
        default_border_attr = curses.A_BOLD
        default_scroll_attr = curses.A_BOLD | curses.A_REVERSE

        # Attempt to use nicer colors if available
        try:
            if curses.has_colors():
                # Use editor's pre-defined colors if they fit the semantic need,
                # or define new pairs if necessary and COLOR_PAIRS allows.
                # For simplicity, let's define specific pairs for help if > 8 colors.
                # Ensure these pair IDs don't clash with those in self.init_colors()
                # It's safer to use a range of pair IDs known to be free.
                # Example: use pairs starting from 30 upwards if 0-20 are used by init_colors.

                HELP_PAIR_ID_START = 30  # Arbitrary start for help-specific color pairs

                if curses.COLORS >= 256 and curses.COLOR_PAIRS > HELP_PAIR_ID_START + 2:
                    # 256+ color mode: e.g., light text on a dark grey background
                    curses.init_pair(
                        HELP_PAIR_ID_START, 231, 236
                    )  # fg: almost white, bg: dark grey
                    default_bg_attr = curses.color_pair(HELP_PAIR_ID_START)
                    default_text_attr = curses.color_pair(HELP_PAIR_ID_START)

                    curses.init_pair(
                        HELP_PAIR_ID_START + 1, 250, 236
                    )  # fg: lighter grey for border
                    default_border_attr = (
                        curses.color_pair(HELP_PAIR_ID_START + 1) | curses.A_BOLD
                    )

                    curses.init_pair(
                        HELP_PAIR_ID_START + 2, 226, 236
                    )  # fg: yellow for scroll indicators
                    default_scroll_attr = (
                        curses.color_pair(HELP_PAIR_ID_START + 2) | curses.A_BOLD
                    )
                elif curses.COLORS >= 8 and curses.COLOR_PAIRS > HELP_PAIR_ID_START + 2:
                    # 8/16 color mode: e.g., white text on blue background
                    curses.init_pair(
                        HELP_PAIR_ID_START, curses.COLOR_WHITE, curses.COLOR_BLUE
                    )
                    default_bg_attr = curses.color_pair(HELP_PAIR_ID_START)
                    default_text_attr = curses.color_pair(HELP_PAIR_ID_START)

                    curses.init_pair(
                        HELP_PAIR_ID_START + 1, curses.COLOR_CYAN, curses.COLOR_BLUE
                    )
                    default_border_attr = (
                        curses.color_pair(HELP_PAIR_ID_START + 1) | curses.A_BOLD
                    )

                    # For scroll indicator, use existing reverse or a specific pair
                    curses.init_pair(
                        HELP_PAIR_ID_START + 2, curses.COLOR_BLACK, curses.COLOR_WHITE
                    )  # Black on White
                    default_scroll_attr = curses.color_pair(HELP_PAIR_ID_START + 2)
                # If fewer than 8 colors or not enough pairs, the A_NORMAL defaults will be used.
        except curses.error as e_color:
            logging.warning(
                f"Ecli.show_help: Curses error initializing help colors: {e_color}. Using defaults."
            )
        except Exception as e_gen_color:
            logging.error(
                f"Ecli.show_help: General error initializing help colors: {e_gen_color}",
                exc_info=True,
            )

        try:
            win = curses.newwin(view_h, view_w, view_y, view_x)
            win.keypad(True)
            win.bkgd(" ", default_bg_attr)  # Apply the background to the new window

            content_display_height = (
                view_h - 2
            )  # Available height for text lines (excluding borders)
            max_lines_on_screen = content_display_height
            total_content_lines = len(lines)
            max_scroll_offset = max(0, total_content_lines - max_lines_on_screen)
            current_scroll_top = 0

            SCROLL_UP_INDICATOR = "↑ (PgUp/k)"  # More informative
            SCROLL_DN_INDICATOR = "↓ (PgDn/j)"

            while True:
                win.erase()  # Clear window content for this frame

                # Draw border
                win.attron(default_border_attr)
                win.border()
                win.attroff(default_border_attr)

                # Display visible portion of help lines
                for i in range(max_lines_on_screen):
                    line_idx_in_buffer = current_scroll_top + i
                    if line_idx_in_buffer < total_content_lines:
                        line_to_display = lines[line_idx_in_buffer]
                        # Truncate line if it's wider than the content area of the help window
                        # Content area width: view_w - 2 (for borders) - 2 (for L/R margins)
                        drawable_text_width = view_w - 4
                        if len(line_to_display) > drawable_text_width:
                            # A simple truncation; consider wcwidth for Unicode if needed here
                            line_to_display = (
                                line_to_display[: drawable_text_width - 3] + "..."
                            )

                        try:
                            # Draw text with left/right margin of 1 char inside the border
                            win.addstr(i + 1, 2, line_to_display, default_text_attr)
                        except (
                            curses.error
                        ):  # Curses can fail if trying to write outside window
                            pass

                # Draw scroll indicators if scrolling is possible
                if current_scroll_top > 0:
                    try:
                        # Position at top-right corner, inside border
                        win.addstr(
                            1,
                            view_w - (len(SCROLL_UP_INDICATOR) + 2),
                            SCROLL_UP_INDICATOR,
                            default_scroll_attr,
                        )
                    except curses.error:
                        pass

                if current_scroll_top < max_scroll_offset:
                    try:
                        # Position at bottom-right corner, inside border
                        win.addstr(
                            view_h - 2,
                            view_w - (len(SCROLL_DN_INDICATOR) + 2),
                            SCROLL_DN_INDICATOR,
                            default_scroll_attr,
                        )
                    except curses.error:
                        pass

                # Optional: Display scroll position (e.g., "Line X/Y")
                if max_scroll_offset > 0:
                    # Display at bottom-left corner, inside border
                    scroll_pos_info = f"{(current_scroll_top + 1)}-{min(current_scroll_top + max_lines_on_screen, total_content_lines)}/{total_content_lines}"
                    try:
                        win.addstr(view_h - 2, 2, scroll_pos_info, default_scroll_attr)
                    except curses.error:
                        pass

                win.refresh()
                key_press = win.getch()

                if key_press in (curses.KEY_UP, ord("k"), ord("K")):
                    current_scroll_top = max(0, current_scroll_top - 1)
                elif key_press in (curses.KEY_DOWN, ord("j"), ord("J")):
                    current_scroll_top = min(max_scroll_offset, current_scroll_top + 1)
                elif key_press == curses.KEY_PPAGE:
                    current_scroll_top = max(
                        0, current_scroll_top - max_lines_on_screen
                    )
                elif key_press == curses.KEY_NPAGE:
                    current_scroll_top = min(
                        max_scroll_offset, current_scroll_top + max_lines_on_screen
                    )
                elif key_press in (curses.KEY_HOME, ord("g")):
                    current_scroll_top = 0
                elif key_press in (curses.KEY_END, ord("G")):
                    current_scroll_top = max_scroll_offset
                elif key_press == curses.KEY_RESIZE:
                    # Re-calculate dimensions and redraw on resize
                    term_h, term_w = self.stdscr.getmaxyx()
                    view_w = min(text_max_width + 6, term_w - 4)
                    view_w = max(20, view_w)
                    view_h = min(len(lines) + 4, term_h - 4)
                    view_h = max(8, view_h)
                    view_y = max(0, (term_h - view_h) // 2)
                    view_x = max(0, (term_w - view_w) // 2)
                    try:
                        win.resize(view_h, view_w)
                        win.mvwin(view_y, view_x)
                    except curses.error:
                        pass
                    content_display_height = view_h - 2
                    max_lines_on_screen = content_display_height
                    max_scroll_offset = max(
                        0, total_content_lines - max_lines_on_screen
                    )
                    current_scroll_top = min(current_scroll_top, max_scroll_offset)
                else:
                    # Any other key closes the help window
                    break

        except curses.error as e_curses_help:
            logging.error(
                f"Ecli.show_help: Curses error in help \
                          window main loop: {e_curses_help}",
                exc_info=True,
            )
            self._set_status_message(f"Help display error: {e_curses_help}")
        except Exception as e_general_help:
            logging.error(
                f"Ecli.show_help: General error in help window: {e_general_help}",
                exc_info=True,
            )
            self._set_status_message(f"Help display error: {e_general_help}")
        finally:
            if (
                original_cursor_visibility is not None
                and original_cursor_visibility != curses.ERR
            ):
                try:
                    curses.curs_set(original_cursor_visibility)
                except curses.error:
                    pass

            # Explicitly clear the main screen and refresh to remove help window
            # artifacts and ensure the editor UI is fully redrawn.
            try:
                self.stdscr.clear()
                # This might be too aggressive if main loop handles redraw well:
                self.stdscr.refresh()
            except curses.error:
                pass

            self._set_status_message("Help closed")
            self._force_full_redraw = True  # Signal main loop to redraw everything
            return True  # Indicates status changed or a major UI interaction happened.

    def show_ai_panel(self, title: str, content: str) -> bool:
        """Displays a panel with an AI response using the PanelManager.
        This method is NON-BLOCKING.
        """
        logging.info(f"Request to display AI panel '{title}' via PanelManager.")

        if self.panel_manager:
            display_content = content.rstrip() + "\n\n"

            # Show the panel. The PanelManager will handle focus.
            # The result (inserted text) is now handled within the panel itself.
            self.panel_manager.show_panel(
                "ai_response", title=title, content=display_content
            )
        else:
            # If panel manager doesn't exist (e.g., lightweight mode)
            self._set_status_message(
                "Cannot show AI panel: PanelManager is not active."
            )
            logging.warning(
                "Attempted to show AI panel, but PanelManager is not available."
            )

        # This action always requires a full redraw, either to show the panel
        # or to update the status message.
        return True

    # ----- Shows a menu AI provider --------
    def select_ai_provider_and_ask(self) -> bool:  # noqa: python:S3516
        """Shows a menu to select an AI provider, then sends the selected text
        to the async engine for explanation.

        This method orchestrates the user interaction for getting AI assistance.
        It performs the following steps:
        1.  Get Selected Text: Retrieves the currently selected text using
            `self.get_selected_text()`. If no text is selected, it sets an
            informative status message and aborts.

        2.  Display Provider Menu: It constructs and displays a prompt with a
            list of available AI providers configured in `config.toml`. The user
            can select a provider by entering a corresponding key.

        3.  Process User Choice: It validates the user's input. If the choice
            is invalid or the user cancels the prompt, the operation is aborted
            with a corresponding status message.

        4.  Submit Async Task: If a valid provider is selected, it formats a
            prompt containing the selected code snippet and submits it as a task
            to the `AsyncEngine`. The engine will process the request in the
            background.

        5.  Update Status: An immediate status message is set to inform the
            user that the request has been sent. The final AI response will be
            handled asynchronously when the result arrives from the `AsyncEngine`.

        Returns:
            bool: True, as this action always involves user interaction (a prompt)
                  or a status message update, thus requiring a UI redraw.
        """
        # Get text to send
        selected_text = self.get_selected_text()
        if not selected_text:
            self._set_status_message("No text selected to send to AI.")
            return True  # Early exit is fine here as it's a precondition check

        # Form the selection menu
        default_provider = self.config.get("ai", {}).get("default_provider", "claude")
        menu_items = {
            "1": "openai",
            "2": "gemini",
            "3": "mistral",
            "4": "claude",
            "5": "grok",
            "6": "huggingface",
            "d": default_provider,
        }
        menu_str = " ".join([f"{k}:{v}" for k, v in menu_items.items() if k != "d"])
        prompt_msg = f"Select AI [{menu_str}] (d: default): "

        # Show the menu to the user
        choice = self.prompt(prompt_msg)
        if not choice:
            self._set_status_message("AI request cancelled.")
        else:
            # Determine the provider
            provider = menu_items.get(choice.lower())
            if not provider:
                self._set_status_message(f"Invalid choice '{choice}'.")
            else:
                logging.info(f"User selected AI provider: {provider}")

                # 5. Form the prompt and submit the task
                prompt_text = f"Please explain the following code snippet:\n\n```\n{selected_text}\n```"
                task = {
                    "type": "ai_chat",
                    "provider": provider,
                    "prompt": prompt_text,
                    "config": self.config,
                }

                # Add check for None
                if self.async_engine:
                    self.async_engine.submit_task(task)
                    self._set_status_message(
                        f"Sent request to {provider.capitalize()}..."
                    )
                else:
                    self._set_status_message("Async engine is not active.")

        # This action always interacts with the user or changes the status,
        # so a redraw is always required.
        return True

    # -------------------- QUEUE PROCESSING --------------------------
    def _process_all_queues(self) -> bool:
        """Processes messages from all internal queues (general status, shell commands, etc.)
        and delegates Git-specific queue processing to the GitBridge component.

        This method updates the editor's state based on these messages, primarily by
        setting the status message. It's called on each iteration of the main loop.

        Returns:
            bool: True if any message was processed that resulted in a change to
                the editor's state (like self.status_message), thus requiring a redraw.
                Returns False otherwise.
        """
        # If we are in lightweight mode, there are no queues or components, so we exit early.
        if self.is_lightweight:
            return False

        any_state_changed_by_queues = False

        # 1. Process shell command results queue (_shell_cmd_q)
        try:
            # Loop to drain the queue of all pending messages in one go.
            while True:
                # get_nowait() is non-blocking and raises queue.Empty if the queue is empty.
                shell_result_msg = self._shell_cmd_q.get_nowait()

                # Optimization: only set the status message if it's different from the current one.
                if self.status_message != str(shell_result_msg):
                    self.status_message = str(shell_result_msg)
                    any_state_changed_by_queues = True
                logging.debug(
                    f"Processed shell command result: '{self.status_message}'"
                )
        except queue.Empty:
            # This is the expected way to exit the non-blocking loop when the queue is empty.
            pass

        # 2. Delegate Git queue processing to its own component.
        # STYLISTIC IMPROVEMENT: Using `|=` is a more concise and Pythonic way
        # to update a boolean flag. It means:
        # any_state_changed_by_queues = any_state_changed_by_queues or self.git.process_queues()
        if self.git:
            any_state_changed_by_queues |= self.git.process_queues()

        # 3. Delegate Linter/LSP queue processing.
        if self.linter_bridge:
            any_state_changed_by_queues |= self.linter_bridge.process_lsp_queue()

        # 4. Process the main asynchronous engine queue (for AI replies, etc.)
        if self.async_engine:
            try:
                while True:
                    async_result = self._async_results_q.get_nowait()
                    logging.debug(f"Processed async result: {async_result}")

                    if async_result.get("type") == "ai_reply":
                        reply_text = async_result.get("text", "AI response was empty.")
                        self.show_ai_panel("AI Assistant Reply", reply_text)

                    elif async_result.get("type") == "task_error":
                        error_msg = async_result.get("error", "Unknown async error.")
                        self._set_status_message(f"Async Error: {error_msg[:100]}")

                        task_type = async_result.get("task_type", "AI task")
                        panel_title = f"Error: {task_type.replace('_', ' ').title()}"
                        panel_content = (
                            "An error occurred while processing your request.\n\n"
                            f"Details:\n{error_msg}"
                        )
                        self.show_ai_panel(panel_title, panel_content)

                    # Any message from the async queue is considered a state change.
                    any_state_changed_by_queues = True
            except queue.Empty:
                pass

        # 5. Lint panel auto-hide logic.
        # This keeps the linter panel visible for a minimum duration after results arrive
        # to prevent it from flashing on the screen for just one frame.
        if self.lint_panel_active and self.lint_panel_message:
            if hasattr(self, "drawer") and hasattr(
                self.drawer, "_keep_lint_panel_alive"
            ):
                self.drawer._keep_lint_panel_alive()

        return any_state_changed_by_queues

    # ------------------  Main editor loop  ------------------------
    def run(self) -> None:
        """The main event loop of the editor.

        This loop orchestrates all top-level operations by delegating tasks to
        specialized helper methods. It runs continuously until the `self.running`
        flag is set to False, typically by the `exit_editor` method.

        The loop is designed to be non-blocking and efficient, performing actions
        only when necessary. Its responsibilities are divided into two main phases,
        handled by `_process_events_and_input` and `_render_screen` respectively.

        It also includes top-level exception handling to catch critical errors
        (like `KeyboardInterrupt` for Ctrl+C) and ensure a graceful shutdown
        by calling `exit_editor`.
        """
        logger.info("Editor main loop started.")
        self.running = True
        self._force_full_redraw = True

        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)

        while self.running:
            try:
                # Phase 1: Process all incoming data (background events and user input)
                redraw_needed = self._process_events_and_input()

                # Phase 2: Update the UI, but only if a change occurred
                self._render_screen(redraw_needed)

            except KeyboardInterrupt:
                logger.info(
                    "Main loop interrupted by KeyboardInterrupt. Initiating exit sequence."
                )
                self.exit_editor()
                break
            except Exception as e:
                logger.critical(
                    "Unhandled exception in main loop: %s", e, exc_info=True
                )
                self.exit_editor()
                break

        logger.info("Editor main loop finished.")

    def _process_events_and_input(self) -> bool:
        """Processes all non-UI events for a single main loop iteration, including
        background task results and user input.

        This method acts as the central hub for event processing and is the first
        phase of the main loop. It performs the following steps:

        1.  It begins by polling all asynchronous queues (`_process_all_queues`)
            for results from background tasks like Git operations, shell commands,
            or AI requests.
        2.  Next, it reads a key press from the terminal using the KeyBinder.
        3.  Crucially, it provides special handling for the `curses.KEY_RESIZE`
            event. This event is intercepted and handled globally by calling
            `self.handle_resize()` directly, ensuring that both the main editor
            and any active panels are correctly resized regardless of the current
            focus.
        4.  All other key events are passed to `_handle_input_dispatch` to be
            routed to the appropriate component (the editor or the active panel)
            based on the current focus.

        Returns:
            bool: True if any processed event or input resulted in a state change
                  that requires a UI redraw. False if no changes occurred.
        """
        redraw_needed = False

        # First, process any results from background tasks (Git, AI, shell, etc.).
        if self._process_all_queues():
            redraw_needed = True

        # Then, attempt to read a key press from the user.
        key_input = self.keybinder.get_key_input()

        # Proceed only if a valid key was received (not an error or timeout).
        if key_input != curses.ERR and key_input != -1:
            # Intercept the RESIZE key at the highest level, BEFORE dispatching it
            # to the focused component. This is a global event that affects the
            # entire UI.
            if key_input == curses.KEY_RESIZE:
                # Directly call the main resize handler. It is responsible for
                # resizing both the editor and the currently active panel.
                if self.handle_resize():
                    redraw_needed = True
            elif self._handle_input_dispatch(key_input):
                # For all other keys, use the standard dispatching logic, which respects
                # the current focus (either the editor or a panel).
                redraw_needed = True

        return redraw_needed

    def _handle_input_dispatch(self, key_input: Any) -> bool:
        """Dispatches a key press to the correct handler (panel or editor).

        This method determines the current focus of the application.
        - If the focus is on a panel (`self.focus == 'panel'`) and a panel is
          active, the key press is passed to the `PanelManager` for handling.
        - Otherwise, the key press is handled by the main editor's input handler
          (`self.handle_input`, which is an alias for `self.keybinder.handle_input`).

        Args:
            key_input: The key event received from curses.

        Returns:
            bool: The result from the called handler, indicating whether the key
                  press caused a state change (True) or not (False).
        """
        if (
            self.focus == "panel"
            and self.panel_manager
            and self.panel_manager.is_panel_active()
        ):
            return self.panel_manager.handle_key(key_input)
        return self.handle_input(key_input)

    def _render_screen(self, redraw_needed: bool) -> None:
        """Manages the screen redraw cycle, updating the UI only if necessary.

        This method is the second phase of the main loop. It redraws the screen
        only if `redraw_needed` is True or if a full redraw has been explicitly
        forced (`self._force_full_redraw`).

        The rendering process involves:
        1.  Calling `self.drawer.draw()` to render the main editor text area,
            line numbers, and status bar.
        2.  Calling `self.panel_manager.draw_active_panel()` to render any
            visible panel on top of the editor.
        3.  Positioning the cursor correctly based on the current focus using
            `self.drawer._position_cursor()` and `curses.curs_set()`.
        4.  Calling `curses.doupdate()` to perform a single, efficient update
            of the physical screen, preventing flicker.

        Args:
            redraw_needed (bool): A flag indicating if a state change occurred
                                  in the previous phase that requires a UI update.
        """
        if not redraw_needed and not self._force_full_redraw:
            return

        is_editor_focused = self.focus == "editor"

        self.drawer.draw()

        if self.panel_manager:
            self.panel_manager.draw_active_panel()

        if is_editor_focused:
            curses.curs_set(1)
            self.drawer._position_cursor()
        else:
            curses.curs_set(0)

        curses.doupdate()

        # Reset the full redraw flag after it has been handled
        self._force_full_redraw = False
