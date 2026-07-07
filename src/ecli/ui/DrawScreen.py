# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/DrawScreen.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

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

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from wcwidth import wcwidth
from ecli.ui.geometry import compute_layout
from ecli.utils.utils import CALM_BG_IDX, WHITE_FG_IDX, get_file_icon


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


def prepare_visible_text_segment(
    source: str,
    cells_to_skip: int,
    max_cells: int,
    char_width: Callable[[str], int] | None = None,
) -> str:
    """Return the visible slice of a line without mutating or stripping it."""
    if max_cells <= 0:
        return ""

    width_of = char_width or _default_char_width
    skipped = 0
    drawn = 0
    visible: list[str] = []

    for ch in source:
        ch_width = width_of(ch)
        if skipped + ch_width <= cells_to_skip:
            skipped += ch_width
            continue
        if skipped < cells_to_skip < skipped + ch_width:
            skipped += ch_width
            continue
        if drawn + ch_width > max_cells:
            break
        visible.append(ch)
        drawn += ch_width

    return "".join(visible)


def _default_char_width(ch: str) -> int:
    width = wcwidth(ch)
    return width if width >= 0 else 1


## ================= class DrawScreen ==============================
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

    # --- Professional chrome layout ------------------------------------
    HEADER_HEIGHT = 1
    STATUS_HEIGHT = 1
    FOOTER_HEIGHT = 1
    # Below this window height the header and footer are dropped (status only)
    # so very small terminals keep the maximum number of editable rows.
    MIN_HEIGHT_FOR_FULL_CHROME = 8

    @classmethod
    def chrome_heights(cls, height: int) -> tuple[int, int, int]:
        """Return ``(header_h, status_h, footer_h)`` for a window height."""
        if height < cls.MIN_HEIGHT_FOR_FULL_CHROME:
            return 0, cls.STATUS_HEIGHT, 0
        return cls.HEADER_HEIGHT, cls.STATUS_HEIGHT, cls.FOOTER_HEIGHT

    @classmethod
    def content_height(cls, height: int) -> int:
        """Number of editor text rows available for a window height."""
        header_h, status_h, footer_h = cls.chrome_heights(height)
        return max(1, height - header_h - status_h - footer_h)

    # Below this width the vertical viewport borders are dropped.
    MIN_WIDTH_FOR_BORDERS = 40

    @classmethod
    def border_cols(cls, height: int, width: int) -> tuple[int, int]:
        """Return ``(left, right)`` vertical-border widths for the window size.

        Borders only appear alongside the full header/footer chrome and on wide
        enough terminals; otherwise they degrade to ``(0, 0)``.
        """
        if height < cls.MIN_HEIGHT_FOR_FULL_CHROME or width < cls.MIN_WIDTH_FOR_BORDERS:
            return 0, 0
        return 1, 1

    # Constructor / colour-initialisation
    def __init__(self, editor: "Ecli", config: dict[str, Any]) -> None:
        self.editor = editor
        self.config = config
        self.stdscr = editor.stdscr
        self.colors = editor.colors
        self._text_start_x: int = 0

        # Initial chrome geometry; draw() recomputes this every frame from the
        # live terminal size so resize is always correct.
        h, w = self.stdscr.getmaxyx()
        header_h, _status_h, _footer_h = self.chrome_heights(h)
        left_b, right_b = self.border_cols(h, w)
        self.content_area_y_offset = header_h
        self.content_area_x_offset = left_b
        self._content_right_x = w - right_b
        self.editor._content_area_y_offset = header_h
        self.editor._content_area_x_offset = left_b
        self.editor._content_right_x = self._content_right_x
        if not hasattr(self.editor, "visible_lines"):
            self.editor.visible_lines = self.content_height(h)

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

        # High pair ids that never collide with the sequential pairs allocated
        # by Ecli.init_colors (syntax + chrome ~1..45). Previously these were
        # 15/16, which silently overwrote the 'builtin' and 'error' syntax pairs.
        max_pairs = curses.COLOR_PAIRS
        pair_norm = max(1, min(250, max_pairs - 2))
        pair_err = max(1, min(251, max_pairs - 1))
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

        # Clip text to the content right-edge (inside the right border).
        _h, window_width = self.stdscr.getmaxyx()
        content_right = getattr(self, "_content_right_x", 0) or window_width

        # The left border is accounted for by the x offset.
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
                content_right,
                text_area_start_x,
            )

    @staticmethod
    def _apply_current_line_variant(token_attr: int, variant_map: dict[int, int]) -> int:
        """Return *token_attr* remapped to its current-line background variant.

        Keeps the foreground colour and text attributes (bold/dim/...), swapping
        only the colour pair to the pre-allocated current-line variant. Returns
        the attribute unchanged when no variant exists for the token's pair.
        """
        variant = variant_map.get(curses.pair_number(token_attr))
        if variant:
            return curses.color_pair(variant) | (token_attr & ~curses.A_COLOR)
        return token_attr

    def _draw_single_line(
        self,
        screen_row: int,
        line_data: tuple[int, list[tuple[str, int]]],
        right_edge: int,
        text_area_start_x: int,
    ) -> None:
        """Draw a single logical line of source text on the given screen row,
        applying horizontal scroll and syntax-highlight attributes.  Wide
        Unicode characters (wcwidth == 2) are never split in half.

        Args:
            screen_row: Absolute Y position in the curses window.
            line_data:  (buffer_index, [(lexeme, attr), ...]).
            right_edge: Exclusive right boundary for content (inside any border).
            text_area_start_x: The screen column where the text area begins.
        """
        _line_index, tokens_for_this_line = line_data
        is_current_line = _line_index == self.editor.cursor_y
        current_line_attr = self.colors.get("ui_current_line", curses.A_NORMAL)
        variant_map = getattr(self.editor, "_current_line_variant", {})

        # Clear the target area first.
        try:
            self.stdscr.move(screen_row, text_area_start_x)
            self.stdscr.clrtoeol()
            if is_current_line:
                # Tint the whole active row (incl. the empty tail) up to the
                # content edge; tokens are repainted over it next.
                tint_w = max(0, right_edge - text_area_start_x)
                if tint_w:
                    self.stdscr.chgat(
                        screen_row, text_area_start_x, tint_w, current_line_attr
                    )
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

            draw_x = max(text_area_start_x, ideal_x)
            avail_screen_w = right_edge - draw_x
            if avail_screen_w <= 0:
                # Nothing further on this line is visible.
                break

            visible_w = max(0, token_disp_width - cells_cut_left)
            visible_w = min(visible_w, avail_screen_w)
            if visible_w <= 0:
                logical_col_abs += token_disp_width
                continue

            text_to_draw = prepare_visible_text_segment(
                token_text,
                cells_cut_left,
                visible_w,
                self.editor.get_char_width,
            )

            # On the active row, swap each token's background to the current-line
            # colour while keeping its foreground and text attributes.
            draw_attr = (
                self._apply_current_line_variant(token_attr, variant_map)
                if is_current_line
                else token_attr
            )

            if text_to_draw:
                try:
                    self.stdscr.addstr(screen_row, draw_x, text_to_draw, draw_attr)
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
                        if cx >= right_edge:
                            break
                        try:
                            self.stdscr.addch(screen_row, cx, ch, draw_attr)
                        except curses.error:
                            break
                        cx += self.editor.get_char_width(ch)

            logical_col_abs += token_disp_width

            # Early exit if we've reached the right edge.
            if draw_x + visible_w >= right_edge:
                break

    def draw(self) -> None:
        """The main screen drawing method."""
        try:
            height, width = self.stdscr.getmaxyx()

            if height < self.MIN_WINDOW_HEIGHT or width < self.MIN_WINDOW_WIDTH:
                self._show_small_window_error(height, width)
                # last_window_size is now correctly set by the handle_resize method
                return

            # Recompute chrome geometry every frame so resize is always correct
            # and the single source of truth stays in sync.
            header_h, status_h, footer_h = self.chrome_heights(height)
            left_b, right_b = self.border_cols(height, width)

            # When a side panel is open the work area splits ~60/40: clip the
            # editor content to the editor region and drop the editor's own right
            # border (the panel's left border is the divider). The global
            # header/status/footer keep their full-width rows untouched.
            editor_right = self._side_panel_editor_width(width, height)
            if editor_right is not None:
                right_b = 0
                content_right = editor_right
            else:
                content_right = width - right_b

            self.content_area_y_offset = header_h
            self.content_area_x_offset = left_b
            self._content_right_x = content_right
            self.editor._content_area_y_offset = header_h
            self.editor._content_area_x_offset = left_b
            self.editor._content_right_x = self._content_right_x
            self.editor.visible_lines = self.content_height(height)

            if self._needs_full_redraw():
                self.stdscr.erase()
                self.editor._force_full_redraw = False
            else:
                self._clear_invalidated_lines()

            if header_h:
                self._draw_header(width)

            self._draw_line_numbers()
            self._draw_text_with_syntax_highlighting()
            self._draw_search_highlights()
            self._draw_selection()
            self.editor.highlight_matching_brackets()
            self._draw_borders(height, width, header_h, self.editor.visible_lines)

            self._draw_status_bar()
            if footer_h:
                self._draw_footer(width)
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
        """Clears the editor content rows that will be redrawn in this frame.

        Chrome rows (header/status/footer) are repainted in full every frame, so
        only the text area is cleared here. Avoids a global clear() to prevent
        flicker.
        """
        offset = self.content_area_y_offset
        text_start = self._text_start_x + self.content_area_x_offset
        for row in range(self.editor.visible_lines):
            try:
                self.stdscr.move(row + offset, text_start)
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
        if not self.editor.show_line_numbers:
            self._text_start_x = 0  # Text starts from the left edge
            return

        _height, width = self.stdscr.getmaxyx()
        max_line_num_digits, line_num_width = self._line_number_width()
        if line_num_width >= width:
            logging.warning(
                f"Window too narrow to draw line numbers ({width} vs {line_num_width})"
            )
            self._text_start_x = 0  # Text starts from 0 column
            return

        self._text_start_x = line_num_width
        offset = self.content_area_y_offset
        gutter_x = self.content_area_x_offset  # leave room for the left border
        line_num_color = self.colors.get("line_number", curses.color_pair(7))
        current_num_color = self.colors.get(
            "ui_current_line_number", line_num_color | curses.A_BOLD
        )
        diagnostic_line = self._active_diagnostic_highlight_line()
        cursor_y = self.editor.cursor_y
        for screen_row in range(self.editor.visible_lines):
            line_idx = self.editor.scroll_top + screen_row
            draw_y = screen_row + offset
            if line_idx < len(self.editor.text):
                self._draw_single_line_number(
                    draw_y,
                    gutter_x,
                    line_idx,
                    max_line_num_digits,
                    self._line_number_color_for(
                        line_idx,
                        cursor_y,
                        diagnostic_line,
                        line_num_color,
                        current_num_color,
                    ),
                )
            else:
                self._draw_empty_line_number(
                    draw_y,
                    gutter_x,
                    line_num_width,
                    line_num_color,
                )

    def _line_number_width(self) -> tuple[int, int]:
        """Return line-number digits and total gutter width."""
        max_line_num = len(self.editor.text)
        max_line_num_digits = len(str(max(1, max_line_num)))
        return max_line_num_digits, max_line_num_digits + 1

    def _line_number_color_for(
        self,
        line_idx: int,
        cursor_y: int,
        diagnostic_line: int | None,
        line_num_color: int,
        current_num_color: int,
    ) -> int:
        """Return the gutter attribute for one visible line."""
        diagnostic_color = self._diagnostic_gutter_style_for_line(
            line_idx,
            diagnostic_line,
            line_num_color,
        )
        if diagnostic_color is not None:
            return diagnostic_color
        if line_idx == cursor_y:
            return current_num_color
        return line_num_color

    def _diagnostic_gutter_style_for_line(
        self,
        line_idx: int,
        diagnostic_line: int | None,
        fallback: int,
    ) -> int | None:
        """Return selected-diagnostic gutter style for a line, if active."""
        if diagnostic_line is None or line_idx != diagnostic_line:
            return None
        return self._diagnostic_line_number_attr(fallback)

    def _draw_single_line_number(
        self,
        draw_y: int,
        gutter_x: int,
        line_idx: int,
        max_line_num_digits: int,
        color: int,
    ) -> None:
        """Draw one populated line-number gutter cell."""
        line_num_str = f"{line_idx + 1:>{max_line_num_digits}} "
        try:
            self.stdscr.addstr(draw_y, gutter_x, line_num_str, color)
        except curses.error as e:
            logging.error(
                f"Curses error drawing line number at ({draw_y}, {gutter_x}): {e}"
            )

    def _draw_empty_line_number(
        self,
        draw_y: int,
        gutter_x: int,
        line_num_width: int,
        line_num_color: int,
    ) -> None:
        """Draw one empty line-number gutter cell."""
        empty_num_str = " " * line_num_width
        try:
            self.stdscr.addstr(draw_y, gutter_x, empty_num_str, line_num_color)
        except curses.error as e:
            logging.error(
                f"Curses error drawing empty line number background at ({draw_y}, {gutter_x}): {e}"
            )

    def _active_diagnostic_highlight_line(self) -> int | None:
        """Return the selected diagnostic line index for the current file."""
        highlight = getattr(self.editor, "diagnostic_line_highlight", None)
        if not isinstance(highlight, dict):
            return None
        highlighted_path = str(highlight.get("file_path") or "")
        if not highlighted_path:
            return None
        current_filename = getattr(self.editor, "filename", None)
        if not current_filename:
            return None
        if os.path.abspath(str(current_filename)) != highlighted_path:
            return None
        try:
            line_number = int(highlight.get("line", 0))
        except (TypeError, ValueError):
            return None
        if line_number < 1:
            return None
        return line_number - 1

    def _diagnostic_line_number_attr(self, fallback: int) -> int:
        """Return the severity-specific gutter attribute for selected diagnostic."""
        highlight = getattr(self.editor, "diagnostic_line_highlight", None)
        severity = ""
        if isinstance(highlight, dict):
            severity = str(highlight.get("severity") or "")
        if severity == "error":
            return self.colors.get("ui_error", fallback | curses.A_BOLD)
        if severity == "warning":
            return self.colors.get("ui_warning", fallback | curses.A_BOLD)
        if severity in {"info", "hint"}:
            return self.colors.get("ui_info", fallback | curses.A_BOLD)
        return fallback | curses.A_BOLD

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

        # Themed, opaque panel: solid surface + title embedded in the border.
        border = self.colors.get("ui_panel_border", curses.A_BOLD)
        fill = self.colors.get("ui_panel", curses.A_NORMAL)
        dim = self.colors.get("ui_panel_dim", curses.A_DIM)
        title = " Diagnostics "
        inner = panel_width - 2
        try:
            for i in range(panel_height):
                if i == 0:
                    label = title[: max(0, inner - 2)]
                    rest = inner - len(label) - 1
                    line = "┌─" + label + "─" * max(0, rest) + "┐"
                elif i == panel_height - 1:
                    line = "└" + "─" * inner + "┘"
                else:
                    line = "│" + " " * inner + "│"
                self.stdscr.addnstr(start_y + i, start_x, line, panel_width, border)
                # Repaint the hollow interior with the solid panel surface.
                if 0 < i < panel_height - 1:
                    self.stdscr.addnstr(
                        start_y + i, start_x + 1, " " * inner, inner, fill
                    )

            # Message split into lines (on the solid surface).
            msg_lines = msg.splitlines()
            for idx, line in enumerate(msg_lines[: panel_height - 3]):
                self.stdscr.addnstr(
                    start_y + idx + 1,
                    start_x + 2,
                    line.strip(),
                    panel_width - 4,
                    fill,
                )
            # Footer
            footer = "Esc: close"
            self.stdscr.addnstr(
                start_y + panel_height - 2,
                start_x + 2,
                footer,
                panel_width - 4,
                dim,
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
        # Text starts after the gutter and the left border; clip to the right edge.
        text_start = line_num_width + self.content_area_x_offset
        content_right = getattr(self, "_content_right_x", 0) or width

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

            screen_y = (
                match_row - self.editor.scroll_top + self.content_area_y_offset
            )  # Screen row for this match
            line = self.editor.text[
                match_row
            ]  # The text of the line containing the match

            # Compute X screen positions (before and after scrolling) for match start and end
            match_screen_start_x_before_scroll = self.editor.get_string_width(
                line[:match_start_idx]
            )
            match_screen_start_x = (
                text_start
                + match_screen_start_x_before_scroll
                - self.editor.scroll_left
            )

            match_screen_end_x_before_scroll = self.editor.get_string_width(
                line[:match_end_idx]
            )
            match_screen_end_x = (
                text_start
                + match_screen_end_x_before_scroll
                - self.editor.scroll_left
            )

            # Clamp drawing area to the visible screen boundaries
            draw_start_x = max(text_start, match_screen_start_x)
            draw_end_x = min(content_right, match_screen_end_x)

            # Calculate the actual width of the highlight to draw
            highlight_width_on_screen = max(0, draw_end_x - draw_start_x)

            # Apply the highlight attribute if there is something to show
            if highlight_width_on_screen > 0:
                try:
                    # Iterate over characters in the line to accurately highlight wide characters
                    current_char_screen_x = (
                        text_start - self.editor.scroll_left
                    )  # Initial X for first char
                    for char_idx, char in enumerate(line):
                        char_width = self.editor.get_char_width(char)
                        char_screen_end_x = current_char_screen_x + char_width

                        # If this character falls within the match range and is visible
                        if (
                            match_start_idx <= char_idx < match_end_idx
                            and current_char_screen_x < content_right
                            and char_screen_end_x > text_start
                        ):
                            draw_char_x = max(text_start, current_char_screen_x)
                            draw_char_width = min(char_width, content_right - draw_char_x)

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
        text_area_start_x = self._text_start_x + self.content_area_x_offset
        content_right = getattr(self, "_content_right_x", 0) or width
        offset = self.content_area_y_offset
        selection_attr = self.colors.get("ui_selection", curses.A_REVERSE)

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
                draw_end_x = min(content_right, x_right)
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
                            screen_y + offset, draw_start_x, highlight_w, selection_attr
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
                draw_end_x = min(content_right, highlight_end_on_screen)
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
                            screen_y + offset, draw_start_x, highlight_w, selection_attr
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

    # --- Professional chrome: header / footer ---------------------------
    def _fill_bar(self, y: int, width: int, attr: int) -> None:
        """Paint a full-width horizontal bar at row *y* without scrolling."""
        if width <= 0:
            return
        try:
            self.stdscr.addstr(y, 0, " " * (width - 1), attr)
            # Fill the final cell with insch so the cursor never wraps/scrolls.
            self.stdscr.insch(y, width - 1, ord(" "), attr)
        except curses.error:
            pass

    def _put(self, y: int, x: int, text: str, attr: int, width: int) -> int:
        """Draw *text* at (y, x), clipped to the window width. Returns next x."""
        if not text or x >= width:
            return x
        max_w = max(0, width - 1 - x)
        clipped = self.truncate_string(text, max_w)
        if not clipped:
            return x
        try:
            self.stdscr.addstr(y, x, clipped, attr)
        except curses.error:
            pass
        return x + self.editor.get_string_width(clipped)

    def _shorten_path(self, path: str, max_width: int) -> str:
        """Shorten *path* to fit *max_width* cells, keeping the basename."""
        if self.editor.get_string_width(path) <= max_width:
            return path
        base = os.path.basename(path)
        if self.editor.get_string_width(base) + 2 >= max_width:
            return "…" + self.truncate_string(base, max(1, max_width - 1))
        head_budget = max_width - self.editor.get_string_width(base) - 2
        head = self.truncate_string(path, max(0, head_budget))
        return f"{head}…/{base}"

    def _draw_header(self, width: int) -> None:
        """Top application header bar: app name, file, modified state, theme."""
        if self.editor.is_lightweight:
            return
        try:
            bar = self.colors.get("ui_header", curses.A_REVERSE)
            accent = self.colors.get("ui_header_accent", bar | curses.A_BOLD)
            dim = self.colors.get("ui_header_dim", bar)

            self._fill_bar(0, width, bar)

            # Right segment: active theme indicator.
            theme = getattr(self.editor, "active_theme", None)
            right = f" theme {theme.theme_id} · {theme.name} " if theme else ""
            right_w = self.editor.get_string_width(right)

            # Left segment: app badge + file name + modified marker.
            x = self._put(0, 0, " ECLI ", accent, width)
            fname = self.editor.filename or "No Name"
            avail = max(8, width - right_w - x - 3)
            shown = self._shorten_path(fname, avail)
            marker = " ●" if self.editor.modified else ""
            x = self._put(0, x, f" {shown}{marker} ", bar, width)

            if right and width - right_w - 1 > x:
                self._put(0, width - right_w - 1, right, dim, width)
        except curses.error:
            pass

    def _draw_footer(self, width: int) -> None:
        """Bottom shortcut/action strip with compact key hints."""
        if self.editor.is_lightweight:
            return
        height, _ = self.stdscr.getmaxyx()
        y = height - 1
        try:
            bar = self.colors.get("ui_footer", curses.A_REVERSE)
            key = self.colors.get("ui_footer_key", bar | curses.A_BOLD)

            self._fill_bar(y, width, bar)

            hints = [
                ("Ctrl+S", "Save"),
                ("Ctrl+O", "Open"),
                ("Ctrl+F", "Find"),
                ("F1", "Help"),
                ("Ctrl+Q", "Quit"),
            ]
            x = 1
            for k, label in hints:
                segment_w = self.editor.get_string_width(f"{k} {label}  ")
                if x + segment_w >= width:
                    break
                x = self._put(y, x, f" {k}", key, width)
                x = self._put(y, x, f" {label} ", bar, width)
        except curses.error:
            pass

    def _side_panel_editor_width(self, width: int, height: int) -> int | None:
        """Editor content width when a non-modal side panel splits the work area.

        Returns ``None`` when no side panel is active (or it is a centered
        modal), so the editor keeps its normal full width.
        """
        pm = getattr(self.editor, "panel_manager", None)
        is_active = getattr(pm, "is_panel_active", None)
        if pm is None or not callable(is_active) or not is_active():
            return None
        panel = getattr(pm, "active_panel", None)
        if panel is None or getattr(panel, "_rendered_as_modal", False):
            return None
        geo = compute_layout(width, height, active_panel=True)
        return geo.editor.width if geo.split else None

    def _draw_borders(
        self, height: int, width: int, content_top: int, content_height: int
    ) -> None:
        """Draw the left/right vertical viewport borders on the content rows.

        The header bar forms the top edge and the status/footer bars the bottom
        edge, so only the verticals are drawn here. Degrades to nothing when
        ``border_cols`` returns zero (small/narrow terminals).
        """
        if self.editor.is_lightweight:
            return
        left_b, right_b = self.border_cols(height, width)
        if self._side_panel_editor_width(width, height) is not None:
            right_b = 0  # the panel's left border is the divider
        if not left_b and not right_b:
            return
        attr = self.colors.get("ui_border", curses.A_DIM)
        glyph = "│"
        for row in range(content_top, content_top + content_height):
            if row >= height:
                break
            if left_b:
                try:
                    self.stdscr.addstr(row, 0, glyph, attr)
                except curses.error:
                    pass
            if right_b and width >= 1:
                try:
                    # insstr never advances the cursor past the last cell.
                    self.stdscr.insstr(row, width - 1, glyph, attr)
                except curses.error:
                    pass

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

            # Status sits just above the footer shortcut strip (or on the last
            # line when chrome is degraded on tiny terminals).
            _header_h, status_h, footer_h = self.chrome_heights(height)
            y = height - footer_h - status_h

            # -- colours (themed status bar) --------------------------
            c_norm = self.colors.get(
                "ui_status", self.colors.get("status", curses.A_REVERSE)
            )
            c_err = self.colors.get(
                "ui_error",
                self.colors.get("status_error", curses.A_REVERSE | curses.A_BOLD),
            )
            c_success = self.colors.get(
                "ui_status_success",
                self.colors.get("ui_success", c_norm | curses.A_BOLD),
            )
            c_git = self.colors.get("ui_success", c_norm)
            c_dirty = self.colors.get("ui_warning", c_norm | curses.A_BOLD)

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
                git_state = getattr(self.editor.git, "repo_state", "unavailable")
                if git_state in {"clean", "dirty"} and branch:
                    dirty = "*" in branch
                    branch = branch.rstrip("*")
                    git_txt = f" Git: {'dirty' if dirty else 'clean'}"
                    git_attr = c_dirty if dirty else c_git
                elif git_state == "loading":
                    git_txt = " Git: loading"
                elif git_state == "not repo":
                    git_txt = " Git: not repo"
                elif git_state == "unavailable":
                    git_txt = " Git: unavailable"
                else:
                    git_txt = " Git: loading"
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
            elif msg.startswith("Diagnostics: PASS"):
                pass_x = left_w + pad_left
                self.stdscr.chgat(y, pass_x, msg_w, c_success)

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

        text_area_start_x = self._text_start_x + self.content_area_x_offset
        content_right = getattr(self, "_content_right_x", 0) or width

        # Explicit calculation of the text area height ---
        # Instead of self.editor.visible_lines, which can be 0 during initialization,
        # we derive it from the live window size and chrome layout.
        text_area_height = self.content_height(height)

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
        text_area_width = max(1, content_right - text_area_start_x)
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
        final_screen_x = max(
            text_area_start_x, min(final_screen_x, content_right - 1)
        )

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
        text_area_height = self.content_height(height)

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
