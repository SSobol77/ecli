# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: src/ecli/integrations/GitBridge.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

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
import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ecli.utils.utils import safe_run


if TYPE_CHECKING:
    from ecli.core.Ecli import Ecli


@dataclass(frozen=True)
class GitCommandResult:
    """Structured result contract for Git command execution."""

    command_label: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str = ""


# ================= GitBridge Class ==============================
class GitBridge:
    """Manages all Git integration for the editor. This class acts as a "backend"
    service for Git operations, containing no UI-specific code.
    """

    def __init__(self, editor: "Ecli"):
        self.editor: Ecli = editor
        self.config: dict = editor.config
        self.info: tuple[str, str, str] = ("", "", "0")
        self.repo_root: Optional[str] = None
        self.repo_state: str = "unavailable"
        self.last_filename_context: Optional[str] = None
        self.info_q: queue.Queue[tuple[str, str, str]] = editor._git_q
        self.cmd_q: queue.Queue[str] = editor._git_cmd_q

    def get_info(self, file_path_context: Optional[str]) -> tuple[str, str, str]:
        """Synchronously fetches essential Git information."""
        return self._get_repo_info_sync(file_path_context)

    def update_git_info(self, force: bool = False) -> None:
        """Initiates a non-blocking, asynchronous update of the Git information."""
        if not self.config.get("git", {}).get("enabled", True):
            if self.info != ("", "", "0"):
                self.reset_state()
            return

        current_file_context = self.editor.filename
        with self.editor._state_lock:
            if not force and current_file_context == self.last_filename_context:
                return
            self.last_filename_context = current_file_context
            self.repo_state = "loading"

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
        self.repo_root = None
        self.repo_state = "unavailable"
        self.last_filename_context = None

    def resolve_repo_root(
        self, file_path_context: Optional[str] = None
    ) -> Optional[str]:
        """Resolve the Git repository root for an active file or current directory."""
        if shutil.which("git") is None:
            self.repo_root = None
            self.repo_state = "unavailable"
            return None

        candidates: list[Path] = []
        if file_path_context:
            path = Path(file_path_context).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            path = path.resolve(strict=False)
            candidates.append(path if path.is_dir() else path.parent)
        candidates.append(Path.cwd())

        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            result = safe_run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(candidate),
                timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                self.repo_root = result.stdout.strip()
                return self.repo_root

        self.repo_root = None
        self.repo_state = "not repo"
        return None

    def run_git_command(
        self,
        cmd_list: list[str],
        *,
        file_path_context: Optional[str] = None,
        timeout: float = 15.0,
    ) -> GitCommandResult:
        """Run a Git command in the resolved repository root."""
        command_label = " ".join(cmd_list)
        repo_root = self.resolve_repo_root(file_path_context)
        if repo_root is None:
            return GitCommandResult(
                command_label=command_label,
                cwd=str(Path.cwd()),
                returncode=128,
                stdout="",
                stderr="Not a Git repository.",
                error="not_repo" if self.repo_state == "not repo" else self.repo_state,
            )

        try:
            result = subprocess.run(
                cmd_list,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return GitCommandResult(
                command_label=command_label,
                cwd=repo_root,
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )
        except subprocess.TimeoutExpired as exc:
            return GitCommandResult(
                command_label=command_label,
                cwd=repo_root,
                returncode=-15,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
                error=f"Command timed out after {timeout:g}s.",
            )
        except OSError as exc:
            return GitCommandResult(
                command_label=command_label,
                cwd=repo_root,
                returncode=127,
                stdout="",
                stderr=str(exc),
                error=str(exc),
            )

    def _get_repo_info_sync(
        self, file_path_context: Optional[str]
    ) -> tuple[str, str, str]:
        repo_dir = self.resolve_repo_root(file_path_context)
        if repo_dir is None:
            return "", "not configured", "0"

        run_git = functools.partial(safe_run, cwd=repo_dir, timeout=3)
        branch, user, commits = "", "", "0"
        res_branch = run_git(["git", "branch", "--show-current"])
        if res_branch.returncode == 0 and res_branch.stdout.strip():
            branch = res_branch.stdout.strip()
        else:
            res_ref = run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            if res_ref.returncode == 0 and res_ref.stdout.strip():
                branch = res_ref.stdout.strip()
            else:
                res_symbolic = run_git(["git", "symbolic-ref", "--short", "HEAD"])
                if res_symbolic.returncode == 0 and res_symbolic.stdout.strip():
                    branch = res_symbolic.stdout.strip()
                else:
                    branch = "detached"
        if branch == "HEAD":
            branch = "detached"

        status_result = run_git(["git", "status", "--porcelain"])
        if status_result.returncode == 0 and status_result.stdout.strip():
            self.repo_state = "dirty"
            branch += "*"
        elif status_result.returncode == 0:
            self.repo_state = "clean"
        else:
            self.repo_state = "unavailable"

        res_user = run_git(["git", "config", "user.name"])
        if res_user.returncode == 0 and res_user.stdout.strip():
            user = res_user.stdout.strip()
        else:
            res_email = run_git(["git", "config", "user.email"])
            user = (
                res_email.stdout.strip()
                if res_email.returncode == 0 and res_email.stdout.strip()
                else "not configured"
            )
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
        res = self.run_git_command(cmd_list, file_path_context=self.editor.filename)
        if res.returncode == 0:
            msg = f"Git {command_name}: Successful."
            if command_name in ["commit", "pull", "push"]:
                self.cmd_q.put("request_git_info_update")
            if res.stdout.strip():
                msg += f" Output: {res.stdout.strip().splitlines()[0][:90]}..."
        else:
            detail = (res.stderr or res.error or "unknown error").strip()
            msg = f"Git {command_name} error: {detail.splitlines()[0][:100]}..."
        self.cmd_q.put(msg)

    def _handle_git_info(self, git_data: tuple[str, str, str]) -> None:
        """Processes fetched Git data and updates the editor's status message."""
        with self.editor._state_lock:
            if git_data == self.info and self.repo_state != "loading":
                return
            self.info = git_data
        branch, user, commits = git_data
        if not branch:
            if self.repo_state == "loading":
                self.repo_state = "not repo"
            self.editor._set_status_message("Not a Git repository.")
            return
        state = "dirty" if "*" in branch else "clean"
        self.repo_state = state
        status = f"Git: {state} - {branch.rstrip('*')} by {user} ({commits} commits)"
        self.editor._set_status_message(status)
