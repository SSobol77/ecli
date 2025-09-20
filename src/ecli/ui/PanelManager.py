# ecli/ui/PanelManager.py
"""PanelManager.py
========================
This module defines the PanelManager class, which is responsible for managing
the lifecycle, visibility, and interaction of non-blocking panels within the
ECLI Editor. The PanelManager allows panels such as AI response and file
browser panels to be shown, closed, and interacted with independently of the
main editor interface, ensuring a seamless user experience without blocking
editor operations.
"""

import curses
import logging
from typing import TYPE_CHECKING, Any, Optional

from .panels import AiResponsePanel, BasePanel, FileBrowserPanel


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


## ================= PanelManager Class ===============================
class PanelManager:
    """PanelManager Class
    ==========================
    Manages the lifecycle, creation, and rendering of non-blocking UI panels within the editor.
    A panel is a UI component that can be shown or hidden without blocking the main editor interface.
    The PanelManager is responsible for registering available panel types, showing or hiding panels,
    handling keyboard events for the active panel, and ensuring proper focus management between the
    editor and panels.

    Attributes:
        editor (Ecli): Reference to the main editor instance.
        active_panel (Optional[BasePanel]): The currently active and visible panel, if any.
        registered_panels (Dict[str, Type[BasePanel]]): Mapping of panel names to their classes.
        editor_instance (Ecli): The main editor instance to which this manager belongs.

    Methods:
        is_panel_active() -> bool:
            Checks if a panel is currently active and visible.
        show_panel(name: str, **kwargs: Any) -> None:
            Creates and shows a panel by name in non-blocking mode. Toggles or replaces panels as needed.
        show_panel_instance(panel_instance: BasePanel) -> None:
            Shows a pre-created panel instance, toggling or replacing as appropriate.
        close_active_panel() -> None:
            Closes the currently active panel and returns focus to the editor.
        handle_key(key: Union[int, str]) -> bool:
            Passes a key event to the active panel if it has focus. Returns True if handled.
        draw_active_panel() -> None:
            Calls the draw method of the active panel, if any.
    """

    def __init__(self, editor_instance: "Ecli"):
        """Initializes the PanelManager.

        Args:
            editor_instance: A back-reference to the main Ecli instance.
        """
        self.editor = editor_instance
        self.active_panel: Optional[BasePanel] = None

        # A registry to map panel names to their corresponding classes.
        # All registered panels must adhere to the non-blocking BasePanel interface.
        self.registered_panels: dict[str, type[BasePanel]] = {
            "ai_response": AiResponsePanel,
            "file_browser": FileBrowserPanel,
        }
        logging.info(
            "PanelManager initialised with: %s", list(self.registered_panels.keys())
        )

    def is_panel_active(self) -> bool:
        """Checks if a panel is currently active and visible."""
        return self.active_panel is not None and self.active_panel.visible

    def show_panel(self, name: str, **kwargs: Any) -> None:
        """Creates and shows a panel in non-blocking mode.
        If a panel of the same type is already active, it's closed (toggle behavior).
        If a different panel is active, it's replaced.
        """
        PanelCls = self.registered_panels.get(name)
        if not PanelCls:
            msg = f"Error: Unknown panel name '{name}'"
            self.editor._set_status_message(msg)
            logging.error(msg)
            return

        # Toggle behavior: if the requested panel is already active, close it.
        if self.is_panel_active() and isinstance(self.active_panel, PanelCls):
            self.close_active_panel()
            return

        # If another, different panel is active, close it before opening the new one.
        if self.is_panel_active():
            self.close_active_panel()

        try:
            # Create an instance of the requested panel.
            self.active_panel = PanelCls(self.editor.stdscr, self.editor, **kwargs)

            # The panel's open() method makes it visible.
            self.active_panel.open()

            # The editor transfers focus to the new panel.
            self.editor.focus = "panel"
            self.editor._force_full_redraw = True
            logging.info(f"Panel '{name}' shown and focus set to 'panel'.")
        except Exception as exc:
            logging.exception("Failed to create or show panel '%s': %s", name, exc)
            self.active_panel = None
            self.editor._set_status_message(f"Panel error: {exc}")
            self.editor.focus = "editor"  # Ensure focus is reset on error

    def show_panel_instance(self, panel_instance: BasePanel) -> None:
        """Shows a pre-created panel instance."""
        if not panel_instance:
            return

        # If this same panel is already active, close it
        if self.active_panel is panel_instance and panel_instance.visible:
            self.close_active_panel()
            return

        # If another panel is active, close it
        if self.is_panel_active() and self.active_panel is not panel_instance:
            self.close_active_panel()

        try:
            self.active_panel = panel_instance
            self.active_panel.open()
            self.editor.focus = "panel"
            self.editor._force_full_redraw = True
            logging.info(f"Panel instance '{panel_instance.__class__.__name__}' shown.")
        except Exception as exc:
            logging.exception("Failed to show panel instance: %s", exc)
            self.active_panel = None
            self.editor.focus = "editor"

    def close_active_panel(self) -> None:
        """Force-closes the currently active panel and returns focus to the editor."""
        if self.active_panel:
            logging.info("Closing panel: %s", self.active_panel.__class__.__name__)
            try:
                # The panel's close method handles its cleanup (e.g., setting visible=False).
                self.active_panel.close()
            except Exception:
                logging.exception("Exception while closing panel")

        self.active_panel = None
        self.editor.focus = "editor"
        curses.curs_set(1)  # Ensure the editor's cursor is visible again.
        self.editor._force_full_redraw = True
        logging.info("Active panel closed. Focus returned to 'editor'.")

    def handle_key(self, key: int | str) -> bool:
        """Passes a key to the active panel if it's in focus.
        Returns True if the panel consumed the event.
        """
        if self.is_panel_active():
            try:
                # The panel itself decides if it can handle the key.
                return self.active_panel.handle_key(key)
            except Exception:
                logging.exception("Panel key-handler crashed")
        return False

    def draw_active_panel(self) -> None:
        """Calls the draw method of the active panel.
        This is called by the main editor loop on every refresh.
        """
        if self.is_panel_active():
            try:
                self.active_panel.draw()
            except Exception:
                logging.exception("Panel draw() crashed")
