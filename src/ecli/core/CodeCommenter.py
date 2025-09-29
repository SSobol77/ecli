# ecli/core/CodeCommenter.py
"""CodeCommenter Module
====================
This module defines the `CodeCommenter` class, which provides comprehensive logic for toggling comments in source code across multiple programming languages. It is designed as a helper component for the main `Ecli` class, enabling advanced comment manipulation features such as adding, removing, and toggling single-line comments, block comments, and language-specific docstrings.
Key Features:
-------------
- Language-Aware Commenting: Automatically detects the active programming language and applies the appropriate comment syntax, including support for line comments, block comments, and docstrings.
- Context-Sensitive Docstrings: Intelligently determines whether a selected code region is suitable for a module, class, or function docstring, adhering to PEP 257 and PEP 8 conventions for Python.
- Robust Comment Toggling: Provides seamless toggling between commented and uncommented states for both line and block comments, ensuring code readability and consistency.
- Editor Integration: Operates directly on the editor's text buffer, maintaining cursor position, selection state, and undo history for a smooth user experience.
- Extensible Configuration: Retrieves comment syntax definitions from the editor's configuration, supporting custom languages and comment styles.
Intended Usage:
---------------
The `CodeCommenter` class is intended to be instantiated and managed by the main `Ecli` class. All comment-related actions, such as toggling comments or inserting docstrings, are delegated to this component to ensure consistent and language-appropriate behavior.
Classes:
--------
- `CodeCommenter`: Encapsulates all logic for analyzing code context and performing comment toggling operations.
Dependencies:
-------------
- `logging`
- `re`
- `typing`
This module is a core part of the ECLI Editor's commenting subsystem and is designed for extensibility and maintainability in multi-language code editing environments.
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Optional


# This block allows using Ecli for type annotations,
# avoiding circular dependency at runtime.
if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


## ================= CodeCommenter Class ====================
class CodeCommenter:
    """Manages all logic for toggling comments in various programming languages.
    This class encapsulates the functionality for adding and removing
    comments from the text buffer. It is designed as a helper component for the
    main `Ecli` class, which delegates all comment-related actions to an
    instance of this class.
    It intelligently handles single-line comments, block comments, and
    language-specific docstrings by analyzing the code's context and the
    active language's syntax.

    Attributes:
        editor: A reference to the main `Ecli` instance, providing
            access to the text buffer, cursor state, and configuration.
        DEFINITION_PATTERNS: Class attribute containing regex patterns for detecting
            function and class definitions.

    Methods:
        perform_toggle: The main public entry point. It analyzes the context
            and dispatches to the appropriate toggling helper method.
        _get_language_comment_info: Retrieves comment syntax (line, block,
            docstring) for the current language from an internal map.
        _analyze_comment_context: Determines if a given location is suitable
            for a docstring (e.g., after a function definition).
        _find_preceding_definition: A helper that searches upwards for the
            nearest `def` or `class` statement to establish context.
        _is_valid_docstring_position: A helper that validates if the space
            between a definition and a comment contains no executable code.
        _toggle_docstring_pep8: The dispatcher for adding or removing
            PEP 8-compliant docstrings.
        _check_existing_docstring_pep8: Checks if a block of text is
            already a well-formed single-line or multi-line docstring.
        _add_docstring_pep8: Wraps a block of text with docstring delimiters.
        _remove_docstring_pep8: Unwraps a block of text by removing its
            docstring delimiters.
        _toggle_line_comments: The dispatcher for adding or removing
            line-by-line comments.
        _add_line_comments: Prepends a comment prefix to each line in a range.
        _remove_line_comments: Strips a comment prefix from each line in a range.
        _toggle_block_comment: Wraps or unwraps a range of lines with
            block comment delimiters (e.g., `/* ... */`).
    """

    # Class attribute for storing definition patterns.
    # This makes them reusable and keeps the method logic cleaner.
    DEFINITION_PATTERNS: list[tuple[str, str]] = [
        (r"def\s+\w+.*?:\s*$", "function"),
        (r"class\s+\w+.*?:\s*$", "class"),
        (r"async\s+def\s+\w+.*?:\s*$", "async_function"),
    ]
    # A list of tuples containing regular expression patterns and their corresponding
    # definition types. These are used to identify function, class, and async
    # function definitions in the text buffer. Note that the patterns do not
    # include `^` or `\s*` at the beginning, as they are matched against
    # stripped lines.

    def __init__(self, editor: "Ecli") -> None:
        """Initializes the CodeCommenter.
        This constructor stores a reference to the main editor instance, allowing
        this component to access and modify the editor's state, such as the
        text buffer, cursor position, and configuration settings.

        Args:
            editor: An instance of the main `Ecli` class.
        """
        self.editor = editor

    def perform_toggle(self, start_y: int, end_y: int) -> None:
        """Dispatches the appropriate comment-toggling action for a line range.
        This method acts as the main entry point for all comment operations. It
        analyzes the language and context of the specified line range and then
        delegates the task to the most suitable helper method. The order of
        priority is:
        1. Docstrings (if the context is appropriate for one).
        2. Line-by-line comments.
        3. Block comments.
        If the language is not supported or no suitable commenting method is
        found, it updates the editor's status bar with an appropriate message.

        Args:
            start_y: The 0-based starting line index of the range to toggle.
            end_y: The 0-based ending line index (inclusive) of the range.

        Example:
            If a user toggles comments on a line following a Python function
            definition, this method will detect the docstring context and call
            `_toggle_docstring_pep8`.
            If the user toggles comments on a standard block of C code, this
            method will likely call `_toggle_line_comments`.
        """
        # First, retrieve the comment syntax for the current language.
        language_info = self._get_language_comment_info()
        if not language_info:
            self.editor._set_status_message("Comments not supported for this language.")
            return

        # Analyze the code context to check if this is a docstring location.
        comment_context = self._analyze_comment_context(start_y, end_y)

        # Dispatch to the appropriate handler based on priority
        # Prioritize docstrings if the context is valid and the language supports it.
        if comment_context["is_docstring_context"] and language_info.get(
            "docstring_delim"
        ):
            self._toggle_docstring_pep8(
                start_y, end_y, language_info["docstring_delim"], comment_context
            )
        # Fall back to line-by-line comments if available.
        elif language_info.get("line_prefix"):
            self._toggle_line_comments(start_y, end_y, language_info["line_prefix"])
        # As a last resort, use block comments if the language supports them.
        elif language_info.get("block_delims"):
            self._toggle_block_comment(start_y, end_y, language_info["block_delims"])
        # If no commenting method is available for the language.
        else:
            self.editor._set_status_message("No suitable comment method available.")

    def _get_language_comment_info(self) -> Optional[dict[str, Any]]:
        """Retrieves comment syntax metadata for the editor's current language from the configuration.
        This method consults the [comments] section of the application's configuration
        to find comment syntax for the language currently active in the editor.
        It uses the primary name and aliases of the active Pygments lexer for the lookup.
        If the language is not yet detected, it will first trigger detection.

        Returns:
            A dictionary containing comment syntax information, or None if the
            language is not supported or defined in the configuration. The dictionary
            may contain the following keys:
            - 'line_prefix' (Optional[str]): The prefix for single-line comments.
            - 'block_delims' (Optional[List[str]]): Delimiters for block comments.
            - 'docstring_delim' (Optional[str]): The delimiter for docstrings.
        """
        # Ensure the language is detected.
        if not self.editor.current_language:
            self.editor.detect_language()
        if not self.editor.current_language or not self.editor._lexer:
            logging.warning("_get_language_comment_info: Language not detected.")
            return None

        # Get the comment configuration section.
        comments_config = self.editor.config.get("comments", {})
        if not comments_config:
            logging.warning("No [comments] section found in the configuration.")
            return None

        # Create a list of names to check, starting with the primary name.
        # Pygments lexer names are typically lowercase.
        lang_keys_to_check = [self.editor.current_language.lower()]
        lang_keys_to_check.extend(
            [alias.lower() for alias in self.editor._lexer.aliases]
        )

        # 4. Search for a matching configuration using the language name and its aliases.
        for lang_key in lang_keys_to_check:
            if lang_key in comments_config:
                logging.debug(f"Found comment syntax for language '{lang_key}'.")
                # Return the configuration for the found language.
                # The unpacking in _toggle_block_comment handles a list fine.
                return comments_config[lang_key]

        # 5. If no match was found after checking all aliases.
        logging.warning(
            f"No comment syntax configuration found for language '{self.editor.current_language}' or its aliases."
        )
        return None

    def _analyze_comment_context(self, start_y: int, end_y: int) -> dict[str, Any]:
        """Analyzes the context around a line range to see if it's a docstring location.
        This method inspects the source code to determine if the given line range
        (`start_y` to `end_y`) qualifies as a docstring for a module, class, or
        function. It applies two main heuristics in order:
        1.  Checks if the location is at the top of the file, suitable for a
            module docstring.
        2.  Checks if the location immediately follows a `def` or `class`
            statement, making it a function or class docstring.

        Args:
            start_y: The 0-based starting line index of the block to analyze.
            end_y: The 0-based ending line index of the block. Currently unused
                but reserved for future, more complex context checks.

        Returns:
            A dictionary summarizing the context analysis. It contains:
            - 'is_docstring_context' (bool): True if the location is suitable.
            - 'definition_line' (Optional[int]): The line of the parent
            definition, or None for module docstrings.
            - 'definition_type' (Optional[str]): The type of context, e.g.,
            'module', 'function', 'class'.
            - 'indentation' (int): The required indentation in spaces for the
            docstring to conform to PEP 257.

        Example:
            If `start_y` is 0 in a new file, the method returns:
            `{'is_docstring_context': True, 'definition_type': 'module', ...}`
            If `start_y` points to a line immediately after `def my_func():`,
            the method returns:
            `{'is_docstring_context': True, 'definition_type': 'function', ...}`
        """
        # Initialize the default context, assuming it's not a docstring location.
        context = {
            "is_docstring_context": False,
            "definition_line": None,
            "definition_type": None,
            "indentation": 0,
        }

        # 1 Check for a module-level docstring at the top of the file
        # A module docstring must be the first statement in the file.
        if start_y <= 1:  # Check the first or second line (0-indexed).
            significant_code_before = False
            # Scan all lines *before* the potential docstring start.
            for y in range(start_y):
                if y >= len(self.editor.text):
                    continue
                line = self.editor.text[y].strip()
                # Ignore shebangs, encoding declarations, modelines, and comments.
                # Any other non-blank line is considered significant code.
                if (
                    line
                    and not line.startswith("#")
                    and not line.startswith("#!/")
                    and "coding:" not in line
                    and "encoding:" not in line
                    and "vim:" not in line
                    and "emacs:" not in line
                ):
                    significant_code_before = True
                    break

            if not significant_code_before:
                context.update(
                    {
                        "is_docstring_context": True,
                        "definition_type": "module",
                        "indentation": 0,  # Module docstrings are not indented.
                    }
                )
                return context

        # 2 Check for a docstring immediately following a definition statement.
        definition_info = self._find_preceding_definition(start_y)
        if definition_info:
            context.update(
                {
                    "is_docstring_context": True,
                    "definition_line": definition_info["line"],
                    "definition_type": definition_info["type"],
                    # Per PEP 257, the docstring should be indented one level
                    # deeper than the definition line.
                    "indentation": definition_info["indentation"] + 4,
                }
            )
            return context

        # If neither heuristic matched, return the default context.
        return context

    def _find_preceding_definition(self, start_y: int) -> Optional[dict[str, Any]]:
        """Finds the nearest preceding `def` or `class` statement.
        This method searches upwards from the line above `start_y` to find the
        closest function, class, or async function definition. The search is
        limited to a 20-line window for performance. For a definition to be
        considered a valid context for a docstring, the space between it and
        `start_y` must not contain any executable code, as verified by
        `_is_valid_docstring_position`.

        Args:
            start_y: The 0-based line index from which to start searching upwards.

        Returns:
            A dictionary containing information about the found definition, or
            None if no suitable definition is found within the search window.
            The dictionary has the following keys:
                'line' (int): The line number of the definition.
                'type' (str): The type of definition ('function', 'class', etc.).
                'indentation' (int): The indentation level of the definition line.

        Example:
            If the text buffer contains:
            '''
            class MyClass:
                def my_method(self):
                    # This is the line where start_y is (e.g., index 3)
            '''
            Calling `_find_preceding_definition(3)` would return:
            `{'line': 2, 'type': 'function', 'indentation': 4}`
        """
        # Search upward from the line just before start_y, for a max of 20 lines.
        for y in range(start_y - 1, max(-1, start_y - 20), -1):
            if y >= len(self.editor.text):
                continue
            full_line_text = self.editor.text[y]
            stripped_line = full_line_text.strip()

            # Skip blank lines and standard comments immediately.
            if not stripped_line or stripped_line.startswith("#"):
                continue

            # Check if the stripped line matches any definition pattern.
            for pattern, def_type in self.DEFINITION_PATTERNS:
                # We match against the stripped line, so patterns don't need `^\s*`.
                if re.match(pattern, stripped_line):
                    # Found a definition. Now, verify if it's a valid context
                    # for a docstring at the `start_y` position.
                    if self._is_valid_docstring_position(y, start_y):
                        return {
                            "line": y,
                            "type": def_type,
                            "indentation": len(full_line_text) - len(stripped_line),
                        }
                    # If it's not a valid position, it might be a definition, but
                    # we can't use it for this docstring. Continue searching upwards.
                    break  # Move to the next line up

            # If we encounter any other significant code, stop the search,
            # as it breaks the immediate link to a preceding definition.
            if stripped_line:
                # We found a line with code that wasn't a definition or comment.
                # This means any definition above it is not "immediately" preceding.
                break
        return None

    def _is_valid_docstring_position(self, def_line: int, comment_start: int) -> bool:
        """Validates if a docstring can be legally placed at a given line.
        In Python, a docstring must be the first statement following a `def`
        or `class` line. This function checks the lines between the definition
        and the potential docstring to ensure no other code exists, which would
        violate PEP 257. Blank lines and standard '#' comments are permitted.

        Args:
            def_line: The 0-based index of the line containing the definition.
            comment_start: The 0-based line index where the docstring would start.

        Returns:
            True if the position is a valid location for a docstring, False otherwise.
        """
        # Iterate through the lines between the definition and the comment's start.
        for y in range(def_line + 1, comment_start):
            # Defensively guard against out-of-range indices.
            if y >= len(self.editor.text):
                continue

            # Get the line and strip leading/trailing whitespace.
            line = self.editor.text[y].strip()

            # If a line is not empty and is not a standard comment, it's executable
            # code, which invalidates the docstring position. We make an exception
            # for lines that are themselves existing docstring delimiters,
            # as they do not count as executable code in this context.
            if line and not line.startswith("#"):
                if not (line.startswith('"""') or line.startswith("'''")):
                    return False

        # If the loop completes, no invalidating code was found.
        return True

    def _toggle_docstring_pep8(
        self, start_y: int, end_y: int, delim: str, context: dict[str, Any]
    ) -> None:
        """Toggles a PEP 8-style docstring on or off for the given line range.
        This method acts as a dispatcher. It first checks if the selected block
        is already a valid docstring. If it is, it calls the removal method.
        Otherwise, it calls the addition method.

        Args:
            start_y: The 0-based starting line index.
            end_y: The 0-based ending line index (inclusive).
            delim: The docstring delimiter.
            context: The context dictionary from _analyze_comment_context,
                    containing indentation information.
        """
        indent_str = " " * context.get("indentation", 0)
        is_existing_doc, is_single_line = self._check_existing_docstring_pep8(
            start_y, end_y, delim, indent_str
        )

        if is_existing_doc:
            # If it's already a docstring, remove it.
            self._remove_docstring_pep8(
                start_y, end_y, delim, indent_str, is_single_line
            )
        else:
            # Otherwise, add a new docstring.
            self._add_docstring_pep8(start_y, end_y, delim, indent_str)

    def _check_existing_docstring_pep8(
        self, start_y: int, end_y: int, delim: str, indent_str: str
    ) -> tuple[bool, bool]:
        """Checks if a line range already forms a well-formed PEP 8 docstring.
        This method inspects the text buffer between `start_y` and `end_y`
        (inclusive) to determine if it is wrapped in docstring delimiters. It
        classifies the block based on two criteria: whether it is a docstring
        and whether it is single-line or multi-line.

        Args:
            start_y: The 0-based index of the first line in the block to check.
            end_y: The 0-based index of the last line in the block.
            delim: The delimiter string to check for.
            indent_str: The expected indentation of the docstring. This argument
                is currently unused but is kept for API consistency with
                related methods.

        Returns:
            A tuple of two booleans (is_docstring, is_single_line)
            - is_docstring - True if the block is a valid docstring, False otherwise.
            - is_single_line - True if the docstring is on a single line. This is
            always False if is_docstring is False.
        """
        # An out-of-bounds selection cannot be a docstring.
        if start_y >= len(self.editor.text):
            return False, False

        first_line_stripped = self.editor.text[start_y].strip()

        # Check for a single-line docstring
        # e.g., """content""" on one line.
        if (
            start_y == end_y
            and first_line_stripped.startswith(delim)
            and first_line_stripped.endswith(delim)
        ):
            return True, True

        # Check for a multi-line docstring
        # This requires the first line to be just the opening delimiter
        # and the last line to be just the closing delimiter.
        if (
            end_y < len(self.editor.text)
            and self.editor.text[start_y].strip() == delim
            and self.editor.text[end_y].strip() == delim
        ):
            return True, False

        # If neither of the above conditions are met, it's not a recognized docstring format.
        return False, False

    def _add_docstring_pep8(
        self, start_y: int, end_y: int, delim: str, indent_str: str
    ) -> None:
        """Inserts PEP 8-compliant docstring delimiters around the selected block.
        This method wraps a range of lines with docstring delimiters, handling
        both single-line and multi-line selections. After the operation, any
        active selection is cleared, and the cursor is repositioned to the
        beginning of the line where it was before the operation started.

        Args:
            start_y: The 0-based starting line index of the range to wrap.
            end_y: The 0-based ending line index (inclusive) of the range.
            delim: The delimiter string to use.
            indent_str: The indentation string to prepend to the delimiters.
        """
        # Remember the original cursor line to restore its position later.
        original_cursor_y = self.editor.cursor_y
        final_cursor_y = original_cursor_y

        if start_y == end_y:
            # Handle single-line docstring creation
            line_content = self.editor.text[start_y].strip()

            # Prevent creating invalid syntax like """ ""-text-"" """
            if delim in line_content:
                self.editor._set_status_message(
                    f"Error: Text contains docstring delimiter '{delim}'."
                )
                return

            self.editor.text[start_y] = f"{indent_str}{delim}{line_content}{delim}"
            # The cursor Y position doesn't change in this case.
            # The X position will be set to 0 later.
        else:
            # Handle multi-line docstring creation
            # Insert the closing delimiter first to avoid shifting start_y.
            self.editor.text.insert(end_y + 1, f"{indent_str}{delim}")
            # Insert the opening delimiter. This will shift all subsequent lines down.
            self.editor.text.insert(start_y, f"{indent_str}{delim}")

            # If the original cursor was at or below the insertion point of the
            # *first* delimiter, it has been shifted down by one line.
            if original_cursor_y >= start_y:
                final_cursor_y += 1
            # Note: we don't need to account for the second insertion at `end_y + 1`
            # because our goal is to place the cursor on the line that was originally
            # at `original_cursor_y`. The second insertion happens *after* this line.

        self.editor.modified = True
        self.editor._set_status_message(f"Added docstring with {delim}")

        # Reset selection and reposition the cursor.
        self.editor.is_selecting = False
        self.editor.selection_start = None
        self.editor.selection_end = None

        # Set the cursor to the beginning of its (now shifted) original line.
        self.editor.cursor_y = min(final_cursor_y, len(self.editor.text) - 1)
        self.editor.cursor_x = 0

    def _remove_docstring_pep8(
        self,
        start_y: int,
        end_y: int,
        delim: str,
        indent_str: str,
        is_single_line: bool,
    ) -> None:
        """Removes PEP8-style docstring delimiters and resets the editor state.
        This method unwraps a text block from its docstring delimiters. After the
        operation, any active selection is cleared, and the cursor is repositioned
        to the beginning of the line where it was before the operation.

        Args:
            start_y: The 0-based starting line index of the docstring block.
            end_y: The 0-based ending line index (inclusive).
            delim: The delimiter string to remove.
            indent_str: The indentation to preserve for single-line unwrapping.
            is_single_line: True if the docstring occupies a single line.
        """
        # Remember the original cursor line.
        original_cursor_y = self.editor.cursor_y

        if is_single_line:
            # Handle single-line docstring removal
            line = self.editor.text[start_y]
            content = line.strip()

            if content.startswith(delim) and content.endswith(delim):
                uncommented_content = content[len(delim) : -len(delim)]
                self.editor.text[start_y] = f"{indent_str}{uncommented_content}"
            # In this case, no lines are deleted, so the original_cursor_y is still valid.
            final_cursor_y = original_cursor_y
        else:
            # Handle multi-line docstring removal
            lines_deleted_before_cursor = 0

            # Remove from the bottom up to keep indices stable during deletion.
            if (
                end_y < len(self.editor.text)
                and self.editor.text[end_y].strip() == delim
            ):
                del self.editor.text[end_y]
                if end_y < original_cursor_y:
                    lines_deleted_before_cursor += 1

            if (
                start_y < len(self.editor.text)
                and self.editor.text[start_y].strip() == delim
            ):
                del self.editor.text[start_y]
                if start_y < original_cursor_y:
                    lines_deleted_before_cursor += 1

            # Calculate the new correct position for the cursor.
            final_cursor_y = original_cursor_y - lines_deleted_before_cursor

        self.editor.modified = True
        self.editor._set_status_message("Removed docstring")

        # Reset selection and set cursor to the corrected position
        self.editor.is_selecting = False
        self.editor.selection_start = None
        self.editor.selection_end = None

        # Set the cursor to the beginning of its (now shifted) original line.
        self.editor.cursor_y = min(final_cursor_y, len(self.editor.text) - 1)
        self.editor.cursor_x = 0

    def _toggle_line_comments(
        self, start_y: int, end_y: int, comment_prefix: str
    ) -> None:
        """Smartly toggles line comments for the given line range.
        Its heuristic is:
        1. If all non-blank lines in the selection are already commented,
        the entire block is uncommented.
        2. Otherwise (if at least one non-blank line is not commented), the
        entire block is commented. Blank lines within the selection
        are ignored during this check but are not modified.
        """
        prefix_to_check = comment_prefix.strip()

        with self.editor._state_lock:
            lines_in_range = []
            for y in range(start_y, end_y + 1):
                if y < len(self.editor.text):
                    lines_in_range.append(self.editor.text[y])

            # Filter out blank lines for the decision-making process.
            non_blank_lines = [line for line in lines_in_range if line.strip()]

            # Decide whether to comment or uncomment.
            # If there are no non-blank lines, we default to commenting.
            should_uncomment = False
            if non_blank_lines:  # Only check if there are non-blank lines.
                should_uncomment = all(
                    line.lstrip().startswith(prefix_to_check)
                    for line in non_blank_lines
                )

            if should_uncomment:
                self._remove_line_comments(start_y, end_y, comment_prefix)
            else:
                self._add_line_comments(start_y, end_y, comment_prefix)

    def _add_line_comments(self, start_y: int, end_y: int, comment_prefix: str) -> None:
        """Adds line comments to a range of lines at a consistent indentation level.
        Skips lines that are already commented to prevent double-commenting.
        """
        prefix_to_add = comment_prefix.strip()

        with self.editor._state_lock:
            # Find the minimum indentation of non-blank lines in the target range.
            min_indent = float("inf")
            lines_to_process = []

            for y in range(start_y, end_y + 1):
                if y < len(self.editor.text):
                    line = self.editor.text[y]
                    if line.strip():
                        lines_to_process.append((y, line))
                        indent = len(line) - len(line.lstrip())
                        min_indent = min(min_indent, indent)

            if not lines_to_process:  # No non-blank lines to comment.
                return

            indent_str = " " * int(min_indent)

            for y, line in lines_to_process:
                # Check if the line is already commented at the correct indent level.
                if not line.lstrip().startswith(prefix_to_add):
                    self.editor.text[y] = (
                        indent_str + prefix_to_add + " " + line.lstrip()
                    )

            self.editor.modified = True
            self.editor._set_status_message(f"Added '{prefix_to_add}' line comments")

    def _remove_line_comments(
        self, start_y: int, end_y: int, comment_prefix: str
    ) -> None:
        """Removes a single level of line comments from a range of lines."""
        prefix_stripped = comment_prefix.strip()

        with self.editor._state_lock:
            for y in range(start_y, end_y + 1):
                if y < len(self.editor.text):
                    line = self.editor.text[y]
                    stripped_line = line.lstrip()

                    if stripped_line.startswith(prefix_stripped):
                        # Find the content after the prefix, stripping one optional space.
                        content_after_prefix = stripped_line[len(prefix_stripped) :]
                        if content_after_prefix.startswith(" "):
                            content_after_prefix = content_after_prefix[1:]

                        # Reconstruct the line.
                        indent_len = len(line) - len(stripped_line)
                        self.editor.text[y] = line[:indent_len] + content_after_prefix

            self.editor.modified = True
            self.editor._set_status_message(
                f"Removed '{prefix_stripped}' line comments"
            )

    def _toggle_block_comment(
        self, start_y: int, end_y: int, block_delims: tuple[str, str]
    ) -> None:
        """Toggles a C-style block comment around the selected line range.
        This method wraps or unwraps a range of lines (`start_y` to `end_y`) with
        block comment delimiters (e.g., `/*` and `*/`). The logic for toggling is
        based on a simple check: if the first non-whitespace part of the first
        selected line is the opening delimiter AND the last non-whitespace part
        of the last line is the closing delimiter, the block is considered
        commented and will be uncommented. Otherwise, the block will be wrapped
        in comment delimiters.
        All text modifications are performed under the editor's state lock to
        ensure thread safety. The editor's `modified` status and status message
        are updated accordingly. Note that this operation does not currently
        adjust the selection or cursor position after modification.

        Args:
            start_y: The 0-based starting line index of the range.
            end_y: The 0-based ending line index (inclusive).
            block_delims: A tuple containing the opening and closing
                comment tags, e.g., `('/*', '*/')`.
        """
        open_tag, close_tag = block_delims

        with self.editor._state_lock:
            # Check if the selection is already wrapped in a block comment.
            first_line = self.editor.text[start_y].lstrip()
            last_line = self.editor.text[end_y].rstrip()

            is_block_commented = first_line.startswith(open_tag) and last_line.endswith(
                close_tag
            )

            if is_block_commented:
                # --- remove the block comment delimiters ---
                # Remove the first occurrence of the opening tag on the first line.
                # Using replace with count=1 ensures we only remove one instance.
                self.editor.text[start_y] = self.editor.text[start_y].replace(
                    open_tag, "", 1
                )

                # Remove the last occurrence of the closing tag on the last line.
                # rsplit is a robust way to handle this from the right side.
                if close_tag in self.editor.text[end_y]:
                    self.editor.text[end_y] = self.editor.text[end_y].rsplit(
                        close_tag, 1
                    )[0]

                self.editor.modified = True
                self.editor._set_status_message(
                    f"Removed {open_tag}...{close_tag} block comment"
                )
            else:
                # --- wrap the range in the block delimiters ---
                # Preserve the leading whitespace of the first line.
                indent = len(self.editor.text[start_y]) - len(first_line)

                # Insert the opening tag after the existing indentation on the first line.
                self.editor.text[start_y] = (
                    self.editor.text[start_y][:indent] + open_tag + " " + first_line
                )

                # Append the closing tag to the end of the last line.
                self.editor.text[end_y] += " " + close_tag

                self.editor.modified = True
                self.editor._set_status_message(
                    f"Wrapped selection in {open_tag}...{close_tag}"
                )
