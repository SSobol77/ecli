# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/panels.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""panels.py
=========

This module defines a suite of non-blocking, interactive UI panels for the ECLI editor, leveraging the curses library for terminal-based interfaces.

Overview:
---------
The panels provided here enable advanced user interactions within the ECLI editor, such as file browsing, AI-assisted responses, and Git integration, all without blocking the main editor event loop. Each panel is designed to be managed by a central `PanelManager`, allowing seamless switching and coexistence with the core text editing experience.

Key Components:
---------------
- BasePanel: An abstract base class establishing the lifecycle and interface for all panels, including methods for opening, closing, drawing, and handling user input.
- AiResponsePanel: An interactive, scrollable text panel for displaying and navigating multi-line content, such as AI-generated responses or Markdown, with support for selection and clipboard operations.
- FileBrowserPanel: A two-pane, non-blocking file navigator inspired by classic file managers, supporting directory traversal and essential file operations (create, copy, rename, delete).
- GitPanel: An integrated Git control panel providing repository status, log viewing, and common Git operations, with real-time status updates and file status integration.

Design Principles:
------------------
- Non-blocking: All panels are designed to operate without halting the main editor loop, ensuring responsive user experience.
- Extensibility: The BasePanel class and panel management pattern allow for easy addition of new panels and UI components.
- Integration: Panels can interact with the main editor state, share clipboard contents, and provide contextual operations relevant to the user's workflow.

Usage:
------
Panels are instantiated and managed by the `PanelManager` (see ecli.py), which coordinates their lifecycle, focus, and rendering. This modular approach enables a rich, multi-pane terminal UI within the ECLI editor.

"""

from __future__ import annotations

import curses
import logging
import os
import queue
import shlex
import shutil
import textwrap
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import pyperclip
from wcwidth import wcswidth

from ecli.diagnostics.display import (
    diagnostic_display_path,
    truncate_end,
    truncate_middle,
)
from ecli.diagnostics.models import Diagnostic, DiagnosticsSnapshot
from ecli.integrations.GitBridge import GitBridge, GitCommandResult
from ecli.ui.design import TuiDesign
from ecli.ui.geometry import centered_modal_rect, compute_layout
from ecli.services.models.doctor import DoctorContext, DoctorFinding
from ecli.services.models.plan import CommandPlan
from ecli.utils.logging_config import logger


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli

CursesWindow = Any


# --- Panel-type vocabulary (split-layout architecture) ---------------------
# All *side* panels are generic consumers of the same split-layout contract:
# the 60/40 editor/panel split (ecli.ui.geometry.compute_layout), an opaque
# themed panel surface, the border/title/footer system, the no-overlap rule
# with the global status/footer, the F12 focus model, Esc-to-close, the theme
# roles, and resize-safe clipping (BasePanel._layout_window).
#
# ``"terminal"`` is the side-panel layout kind used by the PySH Console Panel.
# The panel owns ECLI command-console state and uses PySH only as a subprocess
# command backend; it is not a terminal emulator.
SIDE_PANEL_KINDS: frozenset[str] = frozenset(
    {
        "file_manager",
        "git_control",
        "system_doctor",
        "ai_provider",
        "command_plan",
        "diagnostics",
        "services",
        "terminal",  # PySH Console Panel (F11)
    }
)
#: Centered modal panels (Help, dialogs); not part of the side-panel split.
MODAL_PANEL_KINDS: frozenset[str] = frozenset({"help", "confirm", "info"})


# ==================== BasePanel Class (Non-Blocking) ====================
class BasePanel:
    """A base class for non-blocking, interactive UI panels in the ECLI editor.

    Side panels (``is_modal_panel = False``) are generic consumers of the
    split-layout system: ``_layout_window`` places them in the right 40% work
    area without overlapping the global header/status/footer. The PySH Console
    Panel uses ``panel_kind = "terminal"`` to reuse this unchanged.
    """

    # Shift + Arrow key codes
    key_s_up = getattr(curses, "KEY_SR", 337)
    key_s_down = getattr(curses, "KEY_SF", 336)
    key_s_left = getattr(curses, "KEY_SLEFT", 393)
    key_s_right = getattr(curses, "KEY_SRIGHT", 402)

    #: Panel-type identifier (one of SIDE_PANEL_KINDS / MODAL_PANEL_KINDS).
    panel_kind: str = "generic"

    #: Side panels occupy the right 40% work area; modal panels are centered.
    is_modal_panel: bool = False

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        """Initialize the base attributes for any panel."""
        self.stdscr: CursesWindow = stdscr
        self.editor: Ecli = main_editor_instance
        self.visible: bool = False
        self.term_height, self.term_width = self.stdscr.getmaxyx()
        self.win: Optional[CursesWindow] = None
        self._rendered_as_modal: bool = False
        logger.debug(f"Base class initialized for panel '{self.__class__.__name__}'.")

    def _layout_window(
        self, modal_width: int = 80, modal_height: int = 24
    ) -> CursesWindow:
        """Create the panel's backing window from the split-layout geometry.

        Side panels are placed in the right work-area region (rows ``1..H-3``)
        so they never collide with the global header/status/footer. When the
        terminal is too narrow for a split (or the panel is modal), a centered
        modal rectangle is used instead. The created window is opaque.
        """
        self.term_height, self.term_width = self.stdscr.getmaxyx()
        geo = compute_layout(self.term_width, self.term_height, active_panel=True)
        if self.is_modal_panel or geo.panel is None:
            rect = centered_modal_rect(
                self.term_width, self.term_height, modal_width, modal_height
            )
            self._rendered_as_modal = True
        else:
            rect = geo.panel
            self._rendered_as_modal = False

        self.start_x = rect.x
        self.start_y = rect.y
        self.width = rect.width
        self.height = rect.height
        win = curses.newwin(rect.height, rect.width, rect.y, rect.x)
        win.keypad(True)
        self.win = win
        self._make_opaque(win)
        return win

    def resize(self) -> None:
        """Recalculates terminal dimensions. Must be implemented in subclasses."""
        self.term_height, self.term_width = self.stdscr.getmaxyx()
        logger.info(
            f"Resize event in panel '{self.__class__.__name__}'. New dims: {self.term_width}x{self.term_height}"
        )

    def open(self) -> None:
        """Make the panel visible and mark it as active."""
        self.visible = True
        logger.info(f"Panel '{self.__class__.__name__}' opened.")

    def close(self) -> None:
        """Hide the panel and mark it as inactive."""
        self.visible = False
        logger.info(f"Panel '{self.__class__.__name__}' closed.")

    def draw(self) -> None:
        """Draw one frame of the panel's content and chrome."""
        raise NotImplementedError(
            "The 'draw' method must be implemented in a child class."
        )

    def scroll_by(self, delta: int) -> bool:
        """Scroll the panel content by ``delta`` rows (wheel; +1 = up).

        Non-destructive: adjusts a ``scroll`` offset or a list ``idx`` if the
        panel has one. Returns True when the view changed.
        """
        scroll = getattr(self, "scroll", None)
        if isinstance(scroll, int):
            new = max(0, scroll - delta)
            if new != scroll:
                self.scroll = new
                return True
            return False
        idx = getattr(self, "idx", None)
        entries = getattr(self, "entries", None)
        if isinstance(idx, int) and entries:
            new = max(0, min(len(entries) - 1, idx - delta))
            if new != idx:
                self.idx = new
                return True
        return False

    def _panel_bg_attr(self) -> int:
        """Opaque, themed background attribute for this panel's window."""
        return self.editor.colors.get("ui_panel", curses.A_REVERSE)

    def _panel_border_attr(self, focused: bool = False) -> int:
        """Single source of truth for panel border styling.

        Every panel/modal resolves its border through this one role
        (``panel_border``) and focus convention, so borders share one
        thickness, one colour role and one style — no per-panel ad-hoc curses
        pairs and no mixed border colours between panels. A deliberate severity
        state must come from a design-system role, not a hardcoded local pair.
        """
        return TuiDesign(self.editor.colors).border(focused)

    def _draw_panel_frame(
        self,
        win: Optional[CursesWindow],
        title: str = "",
        *,
        focused: bool = False,
        footer: str = "",
    ) -> None:
        """Draw the shared panel frame used by every panel and modal.

        One single-thickness border in the ``panel_border`` role, the title
        embedded into the top edge (``panel_title`` role) and an optional footer
        label embedded into the bottom edge of the panel's own window — never
        into the global footer, since the window is bounded by ``_layout_window``
        to rows ``1..H-3``.
        """
        if win is None:
            return
        try:
            h, w = win.getmaxyx()
        except (curses.error, AttributeError):
            return
        border_attr = self._panel_border_attr(focused)
        title_attr = self.editor.colors.get("ui_panel_title", border_attr)
        try:
            win.attron(border_attr)
            win.border()
            win.attroff(border_attr)
        except curses.error:
            pass
        if title and w > 6:
            label = f" {title.strip()} "[: max(0, w - 4)]
            try:
                win.addstr(0, 2, label, title_attr)
            except curses.error:
                pass
        if footer and h >= 2 and w > 6:
            label = f" {footer.strip()} "[: max(0, w - 4)]
            try:
                win.addstr(h - 1, 2, label, border_attr)
            except curses.error:
                pass

    def _make_opaque(self, win: Optional[CursesWindow]) -> None:
        """Give *win* a solid themed background so it never shows ghosting.

        Setting ``bkgd`` makes ``erase`` fill every cell with the panel surface
        colour (not transparent spaces), so no editor text bleeds through.
        """
        if win is None or not hasattr(win, "bkgd"):
            return
        try:
            win.bkgd(" ", self._panel_bg_attr())
        except curses.error:
            pass

    def _present(self, win: Optional[CursesWindow]) -> None:
        """Refresh *win*, forcing a full re-copy to defeat overlay ghosting.

        ``touchwin`` marks every cell dirty so ``noutrefresh`` re-copies the
        whole panel over the editor, instead of skipping cells curses thinks are
        unchanged (which is how editor text bled through on redraw).
        """
        if win is None:
            return
        if hasattr(win, "touchwin"):
            try:
                win.touchwin()
            except curses.error:
                pass
        refresh = getattr(win, "noutrefresh", None) or getattr(win, "refresh", None)
        if refresh is not None:
            try:
                refresh()
            except curses.error:
                pass

    def handle_key(self, key: Any) -> bool:
        """Handles a single key press event directed to the panel.

        This is an abstract method that must be implemented by subclasses to define
        the panel's interactive behavior. It is called by the main event loop
        when the panel has focus.

        Args:
            key: The key event received, which can be an integer (for special
                 keys like arrows) or a string (for characters).

        Returns:
            True if the panel consumed the key event, indicating that a redraw
            may be necessary. False if the key was not handled, allowing it
            to be processed further if needed.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError(
            "The 'handle_key' method must be implemented in a child class."
        )


# ==================== AiResponsePanel Class ====================
class AiResponsePanel(BasePanel):
    """Class AiResponsePanel
    =========================
    An interactive text panel with cursor-based navigation and editing features.

    This panel is designed to display and interact with multi-line text content,
    such as AI responses or Markdown-formatted text. It provides a fully-featured,
    non-blocking text viewing experience with a visible cursor, line wrapping,
    and scrolling.

    It supports advanced interactions including:
    - Navigating text with arrow keys.
    - Selecting text using Shift + arrow keys.
    - Copying the selection or the current line to the system/internal clipboard.
    - Pasting content from the clipboard directly into the main editor buffer.

    The panel's visual appearance, including syntax-like highlighting for basic
    Markdown elements and color themes, is customizable through its color
    initialization method.

    Attributes:
        title (str): The title displayed at the top of the panel.
        lines (List[str]): The text content of the panel, stored as a list of strings.
        width (int): The calculated width of the panel window.
        height (int): The calculated height of the panel window.
        cursor_y (int): The logical row (line index) of the cursor.
        cursor_x (int): The logical column (character index) of the cursor.
        scroll (int): The top-most line index of the text buffer visible in the viewport (deprecated, use visual_scroll).
        visual_scroll (int): The top-most visual line (after wrapping) visible in the viewport.
        sel_anchor (Optional[Tuple[int, int]]): The fixed start point (y, x) of a selection.
        sel_active (bool): A flag indicating if text selection is currently active.
    """

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        """Initializes the CursesPanel with text content and UI elements.

        This constructor sets up the panel's dimensions, creates a dedicated curses
        window, and initializes the state for text display, cursor navigation,
        and selection. It processes `kwargs` for content and a title.

        Args:
            stdscr: The main curses window object.
            main_editor_instance: A reference to the main `Ecli` instance.
            **kwargs: Arbitrary keyword arguments. Expected keys include:
                - "title" (str): The title to display at the top of the panel.
                - "content" (str): The raw text content for the panel.
        """
        super().__init__(stdscr, main_editor_instance, **kwargs)

        self.title: str = kwargs.get("title", "AI Response")
        raw = kwargs.get("content", "(no data)")
        self.lines: list[str] = raw.splitlines() or [""]

        # Side-panel geometry (right 40% work area; never overlaps global chrome).
        self.panel_kind = "ai_provider"
        self._layout_window(modal_width=72, modal_height=22)

        self.cursor_y = 0
        self.cursor_x = 0
        self.scroll = 0
        self.visual_scroll = 0

        self.sel_anchor: Optional[tuple[int, int]] = None
        self.sel_active: bool = False

        self.visible = False
        self.is_running = False

        self._init_colors()

    def resize(self) -> None:
        """Handle terminal resize by recalculating dimensions and recreating the window."""
        super().resize()
        self._layout_window(modal_width=72, modal_height=22)

    def _init_colors(self) -> None:
        """Initializes curses color pairs specific to this panel.

        This method defines a set of color pairs for various UI elements like
        the title, border, text, cursor, and selection. It attempts to use
        custom color definitions and falls back to monochrome attributes
        (e.g., `curses.A_BOLD`, `curses.A_REVERSE`) if `curses.error` is raised,
        ensuring graceful degradation on terminals with limited color support.
        """
        try:
            curses.init_pair(201, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(202, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.init_pair(203, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(204, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(
                206, curses.COLOR_MAGENTA, curses.COLOR_BLACK
            )  # Changed BG to BLACK
            self.attr_text = curses.color_pair(201)
            self.attr_title = curses.color_pair(202) | curses.A_BOLD
            self.attr_md = curses.color_pair(203) | curses.A_BOLD
            self.attr_border = curses.color_pair(204) | curses.A_BOLD
            self.attr_cursor = curses.color_pair(206) | curses.A_REVERSE
            self.attr_sel = curses.color_pair(206) | curses.A_REVERSE
            self.attr_dim = curses.color_pair(204) | curses.A_DIM
        except curses.error:
            self.attr_text = curses.A_NORMAL
            self.attr_title = curses.A_BOLD
            self.attr_md = curses.A_BOLD
            self.attr_border = curses.A_BOLD
            self.attr_cursor = curses.A_REVERSE
            self.attr_sel = curses.A_REVERSE
            self.attr_dim = curses.A_DIM

    def open(self) -> None:
        """Makes the panel visible and sets the editor status message.

        Overrides the base `open` method to include panel-specific setup. It makes
        the cursor visible within the panel and updates the main editor's status
        bar with a help message explaining the panel's keybindings.
        """
        if self.visible:
            return
        self.visible = True
        self.is_running = True
        curses.curs_set(1)
        self.editor._set_status_message(
            "Panel: arrows move, Shift+arrows select, Ctrl+C copy, Ctrl+P paste, F12 focus, F7/Esc close"
        )

    def close(self) -> None:
        """Closes the panel and ensures the editor UI is fully refreshed.

        Overrides the base `close` method to perform cleanup. It returns the
        cursor focus to the main editor, signals the `PanelManager` that it is
        no longer active, and forces a full screen redraw to remove any visual
        artifacts left by the panel.
        """
        if not self.visible:
            return
        self.visible = False
        self.is_running = False
        curses.curs_set(1)

        if hasattr(self.editor, "panel_manager"):
            self.editor.panel_manager.active_panel = None

        self.editor.focus = "editor"

        if hasattr(self.editor, "_force_full_redraw"):
            self.editor._force_full_redraw = True

        if hasattr(self.editor, "redraw"):
            self.editor.redraw()
        else:
            self.stdscr.clear()
            self.stdscr.refresh()

    def _wrap_lines(self, wrap_width: int) -> list[tuple[int, int, str]]:
        """Wraps long lines to fit within the panel's width.

        Args:
            wrap_width: Maximum line length before wrapping.

        Returns:
            A list of tuples (original_line_index, char_offset, wrapped_text).
        """
        visual_lines = []
        for y, line in enumerate(self.lines):
            wrapped = textwrap.wrap(line, wrap_width) or [""]
            offset = 0
            for chunk in wrapped:
                visual_lines.append((y, offset, chunk))
                offset += len(chunk)
            if not wrapped:
                visual_lines.append((y, 0, ""))
        return visual_lines

    def _update_scroll_position(
        self, visual_cursor_y: int, viewport_height: int
    ) -> None:
        """Updates the visual scroll position to keep the cursor visible.

        Args:
            visual_cursor_y: Vertical position of the cursor in wrapped text.
            viewport_height: Height of the visible area.
        """
        if not hasattr(self, "visual_scroll"):
            self.visual_scroll = 0

        # Ensure cursor is within visible area
        if visual_cursor_y < self.visual_scroll:
            self.visual_scroll = visual_cursor_y
        elif visual_cursor_y >= self.visual_scroll + viewport_height:
            self.visual_scroll = visual_cursor_y - viewport_height + 1

    def _draw_text_chunk(self, y: int, start_x: int, chunk: str, row_y: int) -> None:
        """Draws a chunk of text at the specified position with attributes.

        Args:
            y: Original line number.
            start_x: Starting x position in original line.
            chunk: Text to draw.
            row_y: Screen row to draw at.
        """
        for x, char in enumerate(chunk):
            screen_x = 1 + x
            doc_x = start_x + x
            attr = self._get_attr(y, doc_x, chunk)
            if screen_x < self.width - 1:
                try:
                    self.win.addch(row_y, screen_x, char, attr)
                except curses.error:
                    pass

    def _draw_cursor(self, row_y: int, cursor_x: int, chunk: str) -> None:
        """Draws the cursor at the specified position.

        Args:
            row_y: Screen row to draw cursor at.
            cursor_x: Screen column to draw cursor at.
            chunk: Text chunk where cursor appears.
        """
        char_under_cursor = " "
        if cursor_x < len(chunk):
            char_under_cursor = chunk[cursor_x]
        try:
            self.win.addch(row_y, 1 + cursor_x, char_under_cursor, self.attr_cursor)
        except curses.error:
            pass

    def draw(self) -> None:
        """Draws the panel's content, including text with line wrapping and cursor.

        This method is called on every frame of the editor's main loop. It handles:
        1. Drawing the panel's border and title chrome.
        2. Wrapping long lines to fit within the panel's width.
        3. Calculating the visual position of the cursor within the wrapped text.
        4. Automatically scrolling the viewport to keep the cursor visible.
        5. Rendering the visible text lines, applying attributes for text, selection,
           and the cursor itself.
        """
        # Abort if the panel is not supposed to be visible.
        if not self.visible:
            return

        # Guard clause: If the panel window has become too small after a resize,
        # abort drawing to prevent a `curses.error`. A minimum of 3x3 is required
        # to draw borders and have at least one character of content space.
        if self.height < 3 or self.width < 3:
            return

        try:
            # Clear the panel's dedicated window for this frame.
            self.win.erase()

            # First, draw the static elements like the border and title.
            self._draw_chrome()

            # --- Setup dimensions for the text area ---
            # The viewport is the drawable area inside the borders.
            viewport_height = self.height - 2
            # The wrap width is the available horizontal space for text.
            wrap_width = self.width - 2

            # If there's no space to draw, exit early.
            if viewport_height <= 0 or wrap_width <= 0:
                self._present(self.win)
                return

            # --- Calculate line wrapping and cursor position ---
            # Convert the logical lines of text into visual lines based on wrap_width.
            visual_lines = self._wrap_lines(wrap_width)
            # Find the cursor's row and column within this new visual line structure.
            visual_cursor_y, visual_cursor_x = self._get_visual_cursor(visual_lines)

            # Adjust the vertical scroll offset to ensure the cursor is visible.
            self._update_scroll_position(visual_cursor_y, viewport_height)

            # --- Render the visible portion of the text ---
            # Slice the visual_lines to get only the lines that fit in the current viewport.
            visible_lines = visual_lines[
                self.visual_scroll : self.visual_scroll + viewport_height
            ]

            # Iterate over the visible lines and draw them one by one.
            for n, (original_line_idx, char_offset, chunk) in enumerate(visible_lines):
                # The screen row `row_y` is the loop index plus 1 (to account for the top border).
                row_y = n + 1

                # Draw the actual text chunk for this visual line.
                self._draw_text_chunk(original_line_idx, char_offset, chunk, row_y)

                # Check if the cursor is on the current visual line being drawn.
                is_cursor_on_this_line = (self.visual_scroll + n) == visual_cursor_y
                if is_cursor_on_this_line:
                    # If so, draw the cursor on top of the character at its position.
                    self._draw_cursor(row_y, visual_cursor_x, chunk)

            # Stage the changes for the next screen update without blocking.
            self._present(self.win)

        except curses.error as e:
            # Catch any unexpected curses errors during the draw cycle to prevent a crash.
            logging.error(f"Curses error in AiResponsePanel.draw: {e}", exc_info=True)
            pass

    def _get_visual_cursor(
        self, visual_lines: list[tuple[int, int, str]]
    ) -> tuple[int, int]:
        """Calculates the cursor's coordinates within the wrapped visual lines.

        Args:
            visual_lines: A list of tuples, where each tuple represents a
                wrapped line segment: `(original_line_index, offset_in_line, text_chunk)`.

        Returns:
            A tuple (visual_row, visual_column) representing the cursor's
            position in the `visual_lines` structure.
        """
        for v_idx, (ly, start_x, chunk) in enumerate(visual_lines):
            if ly == self.cursor_y:
                chunk_len = len(chunk)
                if start_x <= self.cursor_x < start_x + chunk_len or (
                    chunk_len == 0 and self.cursor_x == 0
                ):
                    return v_idx, self.cursor_x - start_x
        return len(visual_lines) - 1, 0

    def _get_attr(self, y: int, x: int, line: str) -> int:
        """Determines the curses attribute for a character at a given coordinate.

        The method prioritizes attributes in the following order:
        1. Cursor: The character at the cursor position gets a special attribute.
        2. Selection: Characters within an active selection are highlighted.
        3. Markdown: Basic Markdown syntax (headers, code blocks) at the start
           of a line receives a distinct style.
        4. Default Text: All other characters use the default text attribute.

        Args:
            y: The logical row (line index) of the character.
            x: The logical column (character index) of the character.
            line: The full string content of the line (currently unused but
                  kept for future context-aware styling).

        Returns:
            An integer representing the curses color pair and attribute mask.
        """
        in_sel = self._is_selected(y, x)
        if in_sel:
            return self.attr_sel

        lstrip = self.lines[y].lstrip() if y < len(self.lines) else ""
        if x == 0:
            if lstrip.startswith("#"):
                return self.attr_title
            if lstrip.startswith("```"):
                return self.attr_md
            if lstrip.startswith(">"):
                return self.attr_md
            if lstrip.startswith("- ") or lstrip.startswith("* "):
                return self.attr_md
        return self.attr_text

    def _handle_navigation_key(self, key: int) -> bool:
        """Handle cursor navigation keys.

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        navigation_map = {
            curses.KEY_UP: (-1, 0, False),
            curses.KEY_DOWN: (1, 0, False),
            curses.KEY_LEFT: (0, -1, False),
            curses.KEY_RIGHT: (0, 1, False),
            self.key_s_up: (-1, 0, True),
            337: (-1, 0, True),
            self.key_s_down: (1, 0, True),
            336: (1, 0, True),
            self.key_s_left: (0, -1, True),
            393: (0, -1, True),
            self.key_s_right: (0, 1, True),
            402: (0, 1, True),
        }

        if key in navigation_map:
            dy, dx, shift = navigation_map[key]
            self._move_cursor(dy, dx, shift)
            return True
        return False

    def _handle_screen_movement_key(self, key: int) -> bool:
        """Handle keys that move cursor to edges or by pages.

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        if key == curses.KEY_HOME:
            self._move_cursor_to_line_edge("home")
        elif key == curses.KEY_END:
            self._move_cursor_to_line_edge("end")
        elif key == curses.KEY_PPAGE:
            self._move_cursor(-(self.height - 2), 0, shift=False)
        elif key == curses.KEY_NPAGE:
            self._move_cursor(self.height - 2, 0, shift=False)
        else:
            return False
        return True

    def _handle_selection_key(self, key: int) -> bool:
        """Handle keys that affect text selection.

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        if key in (27, curses.KEY_F7):
            self.sel_active = False
            self.sel_anchor = None
            self.editor.panel_manager.close_active_panel()
        elif key == 3:  # Ctrl+C
            self._copy_selection()
        elif key == 16:  # Ctrl+P
            self._paste_into_editor()
        else:
            return False
        return True

    def handle_key(self, key: int | str) -> bool:
        """Handles a single key press when the panel is visible and in focus.

        This method processes various key inputs for navigation, text selection,
        and other panel-specific actions. It is designed to be robust across
        different terminal emulators by checking for both standard `curses`
        key constants and common hard-coded integer values for modified keys
        (like Shift+Arrow).

        Args:
            key: The key event received from curses, which can be an integer
                 (for special keys like arrows) or a string (for regular characters).

        Returns:
            True if the key was processed and resulted in a state change
                  that requires a screen redraw. False if the key was not handled
                  by this panel.
        """
        if not self.visible:
            return False

        if not isinstance(key, int):
            if isinstance(key, str) and len(key) == 1:
                key = ord(key)
            else:
                logging.debug(
                    f"CursesPanel received unhandled non-integer/non-char key: {key!r}"
                )
                return False

        if key == getattr(curses, "KEY_F12", 276):
            self.editor.toggle_focus()
            return True

        # Handle key in specific order
        if (
            self._handle_navigation_key(key)
            or self._handle_screen_movement_key(key)
            or self._handle_selection_key(key)
        ):
            return True

        return False

    def _move_cursor(self, dy: int, dx: int, shift: bool) -> None:
        """Moves the cursor and manages selection state.

        Args:
            dy: The change in the vertical direction (rows).
            dx: The change in the horizontal direction (columns).
            shift: If True, selection mode is activated or extended. If False,
                   any active selection is cancelled.
        """
        prev_y, prev_x = self.cursor_y, self.cursor_x

        self.cursor_y = max(0, min(len(self.lines) - 1, self.cursor_y + dy))

        # Ensure x is clamped to the new line's length
        max_x = len(self.lines[self.cursor_y]) if self.lines else 0
        if dx != 0:
            self.cursor_x = max(0, min(max_x, self.cursor_x + dx))
        else:  # For vertical moves, preserve column if possible, but clamp
            self.cursor_x = min(self.cursor_x, max_x)

        if shift:
            if not self.sel_active:
                self.sel_anchor = (prev_y, prev_x)
                self.sel_active = True
        else:
            self.sel_active = False
            self.sel_anchor = None

    def _move_cursor_to_line_edge(self, edge: str) -> None:
        """Moves the cursor to the beginning or end of the current line.

        Args:
            edge: A string, either 'home' to move to the beginning (column 0)
                  or 'end' to move to the end of the line.
        """
        if edge == "home":
            self.cursor_x = 0
        elif edge == "end":
            self.cursor_x = len(self.lines[self.cursor_y])

    def _is_selected(self, y: int, x: int) -> bool:
        """Checks if a given coordinate (y, x) is within the active selection.

        Args:
            y: The logical row (line index) to check.
            x: The logical column (character index) to check.

        Returns:
            True if the coordinate is part of the selection, False otherwise.
        """
        if not self.sel_active or not self.sel_anchor:
            return False
        y0, x0 = self.sel_anchor
        y1, x1 = self.cursor_y, self.cursor_x
        if (y0, x0) > (y1, x1):
            y0, x0, y1, x1 = y1, x1, y0, x0

        if y < y0 or y > y1:
            return False
        if y0 == y1:
            return x0 <= x < x1
        if y == y0:
            return x >= x0
        if y == y1:
            return x < x1
        return True

    def _copy_selection(self) -> None:
        """Copies the selected text to the system and internal clipboards.

        If a multi-line or single-line selection is active, the selected text
        is copied. If no selection is active, the entire current line is copied.
        It attempts to use `pyperclip` for system clipboard access and falls
        back to the editor's internal clipboard if `pyperclip` is unavailable
        or fails.
        """
        if self.sel_active and self.sel_anchor:
            y0, x0 = self.sel_anchor
            y1, x1 = self.cursor_y, self.cursor_x
            if (y0, x0) > (y1, x1):
                y0, x0, y1, x1 = y1, x1, y0, x0
            selected = []
            for y in range(y0, y1 + 1):
                line = self.lines[y]
                if y == y0 and y == y1:
                    selected.append(line[x0:x1])
                elif y == y0:
                    selected.append(line[x0:])
                elif y == y1:
                    selected.append(line[:x1])
                else:
                    selected.append(line)
            text = "\n".join(selected)
        else:
            text = self.lines[self.cursor_y]

        try:
            # Try to copy to system clipboard
            pyperclip.copy(text)
            self.editor._set_status_message("Copied selection → system clipboard")
        except Exception:
            self.editor.internal_clipboard = text
            self.editor._set_status_message("Copied selection → internal clipboard")

    def _paste_into_editor(self) -> None:
        """Pastes text from the clipboard directly into the main editor buffer.

        This method provides a bridge to paste content from this panel's context
        into the main `Ecli`. It first tries to use the editor's internal
        clipboard and then falls back to the system clipboard via `pyperclip`.
        """
        txt = getattr(self.editor, "internal_clipboard", "")
        if not txt:
            try:
                # Try to paste from system clipboard
                txt = pyperclip.paste()
            except Exception:
                pass
        if txt:
            self.editor.insert_text(txt)
            self.editor._set_status_message("Pasted into editor")

    def _draw_chrome(self) -> None:
        """Draws the panel's border, title, and footer.

        This helper method is responsible for rendering the non-content parts
        of the panel, such as the surrounding border, a centered title, and a
        footer with keybinding hints.
        """
        self.win.attron(self.attr_border)
        self.win.border()
        if self.title:
            title = f" {self.title} "
            x = max(1, (self.width - len(title)) // 2)
            if x + len(title) < self.width:
                self.win.addstr(0, x, title, self.attr_title)
        self.win.attroff(self.attr_border)
        footer = " ^C:Copy | Shift+arr:Select | F7:Close | F12:Focus "
        if len(footer) < self.width - 2:
            self.win.addstr(self.height - 1, 2, footer, self.attr_dim)


# ==================== FileBrowserPanel Class ====================
class FileBrowserPanel(BasePanel):
    """Class FileBrowserPanel
    =========================
    A non-blocking, two-pane file navigator for browsing and file operations.

    This panel provides a familiar, Midnight Commander-style interface for
    navigating the filesystem without blocking the main editor's UI thread.
    It displays directory contents, allowing the user to traverse directories and
    open files in the editor.

    It supports a range of essential file management operations, each initiated
    via a function key and confirmed with a simple, self-contained prompt:
    - Creating new files (F2) and folders (F3).
    - Copying (F5), renaming (F6), and deleting (Del) entries.
    - Navigating with standard arrow keys, Enter, and Backspace.

    The panel's focus can be toggled with the main editor using F12, allowing
    seamless switching between file management and text editing.

    Attributes:
        width (int): The calculated width of the panel window.
        height (int): The calculated height of the panel window.
        cwd (pathlib.Path): The current working directory being displayed.
        entries (List[Optional[os.DirEntry]]): The list of files and directories
            in the current `cwd`. `None` represents the ".." parent entry.
        idx (int): The index of the currently selected item in the `entries` list.
    """

    def __init__(
        self,
        stdscr: CursesWindow,
        main_editor_instance: Ecli,
        start_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initializes the FileBrowserPanel instance.

        Sets up the panel's dimensions, creates a dedicated curses window,
        and initializes its state, including the starting directory and file entries.

        Args:
            stdscr: The main curses window object.
            main_editor_instance: A reference to the main `Ecli` instance.
            start_path (Optional[str]): The initial directory path to display.
                If None, defaults to the current working directory.
            **kwargs: Catches any additional keyword arguments.
        """
        super().__init__(stdscr, main_editor_instance, **kwargs)
        self.panel_kind = "file_manager"
        self._layout_window()  # right 40% work area; no global-chrome overlap
        self.cwd = Path(start_path or os.getcwd()).resolve()
        self.entries: list[Optional[os.DirEntry]] = []
        self.idx = 0
        self.attr_border = self.editor.colors.get("status", curses.A_BOLD)
        self.attr_dir = self.editor.colors.get("keyword", curses.A_BOLD)
        self.attr_file = self.editor.colors.get("default", curses.A_NORMAL)
        self.attr_sel = curses.A_REVERSE | curses.A_BOLD
        self.git_panel: Optional[GitPanel] = None
        self.attr_dim = self.editor.colors.get("comment", curses.A_DIM)
        self._refresh_entries()

    def resize(self) -> None:
        """Handle terminal resize by recalculating dimensions and recreating the window."""
        super().resize()
        self._layout_window()

    def set_git_panel(self, git_panel: GitPanel) -> None:
        """Sets a link to GitPanel for integration."""
        logger.debug("Setting GitPanel for FileBrowserPanel")
        self.git_panel = git_panel

    def open(self) -> None:
        """Prepare the panel for display and schedule a non-blocking Git refresh.

        The File Browser must open instantly. The previous implementation ran
        ``git status --porcelain`` synchronously here, which blocked the curses
        UI thread for the duration of the Git subprocess (up to its timeout, or
        indefinitely if Git stalled on an index lock or slow filesystem) and so
        could appear to hang the whole editor. We now render immediately from
        whatever cache already exists and refresh Git status on a background
        worker; results are applied on a later frame by ``process_queues``.
        """
        super().open()
        curses.curs_set(0)
        if self.git_panel is not None:
            logger.debug("FileBrowserPanel open: scheduling async Git status refresh.")
            self.git_panel.request_file_status_refresh()

    def process_queues(self) -> bool:
        """Drain completed async Git status refreshes (called by the main loop).

        Returns ``True`` only when new Git status data was applied, so the
        editor redraws exactly once per update instead of looping continuously
        while the panel is open.
        """
        if self.git_panel is None:
            return False
        return self.git_panel.drain_file_status_results()

    def close(self) -> None:
        """Cleans up the panel upon closing and restores the terminal cursor.

        Overrides the base `close` method to set the curses cursor back to 1
        (visible) for the main editor and ensures the editor's focus is correctly
        restored.
        """
        super().close()
        curses.curs_set(1)
        self.editor.focus = "editor"
        if hasattr(self.editor, "_force_full_redraw"):
            self.editor._force_full_redraw = True

    def _handle_navigation_keys(self, key: Any) -> bool:
        """Handles navigation key presses (up/down/left/right).

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        if key in (curses.KEY_UP, ord("k")):
            if self.entries:
                self.idx = (self.idx - 1 + len(self.entries)) % len(self.entries)
        elif key in (curses.KEY_DOWN, ord("j")):
            if self.entries:
                self.idx = (self.idx + 1) % len(self.entries)
        elif key in (curses.KEY_LEFT, ord("h"), curses.KEY_BACKSPACE, 127):
            self._go_parent()
        elif key in (curses.KEY_RIGHT, ord("l"), curses.KEY_ENTER, 10, 13, "\n"):
            self._enter_selected()
        else:
            return False
        return True

    def _handle_operation_keys(self, key: Any) -> bool:
        """Handles file operation key presses (F2-F6, Del).

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        operations = {
            (curses.KEY_F2, 266): self._new_file,
            (curses.KEY_F3, 267): self._new_folder,
            (curses.KEY_F5, 269): self._copy_entry,
            (curses.KEY_F6, 270): self._rename_entry,
            (curses.KEY_DC, 330): self._delete_entry,
        }

        for keys, operation in operations.items():
            if key in keys:
                operation()
                return True
        return False

    def _handle_panel_keys(self, key: Any) -> bool:
        """Handles panel-specific key presses (exit, close, focus).

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        # Handle exit (Ctrl+Q)
        if key in (17, "\x11"):
            if hasattr(self.editor, "exit_editor"):
                self.editor.exit_editor()
            return True

        # Handle close panel (F10, ESC, q)
        if key in (curses.KEY_F10, 274, 27, ord("q"), ord("\x1b")):
            if hasattr(self.editor, "toggle_file_browser"):
                self.editor.toggle_file_browser()
            else:
                self.close()
            return True

        # Handle focus toggle (F12)
        if key == getattr(curses, "KEY_F12", 276):
            if hasattr(self.editor, "toggle_focus"):
                self.editor.toggle_focus()
            return True

        # Manual refresh: rescan the directory and schedule a bounded, async
        # Git status refresh. Never blocks the UI thread on a subprocess.
        # Returning True already drives exactly one redraw via the main loop.
        if key in (ord("r"), ord("R")):
            self._refresh_entries()
            if self.git_panel is not None:
                self.git_panel.request_file_status_refresh()
            return True

        return False

    def handle_key(self, key: Any) -> bool:
        """Processes a single key press to navigate or perform file operations.

        This method is the primary input handler for the file browser. It maps
        keys to actions such as moving the cursor, entering directories, opening
        files, and initiating file operations (create, copy, rename, delete).
        It also handles global keys like `Ctrl+Q` to quit the editor and `F10`
        to close the panel itself.

        Args:
            key: The key event received from curses, which can be an integer
                 (for special keys like arrows) or a string (for characters).

        Returns:
            True if the key was handled by the panel, False otherwise.
        """
        logging.debug(f"FileBrowserPanel.handle_key: key={key!r}")

        # Try each handler in order of priority
        return (
            self._handle_panel_keys(key)
            or self._handle_navigation_keys(key)
            or self._handle_operation_keys(key)
        )

    def _get_git_entry_info(self, entry: Optional[Path]) -> tuple[str, int]:
        """Gets the Git status prefix and color attribute for a file entry.

        Args:
            entry: The file entry to check. None for parent directory.

        Returns:
            A tuple of (prefix, attribute) for the file.
        """
        if entry is None or entry.is_dir() or not self.git_panel:
            return " ", 0

        # Note: intentionally no per-entry logging here. ``draw`` calls this for
        # every visible row on every frame, so logging would flood the debug log
        # on each redraw.
        git_status = self.git_panel.get_file_git_status(entry.path)

        if not git_status:
            return " ", 0

        status_map = {
            "M": ("M", "git_dirty"),
            "??": ("?", "git_info"),
            "D": ("D", "git_deleted"),
            "A": ("A", "git_added"),
            "R": ("R", "function"),
        }

        prefix, color_key = status_map.get(git_status, (" ", None))
        attr = self.editor.colors.get(color_key, 0) if color_key else 0
        return prefix, attr

    # --- Midnight Commander-style rendering ----------------------------
    @staticmethod
    def _format_size(num: int) -> str:
        """Human-readable file size in <=6 chars (e.g. '4.2K', '1.1M')."""
        size = float(num)
        for unit in ("B", "K", "M", "G", "T"):
            if size < 1024 or unit == "T":
                if unit == "B":
                    return f"{int(size)}{unit}"
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{int(size)}T"

    @staticmethod
    def _format_mtime(ts: float) -> str:
        """Compact modified time: 'HH:MM' today, else 'MMM DD' / 'YYYY-MM-DD'."""
        when = datetime.fromtimestamp(ts)
        now = datetime.now()
        if when.year != now.year:
            return when.strftime("%Y-%m-%d")
        if (now - when).days < 1 and when.day == now.day:
            return when.strftime("%H:%M")
        return when.strftime("%b %d")

    def _is_dir(self, entry: Optional[os.DirEntry]) -> bool:
        if entry is None:
            return True
        try:
            return entry.is_dir(follow_symlinks=False)
        except OSError:
            return False

    def _entry_meta(self, entry: Optional[os.DirEntry]) -> tuple[str, str, str]:
        """Return (display_name, size_str, mtime_str) for a list entry."""
        if entry is None:
            return ("..", "", "")
        is_dir = self._is_dir(entry)
        name = entry.name + ("/" if is_dir else "")
        try:
            st = entry.stat(follow_symlinks=False)
            size_str = "<DIR>" if is_dir else self._format_size(st.st_size)
            mtime_str = self._format_mtime(st.st_mtime)
        except OSError:
            size_str, mtime_str = ("<DIR>" if is_dir else "—"), "—"
        return (name, size_str, mtime_str)

    def _git_marker(self, entry: Optional[os.DirEntry]) -> tuple[str, str]:
        """Return (1-char git status marker, color_key) for an entry."""
        prefix, _attr = self._get_git_entry_info(entry)
        prefix = (prefix or " ")[:1]
        key = {"M": "git_dirty", "?": "git_clean", "A": "git_clean", "D": "error"}.get(
            prefix.strip(), "panel_dim"
        )
        return prefix, key

    def _column_widths(self, inner: int) -> tuple[int, int, int]:
        """Return (name_w, size_w, mod_w); drops columns on narrow panels."""
        usable = inner - 2  # git marker + trailing margin
        if usable >= 40:
            size_w, mod_w = 7, 12
        elif usable >= 26:
            size_w, mod_w = 7, 0
        else:
            size_w, mod_w = 0, 0
        gaps = (1 if size_w else 0) + (1 if mod_w else 0)
        name_w = max(4, usable - size_w - mod_w - gaps)
        return name_w, size_w, mod_w

    def hit_entry_index(self, local_y: int) -> Optional[int]:
        """Map a panel-local row (0-based) to the entry index it shows.

        Returns ``None`` for clicks on the title/header/footer rows or empty
        list area. Pure given the geometry recorded by the last ``draw``; never
        opens or mutates anything — selection only.
        """
        list_top = getattr(self, "_list_first_row", 2)
        list_bottom = getattr(self, "_list_last_row", self.height - 3)
        if not (list_top <= local_y < list_bottom):
            return None
        idx = getattr(self, "_visible_top", 0) + (local_y - list_top)
        if 0 <= idx < len(self.entries):
            return idx
        return None

    def draw(self) -> None:
        """Draw the MC-style file browser: breadcrumb, columns, full-row selection."""
        if not self.visible or self.win is None:
            if self.win is None:
                logger.error("FileBrowserPanel.draw() called, but self.win is None.")
            return
        if self.height < 6 or self.width < 10:
            return

        d = TuiDesign(self.editor.colors)
        is_focused = self.editor.focus == "panel"
        inner = self.width - 2

        self.win.erase()
        self._draw_frame(is_focused, d)

        name_w, size_w, mod_w = self._column_widths(inner)
        name_x, size_x = 3, 3 + name_w + 1
        mod_x = size_x + size_w + 1

        # Column header row.
        header_attr = d.attr("table_header", self.attr_dim)
        try:
            self.win.addnstr(1, 1, " " * inner, inner, header_attr)
            self.win.addnstr(1, name_x, "Name"[:name_w], name_w, header_attr)
            if size_w:
                self.win.addnstr(1, size_x, "Size".rjust(size_w), size_w, header_attr)
            if mod_w:
                self.win.addnstr(1, mod_x, "Modified"[:mod_w], mod_w, header_attr)
        except curses.error:
            pass

        # File list with full-row selection.
        list_top, list_bottom = 2, self.height - 3
        viewport_h = max(0, list_bottom - list_top)
        top = (
            max(0, self.idx - viewport_h + 1)
            if viewport_h and self.idx >= viewport_h
            else 0
        )
        # Remember the list geometry so a mouse click can be mapped to an entry.
        self._list_first_row = list_top
        self._list_last_row = list_bottom
        self._visible_top = top
        sel_attr = d.selected(is_focused)
        dir_attr = d.attr("panel_accent", self.attr_dir)
        file_attr = d.attr("panel_text", self.attr_file)
        dim_attr = d.attr("panel_dim", self.attr_dim)

        for n, entry in enumerate(self.entries[top : top + viewport_h]):
            gi = top + n
            row_y = list_top + n
            is_selected = gi == self.idx
            is_dir = self._is_dir(entry)
            name, size_str, mtime_str = self._entry_meta(entry)
            gchar, gkey = self._git_marker(entry)

            row_bg = sel_attr if is_selected else file_attr
            name_attr = sel_attr if is_selected else (dir_attr if is_dir else file_attr)
            meta_attr = sel_attr if is_selected else dim_attr
            git_attr = sel_attr if is_selected else d.attr(gkey, dim_attr)
            try:
                self.win.addnstr(row_y, 1, " " * inner, inner, row_bg)  # full-row
                self.win.addnstr(row_y, 1, gchar, 1, git_attr)
                self.win.addnstr(row_y, name_x, name, name_w, name_attr)
                if size_w:
                    self.win.addnstr(
                        row_y, size_x, size_str.rjust(size_w)[:size_w], size_w, meta_attr
                    )
                if mod_w:
                    self.win.addnstr(row_y, mod_x, mtime_str[:mod_w], mod_w, meta_attr)
            except curses.error:
                pass

        self._draw_status_line(self.height - 2, inner, d)
        self._draw_action_bar(self.height - 1, inner, d)
        self._present(self.win)  # touchwin + noutrefresh: opaque, no ghosting

    def _draw_status_line(self, y: int, inner: int, d: TuiDesign) -> None:
        """Metadata line for the selected entry (name · type · size · modified)."""
        attr = d.attr("panel_dim", self.attr_dim)
        entry = (
            self.entries[self.idx]
            if self.entries and 0 <= self.idx < len(self.entries)
            else None
        )
        name, size_str, mtime_str = self._entry_meta(entry)
        kind = "dir" if self._is_dir(entry) else "file"
        parts = [name.rstrip("/")]
        parts.append(kind)
        if size_str and size_str != "<DIR>":
            parts.append(size_str)
        if mtime_str and mtime_str != "—":
            parts.append(mtime_str)
        line = " " + " · ".join(parts)
        try:
            self.win.addnstr(y, 1, " " * inner, inner, attr)
            self.win.addnstr(y, 1, line, inner, attr)
        except curses.error:
            pass

    def _draw_action_bar(self, y: int, inner: int, d: TuiDesign) -> None:
        """Bottom action bar with compact, themed function-key hints."""
        bar = d.attr("panel_bg", self.attr_dim)
        key = d.attr("panel_accent", curses.A_BOLD)
        try:
            self.win.addnstr(y, 1, " " * inner, inner, bar)
        except curses.error:
            pass
        hints = [
            ("F2", "New"),
            ("F3", "Dir"),
            ("F5", "Copy"),
            ("F6", "Ren"),
            ("Del", "Del"),
            ("Enter", "Open"),
            ("r", "Refresh"),
            ("F10", "Close"),
        ]
        x = 1
        for k, label in hints:
            seg = f"{k} {label} "
            if x + wcswidth(seg) >= inner + 1:
                break
            try:
                self.win.addnstr(y, x, k, len(k), key)
                self.win.addnstr(y, x + len(k), f" {label} ", len(label) + 2, bar)
            except curses.error:
                break
            x += wcswidth(seg)

    def _draw_frame(self, is_focused: bool, d: TuiDesign | None = None) -> None:
        """Draw the panel border with the current directory embedded as title."""
        assert self.win is not None, "self.win should not be None when drawing frame"
        if d is None:
            d = TuiDesign(self.editor.colors)
        border_attr = d.border(is_focused)
        title_attr = d.attr("panel_title", border_attr)

        # Breadcrumb: shortened current directory path.
        path = str(self.cwd)
        max_title = max(3, self.width - 6)
        if wcswidth(path) > max_title:
            path = "…" + path[-(max_title - 1) :]
        title_display = f" {path} "

        self.win.attron(border_attr)
        self.win.border()
        self.win.attroff(border_attr)
        if wcswidth(title_display) <= self.width - 2:
            try:
                self.win.addnstr(0, 2, title_display, self.width - 4, title_attr)
            except curses.error:
                pass

    def _enter_selected(self) -> None:
        """Handles the 'Enter' key press on the currently selected item.

        - If the selected item is a directory, it changes the current working
          directory (`self.cwd`) to it and refreshes the file list.
        - If the item is '..', it navigates to the parent directory.
        - If the item is a file, it calls the main editor's `open_file` method
          to load it, but keeps the file browser panel open.
        """
        if not self.entries or not (0 <= self.idx < len(self.entries)):
            logging.warning(
                f"FileBrowserPanel._enter_selected called with invalid index {self.idx}."
            )
            return

        entry = self.entries[self.idx]
        if entry is None:
            self._go_parent()
            return

        path = Path(entry.path)
        if entry.is_dir(follow_symlinks=False):
            try:
                # Check access to the directory. If there are no rights,
                # os.scandir will throw a PermissionError.
                with os.scandir(path):
                    pass  # Don't need to iterate, just check opening

                # If the check passed, change the directory
                self.cwd = path.resolve()
                self._refresh_entries()

            except PermissionError:
                self.editor._set_status_message(f"Permission denied: {path.name}")
            except Exception as e:
                self.editor._set_status_message(f"Error entering directory: {e}")
        else:
            try:
                self.editor.open_file(str(path))
                self.editor._set_status_message(f"Opened file: {path.name}")
            except Exception as e:
                self.editor._set_status_message(f"Error opening file: {e}")

    def _refresh_entries(self) -> None:
        """Scans the current directory and updates the list of file entries.

        This method populates `self.entries` with the contents of `self.cwd`.
        It sorts entries to list directories first, then files, both
        alphabetically. It also adds a ".." entry to navigate to the parent
        directory if applicable. Handles `PermissionError` and other exceptions
        gracefully by displaying a status message.
        """
        try:
            with os.scandir(self.cwd) as it:
                listed = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
            self.entries = ([] if self.cwd.parent == self.cwd else [None]) + listed
            self.idx = 0
        except (PermissionError, FileNotFoundError) as e:
            self.editor._set_status_message(f"Error reading dir: {e}")
            if self.cwd.parent != self.cwd:
                self._go_parent()

    def _go_parent(self) -> None:
        """Navigates to the parent directory and refreshes the view."""
        if self.cwd.parent != self.cwd:
            self.cwd = self.cwd.parent
            self._refresh_entries()

    def _prompt(self, message: str, initial: str = "") -> Optional[str]:
        """Displays a blocking input prompt inside the panel for file operations.

        This creates a small, centered window over the file browser to get user
        input for actions like creating, renaming, or confirming operations.
        It handles basic text editing within the prompt.

        Args:
            message: The message to display to the user.
            initial: The default text to place in the input buffer.

        Returns:
            The user's input string if confirmed, or None if cancelled.
        """
        curses.curs_set(1)
        win_h, win_w = 3, max(40, len(message) + len(initial) + 5)
        win_w = min(win_w, self.term_width - 4)
        y = (self.height - win_h) // 2
        x = self.start_x + (self.width - win_w) // 2

        box = curses.newwin(win_h, win_w, y, x)
        box.keypad(True)
        box.bkgd(" ", self.attr_border)
        box.border()
        box.addstr(0, 2, f" {message} ")

        buf = list(initial)
        pos = len(buf)
        while True:
            box.addstr(1, 1, " " * (win_w - 2))
            box.addstr(1, 2, "".join(buf))
            box.move(1, 2 + pos)
            box.refresh()
            ch = box.getch()
            if ch in (10, 13):
                txt = "".join(buf).strip()
                curses.curs_set(0)
                return txt or None
            if ch == 27:
                curses.curs_set(0)
                return None
            if ch == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif ch == curses.KEY_RIGHT:
                pos = min(len(buf), pos + 1)
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                if pos > 0:
                    buf.pop(pos - 1)
                pos -= 1
            elif 32 <= ch < 127 and len(buf) < win_w - 4:
                buf.insert(pos, chr(ch))
                pos += 1

    def _icon(self, fname: str) -> str:
        """Retrieves a file-type-specific icon for a given filename.

        Delegates to the `get_file_icon` utility function, providing it with
        the necessary configuration from the main editor instance.

        Args:
            fname: The filename for which to get an icon.

        Returns:
            A string (typically a single Unicode character) representing the icon.
        """
        try:
            from ecli.utils.utils import get_file_icon

            return get_file_icon(fname, self.editor.config)
        except Exception:
            return "📄"

    def _unique_name(self, stem: str, suffix: str, ext: str) -> str:
        """Generates a unique filename by appending a number if a file exists.

        Used for copy operations to avoid overwriting files. For example, copying
        `file.txt` will result in `file_copy.txt`, then `file_copy-1.txt`, etc.

        Args:
            stem: The base name of the file without the extension.
            suffix: The suffix to add, e.g., "_copy".
            ext: The file extension, including the leading dot.

        Returns:
            A unique filename string that does not currently exist in the `cwd`.
        """
        name = f"{stem}{suffix}{ext}"
        idx = 1
        while (self.cwd / name).exists():
            name = f"{stem}{suffix}-{idx}{ext}"
            idx += 1
        return name

    def _select_by_name(self, name: str) -> None:
        """Sets the selection index to the entry that matches the given name.

        After a file operation like creation or renaming, this method is used to
        move the selection highlight to the newly affected file.

        Args:
            name: The filename to find and select in the `self.entries` list.
        """
        for i, e in enumerate(self.entries):
            if e and e.name == name:
                self.idx = i
                break

    def _new_file(self) -> None:
        """Prompts for a filename and creates a new, empty file."""
        name = self._prompt("New file name:", "untitled.txt")
        if not name:
            return
        try:
            (self.cwd / name).touch(exist_ok=False)
            self._refresh_entries()
            self._select_by_name(name)
        except Exception as e:
            self.editor._set_status_message(f"Error: {e}")

    def _new_folder(self) -> None:
        """Prompts for a folder name and creates a new directory."""
        name = self._prompt("New folder name:", "new_folder")
        if not name:
            return
        try:
            (self.cwd / name).mkdir()
            self._refresh_entries()
            self._select_by_name(name)
        except Exception as e:
            self.editor._set_status_message(f"Error: {e}")

    def _copy_entry(self) -> None:
        """Copies the currently selected file or directory."""
        if not self.entries or self.idx >= len(self.entries):
            return

        entry = self.entries[self.idx]
        if entry is None:  # Checking the ".." entry
            return

        # Now `entry` is definitely os.DirEntry, and access to .path and .name is safe
        src = Path(entry.path)
        stem, ext = os.path.splitext(entry.name)
        dst_name = self._unique_name(stem, "_copy", ext)
        dst = self.cwd / dst_name

        # Correctly check the result of _prompt, which may return None
        response = self._prompt(f"Copy '{entry.name}' to '{dst_name}'? (y/n)")
        if not response or response.lower() != "y":
            return

        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            self._refresh_entries()
            self._select_by_name(dst.name)
        except Exception as e:
            self.editor._set_status_message(f"Copy failed: {e}")

    def _rename_entry(self) -> None:
        """Prompts for a new name and renames the selected file or directory."""
        if not self.entries or self.idx >= len(self.entries):
            return

        entry = self.entries[self.idx]
        if entry is None:  # Checking the ".." entry
            return

        # Now `entry` is definitely os.DirEntry
        new_name = self._prompt("Rename to:", entry.name)
        # `if not new_name` checks for both None and empty string ""
        if not new_name or new_name == entry.name:
            return

        try:
            (self.cwd / entry.name).rename(self.cwd / new_name)
            self._refresh_entries()
            self._select_by_name(new_name)
        except Exception as e:
            self.editor._set_status_message(f"Rename failed: {e}")

    def _delete_entry(self) -> None:
        """Prompts for confirmation and deletes the selected file or directory."""
        if not self.entries or self.idx >= len(self.entries):
            return

        entry = self.entries[self.idx]
        if entry is None:  # Checking the ".." entry
            return

        # Now `entry` is definitely os.DirEntry
        path = Path(entry.path)

        # Correctly check the result of _prompt
        response = self._prompt(f"DELETE '{path.name}'? (y/n)")
        if not response or response.lower() != "y":
            return

        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(path)
            else:
                path.unlink()
            self._refresh_entries()
        except Exception as e:
            self.editor._set_status_message(f"Delete failed: {e}")


# ==================== Phase 1 Service Panels ====================
class _ReadOnlyRightPanel(BasePanel):
    """Shared right-side panel chrome for read-only service views."""

    title = " Service Panel "
    panel_kind = "services"
    close_key = getattr(curses, "KEY_F8", 272)

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        super().__init__(stdscr, main_editor_instance, **kwargs)
        self._layout_window()  # right 40% work area; no global-chrome overlap
        self.scroll = 0
        self.registry = kwargs.get("registry")
        # Panel chrome uses the solid panel-surface colour roles so the modal is
        # opaque and themed (no transparent overlay, no ghosting).
        self.attr_panel = self.editor.colors.get("ui_panel", curses.A_REVERSE)
        self.attr_border = self.editor.colors.get("ui_panel_border", self.attr_panel)
        self.attr_title = self.editor.colors.get("ui_panel_title", curses.A_BOLD)
        self.attr_text = self.attr_panel
        self.attr_dim = self.editor.colors.get("ui_panel_dim", self.attr_panel)
        self.attr_selected = self.editor.colors.get(
            "ui_panel_selected", curses.A_REVERSE | curses.A_BOLD
        )
        self.attr_warning = self.editor.colors.get("ui_panel_warning", curses.A_BOLD)
        self.attr_error = self.editor.colors.get("ui_panel_error", curses.A_BOLD)
        self.attr_success = self.editor.colors.get(
            "ui_panel_success",
            self.editor.colors.get("ui_success", curses.A_BOLD),
        )

    def resize(self) -> None:
        """Handle terminal resize by recreating the backing panel window."""
        super().resize()
        self._layout_window()

    def open(self) -> None:
        """Open the read-only panel and hide the editor cursor."""
        super().open()
        curses.curs_set(0)

    def close(self) -> None:
        """Close the panel and return focus to the editor."""
        super().close()
        curses.curs_set(1)
        self.editor.focus = "editor"
        if hasattr(self.editor, "_force_full_redraw"):
            self.editor._force_full_redraw = True

    def _draw_frame(self, footer: str) -> None:
        is_focused = self.editor.focus == "panel"
        border_attr = self.attr_border | (curses.A_BOLD if is_focused else 0)
        try:
            self.win.border()
            self.win.addnstr(0, 2, self.title, max(1, self.width - 4), self.attr_title)
            self.win.addnstr(
                self.height - 1,
                2,
                footer,
                max(1, self.width - 4),
                self.attr_dim | border_attr,
            )
        except curses.error:
            pass

    def _draw_lines(self, lines: list[str], *, start_row: int = 1) -> None:
        viewport_height = max(0, self.height - start_row - 2)
        max_scroll = max(0, len(lines) - viewport_height)
        self.scroll = min(max(0, self.scroll), max_scroll)
        visible = lines[self.scroll : self.scroll + viewport_height]
        for row_offset, line in enumerate(visible):
            row = start_row + row_offset
            attr = self._line_attr(line)
            try:
                self.win.addnstr(row, 1, line, max(1, self.width - 2), attr)
            except curses.error:
                pass

    def _line_attr(self, line: str) -> int:
        if " CRITICAL " in line or " ERROR " in line or " unavailable" in line:
            return self.attr_error
        if " WARNING " in line or "missing" in line:
            return self.attr_warning
        if line.startswith("  "):
            return self.attr_dim
        return self.attr_text

    def _handle_common_key(self, key: Any) -> bool:
        if key in (self.close_key, 27, ord("q")):
            if hasattr(self.editor, "panel_manager") and self.editor.panel_manager:
                self.editor.panel_manager.close_active_panel()
            else:
                self.close()
            return True
        if key == getattr(curses, "KEY_F12", 276):
            if hasattr(self.editor, "toggle_focus"):
                self.editor.toggle_focus()
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.scroll = max(0, self.scroll - 1)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.scroll += 1
            return True
        if key == curses.KEY_PPAGE:
            self.scroll = max(0, self.scroll - max(1, self.height - 4))
            return True
        if key == curses.KEY_NPAGE:
            self.scroll += max(1, self.height - 4)
            return True
        return False

    def _refresh_window(self) -> None:
        # touchwin forces a full re-copy so the editor never bleeds through.
        self._present(self.win)

    def _service_registry(self) -> Any:
        if self.registry is not None:
            return self.registry
        registry = getattr(self.editor, "service_registry", None)
        if registry is not None:
            return registry
        if hasattr(self.editor, "_get_service_registry"):
            return self.editor._get_service_registry()
        raise RuntimeError("Service registry is not available")


class SystemDoctorPanel(_ReadOnlyRightPanel):
    """Read-only right-side panel for structured SystemDoctor findings."""

    title = " System Doctor "
    panel_kind = "system_doctor"

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        super().__init__(stdscr, main_editor_instance, **kwargs)
        self.findings: list[DoctorFinding] = list(kwargs.get("findings") or [])
        self.selected_idx = 0
        self.loaded = bool(self.findings)
        self.error_message: str | None = None

    def open(self) -> None:
        """Open and refresh read-only doctor findings."""
        super().open()
        if not self.loaded:
            self.refresh_findings()
        self.editor._set_status_message(
            "System Doctor: r refresh, Enter/p preview plan, s services, F8/Esc close"
        )

    def refresh_findings(self) -> None:
        """Run read-only SystemDoctor checks and store deterministic findings."""
        try:
            registry = self._service_registry()
            context = self._doctor_context(registry)
            self.findings = list(registry.system_doctor.detect_problems(context))
            self.loaded = True
            self.error_message = None
            self.selected_idx = min(self.selected_idx, max(0, len(self.findings) - 1))
        except Exception as exc:
            self.findings = []
            self.loaded = True
            self.error_message = f"SystemDoctor unavailable: {exc}"

    def _doctor_context(self, registry: Any) -> DoctorContext:
        project_root = None
        project_service = getattr(registry, "project_service", None)
        if project_service is not None and hasattr(project_service, "root"):
            project_root = project_service.root
        elif getattr(self.editor, "filename", None):
            project_root = Path(self.editor.filename).parent
        return DoctorContext(project_root=project_root, dry_run=True)

    def handle_key(self, key: Any) -> bool:
        """Handle navigation plus read-only doctor panel actions."""
        if self._handle_common_key(key):
            return True
        if key == ord("r"):
            self.refresh_findings()
            return True
        if key == ord("s"):
            self._open_services_panel()
            return True
        if key in (ord("p"), curses.KEY_ENTER, 10, 13, "\n"):
            self._open_selected_plan()
            return True
        return False

    def _open_services_panel(self) -> None:
        if not hasattr(self.editor, "panel_manager") or not self.editor.panel_manager:
            return
        self.editor.panel_manager.show_panel(
            "services_status",
            registry=self._service_registry(),
        )

    def _open_selected_plan(self) -> None:
        if not self.findings:
            self.editor._set_status_message("System Doctor: no findings to preview.")
            return
        finding = self.findings[self.selected_idx]
        if not finding.remediation_available:
            self.editor._set_status_message(
                f"System Doctor: no remediation preview for {finding.finding_id}."
            )
            return
        registry = self._service_registry()
        plan = registry.command_plan_service.create_plan_from_doctor_finding(
            finding,
            actor="system-doctor",
        )
        if plan is None:
            self.editor._set_status_message(
                f"System Doctor: no command plan for {finding.finding_id}."
            )
            return
        self.editor.panel_manager.show_panel(
            "command_plan",
            plans=[plan],
            registry=registry,
        )

    def draw(self) -> None:
        """Render structured doctor findings."""
        if not self.visible or self.win is None:
            return
        if self.height < 5 or self.width < 25:
            return
        self.win.erase()
        self._draw_frame(" r:Refresh Enter/p:Plan s:Services F8/Esc/q:Close ")

        lines = self._finding_lines()
        viewport_height = max(0, self.height - 3)
        top = max(0, self.selected_idx - viewport_height + 1)
        for row_offset, line in enumerate(lines[top : top + viewport_height]):
            row = row_offset + 1
            attr = self._line_attr(line)
            if top + row_offset == self.selected_idx and self.findings:
                attr |= self.attr_selected
            try:
                self.win.addnstr(row, 1, line, max(1, self.width - 2), attr)
            except curses.error:
                pass
        self._refresh_window()

    def _finding_lines(self) -> list[str]:
        if self.error_message is not None:
            return [self.error_message]
        if not self.findings:
            return ["INFO config DOCTOR-OK SystemDoctor found no problems."]
        return [
            (
                f"{finding.severity.value:<8} {finding.category:<15} "
                f"{finding.finding_id} {finding.title} "
                f"[remediation={'yes' if finding.remediation_available else 'no'}]"
            )
            for finding in self.findings
        ]


class CommandPlanPanel(_ReadOnlyRightPanel):
    """Preview-only right-side panel for draft CommandPlan objects."""

    title = " Command Plans "
    panel_kind = "command_plan"

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        super().__init__(stdscr, main_editor_instance, **kwargs)
        plans = list(kwargs.get("plans") or [])
        plan = kwargs.get("plan")
        if plan is not None:
            plans.append(plan)
        self.plans: list[CommandPlan] = plans
        self.lines = self._build_lines()

    def open(self) -> None:
        """Open the preview-only command plan panel."""
        super().open()
        self.editor._set_status_message("Command Plans: preview only, F8/Esc/q close")

    def handle_key(self, key: Any) -> bool:
        """Handle scroll and close keys."""
        return self._handle_common_key(key)

    def draw(self) -> None:
        """Render command plan previews."""
        if not self.visible or self.win is None:
            return
        if self.height < 5 or self.width < 25:
            return
        self.win.erase()
        self._draw_frame(" Preview only | arrows scroll | F8/Esc/q:Close ")
        self._draw_lines(self.lines)
        self._refresh_window()

    def _build_lines(self) -> list[str]:
        if not self.plans:
            return ["No command plan previews are available."]

        lines: list[str] = []
        for plan in self.plans:
            lines.extend(
                [
                    f"Plan ID: {plan.plan_id}",
                    f"Title: {plan.title}",
                    (
                        f"Risk: {plan.risk.value}  Category: {plan.category.value}  "
                        f"Source: {plan.source.value}"
                    ),
                    (
                        f"Status: {plan.status.value}  "
                        f"Confirmation: {plan.confirmation_required}"
                    ),
                    "Commands:",
                ]
            )
            for step in plan.commands:
                warnings = []
                if step.requires_privilege:
                    warnings.append("requires privilege")
                if step.destructive:
                    warnings.append("destructive")
                warning_text = f" [{' / '.join(warnings)}]" if warnings else ""
                lines.append(f"  - {step.display}{warning_text}")
                lines.append(f"    argv: {shlex.join(step.argv)}")
            try:
                export_markdown = (
                    self._service_registry().command_plan_service.export_markdown(plan)
                )
                lines.extend(["", "Markdown preview:", *export_markdown.splitlines()])
            except Exception:
                lines.append("Markdown preview unavailable.")
            lines.append("")
        return lines


class ServicesPanel(_ReadOnlyRightPanel):
    """Read-only right-side service diagnostics/status panel."""

    title = " Services "

    SERVICE_NAMES = (
        ("ConfigService", "config_service"),
        ("ProjectService", "project_service"),
        ("CommandPlanService", "command_plan_service"),
        ("BuiltInPolicyEngine", "policy_engine"),
        ("AuditLogService", "audit_log_service"),
        ("PrivilegedActionService", "privileged_action_service"),
        ("SystemDoctor", "system_doctor"),
    )

    def open(self) -> None:
        """Open the service status panel."""
        super().open()
        self.editor._set_status_message("Services: read-only status, F8/Esc/q close")

    def handle_key(self, key: Any) -> bool:
        """Handle scroll and close keys."""
        return self._handle_common_key(key)

    def draw(self) -> None:
        """Render service availability diagnostics."""
        if not self.visible or self.win is None:
            return
        if self.height < 5 or self.width < 25:
            return
        self.win.erase()
        self._draw_frame(" Read-only service status | F8/Esc/q:Close ")
        self._draw_lines(self._service_lines())
        self._refresh_window()

    def _service_lines(self) -> list[str]:
        try:
            registry = self._service_registry()
        except Exception as exc:
            return [f"ServiceRegistry unavailable: {exc}"]

        lines = ["Phase 1 service graph:"]
        for label, attribute in self.SERVICE_NAMES:
            service = getattr(registry, attribute, None)
            if service is None:
                lines.append(f"{label:<28} unavailable")
            else:
                lines.append(f"{label:<28} available ({service.__class__.__name__})")

        config_result = getattr(registry, "config_result", None)
        if config_result is not None:
            diagnostics = getattr(config_result, "diagnostics", ())
            lines.append("")
            lines.append(f"Config diagnostics: {len(diagnostics)}")
        return lines


class DiagnosticsPanel(_ReadOnlyRightPanel):
    """Right-side diagnostics list panel backed by the diagnostics service."""

    title = " Diagnostics "
    panel_kind = "diagnostics"
    close_key = getattr(curses, "KEY_F4", 268)
    _SEVERITY_LABELS = {
        "error": "E",
        "warning": "W",
        "info": "I",
        "hint": "H",
    }

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        super().__init__(stdscr, main_editor_instance, **kwargs)
        self.selected_idx = 0
        self._last_navigation_message: str | None = None
        self._details_generation: int | None = None
        self._details_key: tuple[object, ...] | None = None
        self._details_diagnostic: Diagnostic | None = None

    def open(self) -> None:
        """Open without starting a linter run."""
        super().open()
        self._clear_legacy_lint_popup()
        self._sync_selected_diagnostic_highlight(self._snapshot(), self._diagnostics())
        self.editor._set_status_message(
            "Diagnostics: r run file, R run workspace, Enter jump, d details"
        )

    def close(self) -> None:
        """Close the panel and any selected-diagnostic details popup."""
        self._clear_details_popup()
        self._clear_diagnostic_line_highlight()
        self._clear_legacy_lint_popup()
        super().close()

    def handle_key(self, key: Any) -> bool:
        """Handle diagnostics panel navigation and explicit refresh actions."""
        if self._details_is_open() and key == 27:
            self._clear_details_popup()
            self.editor._set_status_message("Diagnostic details closed.")
            return True
        if self._handle_close_or_focus_key(key):
            return True
        if self._matches_key(key, "r"):
            return self._request_refresh("buffer")
        if self._matches_key(key, "R"):
            return self._request_refresh("workspace")
        if self._matches_key(key, "d") or key in (ord(" "), " "):
            self._open_details_popup()
            return True
        if key in (curses.KEY_UP, ord("k"), "k"):
            self._move_selection(-1)
            return True
        if key in (curses.KEY_DOWN, ord("j"), "j"):
            self._move_selection(1)
            return True
        if key == curses.KEY_PPAGE:
            self._move_selection(-max(1, self.height - 4))
            return True
        if key == curses.KEY_NPAGE:
            self._move_selection(max(1, self.height - 4))
            return True
        if key in (curses.KEY_ENTER, 10, 13, "\n"):
            self._jump_to_selected()
            return True
        return False

    def draw(self) -> None:
        """Render diagnostics state and current selection."""
        if not self.visible or self.win is None:
            return
        if self.height < 5 or self.width < 25:
            return
        self.win.erase()
        self._draw_frame(self._footer())

        snapshot = self._snapshot()
        diagnostics = self._diagnostics()
        self._invalidate_stale_details(snapshot, diagnostics)
        self.selected_idx = min(self.selected_idx, max(0, len(diagnostics) - 1))
        self._sync_selected_diagnostic_highlight(snapshot, diagnostics)
        status_lines, viewport_height = self._status_lines_with_viewport(
            snapshot, diagnostics
        )
        if diagnostics:
            self.scroll = min(
                max(0, self.scroll),
                max(0, len(diagnostics) - viewport_height),
            )
            if self.selected_idx < self.scroll:
                self.scroll = self.selected_idx
            elif self.selected_idx >= self.scroll + viewport_height:
                self.scroll = self.selected_idx - viewport_height + 1
        else:
            self.scroll = 0

        for row_offset, line in enumerate(status_lines):
            try:
                self.win.addnstr(
                    row_offset + 1,
                    1,
                    line,
                    max(1, self.width - 2),
                    self._line_attr(line),
                )
            except curses.error:
                pass

        start_row = 1 + len(status_lines)
        rows = [self._format_diagnostic(diagnostic) for diagnostic in diagnostics]
        for row_offset, line in enumerate(rows[self.scroll : self.scroll + viewport_height]):
            row = start_row + row_offset
            absolute_idx = self.scroll + row_offset
            attr = self._line_attr(line)
            if diagnostics and absolute_idx == self.selected_idx:
                attr |= self.attr_selected
            try:
                self.win.addnstr(row, 1, line, max(1, self.width - 2), attr)
            except curses.error:
                pass
        self._refresh_window()
        self._draw_details_popup()

    def _handle_close_or_focus_key(self, key: Any) -> bool:
        if key in (self.close_key, 27, ord("q"), "q"):
            self._clear_details_popup()
            self._clear_diagnostic_line_highlight()
            self._clear_legacy_lint_popup()
            if hasattr(self.editor, "panel_manager") and self.editor.panel_manager:
                self.editor.panel_manager.close_active_panel()
            else:
                self.close()
            return True
        if key == getattr(curses, "KEY_F12", 276):
            if hasattr(self.editor, "toggle_focus"):
                self.editor.toggle_focus()
            return True
        return False

    def _request_refresh(self, scope: str) -> bool:
        bridge = getattr(self.editor, "linter_bridge", None)
        requester = getattr(bridge, "request_diagnostics_refresh", None)
        if not callable(requester):
            self.editor._set_status_message("Diagnostics service is not available.")
            return True
        self._clear_details_popup()
        self._clear_diagnostic_line_highlight()
        self._clear_legacy_lint_popup()
        self._last_navigation_message = None
        return bool(requester(scope=scope))

    def _move_selection(self, delta: int) -> None:
        diagnostics = self._diagnostics()
        if not diagnostics:
            self.selected_idx = 0
            return
        new_idx = max(0, min(len(diagnostics) - 1, self.selected_idx + delta))
        if new_idx != self.selected_idx:
            self._last_navigation_message = None
            self._clear_details_popup()
        self.selected_idx = new_idx
        self._sync_selected_diagnostic_highlight(self._snapshot(), diagnostics)

    def _jump_to_selected(self) -> None:
        diagnostic = self._selected_diagnostic()
        if diagnostic is None:
            self.editor._set_status_message("Diagnostics: no diagnostic selected.")
            return
        navigator = getattr(self.editor, "goto_diagnostic", None)
        if callable(navigator):
            before = getattr(self.editor, "status_message", "")
            navigator(diagnostic)
            after = getattr(self.editor, "status_message", "")
            if isinstance(after, str) and after and after != before:
                self._last_navigation_message = after
            return
        self.editor._set_status_message("Diagnostics navigation is not available.")

    def _selected_diagnostic(self) -> Diagnostic | None:
        diagnostics = self._diagnostics()
        if not diagnostics:
            return None
        self.selected_idx = max(0, min(len(diagnostics) - 1, self.selected_idx))
        return diagnostics[self.selected_idx]

    def _status_lines_with_viewport(
        self,
        snapshot: DiagnosticsSnapshot | None,
        diagnostics: tuple[Diagnostic, ...],
    ) -> tuple[list[str], int]:
        showing: tuple[int, int] | None = None
        status_lines = self._status_lines(snapshot, diagnostics, showing)
        while True:
            viewport_height = max(0, self.height - 2 - len(status_lines))
            visible_count = min(len(diagnostics), viewport_height)
            next_showing = (
                (visible_count, len(diagnostics))
                if diagnostics and visible_count < len(diagnostics)
                else None
            )
            next_status_lines = self._status_lines(
                snapshot, diagnostics, next_showing
            )
            if next_showing == showing and len(next_status_lines) == len(status_lines):
                return next_status_lines, viewport_height
            showing = next_showing
            status_lines = next_status_lines

    def _status_lines(
        self,
        snapshot: DiagnosticsSnapshot | None,
        diagnostics: tuple[Diagnostic, ...],
        showing: tuple[int, int] | None,
    ) -> list[str]:
        if snapshot is None or snapshot.status == "idle":
            return [
                "Diagnostics not run yet.",
                "Press r to run diagnostics for this file.",
            ]
        if snapshot.status == "running":
            return ["Running diagnostics..."]
        if snapshot.status == "skipped":
            return [f"Diagnostics skipped: {self._status_reason(snapshot)}"]
        if snapshot.status == "error":
            return [f"Diagnostics failed: {self._status_reason(snapshot)}"]
        if diagnostics:
            lines = [f"Diagnostics: {len(diagnostics)} issue(s)."]
            if showing is not None:
                visible_count, total_count = showing
                lines.append(f"Showing {visible_count}/{total_count} diagnostics")
            return lines
        return ["Diagnostics: PASS", "No issues found."]

    def _status_reason(self, snapshot: DiagnosticsSnapshot) -> str:
        message = " ".join(str(snapshot.message or "").split())
        for prefix in (
            "Diagnostics skipped:",
            "Diagnostics failed:",
            "Diagnostics error:",
        ):
            if message.startswith(prefix):
                message = message[len(prefix) :].strip()
                break
        return message or "unknown reason"

    def _line_attr(self, line: str) -> int:
        if line.startswith("E "):
            return self.attr_error
        if line.startswith("W "):
            return self.attr_warning
        if line.startswith(("I ", "H ")):
            return self.attr_dim
        if line.startswith("Diagnostics failed:"):
            return self.attr_error
        if line.startswith("Diagnostics skipped:"):
            return self.attr_warning
        if line.startswith("Diagnostics: PASS"):
            return self.attr_success
        if line.startswith(("Press ", "Showing ")):
            return self.attr_dim
        return super()._line_attr(line)

    def _format_diagnostic(self, diagnostic: Diagnostic) -> str:
        severity = self._SEVERITY_LABELS.get(diagnostic.severity, "?")
        source = truncate_end(str(diagnostic.source or "?"), 12)
        prefix = f"{severity} {source} "
        path = self._display_path(diagnostic.file_path)
        location_suffix = f":{diagnostic.line}:{diagnostic.column}"
        message = self._row_message(diagnostic)
        content_width = max(1, self.width - 2)

        full_row = f"{prefix}{path}{location_suffix} {message}"
        if len(full_row) <= content_width:
            return full_row
        return self._fit_diagnostic_row(
            prefix=prefix,
            path=path,
            location_suffix=location_suffix,
            message=message,
            content_width=content_width,
        )

    def _fit_diagnostic_row(
        self,
        *,
        prefix: str,
        path: str,
        location_suffix: str,
        message: str,
        content_width: int,
    ) -> str:
        if content_width <= len(prefix):
            return truncate_end(prefix, content_width)

        usable = content_width - len(prefix)
        full_location = f"{path}{location_suffix}"
        if usable <= len(location_suffix) + 2:
            return truncate_end(f"{prefix}{full_location}", content_width)

        min_message_width = min(len(message), max(7, content_width // 4))
        location_width = min(
            len(full_location),
            max(len(location_suffix) + 1, usable - min_message_width - 1),
        )
        message_width = max(1, usable - location_width - 1)
        if message_width < min_message_width and location_width > len(location_suffix) + 1:
            deficit = min_message_width - message_width
            shrink_by = min(deficit, location_width - len(location_suffix) - 1)
            location_width -= shrink_by
            message_width += shrink_by

        location = self._fit_location(path, location_suffix, location_width)
        message_width = max(1, usable - len(location) - 1)
        row = f"{prefix}{location} {truncate_end(message, message_width)}"
        return truncate_end(row, content_width)

    def _fit_location(self, path: str, suffix: str, max_width: int) -> str:
        location = f"{path}{suffix}"
        if len(location) <= max_width:
            return location
        basename = Path(path).name or path
        basename_location = f"{basename}{suffix}"
        if len(basename_location) <= max_width:
            return basename_location
        path_width = max(1, max_width - len(suffix))
        return f"{truncate_middle(basename, path_width)}{suffix}"

    def _row_message(self, diagnostic: Diagnostic) -> str:
        message = " ".join(str(diagnostic.message or "Diagnostic").split())
        return message or "Diagnostic"

    def _display_path(self, file_path: str | None) -> str:
        return diagnostic_display_path(
            file_path,
            project_root=self._diagnostics_project_root(),
            cwd=os.getcwd(),
        )

    def _diagnostics_project_root(self) -> str | None:
        filename = getattr(self.editor, "filename", None)
        if filename:
            path = Path(str(filename)).expanduser()
            return str(path.parent if path.suffix else path)
        registry = getattr(self.editor, "service_registry", None)
        project_service = getattr(registry, "project_service", None)
        root = getattr(project_service, "root", None)
        return str(root) if root else None

    def _diagnostics(self) -> tuple[Diagnostic, ...]:
        snapshot = self._snapshot()
        if snapshot is None:
            return ()
        return snapshot.diagnostics

    def _snapshot(self) -> DiagnosticsSnapshot | None:
        bridge = getattr(self.editor, "linter_bridge", None)
        snapshot = getattr(bridge, "diagnostics_snapshot", None)
        if isinstance(snapshot, DiagnosticsSnapshot):
            return snapshot
        return None

    def _footer(self) -> str:
        full = " r:Run file R:Run workspace Enter:Jump d:Details Esc/F4/q:Close "
        compact = " r:Run R:Workspace Enter:Jump d:Details Esc/F4/q:Close "
        return full if len(full) <= self.width - 4 else compact

    def _open_details_popup(self) -> None:
        diagnostic = self._selected_diagnostic()
        snapshot = self._snapshot()
        if diagnostic is None or snapshot is None:
            self.editor._set_status_message("Diagnostics: no diagnostic selected.")
            return
        self._details_generation = snapshot.generation
        self._details_key = self._diagnostic_key(diagnostic)
        self._details_diagnostic = diagnostic
        self._clear_legacy_lint_popup()
        self.editor._set_status_message("Diagnostic details opened.")
        if hasattr(self.editor, "_force_full_redraw"):
            self.editor._force_full_redraw = True

    def _draw_details_popup(self) -> None:
        if not self._details_is_open():
            return
        diagnostic = self._details_diagnostic
        if diagnostic is None:
            return
        modal_width = min(max(52, self.term_width // 2), max(20, self.term_width - 4))
        content_width = max(1, modal_width - 4)
        popup_lines = self._details_lines(diagnostic, content_width)
        modal_height = min(
            max(9, len(popup_lines) + 4),
            max(5, self.term_height - 2),
        )
        rect = centered_modal_rect(
            self.term_width,
            self.term_height,
            modal_width,
            modal_height,
        )
        try:
            win = curses.newwin(rect.height, rect.width, rect.y, rect.x)
            win.keypad(True)
            self._make_opaque(win)
            win.border()
            title = "Diagnostic details"
            win.addnstr(0, 2, f" {title} ", max(1, rect.width - 4), self.attr_title)
            for row_offset, line in enumerate(popup_lines[: rect.height - 3]):
                win.addnstr(
                    row_offset + 1,
                    2,
                    line,
                    content_width,
                    self.attr_text,
                )
            win.addnstr(
                rect.height - 2,
                2,
                "Esc: close",
                content_width,
                self.attr_dim,
            )
            self._present(win)
        except curses.error:
            pass

    def _details_lines(
        self, diagnostic: Diagnostic, content_width: int
    ) -> list[str]:
        path = self._display_path(diagnostic.file_path)
        lines = [
            f"File: {path}",
            f"Location: {diagnostic.line}:{diagnostic.column}",
            f"Source: {diagnostic.source or '?'}",
        ]
        if diagnostic.code:
            lines.append(f"Code: {diagnostic.code}")
        message = self._row_message(diagnostic)
        lines.extend(self._wrapped_detail("Message: ", message, content_width))
        if diagnostic.fix_hint:
            lines.extend(
                self._wrapped_detail("Fix hint: ", diagnostic.fix_hint, content_width)
            )
        if diagnostic.suggested_code:
            code_shape = " ".join(str(diagnostic.suggested_code).split())
            lines.extend(self._wrapped_detail("Suggested: ", code_shape, content_width))
        lines.append("Preview only. No changes were applied.")
        return lines

    def _wrapped_detail(self, prefix: str, value: str, width: int) -> list[str]:
        width = max(20, min(width, 96))
        text = " ".join(str(value).split())
        wrapped = textwrap.wrap(text, width=max(1, width - len(prefix))) or [""]
        lines = [f"{prefix}{wrapped[0]}"]
        indent = " " * len(prefix)
        lines.extend(f"{indent}{line}" for line in wrapped[1:])
        return lines

    def _details_is_open(self) -> bool:
        return self._details_generation is not None

    def _clear_details_popup(self) -> None:
        self._details_generation = None
        self._details_key = None
        self._details_diagnostic = None
        if hasattr(self.editor, "_force_full_redraw"):
            self.editor._force_full_redraw = True

    def _invalidate_stale_details(
        self,
        snapshot: DiagnosticsSnapshot | None,
        diagnostics: tuple[Diagnostic, ...],
    ) -> None:
        if not self._details_is_open():
            return
        if snapshot is None or snapshot.generation != self._details_generation:
            self._clear_details_popup()
            return
        if not diagnostics:
            self._clear_details_popup()
            return
        selected = self._selected_diagnostic()
        if selected is None or self._diagnostic_key(selected) != self._details_key:
            self._clear_details_popup()

    def _sync_selected_diagnostic_highlight(
        self,
        snapshot: DiagnosticsSnapshot | None,
        diagnostics: tuple[Diagnostic, ...],
    ) -> None:
        if snapshot is None or snapshot.status != "ready" or not diagnostics:
            self._clear_diagnostic_line_highlight()
            return
        diagnostic = self._selected_diagnostic()
        if diagnostic is None:
            self._clear_diagnostic_line_highlight()
            return
        setter = getattr(self.editor, "set_diagnostic_line_highlight", None)
        if callable(setter):
            setter(diagnostic, generation=snapshot.generation)

    def _clear_diagnostic_line_highlight(self) -> None:
        clearer = getattr(self.editor, "clear_diagnostic_line_highlight", None)
        if callable(clearer):
            clearer()

    def _diagnostic_key(self, diagnostic: Diagnostic) -> tuple[object, ...]:
        return (
            diagnostic.file_path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.severity,
            diagnostic.source,
            diagnostic.code,
            diagnostic.message,
            diagnostic.fix_hint,
            diagnostic.suggested_code,
        )

    def _clear_legacy_lint_popup(self) -> None:
        if hasattr(self.editor, "lint_panel_active"):
            self.editor.lint_panel_active = False
        drawer = getattr(self.editor, "drawer", None)
        if drawer is not None and hasattr(drawer, "_next_lint_panel_hide_ts"):
            drawer._next_lint_panel_hide_ts = 0

    def _matches_key(self, key: Any, char: str) -> bool:
        return key == char or key == ord(char)


# ==================== GitPanel Class ====================
class GitPanel(BasePanel):
    """Class GitPanel
    =========================
    Enhanced GitPanel with auto-update, file integration, and git log support.
    This panel provides an interactive Git interface within the editor, allowing users to view repository status,
    perform common Git operations, and browse commit history with pagination. It features auto-updating of Git
    information, integration with the file manager for status display, and a menu-driven UI for executing Git commands.

    Attributes:
        width (int): Width of the panel.
        height (int): Height of the panel.
        start_x (int): X-coordinate where the panel starts.
        win (CursesWindow): The curses window for the panel.
        git_bridge (GitBridge): Bridge object for accessing Git information.
        output_lines (List[str]): Lines of output currently displayed in the panel.
        menu_items (List[str]): List of menu items for Git commands.
        selected_idx (int): Index of the currently selected menu item.
        scroll_offset (int): Scroll offset for output display.
        is_busy (bool): Indicates if a Git command is currently running.
        is_log_view (bool): Indicates if the panel is displaying the git log view.
        auto_update_enabled (bool): Whether auto-update is enabled.
        auto_update_interval (float): Interval in seconds for auto-updating Git info.
        last_update_time (float): Timestamp of the last auto-update.
        auto_update_thread (threading.Thread): Thread for auto-updating Git info.
        should_stop_auto_update (threading.Event): Event to signal stopping auto-update.
        file_status_cache (Dict[str, str]): Cache of file paths to their Git status.
        log_page_size (int): Number of commits per page in git log view.
        log_current_page (int): Current page number in git log view.
        log_format (str): Format string for git log output.

    Methods:
        open(): Prepares the panel for display.
        close(): Cleans up the panel upon closing.
        handle_key(key): Handles keyboard input for navigation and actions.
        draw(): Renders the panel UI.
        get_file_git_status(file_path): Returns the Git status for a given file.
        force_update_file_status_cache(): Forces an update of the file status cache.
        update_file_status(file_path): Updates the Git status cache for a specific file.
        add_watched_file(file_path): Adds a file to the watched files set.
        remove_watched_file(file_path): Removes a file from the watched files set.
        get_watched_files_status(): Returns the statuses of all watched files.
        _handle_status(run_async): Handles the 'Status' command.
        _handle_diff(): Handles the 'Diff' command.
        _handle_log(): Handles the 'Log' command with pagination.
        _handle_add_and_commit(): Handles the 'Add & Commit' command.
        _handle_push(): Handles the 'Push' command.
        _handle_pull(): Handles the 'Pull' command.
        _handle_branch(): Handles branch operations.
        _handle_checkout(): Handles the 'Checkout' command.
        _handle_merge(): Handles the 'Merge' command.
        _handle_fetch(): Handles the 'Fetch' command.
        _handle_reset(): Handles the 'Reset' command.
        _handle_config(): Handles Git config operations.
        _handle_remote(): Handles remote repository operations.
        _toggle_auto_update(): Toggles auto-update on or off.
        _update_file_status_cache(): Updates the file status cache.
        _show_git_log(reset_page): Displays the git log with pagination.
        _handle_log_navigation(key): Handles navigation in git log view.
        _change_log_format(): Changes the format of git log output.
        _run_command_async(cmd_list, show_running): Runs a Git command asynchronously.
        _run_command_sync(cmd_list): Runs a Git command synchronously.
        _run_command_and_display_output(cmd_list, show_running): Runs a Git command and displays output.
        _run_git_command(cmd_list): Executes a Git command in the repository context.
        _start_auto_update(): Starts the auto-update thread.
        _stop_auto_update(): Stops the auto-update thread.
        _auto_update_worker(): Worker function for auto-update.
        _update_git_info_background(): Updates Git info in the background.
        _update_status_help(): Updates the status/help message in the editor.
        _draw_frame(is_focused): Draws the panel border and title.
        _draw_info_section(): Draws repository info section.
        _draw_menu_section(is_focused, menu_width): Draws the menu section.
        _draw_output_section(x, width): Draws the output section.
        _get_line_attr(line): Determines the display attribute for a line.
        _get_viewport_height(): Calculates the output viewport height.
        _execute_action(): Executes the selected menu action.
        _handle_not_implemented(): Displays a message for unimplemented actions.
    """

    def __init__(
        self, stdscr: CursesWindow, main_editor_instance: Ecli, **kwargs: Any
    ) -> None:
        """Initialize GitPanel with given curseswindow and editor instance."""
        super().__init__(stdscr, main_editor_instance, **kwargs)
        logger.debug("GitPanel: Initializing...")
        self.panel_kind = "git_control"

        self._layout_window()  # right 40% work area; no global-chrome overlap

        if main_editor_instance.git is None:
            raise ValueError(
                "GitPanel cannot be initialized without a GitBridge instance."
            )
        self.git_bridge: GitBridge = main_editor_instance.git
        self.output_lines: list[str] = ["Select a command from the menu to run."]
        self.command_results: queue.Queue[tuple[int, GitCommandResult]] = queue.Queue()
        self.current_command_label: str = ""
        self._command_generation = 0
        self.menu_items = [
            "Status",
            "Diff",
            "Log",
            "Fetch",
            "Pull",
            "---",
            "Checkout",
            "Add & Commit",
            "Push",
            "Branch",
            "Merge",
            "Reset",
            "---",
            "Config",
            "Remote",
        ]
        self.selected_idx = 0
        self.scroll_offset = 0
        self.is_busy = False
        self.is_log_view = False

        self.auto_update_enabled = True
        self.auto_update_interval = 5.0
        self.last_update_time = 0.0
        self.auto_update_thread: Optional[threading.Thread] = None
        self.should_stop_auto_update: threading.Event = threading.Event()

        self.file_status_cache: dict[str, str] = {}
        self.watched_files: set[str] = set()

        # Async file-status refresh plumbing (used by the File Browser panel).
        # Opening the File Browser must never run ``git status`` on the curses
        # UI thread, so the refresh happens on a daemon worker and results are
        # delivered through this queue and applied by ``drain_file_status_results``.
        self._file_status_results: queue.Queue[Optional[dict[str, str]]] = queue.Queue()
        self._file_status_lock = threading.Lock()
        self._file_status_refresh_in_flight = False

        self.log_page_size = self.height - 8  # Adaptive page size
        self.log_current_page = 0

        # Line display attributes
        self.attr_commit_hash = curses.A_BOLD | curses.color_pair(2)
        self.attr_commit_message = curses.A_NORMAL | curses.color_pair(3)
        self.attr_status_modified = curses.A_BOLD | curses.color_pair(4)
        self.attr_status_unknown = curses.A_NORMAL | curses.color_pair(5)
        self.attr_status_added = curses.A_BOLD | curses.color_pair(2)
        self.attr_status_deleted = curses.A_BOLD | curses.color_pair(1)
        self.attr_status_renamed = curses.A_BOLD | curses.color_pair(6)
        self.log_format = "--oneline"

        self._init_colors()
        logger.debug("GitPanel: Initialization complete.")

    def resize(self) -> None:
        """Handle terminal resize by recalculating dimensions and recreating the window."""
        super().resize()
        self._layout_window()  # right 40% work area; no global-chrome overlap

    def _init_colors(self) -> None:
        """Uses centralized colors from the editor."""
        self.attr_border = self.editor.colors.get("status", curses.A_BOLD)
        self.attr_text = self.editor.colors.get("default", curses.A_NORMAL)
        self.attr_title = self.editor.colors.get("function", curses.A_BOLD)
        self.attr_branch = self.editor.colors.get("keyword", curses.A_BOLD)
        self.attr_output_error = self.editor.colors.get("error", curses.A_NORMAL)
        # Colors for statuses are now also taken from editor.colors
        self.attr_status_modified = self.editor.colors.get("git_dirty", curses.A_NORMAL)
        self.attr_status_new = self.editor.colors.get("git_added", curses.A_NORMAL)
        self.attr_status_deleted = self.editor.colors.get(
            "git_deleted", curses.A_NORMAL
        )
        self.attr_selected = curses.A_REVERSE | curses.A_BOLD
        self.attr_dim = curses.A_DIM
        self.attr_commit_hash = self.editor.colors.get("number", curses.A_NORMAL)
        self.attr_commit_message = self.editor.colors.get("comment", curses.A_NORMAL)

    def _run_command_async(
        self, cmd_list: list[str], show_running: bool = True
    ) -> None:
        """Runs a command in a separate thread (for long, non-interactive operations)."""
        if self.is_busy:
            return

        self.is_busy = True
        self._command_generation += 1
        command_generation = self._command_generation
        self.current_command_label = " ".join(cmd_list)
        if show_running:
            self._set_output_lines([f"Running: {self.current_command_label}..."])
        self._update_status_help()

        def worker() -> None:
            try:
                result = self._run_git_command(cmd_list)
            except Exception as exc:
                result = GitCommandResult(
                    command_label=" ".join(cmd_list),
                    cwd=str(Path.cwd()),
                    returncode=127,
                    stdout="",
                    stderr=str(exc),
                    error=str(exc),
                )
            self.command_results.put((command_generation, result))

        threading.Thread(target=worker, daemon=True).start()

    def _run_command_sync(self, cmd_list: list[str]) -> None:
        """Executes a command synchronously and immediately updates output_lines."""
        if self.is_busy:
            return

        self.is_busy = True
        self._command_generation += 1
        self.current_command_label = " ".join(cmd_list)
        try:
            result = self._run_git_command(cmd_list)
            self._render_command_result(result)
            if result.error != "not_repo":
                self.git_bridge.update_git_info(force=True)
        finally:
            self.is_busy = False
            self._update_status_help()
            self.editor._force_full_redraw = True

    def process_queues(self) -> bool:
        """Render completed Git command results on the UI thread."""
        changed = False
        try:
            while True:
                command_generation, result = self.command_results.get_nowait()
                if command_generation != self._command_generation:
                    changed = True
                    continue
                self._render_command_result(result)
                self.is_busy = False
                if result.error != "not_repo":
                    self.git_bridge.update_git_info(force=True)
                self._update_status_help()
                changed = True
        except queue.Empty:
            pass

        if changed:
            self.editor._force_full_redraw = True
        return changed

    def _set_output_lines(self, lines: list[str]) -> None:
        self.output_lines = lines or [""]
        self.scroll_offset = 0
        self.editor._force_full_redraw = True

    def _cancel_current_operation(self) -> None:
        self._command_generation += 1
        self.is_busy = False
        self.current_command_label = ""
        self._set_output_lines(["Operation cancelled."])
        self._update_status_help()

    def _empty_success_message(self, result: GitCommandResult) -> str:
        if result.command_label.startswith("git status"):
            return "Clean working tree."
        return "Command successful (no output)."

    def _render_command_result(self, result: GitCommandResult) -> None:
        if result.error == "not_repo":
            self._set_output_lines(["Not a Git repository."])
            return

        if result.timed_out:
            lines = [
                f"Command timed out: {result.command_label}",
                f"CWD: {result.cwd}",
            ]
            if result.error:
                lines.append(result.error)
            self._set_output_lines(lines)
            return

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode == 0:
            if stdout:
                self._set_output_lines(stdout.splitlines())
            elif stderr:
                self._set_output_lines(stderr.splitlines())
            else:
                self._set_output_lines([self._empty_success_message(result)])
            return

        lines = [
            f"Command failed: {result.command_label}",
            f"CWD: {result.cwd}",
            f"Return code: {result.returncode}",
        ]
        if stderr:
            lines.append("stderr:")
            lines.extend(stderr.splitlines())
        if stdout:
            lines.append("stdout:")
            lines.extend(stdout.splitlines())
        if result.error and not stderr:
            lines.append(result.error)
        self._set_output_lines(lines)

    def _start_auto_update(self) -> None:
        """Starts the auto-update thread for git information."""
        if not self.auto_update_enabled:
            return

        self.should_stop_auto_update.clear()
        self.auto_update_thread = threading.Thread(
            target=self._auto_update_worker, daemon=True
        )
        if self.auto_update_thread is not None:
            self.auto_update_thread.start()
            logger.debug("GitPanel: Auto-update thread started.")

    def _auto_update_worker(self) -> None:
        """A worker process that runs on a background thread to update data."""
        while not self.should_stop_auto_update.wait(self.auto_update_interval):
            try:
                # Auto-update works only if the GitPanel is visible and not busy
                if self.visible and not self.is_busy:
                    self._update_git_info_background()
            except Exception as e:
                logger.error(f"GitPanel: Auto-update error: {e}")

    def _update_git_info_background(self) -> None:
        """Updates the git information (file status, branch info) in the background."""
        try:
            self.git_bridge.update_git_info(force=True)
        except Exception as e:
            logger.error(f"GitPanel: Background update failed: {e}")

    def _stop_auto_update(self) -> None:
        """Stops the auto-update thread."""
        logger.debug("GitPanel: Stopping auto-update thread...")
        self.should_stop_auto_update.set()

        if self.auto_update_thread and self.auto_update_thread.is_alive():
            self.auto_update_thread.join(timeout=2.0)

        logger.debug("GitPanel: Auto-update stopped.")

    def _update_status_help(self) -> None:
        if self.is_busy:
            msg = "Git: Running..."
        elif self.is_log_view:
            msg = "Log: [n/p] Page [f] Fmt [q] Menu"
        else:
            msg = "Git: [↑/↓] Nav [Enter] Exec [r] Refresh"

        self.editor._set_status_message(msg + " | [F9/Esc] Close")

    def force_update_file_status_cache(self) -> None:
        """Synchronously rebuild the file status cache.

        This runs ``git status --porcelain`` on the calling thread and must
        only be used off the curses UI path (e.g. the post-save hook). The File
        Browser panel uses :meth:`request_file_status_refresh` instead so that
        opening it never blocks the editor on a Git subprocess.
        """
        logger.info("Forcing an update of the file status cache.")
        self._update_file_status_cache()

    def request_file_status_refresh(self) -> None:
        """Schedule a non-blocking refresh of the file status cache.

        Runs ``git status --porcelain`` on a daemon thread so the File Browser
        panel can open instantly without waiting for the Git subprocess. The
        parsed result is delivered through ``_file_status_results`` and applied
        on the UI thread by :meth:`drain_file_status_results`. Overlapping
        requests are coalesced into a single in-flight worker.
        """
        with self._file_status_lock:
            if self._file_status_refresh_in_flight:
                return
            self._file_status_refresh_in_flight = True

        def worker() -> None:
            cache: Optional[dict[str, str]] = None
            try:
                cache = self._compute_file_status_cache()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("GitPanel: async file status refresh failed: %s", exc)
                cache = None
            finally:
                self._file_status_results.put(cache)

        threading.Thread(
            target=worker, name="GitFileStatusRefresh", daemon=True
        ).start()

    def drain_file_status_results(self) -> bool:
        """Apply any completed async file-status refresh on the UI thread.

        Non-blocking: only consumes results that are already queued. Returns
        ``True`` when the cache actually changed, so the caller can request a
        single redraw instead of looping continuously.
        """
        changed = False
        try:
            while True:
                cache = self._file_status_results.get_nowait()
                with self._file_status_lock:
                    self._file_status_refresh_in_flight = False
                if cache is not None and cache != self.file_status_cache:
                    self.file_status_cache = cache
                    changed = True
        except queue.Empty:
            pass
        return changed

    def _parse_git_status_code(self, status_code: str) -> str:
        """Parse a Git status code into a single character status.

        Args:
            status_code: A two-character Git status code.

        Returns:
            A single character status code (M, A, D, ??, R) or the stripped code.
        """
        if status_code[0] == "M" or status_code[1] == "M":
            return "M"  # Modified
        if status_code[0] == "A" or status_code[1] == "A":
            return "A"  # Added
        if status_code[0] == "D" or status_code[1] == "D":
            return "D"  # Deleted
        if status_code[0] == "?" and status_code[1] == "?":
            return "??"  # Untracked
        if status_code[0] == "R":
            return "R"  # Renamed
        return status_code.strip()

    def _clear_file_cache_entries(self, file_path: str, rel_path: str) -> None:
        """Remove existing entries for a file from the status cache.

        Args:
            file_path: Absolute path to the file.
            rel_path: Path relative to repository root.
        """
        # Remove both absolute and relative path entries if they exist
        if file_path in self.file_status_cache:
            del self.file_status_cache[file_path]
        if rel_path in self.file_status_cache:
            del self.file_status_cache[rel_path]

    def _update_file_cache_entry(
        self, file_path: str, rel_path: str, status: str
    ) -> None:
        """Update the status cache for both absolute and relative paths.

        Args:
            file_path: Absolute path to the file.
            rel_path: Path relative to repository root.
            status: Git status code to set.
        """
        self.file_status_cache[file_path] = status
        self.file_status_cache[rel_path] = status

    def update_file_status(self, file_path: str) -> None:
        """Updates the Git status cache for a specific file after it is saved.

        Args:
            file_path (str): The path to the file to update.
        """
        logger.debug(f"GitPanel: Updating status for saved file: {file_path}")
        try:
            # Get Git status for the specific file
            cmd = ["git", "status", "--porcelain", "--", file_path]
            result = self._run_git_command(cmd)
            if result.returncode != 0:
                return

            # Get relative path for the file
            rel_path = os.path.relpath(file_path, self._get_repo_dir())
            self._clear_file_cache_entries(file_path, rel_path)

            # Process each line of Git status output
            for line in result.stdout.strip().splitlines():
                if len(line) < 3:  # Skip invalid lines
                    continue

                # Parse status line
                status_code = line[:2]
                fp = line[3:].strip()

                # Update cache if we found our file
                if fp in (file_path, rel_path):
                    status = self._parse_git_status_code(status_code)
                    self._update_file_cache_entry(file_path, rel_path, status)
                    break

        except Exception as e:
            logger.error(f"Failed to update status for {file_path}: {e}")

    def _toggle_auto_update(self) -> None:
        """Toggles auto-update."""
        self.auto_update_enabled = not self.auto_update_enabled
        if self.auto_update_enabled:
            self._start_auto_update()
            self.editor._set_status_message("Auto-update enabled.")
        else:
            self._stop_auto_update()
            self.editor._set_status_message("Auto-update disabled.")

    def _compute_file_status_cache(self) -> Optional[dict[str, str]]:
        """Run ``git status --porcelain`` and return a fresh path→status map.

        Returns ``None`` when Git is unavailable or the command fails, so
        callers can preserve the previous cache instead of clearing it. Apart
        from the subprocess, this is pure: it never mutates
        ``self.file_status_cache``, which makes it safe to call from a worker
        thread.
        """
        result = self._run_git_command(["git", "status", "--porcelain"])
        if result.returncode != 0:
            return None

        cache: dict[str, str] = {}
        repo_dir = self._get_repo_dir()
        for line in result.stdout.strip().splitlines():
            if len(line) < 3:
                continue
            status = self._parse_git_status_code(line[:2])
            file_path = line[3:].strip()
            # Save both full and relative paths so lookups by either resolve.
            cache[os.path.join(repo_dir, file_path)] = status
            cache[file_path] = status
        return cache

    def _update_file_status_cache(self) -> None:
        """Synchronously refresh the file status cache for the file manager.

        Used off the curses UI thread (e.g. the post-save hook). On failure or
        when not in a repository the previous cache is preserved unchanged.
        """
        try:
            cache = self._compute_file_status_cache()
        except Exception as e:
            logger.error(f"GitPanel: Failed to update file status cache: {e}")
            return
        if cache is not None:
            self.file_status_cache = cache

    def get_file_git_status(self, file_path: str) -> Optional[str]:
        """Returns the git status of a file for integration with the file manager.

        Args:
            file_path: Path to the file (absolute or relative)

        Returns:
            File status ('M', 'A', 'D', '??', 'R', None)
        """
        return self.file_status_cache.get(file_path)

    def add_watched_file(self, file_path: str) -> None:
        """Adds a file to the list of watched files."""
        self.watched_files.add(file_path)

    def remove_watched_file(self, file_path: str) -> None:
        """Removes a file from the list of watched files."""
        self.watched_files.discard(file_path)

    def get_watched_files_status(self) -> dict[str, str]:
        """Returns the statuses of all watched files."""
        return {
            path: status
            for path in self.watched_files
            if (status := self.get_file_git_status(path)) is not None
        }

    def _handle_log(self) -> None:
        """Shows git log with pagination."""
        self._show_git_log()

    def _show_git_log(self, reset_page: bool = True) -> None:
        """Shows git log with pagination support."""
        if reset_page:
            self.log_current_page = 0

        # Form the command for git log
        skip_commits = self.log_current_page * self.log_page_size
        cmd = [
            "git",
            "log",
            self.log_format,
            f"--max-count={self.log_page_size}",
            f"--skip={skip_commits}",
        ]

        # Add navigation information
        navigation_info = [
            f"=== Git Log (page {self.log_current_page + 1}, format: {self.log_format}) ===",
            "Navigation: [n] Next page, [p] Previous page, [f] Change format",
            "---",
        ]

        result = self._run_git_command(cmd)
        if result.returncode == 0:
            log_lines = result.stdout.strip().splitlines()
            if log_lines:
                self.output_lines = navigation_info + log_lines
            else:
                self.output_lines = navigation_info + ["No more commits."]
        else:
            self.output_lines = navigation_info + [f"Error: {result.stderr.strip()}"]

        self.scroll_offset = 0
        self.editor._set_status_message(f"Git log (page {self.log_current_page + 1})")

    def _handle_log_navigation(self, key: int) -> bool:
        """Handles navigation through git log."""
        if not self.visible or self.menu_items[self.selected_idx] != "Log":
            return False

        if key == ord("n"):  # Next page
            self.log_current_page += 1
            self._show_git_log(reset_page=False)
            return True
        if key == ord("p"):  # Previous page
            if self.log_current_page > 0:
                self.log_current_page -= 1
                self._show_git_log(reset_page=False)
            return True
        if key == ord("f"):  # Change format
            self._change_log_format()
            return True

        return False

    def _change_log_format(self) -> None:
        """Changes the format of git log output."""
        formats = ["--oneline", "--short", "--full"]
        current_idx = (
            formats.index(self.log_format) if self.log_format in formats else 0
        )
        next_idx = (current_idx + 1) % len(formats)
        self.log_format = formats[next_idx]

        format_names = {"--oneline": "oneline", "--short": "short", "--full": "full"}
        self.editor._set_status_message(
            f"Log format changed to: {format_names[self.log_format]}"
        )
        self._show_git_log()

    def open(self) -> None:
        """Prepares the panel for display."""
        super().open()
        logger.info("GitPanel: Opening panel.")
        curses.curs_set(0)
        if self.editor.git:
            self.editor.git.update_git_info(force=True)
            self._handle_status()
            self._update_status_help()

    def close(self) -> None:
        """Cleans up the panel upon closing and restores the terminal cursor."""
        self._stop_auto_update()  # Stop auto-update
        super().close()
        logger.info("GitPanel: Closing panel with auto-update stopped.")
        curses.curs_set(1)

    def _get_repo_dir(self) -> str:
        """Determines the repository directory based on the active file."""
        repo_root = self.git_bridge.resolve_repo_root(self.editor.filename)
        if repo_root is not None:
            return repo_root
        if self.editor.filename:
            path = Path(self.editor.filename).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            return str(path if path.is_dir() else path.parent)
        return os.getcwd()

    def _run_git_command(self, cmd_list: list[str]) -> GitCommandResult:
        """Executes a Git command in the correct repository context."""
        logger.debug(f"GitPanel: Running command: {cmd_list}")
        return self.git_bridge.run_git_command(
            cmd_list,
            file_path_context=self.editor.filename,
            timeout=15.0,
        )

    def _navigate_menu(self, direction: int) -> None:
        """Navigate through the menu items, skipping separators.

        Args:
            direction: 1 for down, -1 for up.
        """
        total = len(self.menu_items)
        self.selected_idx = (self.selected_idx + direction) % total

        # Skip separator lines
        while self.menu_items[self.selected_idx] == "---":
            self.selected_idx = (self.selected_idx + direction) % total

    def _handle_common_actions(self, key: Any) -> bool:
        """Handle common actions like refresh, auto-update toggle, and panel controls.

        Args:
            key: The key event.

        Returns:
            True if the key was handled, False otherwise.
        """
        if key == ord("r"):
            self._handle_status()
        elif key == ord("a"):
            self._toggle_auto_update()
        elif key in (curses.KEY_F9, 27, ord("q")):
            if self.editor.panel_manager:
                self.editor.panel_manager.close_active_panel()
        elif key == getattr(curses, "KEY_F12", 276):
            if hasattr(self.editor, "toggle_focus"):
                self.editor.toggle_focus()
        else:
            return False
        return True

    def handle_key(self, key: Any) -> bool:
        """Processes a single key press when the Git panel has focus.

        This method acts as the main input dispatcher for the Git panel. It maps
        various key events to specific actions, such as navigating the command menu,
        executing Git commands, refreshing the view, or closing the panel.

        The method handles the following key bindings:
        - Up/Down Arrows, 'k'/'j': Navigates through the list of menu items,
          skipping separator lines.
        - Enter: Executes the currently selected command from the menu.
        - 'r': Refreshes the repository status view.
        - 'a': Toggles the auto-update feature on or off.
        - F9, Escape, 'q': Closes the Git panel and returns focus to the editor.
        - F12: Toggles focus between the panel and the main editor window.
        - 'n'/'p'/'f' (in log view): Navigates through Git log pages or changes
          the log format.

        Args:
            key: The key event received from curses. Can be an integer for special
                 keys (e.g., curses.KEY_UP) or a character code.

        Returns:
            True if the key was handled by the panel, which typically signals that
            a screen redraw is required. False if the key was not recognized,
            allowing it to be processed by other handlers if necessary.
        """
        # Basic validity checks
        if not self.visible:
            return False
        if self.is_busy:
            if key in (27, ord("q")):
                self._cancel_current_operation()
                return True
            return False

        # Handle log navigation first as it's a special case
        if self._handle_log_navigation(key):
            return True

        # Handle menu navigation
        if key in (curses.KEY_UP, ord("k")):
            self._navigate_menu(-1)
        elif key in (curses.KEY_DOWN, ord("j")):
            self._navigate_menu(1)
        elif (
            key in (curses.KEY_ENTER, 10, 13, ord("\n"), "\n")
            and self.menu_items[self.selected_idx] != "---"
        ):
            self._execute_action()
        elif not self._handle_common_actions(key):
            return False

        self._update_status_help()
        return True

    def _get_viewport_height(self) -> int:
        """Calculate the available height for the output viewport."""
        return max(1, self.height - 4 - len(self.menu_items) - 3)

    def draw(self) -> None:
        """Draws the Git panel's complete UI, including the header, menu, and output sections.
        This method is called on every frame of the main editor loop.
        """
        # 1. Initial Visibility Check
        # Abort immediately if the panel is not supposed to be visible.
        if not self.visible:
            return

        # 2. Guard Clause for Small Window Sizes
        # Prevent drawing if the panel is too small to render correctly,
        # which can happen after a terminal resize. This avoids `curses.error`.
        # The minimums are chosen to ensure space for borders, headers, and some content.
        if self.height < 8 or self.width < 25:
            return

        try:
            # 3. Prepare for Drawing
            # Clear the panel's dedicated window to remove contents from the previous frame.
            self.win.erase()
            is_focused = self.editor.focus == "panel"

            # 4. Draw UI Components using Helper Methods
            # Draw the main border and title (e.g., "Git Control").
            self._draw_frame(is_focused)
            # Draw the top section containing repository info (branch, user, status).
            self._draw_info_section()

            # 5. Draw Layout Dividers
            # Draw the horizontal line that separates the header from the main content area.
            try:
                # Combine the line character and its attribute for a more robust draw call.
                h_char_attr = curses.ACS_HLINE | self.attr_border
                self.win.hline(3, 1, h_char_attr, self.width - 2)
            except curses.error:
                # Fail silently if this specific line can't be drawn due to edge-case dimensions.
                pass

            # Define the layout for the two main columns: menu and output.
            menu_width = 22  # A fixed width for the left-side command menu.

            # Draw the vertical line that separates the menu from the command output area.
            try:
                v_char_attr = curses.ACS_VLINE | self.attr_border
                # The line should span the height of the content area.
                self.win.vline(4, menu_width, v_char_attr, self.height - 5)
            except curses.error:
                # Fail silently if this line can't be drawn.
                pass

            # 6. Draw Content Sections
            # Draw the interactive command menu on the left side.
            self._draw_menu_section(is_focused, menu_width)
            # Draw the Git command output on the right side.
            self._draw_output_section(menu_width + 1, self.width - menu_width - 1)

            # 7. Finalize Frame
            # Stage all the drawing changes to the virtual screen (buffer).
            # The physical terminal screen will be updated in the main loop's `curses.doupdate()`.
            self._present(self.win)

        except curses.error as e:
            # Catch any other unexpected curses errors during the draw cycle to prevent a crash.
            logging.error(f"Curses error in GitPanel.draw: {e}", exc_info=True)
            pass

    def _execute_action(self) -> None:
        action_name = (
            self.menu_items[self.selected_idx]
            .lower()
            .replace(" ", "_")
            .replace("&", "and")
        )
        handler = getattr(self, f"_handle_{action_name}", self._handle_not_implemented)
        handler()

    def _get_command_name(self, cmd_list: list[str]) -> str:
        """Get the git command name from the command list."""
        return cmd_list[1] if len(cmd_list) > 1 else cmd_list[0]

    def _run_command_and_display_output(
        self, cmd_list: list[str], show_running: bool = True
    ) -> None:
        """Runs a git command and displays its output in the panel."""
        if self.is_busy:
            return

        self.is_busy = True
        self._update_status_help()

        try:
            logger.debug(f"GitPanel: Running command: {cmd_list}")

            if show_running:
                self._set_output_lines([f"Running: {' '.join(cmd_list)}..."])
                self.draw()
                self.win.refresh()

            result = self._run_git_command(cmd_list)
            self._render_command_result(result)

            # Refresh git info and reset scroll
            if result.error != "not_repo":
                self.editor.git.update_git_info(force=True)
            self.scroll_offset = 0

        except Exception as e:
            logger.error(f"GitPanel: Command execution failed: {e}")
            self._set_output_lines([f"Command execution failed: {str(e)}"])
        finally:
            self.is_busy = False
            self._update_status_help()

    # --- UI Drawing Helpers ---
    def _draw_frame(self, is_focused: bool) -> None:
        """Draws the panel's border and title."""
        border_attr = self.attr_border | (
            curses.A_BOLD if is_focused else curses.A_NORMAL
        )
        self.win.attron(border_attr)
        self.win.border()
        self.win.attroff(border_attr)

        title = " Git Control "
        if self.is_busy:
            title = " Git Control [BUSY] "

        title_x = max(1, (self.width - len(title)) // 2)
        if title_x + len(title) < self.width:
            self.win.addstr(0, title_x, title, self.attr_title)

    def _draw_info_section(self) -> None:
        """Draws the repository info section."""
        branch, user, commits = self.git_bridge.info
        repo_state = getattr(self.git_bridge, "repo_state", "unavailable")
        if repo_state in {"not repo", "unavailable"} and not branch:
            status_text = (
                "● Not a Git repository"
                if repo_state == "not repo"
                else "● Git unavailable"
            )
            self.win.addnstr(1, 2, status_text, self.width - 4, self.attr_dim)
            info_str = "Branch: - | User: - | Commits: 0"
            self.win.addnstr(2, 2, info_str, self.width - 4, self.attr_branch)
            self.win.hline(3, 1, curses.ACS_HLINE, self.width - 2, self.attr_border)
            return

        clean_branch = branch.strip("*")
        has_changes = "*" in branch

        # Status of changes
        if has_changes:
            status_text = "● Uncommitted changes"
            status_attr = self.attr_status_modified
        else:
            status_text = "● Clean working tree"
            status_attr = self.attr_status_new

        # Add auto-update indicator
        if self.auto_update_enabled:
            status_text += " [AUTO]"

        self.win.addnstr(1, 2, status_text, self.width - 4, status_attr)

        # Information about the branch
        info_str = f"Branch: {clean_branch} | User: {user} | Commits: {commits}"
        self.win.addnstr(2, 2, info_str, self.width - 4, self.attr_branch)
        self.win.hline(3, 1, curses.ACS_HLINE, self.width - 2, self.attr_border)

    def _draw_output_section(self, x: int, width: int) -> None:
        """Draws the command output area on the right."""
        y = 4
        viewport_h = self.height - y - 1

        # Scroll indicators
        if len(self.output_lines) > viewport_h:
            scroll_info = f"({self.scroll_offset + 1}-{min(self.scroll_offset + viewport_h, len(self.output_lines))}/{len(self.output_lines)})"
            # Position on the right in the output area
            info_x = x + width - len(scroll_info) - 2
            if info_x > x:
                self.win.addstr(y, info_x, scroll_info, self.attr_dim)

        for i in range(viewport_h):
            line_idx = self.scroll_offset + i
            if line_idx >= len(self.output_lines):
                break

            line = self.output_lines[line_idx]
            attr = self._get_line_attr(line)
            self.win.addnstr(y + i, x + 1, line, width - 2, attr)

    def _get_line_attr(self, line: str) -> int:
        """Determine the display attribute for a line based on its content."""
        clean_line = line.strip()

        # Git attribute mapping
        log_attrs = {
            "commit": self.attr_commit_hash,
            "Author:": self.attr_commit_message,
            "Date:": self.attr_commit_message,
        }
        status_attrs = {
            "M ": self.attr_status_modified,
            "?? ": self.attr_status_unknown,
            "A ": self.attr_status_added,
            "D ": self.attr_status_deleted,
            "R ": self.attr_status_renamed,
        }

        # First check for commit hash
        attr = (
            self.attr_commit_hash
            if len(clean_line) >= 7
            and all(c in "0123456789abcdef" for c in clean_line[:7])
            else self.attr_text
        )  # Default text attribute

        # Then check log messages
        for prefix, log_attr in log_attrs.items():
            if clean_line.startswith(prefix):
                attr = log_attr
                break

        # Finally check status markers
        for prefix, status_attr in status_attrs.items():
            if clean_line.startswith(prefix):
                attr = status_attr
                break

        return attr

    def _draw_menu_section(self, is_focused: bool, menu_width: int) -> None:
        y = 4
        for i, item in enumerate(self.menu_items):
            if y >= self.height - 1:
                break
            if item == "---":
                self.win.hline(y, 1, curses.ACS_HLINE, menu_width - 1, self.attr_border)
            else:
                attr = self.attr_dim if self.is_busy else self.attr_text
                if i == self.selected_idx and is_focused:
                    attr = self.attr_selected
                # Align the text to the left within the allotted space
                self.win.addnstr(
                    y, 2, f"  {item.ljust(menu_width - 6)}", menu_width - 4, attr
                )
            y += 1

    # --- Action Handlers ---
    def _handle_status(self, run_async=True) -> None:
        # Status can be called both synchronously (in the background) and asynchronously (by pressing 'r')
        command = ["git", "status", "--short", "--branch"]
        if run_async:
            self._run_command_async(command)
        else:
            self._run_command_sync(command)

    def _handle_diff(self) -> None:
        """Runs `git diff` and displays the output."""
        self._run_command_async(["git", "diff", "--no-color"])

    def _handle_add_and_commit(self) -> None:
        """Prompts for a commit message and commits all tracked changes."""
        commit_msg = self.editor.prompt("Commit message:")
        if commit_msg:
            self._run_command_and_display_output(
                ["git", "commit", "-a", "-m", commit_msg]
            )
        else:
            self.output_lines = ["Commit cancelled."]
            self.editor._set_status_message("Commit cancelled.")

    def _handle_push(self) -> None:
        """Handles `git push` with upstream handling."""
        self._run_command_sync(["git", "push"])
        if any("no upstream" in line.lower() for line in self.output_lines):
            branch_name = self.git_bridge.info[0].strip("*")
            # Use initial
            remote_name = self.editor.prompt("Set upstream remote:", initial="origin")
            if remote_name and branch_name:
                # Use is_yes_no_prompt
                confirm = self.editor.prompt(
                    f"Run 'git push --set-upstream {remote_name} {branch_name}'? (y/n)",
                    is_yes_no_prompt=True,
                )
                if confirm == "y":
                    self._run_command_sync(
                        ["git", "push", "--set-upstream", remote_name, branch_name]
                    )

    def _handle_pull(self) -> None:
        """Runs `git pull`."""
        self._run_command_async(["git", "pull"])

    def _handle_branch(self) -> None:
        """Handles branch operations (list, create, delete)."""
        self._run_command_and_display_output(["git", "branch", "-v"])
        self.draw()
        self.win.refresh()

        user_input = self.editor.prompt(
            "Branch: <new_name> | del <name> | (empty to cancel)"
        )
        if not user_input:
            self._set_output_lines(["Operation cancelled."])
            return

        parts = user_input.strip().split()
        if len(parts) == 1:
            # Create new branch
            self._run_command_and_display_output(["git", "branch", parts[0]])
        elif len(parts) == 2 and parts[0] == "del":
            # Delete branch
            confirm = self.editor.prompt(f"CONFIRM: Delete branch '{parts[1]}'? (y/n)")
            if confirm and confirm.lower().startswith("y"):
                self._run_command_and_display_output(["git", "branch", "-D", parts[1]])
            else:
                self.output_lines.append(
                    f"\nDeletion of branch '{parts[1]}' cancelled."
                )
        else:
            self.output_lines = [f"Invalid branch command: '{user_input}'"]

    def _handle_checkout(self) -> None:
        """Prompts for a branch/commit and checks it out."""
        target = self.editor.prompt("Checkout to branch/commit:")
        if target:
            self._run_command_and_display_output(["git", "checkout", target])
        else:
            self.output_lines = ["Checkout cancelled."]

    def _handle_merge(self) -> None:
        """Prompts for a branch and merges it."""
        branch = self.editor.prompt("Branch to merge:")
        if branch:
            self._run_command_and_display_output(["git", "merge", branch])
        else:
            self.output_lines = ["Merge cancelled."]

    def _handle_fetch(self) -> None:
        """Fetches all changes from all remotes."""
        self._run_command_async(["git", "fetch", "--all", "--prune"])

    def _handle_reset(self) -> None:
        """Prompts for a commit and reset mode, with confirmation."""
        target = self.editor.prompt("Reset to commit (e.g., HEAD~1):")
        if not target:
            return

        # Use initial for the default value
        mode = self.editor.prompt("Mode (--soft, --mixed, --hard):", initial="--hard")
        if not mode or mode not in ["--soft", "--mixed", "--hard"]:
            self.output_lines = ["Invalid reset mode. Cancelled."]
            return

        # Use is_yes_no_prompt for confirmation
        confirm = self.editor.prompt(
            f"CONFIRM: git reset {mode} {target}? (y/n)", is_yes_no_prompt=True
        )
        if confirm == "y":
            self._run_command_sync(["git", "reset", mode, target])
        else:
            self.output_lines = ["Reset cancelled."]

    def _handle_config(self) -> None:
        """Handles getting and setting Git config values."""
        action = self.editor.prompt("Config: get <key> | set <key> <value> | list")
        if not action:
            self.output_lines = ["Config operation cancelled."]
            return

        try:
            parts = shlex.split(action)
        except ValueError as e:
            self.output_lines = [f"Invalid command syntax: {e}"]
            return

        if not parts:
            return

        command = parts[0].lower()

        if command == "list":
            self._run_command_and_display_output(["git", "config", "--list"])
        elif command == "get" and len(parts) == 2:
            self._run_command_and_display_output(["git", "config", "--get", parts[1]])
        elif command == "set" and len(parts) == 3:
            key, value = parts[1], parts[2]
            if "." not in key:
                self.output_lines = [
                    f"Invalid key format: '{key}'. Must be 'section.key'."
                ]
                return
            scope = self.editor.prompt(
                f"Set '{key}' scope (--local, --global):", initial="--local"
            )
            if scope in ["--local", "--global"]:
                self._run_command_and_display_output(
                    ["git", "config", scope, key, value]
                )
            else:
                self.output_lines = ["Invalid scope. Operation cancelled."]
        else:
            self.output_lines = [f"Invalid config command: '{action}'"]

    def _handle_remote(self) -> None:
        """Handles remote repository operations."""
        self._run_command_and_display_output(["git", "remote", "-v"])
        self.draw()
        self.win.refresh()

        action = self.editor.prompt(
            "Remote: add <name> <url> | remove <name> | (empty to cancel)"
        )
        if not action:
            self._set_output_lines(["Operation cancelled."])
            return

        try:
            parts = shlex.split(action)
        except ValueError as e:
            self.output_lines = [f"Invalid command syntax: {e}"]
            return

        if len(parts) == 3 and parts[0] == "add":
            _, name, url = parts
            self._run_command_and_display_output(["git", "remote", "add", name, url])
        elif len(parts) == 2 and parts[0] == "remove":
            _, name = parts
            self._run_command_and_display_output(["git", "remote", "remove", name])
        else:
            self.output_lines = [f"Invalid remote command: '{action}'"]

    def _handle_not_implemented(self) -> None:
        """Displays a message for unimplemented features."""
        self.output_lines = ["This action is not yet implemented."]
