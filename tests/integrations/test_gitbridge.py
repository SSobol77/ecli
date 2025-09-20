# tests/integrations/test_gitbridge.py
"""Unit test for the `GitBridge` integration.
=============================================

This module tests the ability of `GitBridge` to correctly parse information
from a Git repository, including:

- Current branch name.
- Configured user name.
- Commit count.

The test uses a stubbed editor (`StubEditor`) and mocks system calls
(`os.path.isdir`, `safe_run`) to simulate Git behavior without relying
on a real repository.

Tools & libraries:
- `pytest` (test framework, implicitly used).
- `unittest.mock` for patching functions and simulating external behavior.
- `subprocess.CompletedProcess` for mocking process execution results.
"""

import os
import queue  # type: ignore[import]
import subprocess
import threading
from types import SimpleNamespace
from unittest import mock

from ecli.integrations.GitBridge import GitBridge


class StubEditor(SimpleNamespace):
    """Minimal stub for the editor, providing only what GitBridge requires."""

    def __init__(self) -> None:
        """Initialize the stub with default configuration and thread-safe queues."""
        super().__init__(
            config={"git": {"enabled": True}},  # Enable Git integration
            _git_q=queue.Queue(),  # Queue for Git messages
            _git_cmd_q=queue.Queue(),  # Queue for Git commands
            _state_lock=threading.RLock(),  # Thread-safe state lock
            filename=None,  # Current file (unused in this test)
        )

    def _set_status_message(self, _msg): ...

    # Status message setter is unused in this test but present to match API.


@mock.patch("ecli.integrations.GitBridge.safe_run")
@mock.patch("os.path.isdir", return_value=True)  # Pretend `.git` directory exists
def test_git_status_parsing(mock_isdir, mock_run):
    """Test that GitBridge correctly parses branch, user, and commit count.

    This test replaces `safe_run` with a fake implementation that returns
    pre-defined outputs for specific git commands. It ensures that:

    - Current branch is parsed from `git branch --show-current`.
    - User name is parsed from `git config user.name`.
    - Commit count is parsed from `git rev-list --count HEAD`.
    - Empty output from `git status --porcelain` is handled gracefully.
    """

    def fake(cmd, **_):
        """Fake `safe_run` returning mock git command results."""
        table = {
            ("git", "branch", "--show-current"): "main\n",
            ("git", "status", "--porcelain"): "",
            ("git", "config", "user.name"): "Alice\n",
            ("git", "rev-list", "--count", "HEAD"): "42\n",
        }
        return subprocess.CompletedProcess(cmd, 0, table.get(tuple(cmd), ""), "")

    # Replace `safe_run` with our fake
    mock_run.side_effect = fake

    # Initialize GitBridge with a stub editor
    g = GitBridge(StubEditor())  # type: ignore[arg-type]
    branch, user, commits = g.get_info(None)

    # Verify that values are parsed as expected
    assert branch == "main"
    assert user == "Alice"
    assert commits == "42"
