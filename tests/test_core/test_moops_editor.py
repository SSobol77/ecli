# tests/test_core/test_moops_editor.py
"""Test suite for the Ecli class.
=================================

Comprehensive test suite for the `Ecli` class.

This module validates the following functionality:

1. Status message handling
   - Setting simple status messages.
   - Handling linting messages and activating/deactivating the lint panel.
   - Exception handling during status updates.

2. Initialization
   - Verification of core attributes and default state.
   - Component initialization (History, Commenter, Drawer, KeyBinder).
   - Lightweight mode initialization.

3. Closing the editor
   - Proper shutdown of background tasks and linter integration.

4. Focus handling
   - Switching between editor and panel focus.
   - Handling absence of active panels.

5. Git panel integration
   - Behavior when Git integration is missing or not in a repository.
   - Successful display of the Git panel.

6. Comment toggling
   - With and without text selections.

7. Linter integration
   - Reloading DevOps modules.
   - Running linter asynchronously.
   - Showing/hiding the lint panel with or without messages.

8. Clipboard integration (pyclip)
   - Availability checks.
   - Copying to internal and system clipboards.
   - Handling exceptions.

9. Text selection
   - Retrieving selected text across single and multiple lines.

10. Text manipulation
    - Normalizing selection ranges.
    - Deleting text in single or multiple lines.
    - Handling invalid deletion ranges with error logging.

11. Indentation handling
    - Smart unindent logic for selected blocks and current line.

12. Syntax highlighting
    - Tokenization with custom rules, no lexer, and with a lexer.


Usage
-----
Run just this file:

    pytest -q tests/test_core/test_moops_editor.py

Run a single test by node id:

    pytest -q tests/test_core/test_moops_editor.py::TestEcli::test_set_status_message_simple

Increase verbosity and show captured logs:

    pytest -vv -s tests/test_core/test_moops_editor.py

"""

from __future__ import annotations

import curses
import queue
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, patch

import pytest

from ecli.core.AsyncEngine import AsyncEngine
from ecli.core.CodeCommenter import CodeCommenter
from ecli.core.Ecli import Ecli
from ecli.core.History import History
from ecli.integrations.GitBridge import GitBridge
from ecli.integrations.LinterBridge import LinterBridge
from ecli.ui.DrawScreen import DrawScreen
from ecli.ui.KeyBinder import KeyBinder
from ecli.ui.PanelManager import PanelManager
from ecli.ui.panels import FileBrowserPanel, GitPanel


class TestEcli:
    """Grouped tests for the `Ecli` class."""

    # === Tests for _set_status_message ===
    def test_set_status_message_simple(self, real_editor: Ecli) -> None:
        """Verify that a simple status message is set correctly."""
        real_editor._set_status_message("Test message")
        assert real_editor.status_message == "Test message"

    def test_set_status_message_with_lint_status(self, real_editor: Ecli) -> None:
        """Verify status message handling when linting information is provided."""
        real_editor._set_status_message(
            "Lint message",
            is_lint_status=True,
            full_lint_output="Lint output",
            activate_lint_panel_if_issues=True,
        )
        assert real_editor.status_message == "Lint message"
        assert real_editor.lint_panel_message == "Lint output"

    def test_set_status_message_activates_lint_panel(self, real_editor: Ecli) -> None:
        """Verify that the lint panel activates when issues are found."""
        real_editor._set_status_message(
            "Issues found",
            is_lint_status=True,
            full_lint_output="Error: syntax error",
            activate_lint_panel_if_issues=True,
        )
        assert real_editor.lint_panel_active is True

    def test_set_status_message_no_issues(self, real_editor: Ecli) -> None:
        """Verify that the lint panel does not activate if no issues are found."""
        real_editor._set_status_message(
            "No issues",
            is_lint_status=True,
            full_lint_output="No issues found",
            activate_lint_panel_if_issues=True,
        )
        assert real_editor.lint_panel_active is False

    def test_set_status_message_exception_handling(
        self, real_editor: Ecli, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify exception handling when setting a status message."""
        with patch.object(
            real_editor, "_handle_lint_status", side_effect=Exception("Test error")
        ):
            real_editor._set_status_message("Test", is_lint_status=True)
            assert "Status update error" in real_editor.status_message

    # === Tests for _handle_lint_status ===
    def test_handle_lint_status_updates_message(self, real_editor: Ecli) -> None:
        """Verify lint panel message is updated correctly."""
        real_editor._handle_lint_status("New lint output", False)
        assert real_editor.lint_panel_message == "New lint output"

    def test_handle_lint_status_activates_panel(self, real_editor: Ecli) -> None:
        """Verify lint panel activates when errors exist."""
        real_editor.lint_panel_message = "Error: syntax error"
        real_editor._handle_lint_status(None, True)
        assert real_editor.lint_panel_active is True

    def test_handle_lint_status_no_activation_for_no_issues(
        self, real_editor: Ecli
    ) -> None:
        """Verify lint panel does not activate if no issues are reported."""
        real_editor.lint_panel_message = "No issues found"
        real_editor._handle_lint_status(None, True)
        assert real_editor.lint_panel_active is False

    # === Tests for __init__ ===
    def test_init_basic_attributes(self, real_editor: Ecli) -> None:
        """Verify initialization of core attributes."""
        assert real_editor.text == [""]
        assert real_editor.cursor_x == 0
        assert real_editor.cursor_y == 0
        assert real_editor.modified is False
        assert real_editor.insert_mode is True
        assert real_editor.status_message == "Ready"

    def test_init_components(self, real_editor: Ecli) -> None:
        """Verify component initialization in lightweight mode."""
        # In lightweight_mode, heavy components are replaced by mocks
        assert isinstance(real_editor.history, Mock)
        assert isinstance(real_editor.commenter, Mock)
        assert isinstance(real_editor.drawer, Mock)
        assert isinstance(real_editor.keybinder, Mock)

    def test_init_lightweight_mode(
        self, mock_stdscr: MagicMock, mock_config: dict[str, dict[str, Any]]
    ) -> None:
        """Verify initialization when `lightweight_mode=True`."""
        with (
            patch("ecli.core.Ecli.DrawScreen"),
            patch("ecli.core.Ecli.KeyBinder"),
            patch("ecli.core.Ecli.History"),
            patch("ecli.core.Ecli.CodeCommenter"),
            patch("ecli.core.Ecli.curses") as mock_curses,
        ):
            # Configure curses mock to avoid attribute comparison errors
            mock_curses.COLORS = 256
            mock_curses.COLOR_PAIRS = 256
            mock_curses.has_colors.return_value = True

            editor = Ecli(mock_stdscr, mock_config, lightweight_mode=True)
            assert editor.is_lightweight is True
            assert isinstance(editor.git, Mock)
            assert isinstance(editor.linter_bridge, Mock)

    # === Tests for close ===
    def test_close_stops_background_tasks(self, real_editor: Ecli) -> None:
        """Verify that closing stops background tasks."""
        real_editor._auto_save_stop_event = threading.Event()
        real_editor.close()
        assert real_editor._auto_save_stop_event.is_set() is True

    def test_close_shuts_down_linter(self, real_editor: Ecli) -> None:
        """Verify that closing shuts down the linter bridge if active."""
        mock_linter = Mock()
        real_editor.linter_bridge = mock_linter
        real_editor.close()
        mock_linter.shutdown.assert_called_once()

    # === Tests for toggle_focus ===
    def test_toggle_focus_no_panel(self, real_editor: Ecli) -> None:
        """Verify focus toggling when no panel is active."""
        real_editor.panel_manager = Mock()
        real_editor.panel_manager.is_panel_active.return_value = False
        result = real_editor.toggle_focus()
        assert result is True
        assert "No active panel" in real_editor.status_message

    def test_toggle_focus_to_panel(self, real_editor: Ecli) -> None:
        """Verify focus switches to panel mode when a panel is active."""
        real_editor.panel_manager = Mock()
        real_editor.panel_manager.is_panel_active.return_value = True
        real_editor.focus = "editor"

        # Mock curses.curs_set to avoid runtime errors in tests
        with patch("ecli.core.Ecli.curses.curs_set"):
            result = real_editor.toggle_focus()
            assert result is True
            assert real_editor.focus == "panel"
            assert real_editor.status_message == "Focus: Panel"

    def test_toggle_focus_to_editor(self, real_editor: Ecli) -> None:
        """Verify focus switches back to editor mode."""
        real_editor.panel_manager = Mock()
        real_editor.panel_manager.is_panel_active.return_value = True
        real_editor.focus = "panel"

        with patch("ecli.core.Ecli.curses.curs_set"):
            result = real_editor.toggle_focus()
            assert result is True
            assert real_editor.focus == "editor"
            assert real_editor.status_message == "Focus: Editor"

    # === Tests for show_git_panel ===
    def test_show_git_panel_no_git(self, real_editor: Ecli) -> None:
        """Verify Git panel behavior when Git integration is disabled."""
        real_editor.git = None
        real_editor.git_panel_instance = None
        result = real_editor.show_git_panel()
        assert result is True
        assert "Git panel not available" in real_editor.status_message

    def test_show_git_panel_not_repo(self, real_editor: Ecli, temp_dir: Path) -> None:
        """Verify Git panel behavior outside of a Git repository."""
        real_editor.git = Mock()
        real_editor.filename = str(temp_dir / "test.txt")
        real_editor.git_panel_instance = Mock()
        real_editor.panel_manager = Mock()

        with patch("pathlib.Path.is_dir", return_value=False):
            result = real_editor.show_git_panel()
            assert result is True
            assert "Not a Git repository" in real_editor.status_message

    def test_show_git_panel_success(self, real_editor: Ecli, temp_dir: Path) -> None:
        """Verify successful Git panel display inside a repository."""
        real_editor.git = Mock()
        real_editor.filename = str(temp_dir / "test.txt")
        real_editor.git_panel_instance = Mock()
        real_editor.panel_manager = Mock()

        with patch("pathlib.Path.is_dir", return_value=True):
            result = real_editor.show_git_panel()
            assert result is True
            real_editor.panel_manager.show_panel_instance.assert_called_once()

    # === Tests for toggle_comment_block ===
    def test_toggle_comment_block_no_selection(self, real_editor: Ecli) -> None:
        """Verify comment toggling when no text is selected."""
        real_editor.cursor_y = 5
        real_editor.commenter = Mock()

        result = real_editor.toggle_comment_block()
        assert result is True
        real_editor.commenter.perform_toggle.assert_called_once_with(5, 5)

    def test_toggle_comment_block_with_selection(self, real_editor: Ecli) -> None:
        """Verify comment toggling when a text selection exists."""
        real_editor.is_selecting = True
        real_editor.selection_start = (2, 0)
        real_editor.selection_end = (5, 0)
        real_editor.commenter = Mock()

        result = real_editor.toggle_comment_block()
        assert result is True
        real_editor.commenter.perform_toggle.assert_called_once_with(2, 4)

    # === Tests for reload_devops_module ===
    def test_reload_devops_module_no_linter(self, real_editor: Ecli) -> None:
        """Verify behavior when trying to reload DevOps module without linter."""
        real_editor.linter_bridge = None
        result = real_editor.reload_devops_module()
        assert result is False
        assert "Linter component is not active" in real_editor.status_message

    def test_reload_devops_module_success(self, real_editor: Ecli) -> None:
        """Verify successful reload of the DevOps module."""
        mock_linter = Mock()
        mock_linter.reload_devops_module.return_value = True
        real_editor.linter_bridge = mock_linter

        result = real_editor.reload_devops_module()
        assert result is True
        mock_linter.reload_devops_module.assert_called_once()

    # === Tests for run_lint_async ===
    def test_run_lint_async_no_linter(self, real_editor: Ecli) -> None:
        """Verify lint execution when no linter is active."""
        real_editor.linter_bridge = None
        result = real_editor.run_lint_async()
        assert result is True
        assert "Linter component is not active" in real_editor.status_message

    def test_run_lint_async_success(self, real_editor: Ecli) -> None:
        """Verify successful lint execution."""
        mock_linter = Mock()
        mock_linter.run_linter.return_value = True
        real_editor.linter_bridge = mock_linter

        result = real_editor.run_lint_async("code")
        assert result is True
        mock_linter.run_linter.assert_called_once_with("code")

    # === Tests for show_lint_panel ===
    def test_show_lint_panel_hide_active(self, real_editor: Ecli) -> None:
        """Verify hiding the lint panel when it is active."""
        real_editor.lint_panel_active = True
        result = real_editor.show_lint_panel()
        assert result is True
        assert real_editor.lint_panel_active is False
        assert "Lint panel hidden" in real_editor.status_message

    def test_show_lint_panel_show_with_message(self, real_editor: Ecli) -> None:
        """Verify showing the lint panel when a message is present."""
        real_editor.lint_panel_active = False
        real_editor.lint_panel_message = "Lint results"
        result = real_editor.show_lint_panel()
        assert result is True
        assert real_editor.lint_panel_active is True

    def test_show_lint_panel_no_message(self, real_editor: Ecli) -> None:
        """Verify lint panel behavior when no message is available."""
        real_editor.lint_panel_active = False
        real_editor.lint_panel_message = ""
        result = real_editor.show_lint_panel()
        assert result is True
        assert real_editor.lint_panel_active is False
        assert "No linting information" in real_editor.status_message

    # === Tests for _check_pyclip_availability ===
    def test_check_pyclip_disabled_in_config(self, real_editor: Ecli) -> None:
        """Verify clipboard check when disabled in config."""
        real_editor.config["editor"]["use_system_clipboard"] = False
        result = real_editor._check_pyclip_availability()
        assert result is False

    @patch("ecli.core.Ecli.pyperclip")
    def test_check_pyclip_available(
        self, mock_pyperclip: Mock, real_editor: Ecli
    ) -> None:
        """Verify clipboard availability when pyperclip is functional."""
        mock_pyperclip.copy.return_value = None
        result = real_editor._check_pyclip_availability()
        assert result is True

    @patch("ecli.core.Ecli.pyperclip")
    def test_check_pyclip_exception(
        self, mock_pyperclip: Mock, real_editor: Ecli
    ) -> None:
        """Verify exception handling when checking pyclip availability."""

        class MockPyperclipException(Exception):
            """Custom exception to simulate pyperclip errors."""

        # Patch the specific exception class used by Ecli
        with patch(
            "ecli.core.Ecli.pyperclip.PyperclipException",
            MockPyperclipException,
        ):
            mock_pyperclip.copy.side_effect = MockPyperclipException("Clipboard error")
            result = real_editor._check_pyclip_availability()
            assert result is False

    # === Tests for get_selected_text ===
    def test_get_selected_text_no_selection(self, real_editor: Ecli) -> None:
        """Verify that no text is returned when nothing is selected."""
        real_editor.is_selecting = False
        result = real_editor.get_selected_text()
        assert result == ""

    def test_get_selected_text_single_line(self, editor_with_text: Ecli) -> None:
        """Verify correct selection when text is selected on a single line."""
        editor_with_text.is_selecting = True
        editor_with_text.selection_start = (0, 2)
        editor_with_text.selection_end = (0, 5)
        result = editor_with_text.get_selected_text()
        assert result == "f h"

    def test_get_selected_text_multi_line(self, editor_with_text: Ecli) -> None:
        """Verify correct selection across multiple lines."""
        editor_with_text.is_selecting = True
        editor_with_text.selection_start = (0, 2)
        editor_with_text.selection_end = (2, 3)
        result = editor_with_text.get_selected_text()
        assert result == "f hello_world():\n    # This is a comment\n   "

    # === Tests for copy ===
    def test_copy_no_selection(self, real_editor: Ecli) -> None:
        """Verify copying when no selection is made."""
        real_editor.is_selecting = False
        result = real_editor.copy()
        assert result is True
        assert "Nothing to copy" in real_editor.status_message

    @patch("ecli.core.Ecli.pyperclip")
    def test_copy_to_internal_clipboard(
        self, mock_pyperclip: Mock, editor_with_text: Ecli
    ) -> None:
        """Verify copying text to the internal clipboard."""
        editor_with_text.is_selecting = True
        editor_with_text.selection_start = (0, 0)
        editor_with_text.selection_end = (0, 5)
        editor_with_text.use_system_clipboard = False

        result = editor_with_text.copy()
        assert result is True
        assert editor_with_text.internal_clipboard == "def h"
        assert "Copied to internal clipboard" in editor_with_text.status_message

    @patch("ecli.core.Ecli.pyperclip")
    def test_copy_to_system_clipboard(
        self, mock_pyperclip: Mock, editor_with_text: Ecli
    ) -> None:
        """Verify copying text to the system clipboard."""
        editor_with_text.is_selecting = True
        editor_with_text.selection_start = (0, 0)
        editor_with_text.selection_end = (0, 5)
        editor_with_text.use_system_clipboard = True
        editor_with_text.pyclip_available = True

        result = editor_with_text.copy()
        assert result is True
        mock_pyperclip.copy.assert_called_once_with("def h")
        assert "Copied to system clipboard" in editor_with_text.status_message

    # === Tests for _get_normalized_selection_range ===
    def test_get_normalized_selection_range_no_selection(
        self, real_editor: Ecli
    ) -> None:
        """Verify normalization returns None when nothing is selected."""
        real_editor.is_selecting = False
        result = real_editor._get_normalized_selection_range()
        assert result is None

    def test_get_normalized_selection_range_already_normalized(
        self, real_editor: Ecli
    ) -> None:
        """Verify normalization returns the same range if already normalized."""
        real_editor.is_selecting = True
        real_editor.selection_start = (2, 3)
        real_editor.selection_end = (5, 7)
        result = real_editor._get_normalized_selection_range()
        assert result == ((2, 3), (5, 7))

    def test_get_normalized_selection_range_swapped(self, real_editor: Ecli) -> None:
        """Verify normalization correctly swaps inverted ranges."""
        real_editor.is_selecting = True
        real_editor.selection_start = (5, 7)
        real_editor.selection_end = (2, 3)
        result = real_editor._get_normalized_selection_range()
        assert result == ((2, 3), (5, 7))

    # === Tests for delete_text_internal ===
    def test_delete_text_internal_single_line(self, editor_with_text: Ecli) -> None:
        """Verify deleting a single-line text range."""
        # Preserve original text for verification
        original_text = editor_with_text.text.copy()
        editor_with_text.delete_text_internal(0, 2, 0, 5)

        # Text must change and `modified` flag must be set
        assert editor_with_text.text != original_text
        assert editor_with_text.modified is True

        # First line should equal the beginning of original + end after deletion
        expected_first_line = original_text[0][:2] + original_text[0][5:]
        assert editor_with_text.text[0] == expected_first_line

        # Remaining lines should be unchanged
        assert editor_with_text.text[1:] == original_text[1:]

    def test_delete_text_internal_multi_line(self, editor_with_text: Ecli) -> None:
        """Verify deleting a multi-line text range."""
        original_text = editor_with_text.text.copy()
        editor_with_text.delete_text_internal(0, 2, 2, 3)

        # Text must change and `modified` flag must be set
        assert editor_with_text.text != original_text
        assert editor_with_text.modified is True

        # First line = prefix of line 0 + suffix of line 2
        expected_first_line = original_text[0][:2] + original_text[2][3:]
        assert editor_with_text.text[0] == expected_first_line

        # Middle lines removed; total lines reduced by 2
        assert len(editor_with_text.text) == len(original_text) - 2
        assert editor_with_text.text[1:] == original_text[3:]

    def test_delete_text_internal_invalid_range(
        self, editor_with_text: Ecli, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify behavior for invalid deletion ranges (with logging)."""
        original_text = editor_with_text.text.copy()
        editor_with_text.delete_text_internal(0, 0, 5, 0)

        # Text should remain unchanged and error should be logged
        assert editor_with_text.text == original_text
        assert "row index out of bounds" in caplog.text

    # === Tests for handle_smart_unindent ===
    def test_handle_smart_unindent_with_selection(self, real_editor: Ecli) -> None:
        """Verify smart unindent uses block unindent when a selection exists."""
        real_editor.is_selecting = True
        with patch.object(
            real_editor, "handle_block_unindent", return_value=True
        ) as mock_unindent:
            result = real_editor.handle_smart_unindent()
            assert result is True
            mock_unindent.assert_called_once()

    def test_handle_smart_unindent_no_selection(self, real_editor: Ecli) -> None:
        """Verify smart unindent operates on the current line when no selection exists."""
        real_editor.is_selecting = False
        with patch.object(
            real_editor, "unindent_current_line", return_value=True
        ) as mock_unindent:
            result = real_editor.handle_smart_unindent()
            assert result is True
            mock_unindent.assert_called_once()

    # === Tests for _get_tokenized_line ===
    def test_get_tokenized_line_custom_rules(self, real_editor: Ecli) -> None:
        """Verify tokenization path using custom syntax rules."""
        real_editor.custom_syntax_patterns = []
        with patch.object(
            real_editor, "apply_custom_highlighting", return_value=[("text", 1)]
        ) as mock_highlight:
            result = real_editor._get_tokenized_line("test line", 1, True)
            assert result == [("text", 1)]
            mock_highlight.assert_called_once_with("test line")

    def test_get_tokenized_line_no_lexer(self, real_editor: Ecli) -> None:
        """Verify tokenization fallback when no lexer is available."""
        real_editor._lexer = None
        real_editor.colors = {"default": 1}
        result = real_editor._get_tokenized_line("test line", 1, False)
        assert result == [("test line", 1)]

    @patch("ecli.core.Ecli.lex")
    def test_get_tokenized_line_with_lexer(
        self, mock_lex: Mock, real_editor: Ecli
    ) -> None:
        """Verify tokenization when a lexer is available."""
        mock_lexer = Mock()
        real_editor._lexer = mock_lexer
        real_editor.colors = {"default": 1}
        mock_lex.return_value = [("Token.Text", "test")]

        # Mock curses.color_pair to avoid runtime issues in tests
        with patch("ecli.core.Ecli.curses.color_pair", return_value=1):
            result = real_editor._get_tokenized_line("test", 1, False)
            assert len(result) == 1
            mock_lex.assert_called_once()
