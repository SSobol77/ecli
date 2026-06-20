# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/pysh_console_panel.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""ECLI-owned PySH Console Panel."""

from __future__ import annotations

import curses
import os
import queue
import shlex
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Mapping

from ecli.integrations.pysh_backend import PySHCommandResult, PySHSubprocessBackend
from ecli.ui.panels import BasePanel


MAX_TRANSCRIPT_LINES = 1000


class PySHConsolePanel(BasePanel):
    """Right-side command console backed by PySH subprocess execution."""

    panel_kind = "terminal"
    is_modal_panel = False

    def __init__(
        self,
        stdscr: Any,
        main_editor_instance: Any,
        *,
        backend: PySHSubprocessBackend | None = None,
    ) -> None:
        """Initialize panel-local command state and backend wiring."""
        super().__init__(stdscr, main_editor_instance)
        self.input_line = ""
        self.cursor_col = 0
        self.transcript: list[str] = []
        self.history: list[str] = []
        self.history_index: int | None = None
        self.cwd = self._initial_cwd()
        self.scroll = 0
        self.backend = backend or PySHSubprocessBackend(
            executable=self._configured_pysh_executable()
        )
        self._result_queue: queue.Queue[PySHCommandResult] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._running_command: str | None = None
        self._cancel_notice_emitted = False
        self._layout_window()

    def open(self) -> None:
        """Open the panel and hide the editor cursor while focused."""
        super().open()
        self._set_status("PySH Console Panel ready.")
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    def close(self) -> None:
        """Close the panel, cancelling an owned command if one is running."""
        if self._running_command is not None:
            self.backend.cancel()
        super().close()

    def resize(self) -> None:
        """Recompute the backing window using the existing panel geometry."""
        super().resize()
        self._layout_window()

    def process_queues(self) -> bool:
        """Drain completed backend results without blocking the editor loop."""
        changed = False
        while True:
            try:
                result = self._result_queue.get_nowait()
            except queue.Empty:
                break
            self._apply_result(result)
            changed = True
        return changed

    def draw(self) -> None:
        """Draw the transcript, prompt, input line, and shared panel chrome."""
        if not self.visible:
            return
        if self.win is None:
            self._layout_window()
        win = self.win
        if win is None:
            return

        try:
            win.erase()
        except curses.error:
            return
        self._make_opaque(win)
        self._draw_panel_frame(
            win,
            "PySH Console",
            focused=getattr(self.editor, "focus", None) == "panel",
            footer="Enter run | Ctrl+C cancel | F12 focus | Esc close",
        )
        self._draw_transcript(win)
        self._draw_input_line(win)
        self._present(win)

    def handle_key(self, key: int | str) -> bool:
        """Handle one key event while the PySH Console Panel has focus."""
        if not self.visible:
            return False

        normalized = self._normalize_key(key)
        if normalized is None:
            return False
        if self._handle_action_key(normalized):
            return True
        if self._handle_cursor_key(normalized):
            return True
        if self._handle_history_or_scroll_key(normalized):
            return True
        return self._insert_printable_key(normalized)

    def handle_paste(self, text: str) -> bool:
        """Insert pasted text into the panel input line as one command string."""
        pasted = " ".join(line for line in text.splitlines() if line)
        if not pasted:
            return False
        self._insert_text(pasted)
        return True

    def _submit_input(self) -> None:
        command = self.input_line.strip()
        self.input_line = ""
        self.cursor_col = 0
        self.history_index = None
        if not command:
            return
        self._append_transcript(f"{self._prompt()} {command}")
        self.history.append(command)
        if len(self.history) > 200:
            self.history = self.history[-200:]

        if self._handle_builtin(command):
            return
        self._submit_external_command(command)

    def _handle_builtin(self, command: str) -> bool:
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            self._append_transcript(f"builtin parse error: {exc}")
            return True
        if not parts:
            return True
        name = parts[0]
        args = parts[1:]
        handlers: dict[str, Callable[[list[str]], None]] = {
            "cd": self._builtin_cd,
            "pwd": self._builtin_pwd,
            "clear": self._builtin_clear,
            "exit": self._builtin_exit,
        }
        handler = handlers.get(name)
        if handler is None:
            return False
        handler(args)
        return True

    def _builtin_cd(self, args: list[str]) -> None:
        if len(args) > 1:
            self._append_transcript("cd: too many arguments")
            return
        try:
            target = Path.home() if not args else Path(args[0]).expanduser()
        except RuntimeError as exc:
            self._append_transcript(f"cd: cannot resolve home directory: {exc}")
            return
        if not target.is_absolute():
            target = self.cwd / target
        try:
            resolved = target.resolve(strict=False)
        except OSError as exc:
            self._append_transcript(f"cd: invalid path: {exc}")
            return
        if not resolved.exists() or not resolved.is_dir():
            self._append_transcript(f"cd: no such directory: {resolved}")
            return
        self.cwd = resolved
        self._set_status(f"PySH Console cwd: {self.cwd}")

    def _builtin_pwd(self, _args: list[str]) -> None:
        self._append_transcript(str(self.cwd))

    def _builtin_clear(self, _args: list[str]) -> None:
        self.transcript.clear()
        self.scroll = 0

    def _builtin_exit(self, _args: list[str]) -> None:
        self._close_panel()

    def _submit_external_command(self, command: str) -> None:
        if self._running_command is not None:
            self._append_transcript("Command already running.")
            return
        self._running_command = command
        self._cancel_notice_emitted = False
        env = dict(os.environ)
        cwd = self.cwd
        worker = threading.Thread(
            target=self._run_command_worker,
            args=(command, cwd, env),
            daemon=True,
        )
        self._worker_thread = worker
        worker.start()
        self._set_status(f"PySH running: {command}")

    def _run_command_worker(
        self, command: str, cwd: Path, env: Mapping[str, str]
    ) -> None:
        try:
            result = self.backend.run(command, cwd, env)
        except Exception as exc:
            result = PySHCommandResult(
                command=command,
                cwd=cwd,
                returncode=126,
                stdout="",
                stderr=f"PySH backend execution failed: {exc}",
            )
        self._result_queue.put(result)

    def _apply_result(self, result: PySHCommandResult) -> None:
        if result.cancelled:
            if not self._cancel_notice_emitted:
                self._append_transcript("Command cancelled.")
        else:
            self._append_output(result.stdout)
            self._append_output(result.stderr)
            if result.returncode != 0:
                self._append_transcript(f"[exit {result.returncode}]")
        self._running_command = None
        self._worker_thread = None
        self._cancel_notice_emitted = False
        self._set_status("PySH Console Panel ready.")

    def _cancel_running_command(self) -> None:
        if self._running_command is None:
            self._set_status("No PySH command is running.")
            return
        self.backend.cancel()
        if not self._cancel_notice_emitted:
            self._append_transcript("Command cancelled.")
            self._cancel_notice_emitted = True
        self._set_status("PySH command cancellation requested.")

    def _append_output(self, output: str) -> None:
        if not output:
            return
        for line in output.splitlines():
            self._append_transcript(line)

    def _append_transcript(self, line: str) -> None:
        self.transcript.append(line)
        if len(self.transcript) > MAX_TRANSCRIPT_LINES:
            self.transcript = self.transcript[-MAX_TRANSCRIPT_LINES:]
        self.scroll = 0

    def _history_previous(self) -> None:
        if not self.history:
            return
        if self.history_index is None:
            self.history_index = len(self.history) - 1
        else:
            self.history_index = max(0, self.history_index - 1)
        self.input_line = self.history[self.history_index]
        self.cursor_col = len(self.input_line)

    def _history_next(self) -> None:
        if self.history_index is None:
            return
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self.input_line = ""
        else:
            self.input_line = self.history[self.history_index]
        self.cursor_col = len(self.input_line)

    def _insert_printable_key(self, key: int | str) -> bool:
        if not isinstance(key, int):
            return False
        if key < 32 or key == 127:
            return False
        try:
            char = chr(key)
        except ValueError:
            return False
        if not char.isprintable():
            return False
        self._insert_text(char)
        return True

    def _insert_text(self, text: str) -> None:
        self.input_line = (
            self.input_line[: self.cursor_col]
            + text
            + self.input_line[self.cursor_col :]
        )
        self.cursor_col += len(text)
        self.history_index = None

    def _backspace(self) -> bool:
        if self.cursor_col <= 0:
            return True
        self.input_line = (
            self.input_line[: self.cursor_col - 1] + self.input_line[self.cursor_col :]
        )
        self.cursor_col -= 1
        self.history_index = None
        return True

    def _delete_forward(self) -> bool:
        if self.cursor_col >= len(self.input_line):
            return True
        self.input_line = (
            self.input_line[: self.cursor_col] + self.input_line[self.cursor_col + 1 :]
        )
        self.history_index = None
        return True

    def _draw_transcript(self, win: Any) -> None:
        try:
            h, w = win.getmaxyx()
        except (curses.error, AttributeError):
            return
        body_height = self._body_height()
        if body_height <= 0 or w <= 2:
            return
        end = max(0, len(self.transcript) - self.scroll)
        start = max(0, end - body_height)
        visible_lines = self.transcript[start:end]
        attr = self.editor.colors.get("default", curses.A_NORMAL)
        error_attr = self.editor.colors.get("error", attr)
        for row_offset, line in enumerate(visible_lines):
            attr_for_line = error_attr if line.startswith("[exit ") else attr
            try:
                win.addnstr(1 + row_offset, 1, line, max(1, w - 2), attr_for_line)
            except curses.error:
                pass

    def _draw_input_line(self, win: Any) -> None:
        try:
            h, w = win.getmaxyx()
        except (curses.error, AttributeError):
            return
        if h < 4 or w <= 2:
            return
        input_row = h - 2
        prompt = self._prompt()
        input_text = f"{prompt} {self.input_line}"
        attr = self.editor.colors.get("status", curses.A_REVERSE)
        try:
            win.addnstr(input_row, 1, input_text, max(1, w - 2), attr)
        except curses.error:
            pass

        cursor_x = 1 + len(prompt) + 1 + self.cursor_col
        if 1 <= cursor_x < w - 1:
            char = " "
            if self.cursor_col < len(self.input_line):
                char = self.input_line[self.cursor_col]
            try:
                win.addstr(input_row, cursor_x, char, curses.A_REVERSE)
            except curses.error:
                pass

    def _body_height(self) -> int:
        if self.win is None:
            return 0
        try:
            h, _w = self.win.getmaxyx()
        except (curses.error, AttributeError):
            return 0
        return max(0, int(h) - 4)

    def _prompt(self) -> str:
        name = self.cwd.name if self.cwd.name else str(self.cwd)
        return f"{name}>"

    def _close_panel(self) -> None:
        panel_manager = getattr(self.editor, "panel_manager", None)
        if (
            panel_manager is not None
            and getattr(panel_manager, "active_panel", None) is self
        ):
            panel_manager.close_active_panel()
        else:
            self.close()

    def _set_status(self, message: str) -> None:
        setter = getattr(self.editor, "_set_status_message", None)
        if callable(setter):
            setter(message)

    def _initial_cwd(self) -> Path:
        filename = getattr(self.editor, "filename", None)
        if filename:
            path = Path(filename).expanduser()
            if path.exists():
                return path.parent.resolve() if path.is_file() else path.resolve()
            if path.parent.exists():
                return path.parent.resolve()
        return Path.cwd()

    def _configured_pysh_executable(self) -> str:
        config = getattr(self.editor, "config", {}) or {}
        if not isinstance(config, dict):
            return "pysh"
        for section_name in ("pysh", "pysh_console", "terminal"):
            section = config.get(section_name)
            if not isinstance(section, dict):
                continue
            for key in ("executable", "path", "backend_path", "pysh_path"):
                value = section.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return "pysh"

    def _normalize_key(self, key: int | str) -> int | None:
        if isinstance(key, str):
            return ord(key) if len(key) == 1 else None
        return key

    def _handle_action_key(self, key: int) -> bool:
        handlers: dict[int, Callable[[], bool]] = {
            getattr(curses, "KEY_F12", 276): self._toggle_focus,
            27: self._close_panel_handled,
            3: self._cancel_running_command_handled,
            10: self._submit_input_handled,
            13: self._submit_input_handled,
            getattr(curses, "KEY_ENTER", 343): self._submit_input_handled,
            curses.KEY_BACKSPACE: self._backspace,
            127: self._backspace,
            8: self._backspace,
            curses.KEY_DC: self._delete_forward,
            21: self._clear_input_line,
        }
        handler = handlers.get(key)
        if handler is None:
            return False
        return handler()

    def _handle_cursor_key(self, key: int) -> bool:
        if key == curses.KEY_LEFT:
            self.cursor_col = max(0, self.cursor_col - 1)
            return True
        if key == curses.KEY_RIGHT:
            self.cursor_col = min(len(self.input_line), self.cursor_col + 1)
            return True
        if key == curses.KEY_HOME:
            self.cursor_col = 0
            return True
        if key == getattr(curses, "KEY_END", curses.KEY_LL):
            self.cursor_col = len(self.input_line)
            return True
        return False

    def _handle_history_or_scroll_key(self, key: int) -> bool:
        if key == curses.KEY_UP:
            self._history_previous()
            return True
        if key == curses.KEY_DOWN:
            self._history_next()
            return True
        if key == curses.KEY_PPAGE:
            self.scroll = min(
                max(0, len(self.transcript) - 1), self.scroll + self._body_height()
            )
            return True
        if key == curses.KEY_NPAGE:
            self.scroll = max(0, self.scroll - self._body_height())
            return True
        return False

    def _toggle_focus(self) -> bool:
        if hasattr(self.editor, "toggle_focus"):
            self.editor.toggle_focus()
        return True

    def _close_panel_handled(self) -> bool:
        self._close_panel()
        return True

    def _cancel_running_command_handled(self) -> bool:
        self._cancel_running_command()
        return True

    def _submit_input_handled(self) -> bool:
        self._submit_input()
        return True

    def _clear_input_line(self) -> bool:
        self.input_line = ""
        self.cursor_col = 0
        return True
