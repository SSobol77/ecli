# tests/ui/test_PanelManager.py
"""Unit tests PanelManager class.
=================================

Tests for the `PanelManager` class.

This module validates the orchestration logic responsible for registering,
showing, replacing, toggling, and closing UI panels, as well as delegating
key handling and draw calls to the active panel.

Covered areas:
- Initialization and panel registry bootstrap
- Active panel detection (`is_panel_active`)
- Showing panels by name (`show_panel`)
- Showing a concrete panel instance (`show_panel_instance`)
- Closing the active panel (`close_active_panel`)
- Delegating key events (`handle_key`)
- Delegating rendering (`draw_active_panel`)

All tests keep the implementation isolated by mocking curses calls and
injecting lightweight panel doubles.
"""

import curses
from typing import Any, Dict, Optional, Type, Union, cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from ecli.ui.PanelManager import PanelManager
from ecli.ui.panels import AiResponsePanel, BasePanel, FileBrowserPanel


# ====== Dummy panel class used in tests =======


class DummyPanel(BasePanel):
    """A minimal panel used as a test double."""

    def __init__(self, stdscr: Any, editor: Any, **kwargs: Any) -> None:
        """Initialize the dummy panel with a visible state and stable geometry."""
        super().__init__(stdscr, editor)
        self.visible = True
        # Mock `getmaxyx` to avoid terminal-size errors in tests
        self.stdscr.getmaxyx = MagicMock(return_value=(24, 80))

    def open(self) -> None:
        """Open the panel (set visible to True)."""
        self.visible = True

    def close(self) -> None:
        """Close the panel (set visible to False)."""
        self.visible = False

    def handle_key(self, key: int | str) -> bool:
        """Handle a key press (always returns False in the dummy)."""
        return False

    def draw(self) -> None:
        """Render the panel (no-op for the dummy)."""
        pass


# ====== Fixtures =======


@pytest.fixture
def mock_editor() -> Mock:
    """Create a mock editor object compatible with `PanelManager` expectations."""
    editor = Mock()
    editor.stdscr = Mock()
    editor.stdscr.getmaxyx = MagicMock(return_value=(24, 80))
    editor.focus = "editor"
    editor._force_full_redraw = False
    editor._set_status_message = Mock()
    return editor


@pytest.fixture
def panel_manager(mock_editor: Mock) -> PanelManager:
    """Instantiate `PanelManager` with a mocked editor and silenced logging."""
    with patch("ecli.ui.PanelManager.logging"):
        return PanelManager(mock_editor)


@pytest.fixture
def mock_panel() -> Mock:
    """Provide a base mock panel with `visible=True`."""
    panel = Mock(spec=BasePanel)
    panel.visible = True
    return panel


# Globally mock `curses.curs_set` to avoid terminal dependency in tests
@pytest.fixture(autouse=True)
def mock_curses() -> Any:
    """Auto-applied fixture to mock `curses.curs_set` for all tests."""
    with patch("curses.curs_set"):
        yield


# ===== Initialization tests =======


def test_panel_manager_initialization(mock_editor: Mock) -> None:
    """`PanelManager` initializes with editor, registry, and no active panel."""
    with patch("ecli.ui.PanelManager.logging") as mock_logging:
        manager = PanelManager(mock_editor)
        assert manager.editor == mock_editor
        assert manager.active_panel is None
        assert "ai_response" in manager.registered_panels
        assert "file_browser" in manager.registered_panels
        mock_logging.info.assert_called_once()


# ====== is_panel_active tests ======


def test_is_panel_active_no_panel(panel_manager: PanelManager) -> None:
    """Returns False when no active panel is set."""
    assert not panel_manager.is_panel_active()


def test_is_panel_active_with_panel(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Returns True when a visible active panel exists."""
    panel_manager.active_panel = mock_panel
    assert panel_manager.is_panel_active()


def test_is_panel_active_invisible_panel(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Returns False when the active panel is not visible."""
    mock_panel.visible = False
    panel_manager.active_panel = mock_panel
    assert not panel_manager.is_panel_active()


# ====== show_panel tests ======


def test_show_panel_unknown_name(panel_manager: PanelManager) -> None:
    """Shows an error status when a panel name is not registered."""
    panel_manager.show_panel("unknown")

    # Explicit cast for mypy
    status_mock = cast(Mock, panel_manager.editor._set_status_message)
    status_mock.assert_called_once_with("Error: Unknown panel name 'unknown'")


def test_show_panel_toggle_active(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Toggles (closes) the current active panel if the same panel is requested."""
    panel_manager.active_panel = mock_panel
    panel_manager.registered_panels["test"] = DummyPanel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel("test")
        mock_close.assert_called_once()


def test_show_panel_replace_active(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Replaces an existing active panel with a newly created one."""
    old_panel = Mock()
    panel_manager.active_panel = old_panel
    panel_manager.registered_panels["new"] = DummyPanel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel("new")
        mock_close.assert_called_once()
        assert isinstance(panel_manager.active_panel, DummyPanel)


def test_show_panel_success(panel_manager: PanelManager) -> None:
    """Successfully creating and showing a panel updates focus and redraw flags."""
    panel_manager.registered_panels["test"] = DummyPanel

    panel_manager.show_panel("test")

    # Panel should exist and be visible
    assert panel_manager.active_panel is not None
    assert panel_manager.active_panel.visible
    assert panel_manager.editor.focus == "panel"
    assert panel_manager.editor._force_full_redraw


def test_show_panel_exception(panel_manager: PanelManager) -> None:
    """Exceptions during panel creation are caught; focus returns to editor."""

    class FailingPanel(BasePanel):
        """A panel that raises during initialization to test error handling."""

        def __init__(self, stdscr: Any, editor: Any, **kwargs: Any) -> None:
            super().__init__(stdscr, editor)
            # Use a concrete exception type for clarity
            raise RuntimeError("Test error")

    panel_manager.registered_panels["test"] = FailingPanel

    panel_manager.show_panel("test")

    # Explicit cast for mypy
    status_mock = cast(Mock, panel_manager.editor._set_status_message)
    status_mock.assert_called_once()

    assert panel_manager.active_panel is None
    assert panel_manager.editor.focus == "editor"


# ====== show_panel_instance tests ======


def test_show_panel_instance_none(panel_manager: PanelManager) -> None:
    """Passing `None` is handled gracefully and results in no active panel."""
    # Type ignore is intentional: production code handles None internally
    panel_manager.show_panel_instance(None)  # type: ignore[arg-type]
    assert panel_manager.active_panel is None


def test_show_panel_instance_toggle(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """When the same instance is shown, the active panel is toggled/closed."""
    panel_manager.active_panel = mock_panel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel_instance(mock_panel)
        mock_close.assert_called_once()


def test_show_panel_instance_replace(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Showing a different instance replaces the current active panel."""
    old_panel = Mock()
    panel_manager.active_panel = old_panel

    with patch.object(panel_manager, "close_active_panel") as mock_close:
        panel_manager.show_panel_instance(mock_panel)
        mock_close.assert_called_once()
        assert panel_manager.active_panel == mock_panel


def test_show_panel_instance_success(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Successful show of a panel instance focuses the panel and requests redraw."""
    panel_manager.show_panel_instance(mock_panel)
    mock_panel.open.assert_called_once()
    assert panel_manager.editor.focus == "panel"
    assert panel_manager.editor._force_full_redraw


def test_show_panel_instance_exception(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Exceptions during `open()` are caught and focus returns to editor."""
    mock_panel.open.side_effect = RuntimeError("Test error")

    panel_manager.show_panel_instance(mock_panel)
    assert panel_manager.active_panel is None
    assert panel_manager.editor.focus == "editor"


# ====== close_active_panel tests ======


def test_close_active_panel_no_panel(panel_manager: PanelManager) -> None:
    """No-op when there is no active panel; focus remains 'editor'."""
    panel_manager.close_active_panel()
    assert panel_manager.editor.focus == "editor"


def test_close_active_panel_with_panel(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Closing an active panel calls `close`, clears it, and restores editor focus."""
    panel_manager.active_panel = mock_panel
    # Set a non-editor focus to verify it switches back
    panel_manager.editor.focus = "panel"

    panel_manager.close_active_panel()

    mock_panel.close.assert_called_once()
    assert panel_manager.active_panel is None
    assert panel_manager.editor.focus == "editor"  # type: ignore[unreachable]


def test_close_active_panel_exception(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Exceptions from the panel `close` method are logged and the panel is cleared."""
    mock_panel.close.side_effect = RuntimeError("Test error")
    panel_manager.active_panel = mock_panel

    # Global patch for logging.exception
    with patch("logging.exception") as mock_exception:
        panel_manager.close_active_panel()
        mock_exception.assert_called_once_with("Exception while closing panel")

    assert panel_manager.active_panel is None


# ===== handle_key tests =====


def test_handle_key_no_panel(panel_manager: PanelManager) -> None:
    """Returns False when no active panel exists to handle the key."""
    assert not panel_manager.handle_key("test")


def test_handle_key_with_panel(panel_manager: PanelManager, mock_panel: Mock) -> None:
    """Delegates key to the active panel and returns True when handled."""
    panel_manager.active_panel = mock_panel
    mock_panel.handle_key.return_value = True

    assert panel_manager.handle_key("test")
    mock_panel.handle_key.assert_called_once_with("test")


def test_handle_key_panel_not_handled(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Returns False when the active panel declines to handle the key."""
    panel_manager.active_panel = mock_panel
    mock_panel.handle_key.return_value = False

    assert not panel_manager.handle_key("test")


def test_handle_key_exception(panel_manager: PanelManager, mock_panel: Mock) -> None:
    """Exceptions from panel key handlers are logged and reported as not handled."""
    panel_manager.active_panel = mock_panel
    mock_panel.handle_key.side_effect = RuntimeError("Test error")

    with patch("ecli.ui.PanelManager.logging") as mock_logging:
        assert not panel_manager.handle_key("test")
        mock_logging.exception.assert_called_once()


# ======= draw_active_panel tests =======


def test_draw_active_panel_no_panel(panel_manager: PanelManager) -> None:
    """No active panel: drawing is a no-op and must not raise."""
    panel_manager.draw_active_panel()  # Should not raise


def test_draw_active_panel_with_panel(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Delegates `draw()` to the active panel."""
    panel_manager.active_panel = mock_panel

    panel_manager.draw_active_panel()
    mock_panel.draw.assert_called_once()


def test_draw_active_panel_exception(
    panel_manager: PanelManager, mock_panel: Mock
) -> None:
    """Exceptions during drawing are logged; no exception escapes to the caller."""
    panel_manager.active_panel = mock_panel
    mock_panel.draw.side_effect = RuntimeError("Test error")

    with patch("ecli.ui.PanelManager.logging") as mock_logging:
        panel_manager.draw_active_panel()
        mock_logging.exception.assert_called_once()
