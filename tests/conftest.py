# tests/conftest.py
"""Pytest configuration with shared fixtures for the Ecli editor tests.

Compatibility: Python 3.13.5
Tooling: Ruff, uv, SonarQube, Pylance
Requirements: Mandatory type annotations, strict typing
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


# --- Automatic mocking of the curses module ---
@pytest.fixture(autouse=True)
def mock_curses_functions() -> Generator[None, None, None]:
    """Automatically mock `curses` functions for tests.

    This fixture prevents errors when code under test calls `curses` APIs in a
    test environment where `curses` has not been initialized via `initscr()`.

    Yields:
        None: Context manager-style generator to apply and then remove the mock.
    """
    # Create a full mock of the curses module
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

    # Replace the entire curses module with our mock
    with patch.dict("sys.modules", {"curses": curses_mock}):
        # Also replace curses in the current module
        import sys

        if "curses" in sys.modules:
            del sys.modules["curses"]

        # Re-import to ensure our mock is used
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


# --- Base fixtures for curses and configuration ---
@pytest.fixture
def mock_stdscr() -> MagicMock:
    """Create a mock of the `curses` stdscr for testing UI components.

    Returns:
        MagicMock: A mocked `stdscr` with terminal size set to (24, 80).
    """
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)  # Typical terminal size
    return stdscr


@pytest.fixture
def mock_config() -> dict[str, dict[str, Any]]:
    """Provide a baseline configuration for Ecli tests.

    Returns:
        dict[str, dict[str, Any]]: Editor configuration dictionary.
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


# --- Ecli fixtures ---
@pytest.fixture
def mock_editor() -> Mock:
    """Create a comprehensive mock of the main Ecli editor.

    The mock includes attributes and methods used by panels and integrations:
    - Color schemes
    - Configuration
    - Status/focus/clipboard controls
    - File operations
    - Panel manager APIs

    Returns:
        Mock: Configured mock of an `Ecli` instance.
    """
    editor = Mock(spec=Ecli)

    # Color schemes for panels
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

    # Editor configuration and core state
    editor.config = {}
    editor.filename = "/path/to/test_file.py"
    editor.focus = "editor"

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

    # Panel manager mocks
    editor.panel_manager = MagicMock()
    editor.panel_manager.close_active_panel = MagicMock()
    editor.panel_manager.active_panel = None

    # Status/clipboard helpers
    editor._set_status_message = MagicMock()

    # File operation mocks
    editor.open_file = MagicMock()
    editor.insert_text = MagicMock()
    editor.exit_editor = MagicMock()
    editor.toggle_file_browser = MagicMock()
    editor.toggle_focus = MagicMock()

    # UI mocks
    editor.prompt = MagicMock()
    editor._force_full_redraw = MagicMock()
    editor.redraw = MagicMock()

    # Integrations
    editor.git = None
    editor.linter_bridge = None

    return editor


@pytest.fixture
def real_editor(mock_stdscr: MagicMock, mock_config: dict[str, dict[str, Any]]) -> Ecli:
    """Create a real `Ecli` instance with mocked dependencies.

    Use this fixture to test the logic of the `Ecli` class itself rather than its
    interactions with other components.

    Args:
        mock_stdscr: Mocked curses window.
        mock_config: Editor configuration.

    Returns:
        Ecli: A real `Ecli` instance with dependencies mocked out.
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
        # Mock `curses` inside ecli.core.Ecli as well
        patch("ecli.core.Ecli.curses") as mock_curses,
    ):
        # Configure the curses mock
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

        # Instantiate with mocked dependencies
        editor = Ecli(mock_stdscr, mock_config, lightweight_mode=True)

        return editor


# --- Integration fixtures ---
@pytest.fixture
def mock_git_bridge() -> Mock:
    """Create a `GitBridge` mock for testing GitPanel and Git integrations.

    Returns:
        Mock: Configured `GitBridge` mock with sample data.
    """
    git_bridge = Mock(spec=GitBridge)
    git_bridge.info = ("* main", "user@example.com", "123")
    git_bridge.update_git_info = MagicMock()
    return git_bridge


@pytest.fixture
def mock_linter_bridge() -> Mock:
    """Create a `LinterBridge` mock for testing linter/LSP integrations.

    Returns:
        Mock: Configured `LinterBridge` mock.
    """
    linter_bridge = Mock(spec=LinterBridge)
    linter_bridge.run_linter = MagicMock(return_value=True)
    linter_bridge.shutdown = MagicMock()
    linter_bridge.reload_devops_module = MagicMock(return_value=True)
    return linter_bridge


# --- Filesystem fixtures ---
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with sample files and subdirectories.

    The structure includes:
    - file1.txt: Plain text file
    - file2.py: Python file
    - subdir/: Subdirectory containing subfile.txt

    Yields:
        Path: Path object pointing to the temporary directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create sample files
        (tmp_path / "file1.txt").write_text("Content of file1")
        (tmp_path / "file2.py").write_text("print('Hello, world!')")

        # Create subdirectory with a file
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("Content of subfile")

        yield tmp_path


# --- Helper fixtures ---
@pytest.fixture
def sample_text() -> list[str]:
    """Provide a sample code snippet as a list of lines.

    Returns:
        list[str]: Code lines for use in tests.
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
    """Create a mock of `queue.Queue` for async operations.

    Returns:
        Mock: Mocked `queue.Queue`.
    """
    return Mock(spec=queue.Queue)


@pytest.fixture
def mock_threading_event() -> Mock:
    """Create a mock of `threading.Event`.

    Returns:
        Mock: Mocked `threading.Event`.
    """
    return Mock(spec=threading.Event)


# --- Test data fixtures ---
@pytest.fixture
def test_file_content() -> str:
    """Provide test file contents as a string.

    Returns:
        str: The contents of a test file.
    """
    return """def test_function():
    \"\"\"This is a test function.\"\"\"
    return True
"""


@pytest.fixture
def test_file_path(temp_dir: Path) -> Path:
    """Create a test file in the temporary directory.

    Args:
        temp_dir: Temporary directory path.

    Returns:
        Path: Path to the created test file.
    """
    test_file = temp_dir / "test_file.py"
    test_file.write_text("print('Hello, world!')")
    return test_file


# --- Scenario fixtures ---
@pytest.fixture
def editor_with_text(real_editor: Ecli, sample_text: list[str]) -> Ecli:
    """Provide an `Ecli` instance preloaded with sample text.

    Args:
        real_editor: Real editor instance.
        sample_text: Code lines to preload.

    Returns:
        Ecli: The editor with text loaded into the buffer.
    """
    real_editor.text = sample_text.copy()
    return real_editor


@pytest.fixture
def editor_with_selection(real_editor: Ecli, sample_text: list[str]) -> Ecli:
    """Provide an `Ecli` instance with a selected text region.

    Args:
        real_editor: Real editor instance.
        sample_text: Code lines to preload.

    Returns:
        Ecli: The editor with an active selection.
    """
    real_editor.text = sample_text.copy()
    real_editor.is_selecting = True
    real_editor.selection_start = (1, 4)  # Selection start
    real_editor.selection_end = (2, 10)  # Selection end
    return real_editor
