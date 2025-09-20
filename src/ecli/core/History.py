# ecli/core/History.py
"""History Module for ECLI Editor
===============================
This module provides the `History` class, which manages the undo and redo action history for the ECLI text editor.
It enables robust tracking and reversal of user actions, supporting both simple and compound operations. The class
ensures that all changes to the editor's content, cursor position, selection state, and modification status can be
reliably undone and redone, maintaining consistency and integrity of the editor's state.

Key Features:
-------------
- Tracks a stack of user actions, allowing for multi-level undo and redo functionality.
- Supports compound actions, enabling groups of changes to be undone or redone as a single operation.
- Handles a variety of editor actions, including text insertion, deletion, block indentation, commenting, and selection changes.
- Maintains synchronization between the editor's text buffer, cursor, selection, and modification flags.
- Provides detailed logging and error handling to ensure reliability and facilitate debugging.

Intended Usage:
---------------
This module is intended to be used as an internal component of the ECLI Editor, providing seamless undo/redo
capabilities for end-users. It is designed to be thread-safe and to interact closely with the editor's core state.

Classes:
--------
- History: Manages the undo and redo stacks, and provides methods to add actions, clear history, and perform undo/redo operations.
"""
import logging
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli

## ==================== History Class (Undo/Redo) ====================
class History:
    """Class History
    ===================
    Manages the undo and redo action history for the editor.
    This class tracks user actions performed in the editor, allowing them to be undone and redone.
    It maintains separate stacks for performed actions and undone actions, and supports compound
    actions that group multiple changes into a single undo/redo step.

    Attributes:
        editor (Ecli): The editor instance this history manager is associated with.
        _action_history (list[dict[str, Any]]): Stack of performed actions for undo.
        _undone_actions (list[dict[str, Any]]): Stack of undone actions for redo.
        _is_in_compound_action (bool): Indicates if a compound action is in progress.

    Methods:
        begin_compound_action():
            Starts a sequence of actions that should be undone/redone together.
        end_compound_action():
            Ends a compound action sequence and clears the redo stack.
        add_action(action: dict[str, Any]):
            Adds a new action to the history. Clears the redo stack if not in a compound action.
        clear():
            Clears both the undo and redo stacks.
        undo() -> bool:
            Undoes the last action. Restores the editor's state to before the action.
                bool: True if the editor's state changed as a result of the undo operation, False otherwise.
        redo() -> bool:
            Redoes the last undone action. Restores the editor's state to after the action.
                bool: True if the editor's state changed as a result of the redo operation, False otherwise.
    """
    def __init__(self, editor: "Ecli"):
        """Initializes the History manager for the given editor instance.

            editor (Ecli): The editor instance to associate with this history manager.

        Attributes:
            editor (Ecli): Reference to the associated editor.
            _action_history (list[dict[str, Any]]): List storing the history of performed actions.
            _undone_actions (list[dict[str, Any]]): List storing actions that have been undone and can be redone.
            _is_in_compound_action (bool): Flag indicating if a compound action is currently being recorded.
        """
        self.editor = editor
        self._action_history: list[dict[str, Any]] = []
        self._undone_actions: list[dict[str, Any]] = []
        self._is_in_compound_action = False

    def begin_compound_action(self) -> None:
        """Starts a sequence of actions that should be undone/redone together."""
        self._is_in_compound_action = True
        logging.debug("History: Beginning compound action.")

    def end_compound_action(self) -> None:
        """Ends a sequence of actions."""
        self._is_in_compound_action = False
        # Clear the redo stack only at the end of the entire operation
        self._undone_actions.clear()
        logging.debug("History: Ended compound action, cleared redo stack.")

    def add_action(self, action: dict[str, Any]) -> None:
            """Adds a new action to the history."""
            if not isinstance(action, dict) or "type" not in action:
                logging.warning(f"History: Attempted to add invalid action: {action}")
                return

            self._action_history.append(action)

            # Clear the redo stack only if we are NOT in a compound action
            if not self._is_in_compound_action:
                self._undone_actions.clear()

            logging.debug(f"History: Action '{action['type']}' added. History size: {len(self._action_history)}")

    def clear(self) -> None:
        """Clears both undo and redo stacks."""
        self._action_history.clear()
        self._undone_actions.clear()
        logging.debug("History: Undo/Redo stacks cleared.")

    def undo(self) -> bool:
        """Undoes the last action from the _action_history stack.
        Restores the text, cursor position, selection state, and modified status
        to what it was before the last action was performed.

        Returns:
            bool: True if the editor's state (text, cursor, scroll, selection, modified flag,
                  or status message) changed as a result of the undo operation, False otherwise.
        """
        logging.debug(f"UNDO CALLED. Action history length: {len(self._action_history)}")
        if self._action_history:
            logging.debug(f"Next action to undo: {self._action_history[-1]['type']}")
        with self.editor._state_lock:
            original_status = self.editor.status_message  # For checking if status message changes at the end

            if not self._action_history:
                self.editor._set_status_message("Nothing to undo")
                return self.editor.status_message != original_status  # Redraw if status changed

            # Store current state to compare against after undoing the action
            pre_undo_text_tuple = tuple(self.editor.text)
            pre_undo_cursor_pos = (self.editor.cursor_y, self.editor.cursor_x)
            pre_undo_scroll_pos = (self.editor.scroll_top, self.editor.scroll_left)
            pre_undo_selection_state = (self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end)
            pre_undo_modified_flag = self.editor.modified

            last_action = self._action_history.pop()
            action_type = last_action.get("type")
            # This flag tracks if the core data (text, selection, cursor) was changed by this undo
            content_or_selection_changed_by_this_undo = False

            logging.debug(f"Undo: Attempting to undo action of type '{action_type}' with data: {last_action}")

            try:
                if action_type == "insert":
                    text_that_was_inserted = last_action["text"]
                    row, col = last_action["position"]
                    lines_inserted = text_that_was_inserted.split("\n")
                    num_lines_in_inserted_text = len(lines_inserted)

                    if not (0 <= row < len(self.editor.text)):
                        raise IndexError(
                            f"Undo insert: Start row {row} out of bounds (text len {len(self.editor.text)}). Action: {last_action}")

                    if num_lines_in_inserted_text == 1:
                        len_inserted = len(text_that_was_inserted)
                        # Check if the text to be removed actually matches what's there
                        if not (col <= len(self.editor.text[row]) and self.editor.text[row][
                                                               col:col + len_inserted] == text_that_was_inserted):
                            logging.warning(
                                f"Undo insert: Text mismatch for deletion at [{row},{col}] len {len_inserted}. Expected '{text_that_was_inserted}', found '{self.text[row][col:col + len_inserted]}'.")
                            # Potentially raise error or try to proceed if desired, for now, log and proceed carefully.
                            # This indicates a potential inconsistency in undo stack or text state.
                        self.editor.text[row] = self.editor.text[row][:col] + self.editor.text[row][col + len_inserted:]
                    else:  # Multi-line insert undo
                        end_row_affected_by_original_insert = row + num_lines_in_inserted_text - 1
                        if end_row_affected_by_original_insert >= len(self.editor.text):
                            raise IndexError(
                                f"Undo insert: End row {end_row_affected_by_original_insert} out of bounds (text len {len(self.editor.text)}). Action: {last_action}")

                        # The suffix that was originally on line 'row' and got pushed down
                        # is now at the end of line 'end_row_affected_by_original_insert'
                        # after the last segment of the inserted text.
                        original_suffix_from_line_row = self.editor.text[end_row_affected_by_original_insert][
                                                        len(lines_inserted[-1]):]

                        self.editor.text[row] = self.editor.text[row][:col] + original_suffix_from_line_row
                        # Delete the lines that were created by the multi-line insert
                        del self.editor.text[row + 1: end_row_affected_by_original_insert + 1]

                    self.editor.cursor_y, self.editor.cursor_x = row, col
                    content_or_selection_changed_by_this_undo = True

                elif action_type == "delete_char":
                    y, x = last_action["position"]  # Position where char was deleted, and cursor stayed
                    char_that_was_deleted = last_action["text"]
                    if not (0 <= y < len(self.editor.text) and 0 <= x <= len(self.editor.text[y])):
                        raise IndexError(
                            f"Undo delete_char: Invalid position ({y},{x}) for re-insertion. Action: {last_action}")
                    self.editor.text[y] = self.editor.text[y][:x] + char_that_was_deleted + self.editor.text[y][x:]
                    self.editor.cursor_y, self.editor.cursor_x = y, x  # Cursor stays at the position of the re-inserted char
                    content_or_selection_changed_by_this_undo = True

                elif action_type == "delete_newline":
                    y, x_at_split_point = last_action["position"]  # Cursor pos after original merge
                    content_of_merged_line = last_action["text"]  # This was the line that got appended
                    if not (0 <= y < len(self.editor.text) and 0 <= x_at_split_point <= len(self.editor.text[y])):
                        raise IndexError(
                            f"Undo delete_newline: Invalid position ({y},{x_at_split_point}) for split. Action: {last_action}")

                    line_to_be_split = self.editor.text[y]
                    self.editor.text[y] = line_to_be_split[:x_at_split_point]
                    self.editor.text.insert(y + 1, content_of_merged_line)
                    self.editor.cursor_y, self.editor.cursor_x = y, x_at_split_point  # Cursor to the split point
                    content_or_selection_changed_by_this_undo = True

                elif action_type == "delete_selection":
                    deleted_segments = last_action["text"]  # This is a list[str]
                    start_y, start_x = last_action["start"]  # Coords where deletion started

                    text_to_restore = "\n".join(deleted_segments)
                    if self.editor.insert_text_at_position(text_to_restore, start_y, start_x):  # This returns bool
                        content_or_selection_changed_by_this_undo = True
                    # For undo of delete_selection, cursor should go to the start of the re-inserted text.
                    self.editor.cursor_y, self.editor.cursor_x = start_y, start_x
                    # Restore selection state if it was stored with the action (optional enhancement)
                    # For now, just clear selection after undoing a deletion.
                    self.editor.is_selecting = False
                    self.editor.selection_start = None
                    self.editor.selection_end = None

                elif action_type in ("block_indent", "block_unindent", "comment_block", "uncomment_block"):
                    changes = last_action.get("changes", [])  # List of dicts
                    if not changes:
                        logging.warning(f"Undo ({action_type}): No 'changes' data in action. Action: {last_action}")

                    for change_item in reversed(changes):  # Restore original_text in reverse order of application
                        idx = change_item["line_index"]
                        original_line_text = change_item.get("original_text")
                        if original_line_text is None:
                            logging.warning(f"Undo ({action_type}): Missing 'original_text' for line {idx}. Skipping.")
                            continue
                        if idx < len(self.editor.text):
                            if self.editor.text[idx] != original_line_text:
                                self.editor.text[idx] = original_line_text
                                content_or_selection_changed_by_this_undo = True
                        else:
                            logging.warning(
                                f"Undo ({action_type}): Line index {idx} out of bounds for text len {len(self.editor.text)}. Skipping.")

                    # Restore selection and cursor state as it was *before* the original operation
                    selection_state_before_op = last_action.get("selection_before")
                    cursor_state_no_sel_before_op = last_action.get("cursor_before_no_selection")

                    # Store current selection/cursor to compare *after* attempting to restore
                    current_sel_is, current_sel_start, current_sel_end = self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end
                    current_curs_y, current_curs_x = self.editor.cursor_y, self.editor.cursor_x

                    if selection_state_before_op and isinstance(selection_state_before_op, tuple) and len(
                            selection_state_before_op) == 2:
                        # Assumes selection_before is (sel_start_coords, sel_end_coords)
                        # The full state was (is_selecting, sel_start_coords, sel_end_coords)
                        # Let's assume "selection_before" from actions like block_indent stores the tuple (start_coords, end_coords)
                        # and implies is_selecting = True.
                        # If it stores (is_selecting, start_coords, end_coords), then adjust accordingly.
                        # Based on block_indent, it stores (start_coords, end_coords).
                        self.editor.is_selecting = True
                        self.editor.selection_start, self.editor.selection_end = selection_state_before_op[0], \
                        selection_state_before_op[1]
                        if self.editor.is_selecting and self.editor.selection_end:  # Position cursor at end of restored selection
                            self.editor.cursor_y, self.editor.cursor_x = self.editor.selection_end
                    elif cursor_state_no_sel_before_op and isinstance(cursor_state_no_sel_before_op, tuple):
                        self.editor.is_selecting = False
                        self.editor.selection_start, self.editor.selection_end = None, None
                        self.editor.cursor_y, self.editor.cursor_x = cursor_state_no_sel_before_op
                    else:  # Fallback if no specific state stored, clear selection
                        self.editor.is_selecting = False
                        self.editor.selection_start, self.editor.selection_end = None, None
                        # Cursor might have been affected by text changes if any.

                    # Check if selection or cursor state actually changed due to restoration
                    if (self.editor.is_selecting != current_sel_is or
                            self.editor.selection_start != current_sel_start or
                            self.editor.selection_end != current_sel_end or
                            (self.editor.cursor_y, self.editor.cursor_x) != (current_curs_y, current_curs_x)):
                        content_or_selection_changed_by_this_undo = True

                else:
                    logging.warning(f"Undo: Unknown action type '{action_type}'. Cannot undo. Action: {last_action}")
                    self._action_history.append(last_action)  # Put it back on history if not handled
                    self.editor._set_status_message(f"Undo failed: Unknown action type '{action_type}'")
                    return True  # Status changed

            except IndexError as e_idx:  # Catch errors from list/string indexing during undo logic
                logging.error(f"Undo: IndexError during undo of '{action_type}': {e_idx}", exc_info=True)
                self.editor._set_status_message(f"Undo error for '{action_type}': Index out of bounds.")
                self._action_history.append(last_action)  # Attempt to put action back
                return True  # Status changed, state might be inconsistent
            except Exception as e_undo_general:  # Catch any other unexpected errors
                logging.exception(f"Undo: Unexpected error during undo of '{action_type}': {e_undo_general}")
                self.editor._set_status_message(f"Undo error for '{action_type}': {str(e_undo_general)[:60]}...")
                self._action_history.append(last_action)  # Attempt to put action back
                return True  # Status changed

            # If undo logic completed (even if it raised an error that was caught and handled above by returning True)
            self._undone_actions.append(last_action)  # Move the undone action to the redo stack

            # Determine `self.editor.modified` state after undo
            if not self._action_history:  # If history is now empty
                self.editor.modified = False  # All changes undone, back to last saved or new state
                logging.debug("Undo: Action history empty, file considered not modified.")
            else:
                # Check if the current text matches the state of the last item in history
                # This is complex. A simpler heuristic: if there's history, it's modified.
                # A more robust system would store a "saved_checkpoint" in history.
                self.editor.modified = True
                logging.debug(
                    f"Undo: Action history not empty ({len(self._action_history)} items), file considered modified.")

            # Ensure cursor and scroll are valid after any operation
            self.editor._ensure_cursor_in_bounds()
            scroll_changed_by_clamp = self.editor._clamp_scroll_and_check_change(pre_undo_scroll_pos)

            # Determine if a redraw is needed based on actual state changes
            final_redraw_needed = False
            if (content_or_selection_changed_by_this_undo or
                    tuple(self.editor.text) != pre_undo_text_tuple or
                    (self.editor.cursor_y, self.editor.cursor_x) != pre_undo_cursor_pos or
                    scroll_changed_by_clamp or
                    (self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end) != pre_undo_selection_state or
                    self.editor.modified != pre_undo_modified_flag):
                final_redraw_needed = True

            if final_redraw_needed:
                self.editor._set_status_message("Action undone")
                logging.debug(f"Undo successful, state changed for action type '{action_type}'. Redraw needed.")
            else:
                # This implies the undo operation resulted in the exact same state as before it ran
                if self.editor.status_message == original_status:
                    self.editor._set_status_message("Undo: No effective change from current state")
                logging.debug(
                    f"Undo for action type '{action_type}' resulted in no effective change from current state.")

            # Return True if a redraw is needed due to state changes OR if status message changed
            return final_redraw_needed or (self.editor.status_message != original_status)

    def redo(self) -> bool:
        """Redoes the last undone action from the undo stack, restoring the editor's state to what it was after the original action was performed.

        This method handles various action types such as insertions, deletions, block indentations, and commenting actions. It restores the text, cursor position, selection state, and modified status as appropriate for each action. If there are no actions to redo, it updates the status message accordingly.

            bool: True if the editor's state (text, cursor, scroll, selection, modified flag, or status message) changed as a result of the redo operation, False otherwise.

        Raises:
            IndexError: If the redo operation encounters an invalid position or text mismatch.
            Exception: For any unexpected errors during the redo process.
        """
        logging.debug(f"REDO CALLED. Undone actions length: {len(self._undone_actions)}")
        if self._undone_actions:
            logging.debug(f"Next action to redo: {self._undone_actions[-1]['type']}")
        # Use the editor's state lock to ensure thread safety during the redo operation
        with self.editor._state_lock:
            original_status = self.editor.status_message  # For checking if status message changes at the end

            if not self._undone_actions:
                self.editor._set_status_message("Nothing to redo")
                return self.editor.status_message != original_status  # Redraw if status message changed

            # Store current state to compare against after redoing the action
            pre_redo_text_tuple = tuple(self.editor.text)
            pre_redo_cursor_pos = (self.editor.cursor_y, self.editor.cursor_x)
            pre_redo_scroll_pos = (self.editor.scroll_top, self.editor.scroll_left)
            pre_redo_selection_state = (self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end)
            pre_redo_modified_flag = self.editor.modified

            action_to_redo = self._undone_actions.pop()
            action_type = action_to_redo.get("type")
            # This flag tracks if the core data (text, selection, cursor) was changed by this redo
            content_or_selection_changed_by_this_redo = False

            logging.debug(f"Redo: Attempting to redo action of type '{action_type}' with data: {action_to_redo}")

            try:
                if action_type == "insert":
                    # To redo an insert, we re-insert the text.
                    # 'text' is the text that was originally inserted.
                    # 'position' is (row, col) where insertion originally started.
                    text_to_re_insert = action_to_redo["text"]
                    row, col = action_to_redo["position"]
                    # insert_text_at_position updates cursor and self.editor.modified
                    if self.editor.insert_text_at_position(text_to_re_insert, row, col):
                        content_or_selection_changed_by_this_redo = True
                    # Cursor is set by insert_text_at_position to be after the inserted text.

                elif action_type == "delete_char":
                    # To redo a delete_char, we re-delete the character.
                    # 'text' is the character that was originally deleted.
                    # 'position' is (y,x) where the character was (and where cursor stayed).
                    y, x = action_to_redo["position"]
                    # Ensure the character that was re-inserted by 'undo' is still there to be 're-deleted'.
                    # This also implies the line length and content should match expectations.
                    char_that_was_reinserted_by_undo = action_to_redo["text"]
                    if not (0 <= y < len(self.editor.text) and
                            0 <= x < len(self.editor.text[y]) and
                            self.editor.text[y][x] == char_that_was_reinserted_by_undo):
                        raise IndexError(
                            f"Redo delete_char: Text mismatch or invalid position ({y},{x}) for re-deletion. "
                            f"Expected '{char_that_was_reinserted_by_undo}' at position. Action: {action_to_redo}"
                        )
                    self.editor.text[y] = self.editor.text[y][:x] + self.editor.text[y][x + 1:]
                    self.editor.cursor_y, self.editor.cursor_x = y, x  # Cursor stays at the position of deletion
                    content_or_selection_changed_by_this_redo = True

                elif action_type == "delete_newline":
                    # To redo a delete_newline (merge), we re-merge the lines.
                    # 'text' is the content of the line that was merged up.
                    # 'position' is (y,x) where cursor ended after original merge.
                    y_target_line, x_cursor_after_merge = action_to_redo["position"]
                    # To redo, we expect line y_target_line to exist, and line y_target_line + 1
                    # (which was re-created by undo) to also exist and match 'text'.
                    if not (0 <= y_target_line < len(self.editor.text) - 1 and
                            self.editor.text[y_target_line + 1] == action_to_redo["text"]):
                        raise IndexError(
                            f"Redo delete_newline: State mismatch for re-merging at line {y_target_line}. Action: {action_to_redo}")

                    self.editor.text[y_target_line] += self.editor.text.pop(y_target_line + 1)
                    self.editor.cursor_y, self.editor.cursor_x = y_target_line, x_cursor_after_merge
                    content_or_selection_changed_by_this_redo = True

                elif action_type == "delete_selection":
                    # To redo a delete_selection, we re-delete the selection.
                    # 'start' and 'end' are the normalized coordinates of the original selection.
                    start_y, start_x = action_to_redo["start"]
                    end_y, end_x = action_to_redo["end"]
                    # delete_selected_text_internal updates cursor and self.editor.modified
                    # It expects normalized coordinates.
                    deleted_segments_again = self.editor.delete_selected_text_internal(start_y, start_x, end_y, end_x)
                    # Check if something was actually deleted this time.
                    if deleted_segments_again or (start_y, start_x) != (end_y, end_x):
                        content_or_selection_changed_by_this_redo = True
                    # Cursor is set by delete_selected_text_internal to (start_y, start_x)

                elif action_type in ("block_indent", "block_unindent", "comment_block", "uncomment_block"):
                    # These actions store 'changes': list of {"line_index", "original_text", "new_text"}
                    # and 'selection_after', 'cursor_after_no_selection' which represent the state
                    # *after* the original operation was performed.
                    # To redo, we re-apply the "new_text" for each change and restore "after" states.
                    changes = action_to_redo.get("changes", [])
                    if not changes:
                        logging.warning(f"Redo ({action_type}): No 'changes' data in action. Action: {action_to_redo}")

                    for change_item in changes:  # Apply in the original order
                        idx = change_item["line_index"]
                        new_line_text = change_item.get("new_text")
                        if new_line_text is None:
                            logging.warning(f"Redo ({action_type}): Missing 'new_text' for line {idx}. Skipping.")
                            continue
                        if idx < len(self.editor.text):
                            if self.editor.text[idx] != new_line_text:
                                self.editor.text[idx] = new_line_text
                                content_or_selection_changed_by_this_redo = True
                        else:
                            logging.warning(f"Redo ({action_type}): Line index {idx} out of bounds. Skipping.")

                    selection_state_after_op = action_to_redo.get("selection_after")
                    cursor_state_no_sel_after_op = action_to_redo.get("cursor_after_no_selection")

                    current_sel_is, current_sel_start = self.editor.is_selecting, self.editor.selection_start
                    current_sel_end = self.editor.selection_end
                    current_curs_y, current_curs_x = self.editor.cursor_y, self.editor.cursor_x

                    if selection_state_after_op and isinstance(selection_state_after_op, tuple) and len(
                            selection_state_after_op) == 3:
                        self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end = selection_state_after_op
                        if self.is_selecting and self.selection_end:
                            self.editor.cursor_y, self.editor.cursor_x = self.editor.selection_end
                    elif cursor_state_no_sel_after_op and isinstance(cursor_state_no_sel_after_op, tuple):
                        self.editor.is_selecting = False
                        self.editor.selection_start, self.editor.selection_end = None, None
                        self.editor.cursor_y, self.editor.cursor_x = cursor_state_no_sel_after_op
                    else:  # Fallback
                        self.editor.is_selecting = False
                        self.editor.selection_start, self.editor.selection_end = None, None

                    if (self.editor.is_selecting != current_sel_is or
                            self.editor.selection_start != current_sel_start or
                            self.editor.selection_end != current_sel_end or
                            (self.editor.cursor_y, self.editor.cursor_x) != (current_curs_y, current_curs_x)):
                        content_or_selection_changed_by_this_redo = True

                    if not changes and not content_or_selection_changed_by_this_redo:
                        pass  # No change by this redo
                    elif not content_or_selection_changed_by_this_redo and changes:  # Text didn't change but selection/cursor might have
                        content_or_selection_changed_by_this_redo = True

                else:
                    logging.warning(f"Redo: Unknown action type '{action_type}'. Cannot redo. Action: {action_to_redo}")
                    self._undone_actions.append(action_to_redo)  # Put it back on undone stack
                    self.editor._set_status_message(f"Redo failed: Unknown action type '{action_type}'")
                    return True  # Status changed

            except IndexError as e_idx:
                logging.error(f"Redo: IndexError during redo of '{action_type}': {e_idx}", exc_info=True)
                self.editor._set_status_message(f"Redo error for '{action_type}': Index out of bounds or text mismatch.")
                self._undone_actions.append(action_to_redo)
                return True
            except Exception as e_redo_general:
                logging.exception(f"Redo: Unexpected error during redo of '{action_type}': {e_redo_general}")
                self.editor._set_status_message(f"Redo error for '{action_type}': {str(e_redo_general)[:60]}...")
                self._undone_actions.append(action_to_redo)
                return True

                # If redo logic completed for a known action type
            self._action_history.append(action_to_redo)  # Move action back to main history

            # A redo operation always implies the document is modified from its last saved state,
            # because it's re-applying a change that was previously undone.
            if content_or_selection_changed_by_this_redo:  # If redo actually did something
                self.editor.modified = True

            self.editor._ensure_cursor_in_bounds()
            scroll_changed_by_clamp = self.editor._clamp_scroll_and_check_change(pre_redo_scroll_pos)

            final_redraw_needed = False
            if (content_or_selection_changed_by_this_redo or
                    tuple(self.editor.text) != pre_redo_text_tuple or
                    (self.editor.cursor_y, self.editor.cursor_x) != pre_redo_cursor_pos or
                    scroll_changed_by_clamp or
                    (self.editor.is_selecting, self.editor.selection_start, self.editor.selection_end) != pre_redo_selection_state or
                    self.editor.modified != pre_redo_modified_flag):
                final_redraw_needed = True

            if final_redraw_needed:
                self.editor._set_status_message("Action redone")
                logging.debug(f"Redo successful and state changed for action type '{action_type}'. Redraw needed.")
            else:
                if self.editor.status_message == original_status:
                    self.editor._set_status_message("Redo: No effective change from current state")
                logging.debug(
                    f"Redo for action type '{action_type}' resulted in no effective change from current state.")

            return final_redraw_needed or (self.editor.status_message != original_status)

