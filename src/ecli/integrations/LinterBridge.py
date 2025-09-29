# ecli/integrations/LinterBridge.py
"""LinterBridge.py
========================
Module for managing linting operations in the ECLI editor.
This module provides a backend service for linting operations, allowing the editor
to perform linting commands and fetch diagnostics without any UI-specific code.
It supports both external DevOps linters and the Ruff Language Server Protocol (LSP)
for Python files.
It handles the initialization of the LSP server, sending and receiving
messages, and processing diagnostics to update the editor's UI.
It is designed to be used with the Ecli class, which is expected to provide
the necessary configuration and state management for linting operations.
"""

import importlib.util
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import traceback
import types
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


logger = logging.getLogger(__name__)


## ================== LinterBridge Class ====================
class LinterBridge:
    """
    Manages all linting operations, choosing between LSP (for Python)
    and external CLI linters (for DevOps formats).
    """

    def __init__(self, editor: "Ecli") -> None:
        self.editor = editor
        # --- State for LSP ---
        self.lsp_proc: Optional[subprocess.Popen[bytes]] = None
        self.lsp_reader: Optional[threading.Thread] = None
        self.lsp_message_q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=256)
        self.is_lsp_initialized: bool = False
        self.lsp_seq_id: int = 0
        self.lsp_doc_versions: dict[str, int] = {}

        # --- State for DevOps linters ---
        self.HAS_DEVOPS_LINTERS: bool = (
            importlib.util.find_spec("lint_devops") is not None
        )
        self.devops_linter_module: Optional[types.ModuleType] = None
        if self.HAS_DEVOPS_LINTERS:
            try:
                self.devops_linter_module = importlib.import_module("lint_devops")
                logging.info("Successfully imported 'lint_devops' module.")
            except ImportError as e:
                logging.error("Found 'lint_devops' but failed to import it: %s", e)
                self.HAS_DEVOPS_LINTERS = False

    def run_linter(self, code: Optional[str] = None) -> bool:
        """Acts as the primary dispatcher for all linting operations.

        This method determines which linting tool to use based on the current
        file's language. It handles:
        1.  Running external DevOps linters via `lint_devops.py`.
        2.  Running the Ruff LSP for Python files.
        3.  Reporting when no suitable linter is available.

        It orchestrates the entire process, from getting the code to be linted
        to updating the editor's status and initiating the asynchronous analysis.

        Args:
            code (Optional[str]): The source code to lint. If None, the current
                                editor buffer content is used. This is useful for
                                linting the file content as it was just saved.

        Returns:
            bool: True if the editor's status message was changed, indicating a
                redraw is needed. False otherwise.
        """
        original_status = self.editor.status_message
        if self.editor.current_language is None:
            self.editor.detect_language()
        current_lang = self.editor.current_language

        if (
            self.devops_linter_module
            and hasattr(self.devops_linter_module, "DEVOPS_LINTERS")
            and current_lang in self.devops_linter_module.DEVOPS_LINTERS
        ):
            code_to_lint = os.linesep.join(self.editor.text) if code is None else code
            self.editor._set_status_message(
                f"Running linter for {current_lang}...", is_lint_status=True
            )
            thread = threading.Thread(
                target=self._run_devops_linter_thread,
                args=(current_lang, code_to_lint),
                daemon=True,
            )
            thread.start()
            return self.editor.status_message != original_status

        if current_lang != "python":
            msg = "Ruff: Linting is only available for Python files."
            self.editor._set_status_message(
                message_for_statusbar=msg,
                is_lint_status=True,
                full_lint_output=msg,
                activate_lint_panel_if_issues=False,
            )
            return self.editor.status_message != original_status

        code_to_lint = os.linesep.join(self.editor.text) if code is None else code
        return self._run_python_lsp(code_to_lint)

    def _run_devops_linter_thread(self, language: str, code: str) -> None:
        """Worker function for the thread that runs an external linter."""
        if not self.devops_linter_module:
            return
        try:
            result = self.devops_linter_module.run_devops_linter(language, code)
            self.editor._set_status_message(
                f"{language}: analysis complete.",
                is_lint_status=True,
                full_lint_output=result,
                activate_lint_panel_if_issues=True,
            )
        except Exception as e:
            logging.error(f"Error running DevOps linter for {language}", exc_info=True)
            self.editor._set_status_message(
                f"Error in {language} linter: {e}",
                is_lint_status=True,
                full_lint_output=traceback.format_exc(),
                activate_lint_panel_if_issues=True,
            )

    def _run_python_lsp(self, code: str) -> bool:
        """Runs and interacts with the Ruff LSP for Python."""
        original_status = self.editor.status_message
        self._start_lsp_server_if_needed()
        if not self.is_lsp_initialized:
            msg = "Ruff LSP is still initializing..."
            self.editor._set_status_message(
                msg, is_lint_status=True, full_lint_output=msg
            )
            return self.editor.status_message != original_status
        uri = self._get_lsp_uri()
        op = "didChange" if uri in self.lsp_doc_versions else "didOpen"
        if op == "didOpen":
            self._send_lsp_did_open(code)
        else:
            self._send_lsp_did_change(code)
        self.editor._set_status_message(
            "Ruff: analysis started...",
            is_lint_status=True,
            full_lint_output="Ruff: analysis in progress...",
        )
        logging.debug("Sent %s (%d bytes) to Ruff-LSP.", op, len(code))
        return self.editor.status_message != original_status

    def reload_devops_module(self) -> bool:
        """Attempts to hot-reload the `lint_devops` module at runtime."""
        if not self.devops_linter_module:
            self.editor._set_status_message(
                "'lint_devops' module not available to reload."
            )
            return False
        try:
            self.devops_linter_module = importlib.reload(self.devops_linter_module)
            self.editor._set_status_message("DevOps linters module reloaded.")
            return True
        except Exception as e:
            self.editor._set_status_message(f"Error reloading linters module: {e}")
            return False

    def _start_lsp_server_if_needed(self) -> None:
        """Starts or reuses the Ruff LSP process."""
        if self.lsp_proc and self.lsp_proc.poll() is None:
            return
        cmd = ["ruff", "server", "--preview"]
        try:
            preexec_fn = os.setsid if sys.platform != "win32" else None
            self.lsp_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                preexec_fn=preexec_fn,
            )
            logging.info("Ruff LSP started with PID %s", self.lsp_proc.pid)
        except Exception as exc:
            self.editor._set_status_message(f"Ruff LSP error: {exc}")
            self.lsp_proc = None
            return
        self.lsp_reader = threading.Thread(
            target=self._lsp_reader_loop, name="LSP-stdout", daemon=True
        )
        self.lsp_reader.start()
        root_uri = f"file://{os.getcwd()}"
        params = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {},
            "clientInfo": {"name": "Ecli"},
            "workspaceFolders": [{"uri": root_uri, "name": "workspace"}],
        }
        self._send_lsp("initialize", params, is_request=True)
        self._send_lsp("initialized", {})
        self.is_lsp_initialized = True

    def _send_lsp(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        *,
        is_request: bool = False,
    ) -> None:
        """Sends an LSP message to the server."""
        if (
            not self.lsp_proc
            or self.lsp_proc.stdin is None
            or self.lsp_proc.poll() is not None
        ):
            return
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        if is_request:
            self.lsp_seq_id += 1
            payload["id"] = self.lsp_seq_id
        payload_json = json.dumps(payload)
        payload_bytes = payload_json.encode("utf-8")
        header = f"Content-Length: {len(payload_bytes)}\r\n\r\n"
        try:
            self.lsp_proc.stdin.write(header.encode("utf-8") + payload_bytes)
            self.lsp_proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self.shutdown()

    def _lsp_reader_loop(self) -> None:
        """Continuously reads and processes responses from the LSP server's stdout."""
        while True:
            proc = self.lsp_proc
            if not proc or proc.poll() is not None:
                break
            stream = proc.stdout
            if not stream:
                break
            header_buffer = b""
            try:
                while not header_buffer.endswith(b"\r\n\r\n"):
                    byte = stream.read(1)
                    if not byte:
                        return
                    header_buffer += byte
                    if len(header_buffer) > 4096:
                        return
            except Exception:
                return
            header_str = header_buffer.decode("ascii", "ignore")
            match = re.search(r"Content-Length:\s*(\d+)", header_str, re.IGNORECASE)
            if not match:
                continue
            content_length = int(match.group(1))
            body_bytes = b""
            bytes_remaining = content_length
            try:
                while bytes_remaining > 0:
                    chunk = stream.read(bytes_remaining)
                    if not chunk:
                        return
                    body_bytes += chunk
                    bytes_remaining -= len(chunk)
            except Exception:
                return
            try:
                message = json.loads(body_bytes.decode("utf-8"))
                self.lsp_message_q.put_nowait(message)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.debug(
                    "Dropping invalid message (%s): %r",
                    type(exc).__name__,
                    body_bytes[:200],
                )
            except queue.Full:
                logger.warning("LSP message queue is full; dropping message.")

    def process_lsp_queue(self) -> bool:
        """Processes all pending messages from the internal LSP server queue."""
        changed = False
        while not self.lsp_message_q.empty():
            try:
                message = self.lsp_message_q.get_nowait()
                if message.get("method") == "textDocument/publishDiagnostics":
                    params = message.get("params", {})
                    self._handle_diagnostics(params)
                    changed = True
            except queue.Empty:
                break
            except Exception as e:
                logging.error(
                    "LSP: Error processing message from queue: %s", e, exc_info=True
                )
        return changed

    def _handle_diagnostics(self, params: dict[str, Any]) -> None:
        """Processes diagnostics data received from the LSP server."""
        diagnostics: list[dict] = params.get("diagnostics", [])
        if not diagnostics:
            self.editor._set_status_message(
                message_for_statusbar="✓ No issues found (Ruff)",
                is_lint_status=True,
                full_lint_output="✓ No issues found (Ruff)",
                activate_lint_panel_if_issues=False,
            )
            return
        try:
            first = diagnostics[0]
            line = first.get("range", {}).get("start", {}).get("line", -1) + 1
            msg = first.get("message", "Unknown issue")
            status_bar_message = (
                f"Ruff: {msg} (Line {line})" if line > 0 else f"Ruff: {msg}"
            )
        except (AttributeError, TypeError):  # zawężone z Exception
            status_bar_message = "Ruff: Issues found (check panel)"
        panel_lines = []
        for diag in diagnostics:
            try:
                line = diag.get("range", {}).get("start", {}).get("line", -1) + 1
                char = diag.get("range", {}).get("start", {}).get("character", -1) + 1
                msg = diag.get("message", "No message provided.")
                panel_lines.append(f"{line}:{char}  {msg}" if line > 0 else msg)
            except (AttributeError, TypeError):  # zawężone z Exception
                panel_lines.append("Malformed diagnostic item.")
        panel_text = "\n".join(panel_lines)
        self.editor._set_status_message(
            message_for_statusbar=status_bar_message,
            is_lint_status=True,
            full_lint_output=panel_text,
            activate_lint_panel_if_issues=True,
        )

    def _get_lsp_uri(self) -> str:
        """Returns the file:// URI that identifies the current buffer."""
        filename = self.editor.filename or "<buffer>"
        return f"file://{os.path.abspath(filename)}"

    def _send_lsp_did_open(self, text: str) -> None:
        """Sends a `textDocument/didOpen` notification."""
        uri = self._get_lsp_uri()
        self.lsp_doc_versions[uri] = 1
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": "python",
                "version": 1,
                "text": text,
            }
        }
        self._send_lsp("textDocument/didOpen", params)

    def _send_lsp_did_change(self, text: str) -> None:
        """Sends a `textDocument/didChange` notification."""
        uri = self._get_lsp_uri()
        version = self.lsp_doc_versions.get(uri, 1) + 1
        self.lsp_doc_versions[uri] = version
        params = {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": [{"text": text}],
        }
        self._send_lsp("textDocument/didChange", params)

    def shutdown(self) -> None:
        """Gracefully shuts down the LSP server and related threads."""
        logging.info("Shutting down LinterBridge and LSP server...")
        if self.lsp_proc and self.lsp_proc.poll() is None:
            try:
                self._send_lsp("shutdown", is_request=True)
                self._send_lsp("exit")
                self.lsp_proc.terminate()
                self.lsp_proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, Exception) as e:
                logging.warning(f"Forcing LSP process kill due to: {e}")
                self.lsp_proc.kill()
        self.is_lsp_initialized = False
        self.lsp_proc = None
        self.lsp_reader = None
