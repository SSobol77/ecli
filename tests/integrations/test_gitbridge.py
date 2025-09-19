import os
import queue  # type: ignore[import]
import subprocess
import threading
from types import SimpleNamespace
from unittest import mock

from ecli.integrations.GitBridge import GitBridge


class StubEditor(SimpleNamespace):
    def __init__(self):
        super().__init__(
            config={"git": {"enabled": True}},
            _git_q=queue.Queue(),
            _git_cmd_q=queue.Queue(),
            _state_lock=threading.RLock(),
            filename=None,
        )
    def _set_status_message(self, _msg): ...

@mock.patch("ecli.integrations.GitBridge.safe_run")
@mock.patch("os.path.isdir", return_value=True)       # git‑папка «есть»
def test_git_status_parsing(mock_isdir, mock_run):
    def fake(cmd, **_):
        table = {
            ("git", "branch", "--show-current"): "main\n",
            ("git", "status", "--porcelain"): "",
            ("git", "config", "user.name"): "Alice\n",
            ("git", "rev-list", "--count", "HEAD"): "42\n",
        }
        return subprocess.CompletedProcess(cmd, 0, table.get(tuple(cmd), ""), "")
    mock_run.side_effect = fake

    g = GitBridge(StubEditor())      # type: ignore[arg-type]
    branch, user, commits = g.get_info(None)

    assert branch == "main"
    assert user == "Alice"
    assert commits == "42"
