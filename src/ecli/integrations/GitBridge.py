# ecli/integrations/GitBridge.py
"""GitBridge.py
========================
Module for managing Git integration in the ECLI editor.
This module provides a backend service for Git operations, allowing the editor
to perform Git commands and fetch repository information without any UI-specific code.
It uses threading to perform operations asynchronously, ensuring that the editor remains responsive.
It also handles the processing of Git-related queues for commands and information updates.
This module is designed to be used with the Ecli class, which is expected to provide
the necessary configuration and state management for Git operations.
"""

import functools
import os
import queue
import threading
from typing import TYPE_CHECKING, Optional

from ecli.utils.utils import safe_run


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


# ================= GitBridge Class ==============================
class GitBridge:
    """Manages all Git integration for the editor. This class acts as a "backend"
    service for Git operations, containing no UI-specific code.
    """

    def __init__(self, editor: "Ecli"):
        self.editor: Ecli = editor
        self.config: dict = editor.config
        self.info: tuple[str, str, str] = ("", "", "0")
        self.last_filename_context: Optional[str] = None
        self.info_q: queue.Queue[tuple[str, str, str]] = editor._git_q
        self.cmd_q: queue.Queue[str] = editor._git_cmd_q

    def get_info(self, file_path_context: Optional[str]) -> tuple[str, str, str]:
        """Synchronously fetches essential Git information."""
        return self._get_repo_info_sync(file_path_context)

    def update_git_info(self) -> None:
        """Initiates a non-blocking, asynchronous update of the Git information."""
        if not self.config.get("git", {}).get("enabled", True):
            if self.info != ("", "", "0"):
                self.reset_state()
            return

        current_file_context = self.editor.filename
        with self.editor._state_lock:
            if current_file_context == self.last_filename_context:
                return
            self.last_filename_context = current_file_context

        thread = threading.Thread(
            target=self._fetch_git_info_async,
            args=(current_file_context,),
            daemon=True,
            name="GitInfoFetchThread",
        )
        thread.start()

    def run_command_async(self, cmd_list: list[str]):
        """Executes a given Git command asynchronously."""
        command_name = cmd_list[1] if len(cmd_list) > 1 else "command"
        self.editor._set_status_message(f"Running git {command_name}...")

        thread = threading.Thread(
            target=self._run_git_command_async,
            args=(cmd_list, command_name),
            daemon=True,
            name=f"GitExecThread-{command_name}",
        )
        thread.start()

    def process_queues(self) -> bool:
        """Processes all pending messages from the Git-related queues."""
        changed = False
        try:
            while True:
                git_info_data = self.info_q.get_nowait()
                self._handle_git_info(git_info_data)
                changed = True
        except queue.Empty:
            pass

        try:
            while True:
                result_msg = self.cmd_q.get_nowait()
                if result_msg == "request_git_info_update":
                    self.update_git_info()
                else:
                    self.editor._set_status_message(result_msg)
                changed = True
        except queue.Empty:
            pass
        return changed

    def reset_state(self):
        """Resets the cached Git state."""
        self.info = ("", "", "0")
        self.last_filename_context = None

    def _get_repo_info_sync(
        self, file_path_context: Optional[str]
    ) -> tuple[str, str, str]:
        # (Your original, unchanged code for this method goes here)
        repo_dir = os.getcwd()
        if file_path_context and os.path.isfile(file_path_context):
            repo_dir = os.path.dirname(os.path.abspath(file_path_context))
        if not os.path.isdir(os.path.join(repo_dir, ".git")):
            return "", "", "0"
        run_git = functools.partial(safe_run, cwd=repo_dir, timeout=3)
        branch, user, commits = "", "", "0"
        res_branch = run_git(["git", "branch", "--show-current"])
        if res_branch.returncode == 0 and res_branch.stdout.strip():
            branch = res_branch.stdout.strip()
        else:
            res_ref = run_git(["git", "symbolic-ref", "--short", "HEAD"])
            if res_ref.returncode == 0 and res_ref.stdout.strip():
                branch = res_ref.stdout.strip()
            else:
                branch = "detached"
        if run_git(["git", "status", "--porcelain"]).stdout.strip():
            branch += "*"
        res_user = run_git(["git", "config", "user.name"])
        if res_user.returncode == 0:
            user = res_user.stdout.strip()
        res_commits = run_git(["git", "rev-list", "--count", "HEAD"])
        if res_commits.returncode == 0 and res_commits.stdout.strip().isdigit():
            commits = res_commits.stdout.strip()
        return branch, user, commits

    def _fetch_git_info_async(self, file_path_context: Optional[str]) -> None:
        """Asynchronous worker that calls the synchronous fetch method."""
        try:
            git_data = self._get_repo_info_sync(file_path_context)
            self.info_q.put(git_data)
        except Exception as e:
            self.info_q.put((f"fetch_error {e}", "", "0"))

    def _run_git_command_async(self, cmd_list: list[str], command_name: str) -> None:
        """Executes a Git command in a thread and puts the result in the queue."""
        # (Your original, unchanged code for this method goes here)
        msg = ""
        try:
            repo_dir = os.getcwd()
            if self.editor.filename and os.path.isfile(self.editor.filename):
                repo_dir = os.path.dirname(os.path.abspath(self.editor.filename))
            res = safe_run(cmd_list, cwd=repo_dir)
            if res.returncode == 0:
                msg = f"Git {command_name}: Successful."
                if command_name in ["commit", "pull", "push"]:
                    self.cmd_q.put("request_git_info_update")
                if res.stdout.strip():
                    msg += f" Output: {res.stdout.strip().splitlines()[0][:90]}..."
            else:
                msg = f"Git {command_name} error: {res.stderr.strip().splitlines()[0][:100]}..."
        except Exception as e:
            msg = f"Git {command_name} system error: {e}"
        self.cmd_q.put(msg)

    def _handle_git_info(self, git_data: tuple[str, str, str]) -> None:
        """Processes fetched Git data and updates the editor's status message."""
        with self.editor._state_lock:
            if git_data == self.info:
                return
            self.info = git_data
        branch, user, commits = git_data
        if not branch:
            self.editor._set_status_message("Not a Git repository.")
            return
        status = f"Git: {branch} by {user} ({commits} commits)"
        self.editor._set_status_message(status)
