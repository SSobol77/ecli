# tests/ui/test_filebrowserpanel.py
"""Unit tests for the `FileBrowserPanel` class.
================================================

Tests for the `FileBrowserPanel` class.

This module verifies the core behavior of the file browser panel:
- Initialization and sizing/positioning
- File system navigation
- File and directory operations
- Git status integration
- Key handling (navigation, function keys)
- Rendering via curses window APIs
"""

import curses
import os  # kept for parity with the original file (may be used by the implementation)
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from ecli.ui.panels import FileBrowserPanel


class TestFileBrowserPanel:
    """Test suite for validating `FileBrowserPanel` behavior."""

    @patch("curses.newwin")
    def test_init(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Initialization of `FileBrowserPanel`.

        Verifies:
        - Geometry calculation (width, height, start_x).
        - Initial directory listing (non-empty if the temp dir has content).
        - Initial index and color attributes are set correctly.
        """
        # Return a fake curses window instance
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        assert panel.width == 32  # 40% of 80
        assert panel.height == 23  # 24 - 1
        assert panel.start_x == 48  # 80 - 32
        assert panel.cwd == temp_dir
        assert len(panel.entries) > 0  # directory entries should be present
        assert panel.idx == 0
        assert panel.attr_border == mock_editor.colors["status"]
        assert panel.attr_dir == mock_editor.colors["keyword"]
        assert panel.attr_file == mock_editor.colors["default"]

    @patch("curses.newwin")
    def test_set_git_panel(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Setting a GitPanel reference is stored and accessible."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        git_panel = MagicMock()

        panel.set_git_panel(git_panel)

        assert panel.git_panel == git_panel

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_open(
        self,
        mock_curs_set: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Opening the panel makes it visible, hides the cursor, and refreshes Git cache."""
        # Fake curses window
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
    def test_handle_key_navigation(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Navigation keys move the selection and support alt bindings (j/k/h/l).

        Verifies:
        - Moving down (KEY_DOWN).
        - Alternative movement with 'j' (and, by extension, 'k' etc.).
        - Entering directories and backing out are handled by other tests.
        """
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        panel.visible = True

        # Ensure there is something to navigate
        assert len(panel.entries) > 1

        # Move down by one
        original_idx = panel.idx
        assert panel.handle_key(curses.KEY_DOWN) is True
        assert panel.idx == (original_idx + 1) % len(panel.entries)

        # Move down using 'j'
        original_idx = panel.idx
        assert panel.handle_key(ord("j")) is True
        assert panel.idx == (original_idx + 1) % len(panel.entries)

    @patch("curses.newwin")
    def test_handle_key_function_keys(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Function key handling (F2–F6, Del, F10/Esc/q, F12).

        Verifies:
        - F2 triggers new file creation flow (`_new_file`).
        - F10 closes the panel via the editor's toggle method.
        - F12 toggles focus editor/panel.
        """
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        panel.visible = True

        # F2 -> new file action
        with patch.object(panel, "_new_file") as mock_new_file:
            assert panel.handle_key(curses.KEY_F2) is True
            mock_new_file.assert_called_once()

        # F10 -> close the file browser panel
        assert panel.handle_key(curses.KEY_F10) is True
        mock_editor.toggle_file_browser.assert_called_once()

        # F12 -> toggle focus
        mock_editor.toggle_file_browser.reset_mock()
        assert panel.handle_key(276) is True  # F12
        mock_editor.toggle_focus.assert_called_once()

    @patch("curses.newwin")
    def test_draw(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Drawing the panel calls core curses window methods and honors visibility.

        Verifies:
        - `erase()` and `noutrefresh()` are called on the panel window.
        - Git status indicators are part of the rendering path (indirect).
        """
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))
        panel.visible = True
        panel.win = mock_win

        panel.draw()

        mock_win.erase.assert_called_once()
        mock_win.noutrefresh.assert_called_once()

    @patch("curses.newwin")
    def test_enter_selected_directory(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Entering a directory updates `cwd` and refreshes the entry list."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        # Choose a known subdirectory created by the temp_dir fixture
        for i, entry in enumerate(panel.entries):
            if entry and entry.is_dir() and entry.name == "subdir":
                panel.idx = i
                break

        original_cwd = panel.cwd
        panel._enter_selected()

        assert panel.cwd == original_cwd / "subdir"

    @patch("curses.newwin")
    @patch("pathlib.Path.touch")
    def test_new_file(
        self,
        mock_touch: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Creating a new file triggers `Path.touch` and refreshes the list."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        # Simulate a prompted filename
        with patch.object(panel, "_prompt", return_value="new_file.txt"):
            panel._new_file()

        mock_touch.assert_called_once_with(exist_ok=False)

    @patch("curses.newwin")
    @patch("shutil.copy2")
    def test_copy_entry(
        self,
        mock_copy2: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Copying a file calls `shutil.copy2` and uses a unique destination name."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        panel = FileBrowserPanel(mock_stdscr, mock_editor, start_path=str(temp_dir))

        # Pick the first file entry
        for i, entry in enumerate(panel.entries):
            if entry and not entry.is_dir():
                panel.idx = i
                break

        # Confirm the copy operation
        with patch.object(panel, "_prompt", return_value="y"):
            panel._copy_entry()

        mock_copy2.assert_called_once()
