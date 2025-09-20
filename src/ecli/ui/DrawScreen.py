# ecli/ui/DrawScreen.py
"""DrawScreen.py
========================
DrawScreen — the main class responsible for rendering the ECLI editor interface using the curses library.

It is responsible for:
- displaying text with syntax highlighting,
- drawing line numbers,
- highlighting search matches and selected text,
- rendering the status bar and linter panel,
- correct cursor positioning,
- handling window resizing and scrolling,
- working with terminal colors and attributes.

The class ensures proper handling of wide Unicode characters, supports various terminal color modes,
and implements double buffering for smooth screen updates.
"""

import curses
import logging
import os
import time

from typing import TYPE_CHECKING, Any
from wcwidth import wcwidth
from ecli.utils.utils import CALM_BG_IDX, WHITE_FG_IDX, get_file_icon


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


## ================= сlass DrawScreen ==============================
class DrawScreen:
    """DrawScreen Class
    =========================
    DrawScreen is responsible for rendering the main editor interface using the curses library.
    This class manages all aspects of drawing the editor's UI, including the text area with syntax highlighting,
    line numbers, status bar, search highlights, selection highlights, and optional panels such as lint results.
    It handles window resizing, color initialization, and ensures proper rendering of Unicode and wide characters.
    DrawScreen delegates certain helper methods to the editor core for string width calculations and syntax highlighting.

    Attributes:
        MIN_WINDOW_WIDTH (int): Minimum allowed width of the editor window.
        MIN_WINDOW_HEIGHT (int): Minimum allowed height of the editor window.
        DEFAULT_TAB_WIDTH (int): Default width for tab characters.
        editor (Ecli): Reference to the main editor instance.
        config (Dict[str, Any]): Editor configuration dictionary.
        stdscr (curses.window): The main curses window object.
        colors (Dict[str, int]): Mapping of color names to curses color pairs or attributes.
        _text_start_x (int): X offset where the text area begins.
        content_area_y_offset (int): Y offset for the content area (for panels or padding).
        content_area_x_offset (int): X offset for the content area (for panels or padding).

    Methods:
        get_string_width(text): Returns the display width of a string, accounting for tabs and wide glyphs.
        get_char_width(ch): Returns the display width of a single Unicode character.
        draw(is_editor_focused): Main method to render the entire editor screen.
        truncate_string(s, max_width): Clips a string to a maximum visual width, respecting wide Unicode characters.
        _draw_text_with_syntax_highlighting(): Draws the text area with syntax highlighting.
        _draw_single_line(...): Draws a single line of text with syntax highlighting and scrolling.
        _draw_line_numbers(): Renders line numbers in the gutter.
        _draw_status_bar(): Draws the status bar at the bottom of the screen.
        _draw_search_highlights(): Highlights all visible search matches.
        _draw_selection(): Highlights the current text selection.
        _draw_lint_panel(): Displays the lint results panel if active.
        _show_small_window_error(height, width): Displays an error message if the window is too small.
        _clear_invalidated_lines(): Clears lines that will be redrawn in the current frame.
        _needs_full_redraw(): Determines if a full screen redraw is required.
        _safe_cut_left(s, cells_to_skip): Safely skips a number of screen cells from the left of a string.
        _should_draw_text(): Checks if the text area should be drawn based on window size and content.
        _get_visible_content_and_highlight(): Retrieves visible lines and their syntax-highlighted tokens.
        _position_cursor(): Positions the cursor on the screen, respecting scrolling and boundaries.
        _adjust_vertical_scroll(): Adjusts vertical scrolling to keep the cursor visible.
        _keep_lint_panel_alive(hold_ms): Keeps the lint panel visible for a minimum duration.
        _maybe_hide_lint_panel(): Hides the lint panel after the hold timer expires.
        _update_display(): Physically updates the terminal display using curses double-buffering.
        None directly; all curses errors are caught and logged to ensure the editor remains responsive.
    """

    MIN_WINDOW_WIDTH = 20
    MIN_WINDOW_HEIGHT = 5
    DEFAULT_TAB_WIDTH = 4

    # Constructor / colour-initialisation
    def __init__(self, editor: "Ecli", config: dict[str, Any]) -> None:
        self.editor = editor
        self.config = config
        self.stdscr = editor.stdscr
        self.colors = editor.colors
        self._text_start_x: int = 0

        # panel offsets
        self.content_area_y_offset = 0
        self.content_area_x_offset = 0

        # visible line count initially = window height − 2 (numbers + status bar)
        if not hasattr(self.editor, "visible_lines"):
            h, _ = self.stdscr.getmaxyx()
            self.editor.visible_lines = h - 2

        # ensure calm-dark status colour pairs exist
        self._init_status_colors()

    # Public delegates → make editor helpers available inside this class

    def get_string_width(self, text: str) -> int:
        """Return display width of *text* (accounts for tabs & wide glyphs)."""
        return self.editor.get_string_width(text)

    def get_char_width(self, ch: str) -> int:
        """Return width (1‒2 cells) of a single Unicode code-point."""
        return self.editor.get_char_width(ch)

    # colors xterm-236/ TTY
    def _init_status_colors(self) -> None:
        """Creates status bar pairs based on terminal capabilities.
        - GUI / 256-color: white on xterm-236 (#303030).
        - 16-color: white on black.
        - 8-color / TTY: white on terminal background.
        """
        try:
            curses.use_default_colors()  # allow -1 as the "default background"
        except curses.error:
            pass

        pair_norm, pair_err = 15, 16  # pair numbers can remain the same
        max_colors = curses.COLORS

        if max_colors >= 256:
            fg_idx, bg_idx = WHITE_FG_IDX, CALM_BG_IDX
        elif max_colors >= 16:
            fg_idx, bg_idx = curses.COLOR_WHITE, curses.COLOR_BLACK
        else:  # 8-color mode
            fg_idx, bg_idx = curses.COLOR_WHITE, -1  # -1 - terminal background

        # Ensure indices are within 0..COLORS-1 (except -1)
        fg_idx = fg_idx if fg_idx == -1 or fg_idx < max_colors else curses.COLOR_WHITE
        bg_idx = bg_idx if bg_idx == -1 or bg_idx < max_colors else 0

        try:
            curses.init_pair(pair_norm, fg_idx, bg_idx)
            curses.init_pair(pair_err, fg_idx, bg_idx)
        except curses.error as exc:
            logging.warning("init_pair failed (%s) – roll back to A_REVERSE", exc)
            self.colors["status"] = curses.A_REVERSE
            self.colors["status_error"] = curses.A_REVERSE | curses.A_BOLD
            return

        # Write ready-made attributes
        self.colors["status"] = curses.color_pair(pair_norm)
        self.colors["status_error"] = curses.color_pair(pair_err) | curses.A_BOLD

    def _needs_full_redraw(self) -> bool:
        """Return True when DrawScreen.draw() must call stdscr.erase().

        A full redraw is required (a) after a window-resize or
        (b) when the editor core explicitly sets the private flag
        `_force_full_redraw` to True.
        """
        resized = self.editor.last_window_size != self.stdscr.getmaxyx()
        force = getattr(self.editor, "_force_full_redraw", False)
        return resized or force

    # ---------------------  Safe Left Cut  -------------------
    def _safe_cut_left(self, s: str, cells_to_skip: int) -> str:
        """Cuts off exactly cells_to_skip screen cells (not characters!) from the left,
        ensuring that we do NOT cut a wide character in half.
        Returns the remaining tail of the string.
        """
        skipped = 0
        res = []
        for ch in s:
            w = self.editor.get_char_width(ch)  # 1 or 2 (wcwidth)
            if skipped + w <= cells_to_skip:  # still in the "scroll" zone
                skipped += w
                continue
            if skipped < cells_to_skip < skipped + w:  # boundary hit inside wide-char
                skipped += w  # skip it entirely
                continue
            res.append(ch)
        return "".join(res)

    def _should_draw_text(self) -> bool:
        """Checks whether the text area should be drawn.
        Considers line visibility and minimum window sizes.
        """
        height, width = self.stdscr.getmaxyx()
        if self.editor.visible_lines <= 0:
            logging.debug(
                "DrawScreen _should_draw_text: No visible lines area (visible_lines <= 0)."
            )
            return False
        if height < self.MIN_WINDOW_HEIGHT or width < self.MIN_WINDOW_WIDTH:
            logging.debug(
                f"DrawScreen _should_draw_text: Window too small ({width}x{height}). "
                f"Min required: {self.MIN_WINDOW_WIDTH}x{self.MIN_WINDOW_HEIGHT}."
            )
            return False

        # Additional check: is there any text to draw?
        if not self.editor.text or (
            len(self.editor.text) == 1 and not self.editor.text[0]
        ):
            # TODO:
            # If the text is empty, we may still need to clear the area, but we don't need to draw the text itself.
            # For simplicity, if there's no text, we consider that there's nothing to draw.
            # This could be more complex (e.g., drawing an empty buffer).
            # logging.debug("DrawScreen _should_draw_text: Text buffer is empty.")
            # return False # Uncomment if empty text should not trigger rendering
            pass

        logging.debug("DrawScreen _should_draw_text: Conditions met for drawing text.")
        return True

    def _get_visible_content_and_highlight(
        self,
    ) -> list[tuple[int, list[tuple[str, int]]]]:
        """Gets visible lines and their tokens with syntax highlighting.
        Returns a list of tuples: (line_index, tokens_for_this_line).
        """
        start_line = self.editor.scroll_top
        # self.editor.visible_lines must be set correctly (e.g. height - 2)
        num_displayable_lines = self.editor.visible_lines

        end_line = min(start_line + num_displayable_lines, len(self.editor.text))

        if start_line >= end_line:
            logging.debug(
                "DrawScreen _get_visible_content: No visible lines to process."
            )
            return []

        visible_lines_content = self.editor.text[start_line:end_line]
        line_indices = list(range(start_line, end_line))

        # highlighted_lines_tokens this list[list[tuple[str, int]]]
        highlighted_lines_tokens = self.editor.apply_syntax_highlighting_with_pygments(
            visible_lines_content, line_indices
        )

        # Collect the result in the format list[tuple[int, list[tuple[str, int]]]]
        visible_content_data = []
        for i, line_idx in enumerate(line_indices):
            if i < len(highlighted_lines_tokens):
                tokens_for_line = highlighted_lines_tokens[i]
                visible_content_data.append((line_idx, tokens_for_line))
            else:
                # This should not happen if apply_syntax_highlighting_with_pygments works correctly.
                logging.warning(
                    f"Mismatch between line_indices and highlighted_tokens for line_idx {line_idx}"
                )
                # Add empty tokens for this line to avoid an error.
                visible_content_data.append((line_idx, []))

        logging.debug(
            f"DrawScreen _get_visible_content: Prepared {len(visible_content_data)} lines for drawing."
        )
        return visible_content_data

    def _draw_text_with_syntax_highlighting(self) -> None:
        """Draws text content, respecting line numbers and internal padding."""
        if not self._should_draw_text():
            logging.debug(
                "DrawScreen _draw_text_with_syntax_highlighting: Drawing skipped by _should_draw_text."
            )
            # Clear the text area when not drawing to remove old text
            # This is important if _should_draw_text returns False due to a small window.
            try:
                for r in range(self.editor.visible_lines):
                    self.stdscr.move(
                        r, self._text_start_x
                    )  # self._text_start_x - beginning of text area
                    self.stdscr.clrtoeol()
            except curses.error as e:
                logging.warning(
                    f"Curses error clearing text area in _draw_text_with_syntax_highlighting: {e}"
                )
            return

        visible_content_data = self._get_visible_content_and_highlight()

        if not visible_content_data:
            logging.debug(
                "DrawScreen _draw_text_with_syntax_highlighting: No visible content from _get_visible_content_and_highlight."
            )
            # Clear the text area when no content is available (e.g. empty file out of view)
            try:
                for r in range(self.editor.visible_lines):
                    self.stdscr.move(r, self._text_start_x)
                    self.stdscr.clrtoeol()
            except curses.error as e:
                logging.warning(f"Curses error clearing text area (no content): {e}")
            return

        # Get the window width once
        _h, window_width = self.stdscr.getmaxyx()

        # The padding is now handled by the offset, so we can simplify this.
        text_area_start_x = self._text_start_x + self.content_area_x_offset

        logging.debug(
            f"DrawScreen: Drawing {len(visible_content_data)} lines. "
            f"scroll_left={self.editor.scroll_left}, text_start_x={text_area_start_x}, "
            f"offsets(Y,X)=({self.content_area_y_offset},{self.content_area_x_offset}), "
            f"window_width={window_width}"
        )

        for screen_row, line_data_tuple in enumerate(visible_content_data):
            self._draw_single_line(
                screen_row + self.content_area_y_offset,
                line_data_tuple,
                window_width,
                text_area_start_x,
            )

    def _draw_single_line(
        self,
        screen_row: int,
        line_data: tuple[int, list[tuple[str, int]]],
        window_width: int,
        text_area_start_x: int,
    ) -> None:
        """Draw a single logical line of source text on the given screen row,
        applying horizontal scroll and syntax-highlight attributes.  Wide
        Unicode characters (wcwidth == 2) are never split in half.

        Args:
            screen_row: Absolute Y position in the curses window.
            line_data:  (buffer_index, [(lexeme, attr), ...]).
            window_width: Current terminal width (in cells).
            text_area_start_x: The screen column where the text area begins.
        """
        _line_index, tokens_for_this_line = line_data

        # Clear the target area first.
        try:
            self.stdscr.move(screen_row, text_area_start_x)
            self.stdscr.clrtoeol()
        except curses.error as e:
            logging.error("Curses error while clearing line %d: %s", screen_row, e)
            return

        logical_col_abs = 0  # running display width from line start

        for token_text, token_attr in tokens_for_this_line:
            if not token_text:
                continue

            token_disp_width = self.editor.get_string_width(token_text)
            token_start_abs = logical_col_abs
            # Using the new starting position
            ideal_x = text_area_start_x + (token_start_abs - self.editor.scroll_left)

            cells_cut_left = 0
            if ideal_x < text_area_start_x:
                cells_cut_left = text_area_start_x - ideal_x

            draw_x = max(self._text_start_x, ideal_x)
            avail_screen_w = window_width - draw_x
            if avail_screen_w <= 0:
                # Nothing further on this line is visible.
                break

            visible_w = max(0, token_disp_width - cells_cut_left)
            visible_w = min(visible_w, avail_screen_w)
            if visible_w <= 0:
                logical_col_abs += token_disp_width
                continue

            # Cut left part safely (do not split a wide char).
            visible_part = self._safe_cut_left(token_text, cells_cut_left)
            if not visible_part:
                logical_col_abs += token_disp_width
                continue

            # Cut right part to fit remaining screen width.
            text_to_draw = ""
            drawn_w = 0
            for ch in visible_part:
                char_w = self.editor.get_char_width(ch)
                if drawn_w + char_w > visible_w:
                    break
                text_to_draw += ch
                drawn_w += char_w

            if text_to_draw:
                try:
                    self.stdscr.addstr(screen_row, draw_x, text_to_draw, token_attr)
                except curses.error as e:
                    # Fallback: draw char-by-char if addstr fails (rare, but safe).
                    logging.debug(
                        "addstr failed at (%d,%d): %s – falling back to addch",
                        screen_row,
                        draw_x,
                        e,
                    )
                    cx = draw_x
                    for ch in text_to_draw:
                        if cx >= window_width:
                            break
                        try:
                            self.stdscr.addch(screen_row, cx, ch, token_attr)
                        except curses.error:
                            break
                        cx += self.editor.get_char_width(ch)

            logical_col_abs += token_disp_width

            # Early exit if we've reached the right edge.
            if draw_x + visible_w >= window_width:
                break

    def draw(self) -> None:
        """The main screen drawing method."""
        try:
            height, width = self.stdscr.getmaxyx()

            if height < self.MIN_WINDOW_HEIGHT or width < self.MIN_WINDOW_WIDTH:
                self._show_small_window_error(height, width)
                # last_window_size is now correctly set by the handle_resize method
                return

            if self._needs_full_redraw():
                self.stdscr.erase()
                self.editor._force_full_redraw = False
            else:
                self._clear_invalidated_lines()

            self._draw_line_numbers()
            self._draw_text_with_syntax_highlighting()
            self._draw_search_highlights()
            self._draw_selection()
            self.editor.highlight_matching_brackets()

            separator_y = height - 2
            try:
                char_with_attr = curses.ACS_HLINE | self.colors.get(
                    "comment", curses.A_DIM
                )
                self.stdscr.hline(separator_y, 0, char_with_attr, width)
            except curses.error:
                pass

            self._draw_status_bar()
            self._draw_lint_panel()

            # This logic should happen within the try block and before noutrefresh
            self._maybe_hide_lint_panel()

            self.stdscr.noutrefresh()

        except curses.error as e:
            logging.error(f"Curses error in DrawScreen.draw(): {e}", exc_info=True)
            self.editor._set_status_message(f"Draw error: {str(e)[:80]}...")
        except Exception as e:
            logging.exception("Unexpected error in DrawScreen.draw()")
            self.editor._set_status_message(f"Draw error: {str(e)[:80]}...")

    def _clear_invalidated_lines(self) -> None:
        """Clears the rows that will be redrawn in this frame.
        Avoiding global clear()
        """
        for row in range(self.editor.visible_lines):
            try:
                self.stdscr.move(row, self._text_start_x)
                self.stdscr.clrtoeol()
            except curses.error:
                pass
        # status bar
        try:
            h, _ = self.stdscr.getmaxyx()
            self.stdscr.move(h - 1, 0)
            self.stdscr.clrtoeol()
        except curses.error:
            pass

    def _keep_lint_panel_alive(self, hold_ms: int = 400) -> None:
        """Pin the lint-panel open for a minimum time window.

        This helper is meant to be called immediately after the Flake8 worker
        (running in a background thread) delivers its final output and
        `self.lint_panel_message` has been populated.

        The method sets a future timestamp in the private attribute
        ``_next_lint_panel_hide_ts``.  While the current wall-clock time is less
        than that timestamp, :pymeth:`_maybe_hide_lint_panel` will keep
        ``self.editor.lint_panel_active`` set to ``True`` so that the panel is
        drawn on every frame and does not “flash” for only a single frame.

        Args:
            hold_ms: Minimum time in milliseconds for which the lint panel
                must remain visible.  Default is 400 ms.

        Side Effects:
            * Forces ``self.editor.lint_panel_active = True``.
            * Updates the private timer ``self._next_lint_panel_hide_ts``.

        Notes:
            The draw-loop should call :pymeth:`_maybe_hide_lint_panel` once per
            frame to honour the timer created here.
        """
        self.editor.lint_panel_active = True
        self._next_lint_panel_hide_ts = time.time() + hold_ms / 1000.0

    def _maybe_hide_lint_panel(self) -> None:
        """Deactivate the lint panel once the hold timer expires.

        Should be invoked once per draw frame (e.g. near the end of
        :pymeth:`DrawScreen.draw`).  If the current time is past the moment
        stored in ``self._next_lint_panel_hide_ts``, the helper clears
        ``self.editor.lint_panel_active`` so the panel will no longer be painted.

        This keeps the panel visible for at least the duration requested via
        :pymeth:`_keep_lint_panel_alive` and automatically hides it afterwards.

        Side Effects:
            May set ``self.editor.lint_panel_active = False`` when the timer
            elapses.  Does nothing if the panel was already inactive or if the
            timer has not yet expired.
        """
        if getattr(self, "_next_lint_panel_hide_ts", 0) < time.time():
            self.editor.lint_panel_active = False

    def _show_small_window_error(self, height: int, width: int) -> None:
        """Displays a message that the window is too small."""
        msg = f"Window too small ({width}x{height}). Minimum is 20x5."
        try:
            self.stdscr.clear()  # Clearing before the message
            # Centering the message if possible
            msg_len = len(msg)
            start_col = max(0, (width - msg_len) // 2)
            self.stdscr.addstr(height // 2, start_col, msg)
        except curses.error:
            # If even this doesn't work, the terminal is in a bad state
            pass

    def _draw_line_numbers(self) -> None:
        """Draws line numbers"""
        # Checking the flag
        if not self.editor.show_line_numbers:
            self._text_start_x = 0  # Text starts from the left edge
            return

        _height, width = self.stdscr.getmaxyx()
        # Calculating the width needed for line numbers
        # The maximum line number is the total number of lines in the file
        max_line_num = len(self.editor.text)
        max_line_num_digits = len(
            str(max(1, max_line_num))
        )  # Minimum 1 digit for empty files
        line_num_width = max_line_num_digits + 1  # +1 for space after number

        # Checking if line numbers fit within the window width
        if line_num_width >= width:
            logging.warning(
                f"Window too narrow to draw line numbers ({width} vs {line_num_width})"
            )
            # If they don't fit, skip drawing line numbers
            self._text_start_x = 0  # Text starts from 0 column
            return
        # Saving the starting position for text drawing
        self._text_start_x = line_num_width
        line_num_color = self.colors.get("line_number", curses.color_pair(7))
        # Iterating over visible lines on the screen
        for screen_row in range(self.editor.visible_lines):
            # Calculating the line index in self.text
            line_idx = self.editor.scroll_top + screen_row
            # Checking if this line exists in self.text
            if line_idx < len(self.editor.text):
                # Formatting the line number (1-based)
                line_num_str = (
                    f"{line_idx + 1:>{max_line_num_digits}} "  # Right-aligning + space
                )
                try:
                    # Drawing the line number
                    self.stdscr.addstr(screen_row, 0, line_num_str, line_num_color)
                except curses.error as e:
                    logging.error(
                        f"Curses error drawing line number at ({screen_row}, 0): {e}"
                    )
                    # If an error occurs, skip drawing this line and continue
            else:
                # Drawing empty lines with the desired background in the line number area
                empty_num_str = " " * line_num_width
                try:
                    self.stdscr.addstr(screen_row, 0, empty_num_str, line_num_color)
                except curses.error as e:
                    logging.error(
                        f"Curses error drawing empty line number background at ({screen_row}, 0): {e}"
                    )

    def _draw_lint_panel(self) -> None:
        """Draws a popup panel with the linter's results."""
        if not getattr(self.editor, "lint_panel_active", False):
            return
        msg = self.editor.lint_panel_message
        if not msg:
            return
        h, w = self.stdscr.getmaxyx()
        panel_height = min(max(6, msg.count("\n") + 4), h - 2)
        panel_width = min(
            max(40, max(len(line) for line in msg.splitlines()) + 4), w - 4
        )
        start_y = max(1, (h - panel_height) // 2)
        start_x = max(2, (w - panel_width) // 2)

        # Framing the window
        try:
            for i in range(panel_height):
                line = ""
                if i == 0:
                    line = "┌" + "─" * (panel_width - 2) + "┐"
                elif i == panel_height - 1:
                    line = "└" + "─" * (panel_width - 2) + "┘"
                else:
                    line = "│" + " " * (panel_width - 2) + "│"
                self.stdscr.addstr(start_y + i, start_x, line, curses.A_BOLD)

            # Message split into lines
            msg_lines = msg.splitlines()
            for idx, line in enumerate(msg_lines[: panel_height - 3]):
                self.stdscr.addnstr(
                    start_y + idx + 1,
                    start_x + 2,
                    line.strip(),
                    panel_width - 4,
                    curses.A_NORMAL,
                )
            # Footer
            footer = "Press Esc to close"
            self.stdscr.addnstr(
                start_y + panel_height - 2,
                start_x + 2,
                footer,
                panel_width - 4,
                curses.A_DIM,
            )
        except curses.error as e:
            logging.error(f"Curses error drawing linter panel: {e}")

    def _draw_search_highlights(self) -> None:
        """Applies visual highlighting to all search matches found in the visible text area.

        This method iterates through all currently highlighted search matches and uses
        curses attributes to visually distinguish them on the screen (for example,
        by applying a reverse color scheme or a special color pair). Only matches
        that are currently visible on the screen are processed.

        Cautiously handles Unicode and wide characters, screen boundaries, and
        possible curses errors for robust rendering.

        Raises:
            None. All curses errors are logged; the editor remains responsive.
        """
        if not self.editor.highlighted_matches:
            return  # No matches to highlight

        # Get the search highlight color attribute (defaults to A_REVERSE if not set)
        search_color = self.colors.get("search_highlight", curses.A_REVERSE)
        _height, width = self.stdscr.getmaxyx()
        line_num_width = (
            len(str(max(1, len(self.editor.text)))) + 1
        )  # Width for line numbers plus space

        # Iterate through all matches to be highlighted
        for (
            match_row,
            match_start_idx,
            match_end_idx,
        ) in self.editor.highlighted_matches:
            # Check if the match is within the currently visible lines
            if (
                match_row < self.editor.scroll_top
                or match_row >= self.editor.scroll_top + self.editor.visible_lines
            ):
                continue

            screen_y = match_row - self.editor.scroll_top  # Screen row for this match
            line = self.editor.text[
                match_row
            ]  # The text of the line containing the match

            # Compute X screen positions (before and after scrolling) for match start and end
            match_screen_start_x_before_scroll = self.editor.get_string_width(
                line[:match_start_idx]
            )
            match_screen_start_x = (
                line_num_width
                + match_screen_start_x_before_scroll
                - self.editor.scroll_left
            )

            match_screen_end_x_before_scroll = self.editor.get_string_width(
                line[:match_end_idx]
            )
            match_screen_end_x = (
                line_num_width
                + match_screen_end_x_before_scroll
                - self.editor.scroll_left
            )

            # Clamp drawing area to the visible screen boundaries
            draw_start_x = max(line_num_width, match_screen_start_x)
            draw_end_x = min(width, match_screen_end_x)

            # Calculate the actual width of the highlight to draw
            highlight_width_on_screen = max(0, draw_end_x - draw_start_x)

            # Apply the highlight attribute if there is something to show
            if highlight_width_on_screen > 0:
                try:
                    # Iterate over characters in the line to accurately highlight wide characters
                    current_char_screen_x = (
                        line_num_width - self.editor.scroll_left
                    )  # Initial X for first char
                    for char_idx, char in enumerate(line):
                        char_width = self.editor.get_char_width(char)
                        char_screen_end_x = current_char_screen_x + char_width

                        # If this character falls within the match range and is visible
                        if (
                            match_start_idx <= char_idx < match_end_idx
                            and current_char_screen_x < width
                            and char_screen_end_x > line_num_width
                        ):
                            draw_char_x = max(line_num_width, current_char_screen_x)
                            draw_char_width = min(char_width, width - draw_char_x)

                            if draw_char_width > 0:
                                try:
                                    # Highlight a single character cell with the search color
                                    # chgat(y, x, num_chars, attr): num_chars=1 for one character
                                    self.stdscr.chgat(
                                        screen_y, draw_char_x, 1, search_color
                                    )
                                except curses.error as e:
                                    logging.warning(
                                        f"Curses error highlighting single char at ({screen_y}, {draw_char_x}): {e}"
                                    )
                        current_char_screen_x += (
                            char_width  # Move X for the next character
                        )
                except curses.error as e:
                    logging.error(f"Curses error applying search highlight: {e}")

    def _draw_selection(self) -> None:
        """Paints a visual highlight for the current text selection.

        - For single-line selections, it highlights the precise characters.
        - For multi-line selections, it creates a solid block highlight. The width
        of this block is determined by the longest line within the selection,
        ensuring a continuous, rectangular appearance. Empty lines within the
        selection are also highlighted to this width.
        """
        if (
            not self.editor.is_selecting
            or not self.editor.selection_start
            or not self.editor.selection_end
        ):
            return

        norm_range = self.editor._get_normalized_selection_range()
        if not norm_range:
            return

        start_coords, end_coords = norm_range
        start_y, start_x = start_coords
        end_y, end_x = end_coords

        _height, width = self.stdscr.getmaxyx()
        text_area_start_x = self._text_start_x
        selection_attr = curses.A_REVERSE

        # Initial log for the selection action
        logging.debug(
            f"--- Drawing Selection --- "
            f"Mode: {'Single-Line' if start_y == end_y else 'Multi-Line Block'}, "
            f"Range: ({start_y},{start_x}) -> ({end_y},{end_x})"
        )

        if start_y == end_y:
            # PRECISE SINGLE-LINE SELECTION
            line_text = self.editor.text[start_y]
            screen_y = start_y - self.editor.scroll_top

            if 0 <= screen_y < self.editor.visible_lines:
                x_left = (
                    text_area_start_x
                    + self.editor.get_string_width(line_text[:start_x])
                    - self.editor.scroll_left
                )
                x_right = (
                    text_area_start_x
                    + self.editor.get_string_width(line_text[:end_x])
                    - self.editor.scroll_left
                )

                draw_start_x = max(text_area_start_x, x_left)
                draw_end_x = min(width, x_right)
                highlight_w = max(0, draw_end_x - draw_start_x)

                # Logging for single-line highlight
                logging.debug(
                    f"  Line {start_y} (Screen {screen_y}): Single-line highlight. "
                    f"x_left={x_left}, x_right={x_right}, "
                    f"draw_start={draw_start_x}, draw_end={draw_end_x}, highlight_w={highlight_w}"
                )

                if highlight_w > 0:
                    try:
                        self.stdscr.chgat(
                            screen_y, draw_start_x, highlight_w, selection_attr
                        )
                    except curses.error as e:
                        logging.error(f"Curses error on single-line chgat: {e}")

        else:
            # SOLID BLOCK FOR MULTI-LINE SELECTION
            # Find the maximum visual width of all lines in the selection.
            max_visual_width = 0
            for i in range(start_y, end_y + 1):
                if i < len(self.editor.text):
                    line_width = self.editor.get_string_width(self.editor.text[i])
                    max_visual_width = max(max_visual_width, line_width)

            # Log the calculated max width for the block
            logging.debug(
                f"  Multi-line: Calculated max_visual_width for block: {max_visual_width} cells."
            )

            # Iterate through the selected lines and draw the highlight block.
            for doc_y in range(start_y, end_y + 1):
                screen_y = doc_y - self.editor.scroll_top

                if not (0 <= screen_y < self.editor.visible_lines):
                    # Log when a line is skipped because it's off-screen
                    logging.debug(f"  Line {doc_y}: Skipped (not visible on screen).")
                    continue

                highlight_start_on_screen = text_area_start_x - self.editor.scroll_left
                highlight_end_on_screen = highlight_start_on_screen + max_visual_width

                draw_start_x = max(text_area_start_x, highlight_start_on_screen)
                draw_end_x = min(width, highlight_end_on_screen)
                highlight_w = max(0, draw_end_x - draw_start_x)

                # Detailed log for each line in the multi-line block
                logging.debug(
                    f"  Line {doc_y} (Screen {screen_y}): Multi-line highlight. "
                    f"highlight_start={highlight_start_on_screen}, highlight_end={highlight_end_on_screen}, "
                    f"draw_start={draw_start_x}, draw_end={draw_end_x}, highlight_w={highlight_w}"
                )

                if highlight_w > 0:
                    try:
                        self.stdscr.chgat(
                            screen_y, draw_start_x, highlight_w, selection_attr
                        )
                    except curses.error as e:
                        logging.error(
                            f"Curses error on multi-line chgat for line {doc_y}: {e}"
                        )

    def truncate_string(self, s: str, max_width: int) -> str:
        """Return `s` clipped to visual width `max_width`.

        Wide-Unicode characters (e.g. CJK), zero-width joiners and other
        multi-cell glyphs are accounted for with :pyfunc:`wcwidth.wcwidth`.

        Parameters
        ----------
        s :
            The original text.
        max_width :
            Maximum number of terminal cells the string may occupy.

        Returns:
        -------
        str
            Either the original text (if it already fits) or a prefix whose
            display width does not exceed *max_width*.
        """
        result: list[str] = []
        consumed = 0

        for ch in s:
            w = wcwidth(ch)
            if w < 0:  # Non-printable → treat as single-cell
                w = 1
            if consumed + w > max_width:  # Would overflow → stop
                break
            result.append(ch)
            consumed += w

        return "".join(result)

    def _draw_status_bar(self) -> None:
        """Single-line status bar (bottom of the screen).

        ╭─ Left ─────────────────────────────────────────────────────────────╮
        │  🗎  file.py* | Python | UTF-8 | Ln 42/123 | Col 8 | INS            │
        ├─ Middle ───────────────────────────────────────────────────────────┤
        │                               Ready                                │
        ╰─ Right ────────────────────────────────────────────────────────────╯
                                          Git: user.name, main, 3   ← green
                                          Git: None                 ← normal
        """
        if self.editor.is_lightweight:
            return

        try:
            height, width = self.stdscr.getmaxyx()
            if height <= 2:
                return  # not enough space

            y = height - 1  # last line

            # -- colours ----------------------------------------------
            c_norm = self.colors["status"]  # white on calm-dark
            c_err = self.colors["status_error"]  # bold white on calm-dark
            c_git = self.colors.get("git_info", c_norm)
            c_dirty = self.colors.get("git_dirty", c_norm | curses.A_BOLD)

            # -- left part --------------------------------------------
            icon = get_file_icon(self.editor.filename, self.config)
            fname = (
                os.path.basename(self.editor.filename)
                if self.editor.filename
                else "No Name"
            )
            lexer = self.editor._lexer.name if self.editor._lexer else "plain text"
            left = (
                f" {icon} {fname}{'*' if self.editor.modified else ''} | "
                f"{lexer} | {self.editor.encoding.upper()} | "
                f"Ln {self.editor.cursor_y + 1}/{len(self.editor.text)} | "
                f"Col {self.editor.cursor_x + 1} | "
                f"{'INS' if self.editor.insert_mode else 'REP'} "
            )
            left_w = self.editor.get_string_width(left)

            # -- right part = Git info ---------------------------------
            git_txt = ""
            git_attr = None
            if self.editor.git and self.editor.config.get("git", {}).get(
                "enabled", True
            ):
                branch, user, commits = self.editor.git.info
                if branch:
                    dirty = "*" in branch
                    branch = branch.rstrip("*")
                    git_txt = f" Git: {user}, {branch}, {commits or '0'}"
                    git_attr = c_dirty if dirty else c_git
                else:
                    git_txt = " Git: None"
            right_w = self.editor.get_string_width(git_txt)

            # -- middle = status message --------------------------------
            msg = self.editor.status_message or "Ready"
            spacing = width - left_w - right_w
            if spacing < self.editor.get_string_width(msg):
                msg = self.truncate_string(msg, max(0, spacing - 1))

            msg_w = self.editor.get_string_width(msg)
            pad_left = max(0, (spacing - msg_w) // 2)
            pad_right = max(0, spacing - msg_w - pad_left)
            middle = " " * pad_left + msg + " " * pad_right

            # -- compose & paint ----------------------------------------
            line = (left + middle + git_txt)[:width]
            line += " " * (width - self.editor.get_string_width(line))
            self.stdscr.addstr(y, 0, line, c_norm)

            # colourise Git section
            if git_attr is not None and right_w:
                git_x = width - right_w
                if git_x >= 0:
                    self.stdscr.chgat(y, git_x, right_w, git_attr)

            # highlight “error” in message
            if "error" in msg.lower():
                err_x = left_w + pad_left
                self.stdscr.chgat(y, err_x, msg_w, c_err)

        except curses.error:
            pass  # drawing outside screen
        except Exception:
            logging.exception("Unexpected error in _draw_status_bar")

    def _position_cursor(self) -> None:
        """Positions the cursor on the screen, respecting scrolling and view boundaries.
        Correctly handles the cursor being on the virtual line after the last line of text.
        """
        height, width = self.stdscr.getmaxyx()
        if height <= 2:
            return

        text_area_start_x = self._text_start_x

        # Explicit calculation of the text area height ---
        # Instead of self.editor.visible_lines, which can be 0 during initialization,
        # we use the actual window dimensions.
        text_area_height = max(1, height - 2)

        if self.editor.cursor_y >= len(self.editor.text):
            cursor_display_width = 0
        else:
            self.editor._ensure_cursor_in_bounds()
            current_line = self.editor.text[self.editor.cursor_y]
            cursor_display_width = self.editor.get_string_width(
                current_line[: self.editor.cursor_x]
            )

        # 2. Adjust Vertical Scroll
        max_screen_row = text_area_height - 1
        if self.editor.cursor_y < self.editor.scroll_top:
            self.editor.scroll_top = self.editor.cursor_y
        elif self.editor.cursor_y > self.editor.scroll_top + max_screen_row:
            self.editor.scroll_top = self.editor.cursor_y - max_screen_row

        # 3. Adjust Horizontal Scroll
        text_area_width = max(1, width - text_area_start_x)
        if cursor_display_width < self.editor.scroll_left:
            self.editor.scroll_left = cursor_display_width
        elif cursor_display_width >= self.editor.scroll_left + text_area_width:
            self.editor.scroll_left = cursor_display_width - text_area_width + 1

        # 4. Calculate Final Screen Coordinates
        final_screen_y = (
            self.editor.cursor_y - self.editor.scroll_top
        ) + self.content_area_y_offset
        final_screen_x = (
            text_area_start_x + cursor_display_width - self.editor.scroll_left
        )

        final_screen_y = max(
            self.content_area_y_offset,
            min(final_screen_y, max_screen_row + self.content_area_y_offset),
        )
        final_screen_x = max(text_area_start_x, min(final_screen_x, width - 1))

        # 5. Move the Physical Cursor
        try:
            logging.debug(
                f"Positioning cursor: screen_y={final_screen_y}, screen_x={final_screen_x}. "
                f"Logical: ({self.editor.cursor_y}, {self.editor.cursor_x}). Scroll: ({self.editor.scroll_top}, {self.editor.scroll_left}). "
                f"Offsets(Y,X)=({self.content_area_y_offset},{self.content_area_x_offset})"
            )
            self.stdscr.move(final_screen_y, final_screen_x)
        except curses.error as e:
            logging.warning(
                f"Curses error positioning cursor at ({final_screen_y}, {final_screen_x}): {e}"
            )
            try:
                self.stdscr.move(0, text_area_start_x)
            except curses.error:
                pass

    def _adjust_vertical_scroll(self) -> None:
        """Adjusts the vertical scroll (scroll_top) to ensure the cursor remains visible on the screen.

        This method is typically called after window resize events or other situations
        where the cursor could move off-screen. It ensures that scroll_top is always
        within valid bounds and that the cursor is always within the visible text area.

        Side Effects:
            Modifies self.editor.scroll_top as necessary.

        Raises:
            None. All adjustments are logged.
        """
        height, _width = self.stdscr.getmaxyx()
        text_area_height = max(1, height - 2)

        # If the total number of lines fits on the screen, always show from the top.
        if len(self.editor.text) <= text_area_height:
            self.editor.scroll_top = 0
            return

        # Calculate the cursor's position relative to the visible area.
        screen_y = self.editor.cursor_y - self.editor.scroll_top

        # If the cursor is above the visible area, scroll up.
        if screen_y < 0:
            self.editor.scroll_top = self.editor.cursor_y
            logging.debug(
                f"Adjusted vertical scroll: cursor above view. New scroll_top: {self.editor.scroll_top}"
            )
        # If the cursor is below the visible area, scroll down.
        elif screen_y >= text_area_height:
            self.editor.scroll_top = self.editor.cursor_y - text_area_height + 1
            logging.debug(
                f"Adjusted vertical scroll: cursor below view. New scroll_top: {self.editor.scroll_top}"
            )

        # Ensure scroll_top stays within valid bounds.
        self.editor.scroll_top = max(
            0, min(self.editor.scroll_top, len(self.editor.text) - text_area_height)
        )
        logging.debug(f"Final adjusted scroll_top: {self.editor.scroll_top}")

    def _update_display(self) -> None:
        """Physically updates the screen contents using the curses library.

        This method prepares the virtual screen refresh with `noutrefresh()`, which collects all
        pending drawing operations in memory, and then applies all those changes at once to the
        physical terminal using `curses.doupdate()`. This double-buffering approach helps prevent
        flickering and ensures smoother UI updates.

        If a curses error occurs during the refresh, the error is logged and the method
        returns gracefully, assuming the main application loop will handle the situation.

        Raises:
            None. All errors are logged; the editor remains operational.
        """
        try:
            # noutrefresh() prepares window updates in memory, without immediately
            # applying them to the physical terminal screen.
            self.stdscr.noutrefresh()

            # doupdate() applies all pending updates from all windows to the terminal at once.
            curses.doupdate()
        except curses.error as e:
            logging.error(f"Curses doupdate error: {e}")
            # Continue running; the main application loop will handle screen errors gracefully.
            pass
