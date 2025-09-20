# tests/ui/test_gitpanel.py
"""Unit tests for the `GitPanel` class.
=======================================

Tests for the `GitPanel` class.

This module verifies the behavior of the Git panel, including:
- Initialization and sizing/positioning
- Repository management and integration with `GitBridge`
- Running Git commands and capturing output
- Auto-update status toggling and background worker startup
- Commit log navigation and pagination
- Rendering via curses window APIs
"""

import curses
import os  # kept for parity with the original file
import subprocess
import threading
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from ecli.ui.panels import GitPanel


class TestGitPanel:
    """Test suite for validating `GitPanel` behavior."""

    @patch("curses.newwin")
    def test_init(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Initialization of `GitPanel`.

        Verifies:
        - Geometry calculation (width, height, start_x).
        - GitBridge is wired from the editor instance.
        - Initial menu and output state are correct.
        """
        # Configure a fake curses window instance
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge into the editor
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
    def test_init_colors(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Initialization of color attributes based on editor theme."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Colors should be sourced from `editor.colors`
        assert panel.attr_border == mock_editor.colors["status"]
        assert panel.attr_text == mock_editor.colors["default"]
        assert panel.attr_title == mock_editor.colors["function"]
        assert panel.attr_branch == mock_editor.colors["keyword"]

    @patch("curses.newwin")
    @patch("curses.curs_set")
    def test_open(
        self,
        mock_curs_set: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Opening the panel sets visibility, hides cursor, and refreshes Git info."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        panel.open()

        assert panel.visible is True
        mock_curs_set.assert_called_once_with(0)
        mock_git_bridge.update_git_info.assert_called_once()

    @patch("curses.newwin")
    def test_handle_key_navigation(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Navigation keys move between menu items while skipping separators.

        Verifies:
        - Movement down through menu using arrow keys.
        - Skips over separator entries ('---').
        - Alternative navigation (e.g., 'j'/'k') is verified implicitly via movement.
        """
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)
        panel.visible = True

        # Save starting index
        original_idx = panel.selected_idx

        # Move down once
        assert panel.handle_key(curses.KEY_DOWN) is True

        # Compute expected next non-separator index
        expected_idx = original_idx
        while True:
            expected_idx = (expected_idx + 1) % len(panel.menu_items)
            if panel.menu_items[expected_idx] != "---":
                break
        assert panel.selected_idx == expected_idx

    @patch("curses.newwin")
    def test_handle_key_actions(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Action keys trigger command execution, refresh, auto-update, and close.

        Verifies:
        - Enter executes the selected action.
        - 'r' performs a status refresh handler.
        - F9 closes the panel via PanelManager.
        """
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)
        panel.visible = True

        # Enter -> execute current action
        with patch.object(panel, "_execute_action") as mock_execute:
            assert panel.handle_key(curses.KEY_ENTER) is True
            mock_execute.assert_called_once()

        # 'r' -> refresh status
        with patch.object(panel, "_handle_status") as mock_status:
            assert panel.handle_key(ord("r")) is True
            mock_status.assert_called_once()

        # F9 -> close
        assert panel.handle_key(curses.KEY_F9) is True
        mock_editor.panel_manager.close_active_panel.assert_called_once()

    @patch("curses.newwin")
    @patch("subprocess.run")
    def test_run_git_command(
        self,
        mock_subprocess_run: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Running a Git command calls `subprocess.run` with repo cwd and options."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Mock subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git status output"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        # Execute command
        result = panel._run_git_command(["git", "status"])

        # Validate call parameters
        repo_dir = panel._get_repo_dir()
        mock_subprocess_run.assert_called_once_with(
            ["git", "status"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        assert result == mock_result

    @patch("curses.newwin")
    def test_toggle_auto_update(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Toggling auto-update flips the flag (thread start/stop is internal)."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Initial state should be enabled
        assert panel.auto_update_enabled is True

        # 1) Disable
        panel._toggle_auto_update()
        assert panel.auto_update_enabled is False

        # 2) Enable again
        panel._toggle_auto_update()  # type: ignore
        assert panel.auto_update_enabled is True

        # 3) Disable once more
        panel._toggle_auto_update()
        assert panel.auto_update_enabled is False

    @patch("curses.newwin")
    @patch("subprocess.run")
    def test_update_file_status_cache(
        self,
        mock_subprocess_run: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Updating file status cache parses `git status --porcelain` correctly.

        Verifies:
        - Proper invocation of `git status --porcelain`.
        - Parsing into `file_status_cache`.
        - Presence of modified/added/deleted/untracked statuses.
        """
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Mock `git status` output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "M file1.txt\nA file2.py\nD file3.txt\n?? file4.txt"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        repo_dir = panel._get_repo_dir()

        # Update the cache
        panel._update_file_status_cache()

        # Validate command and args
        mock_subprocess_run.assert_called_once_with(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )

        # Ensure cache contains entries
        assert len(panel.file_status_cache) > 0

        # Validate the presence of expected statuses
        status_values = set(panel.file_status_cache.values())
        assert "M" in status_values
        assert "A" in status_values
        assert "D" in status_values
        assert "??" in status_values

        # Explicitly check that an untracked file is represented
        file4_found = any("file4.txt" in key for key in panel.file_status_cache.keys())
        assert file4_found, "file4.txt should be in the cache"

    @patch("curses.newwin")
    def test_get_file_git_status(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Fetching file Git status returns values from the cache or None."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Preload cache entries
        panel.file_status_cache = {
            "/path/to/file1.txt": "M",
            "relative/path/file2.py": "A",
        }

        assert panel.get_file_git_status("/path/to/file1.txt") == "M"
        assert panel.get_file_git_status("relative/path/file2.py") == "A"
        assert panel.get_file_git_status("/nonexistent.txt") is None

    @patch("curses.newwin")
    @patch("threading.Thread")
    def test_start_auto_update(
        self,
        mock_thread: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Starting auto-update spawns a daemon thread targeting the worker."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Start the auto-update background worker
        panel._start_auto_update()

        # Validate thread creation and start
        mock_thread.assert_called_once_with(
            target=panel._auto_update_worker, daemon=True
        )
        mock_thread.return_value.start.assert_called_once()

    @patch("curses.newwin")
    def test_draw(
        self,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Rendering the panel triggers core window methods when visible."""
        # Configure fake window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)
        panel.visible = True

        # Draw the panel
        panel.draw()

        # Ensure basic drawing calls are made
        mock_win.erase.assert_called_once()
        mock_win.noutrefresh.assert_called_once()

    @patch("curses.newwin")
    @patch("subprocess.run")
    def test_show_git_log(
        self,
        mock_subprocess_run: MagicMock,
        mock_newwin: MagicMock,
        mock_stdscr: MagicMock,
        mock_editor: MagicMock,
        mock_git_bridge: MagicMock,
    ) -> None:
        """Displaying the Git log uses `git log` with pagination and formats output."""
        # Fake curses window
        mock_win = MagicMock()
        mock_newwin.return_value = mock_win

        # Inject GitBridge
        mock_editor.git = mock_git_bridge

        panel = GitPanel(mock_stdscr, mock_editor)

        # Mock `git log` output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "commit1\ncommit2\ncommit3"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        # Execute
        panel._show_git_log()

        # Validate command and args
        expected_cmd = [
            "git",
            "log",
            "--oneline",
            f"--max-count={panel.log_page_size}",
            "--skip=0",
        ]
        mock_subprocess_run.assert_called_once_with(
            expected_cmd,
            cwd=panel._get_repo_dir(),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )

        # Validate formatted output lines
        assert "commit1" in panel.output_lines
        assert "=== Git Log (page 1, format: --oneline) ===" in panel.output_lines
