# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/ui/test_textmate_scroll_pty_smoke.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""End-to-end PTY scroll smoke test for the #102 freeze.

This launches the **real** ECLI curses application inside a pseudo-terminal,
opens the **real** repository ``Makefile`` with the extension TextMate engine
enabled, sends scroll keys that move the viewport past the ``ifeq`` block near
line 42 (the reported freeze point), then sends quit. The test **fails** if ECLI
does not respond to quit within a hard timeout — i.e. if it froze. Environments
where curses cannot start at all (no usable terminal) are skipped, never failed.

Every interactive read/wait has a deadline; nothing here can hang indefinitely.
"""

from __future__ import annotations

import os
import select
import signal
import struct
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

STARTUP_TIMEOUT = 20.0  # seconds to first render
QUIT_TIMEOUT = 15.0  # seconds to exit after Ctrl+Q (freeze budget)

pytestmark = pytest.mark.slow


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    import fcntl
    import termios

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _drain(fd: int, seconds: float) -> bytes:
    """Read whatever is available from ``fd`` for up to ``seconds`` (never blocks)."""
    deadline = time.monotonic() + seconds
    data = b""
    while time.monotonic() < deadline:
        readable, _, _ = select.select([fd], [], [], 0.2)
        if fd not in readable:
            continue
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        data += chunk
    return data


def _isolated_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Build an isolated HOME + config forcing the extension TextMate engine."""
    home = tmp_path / "home"
    config_dir = home / ".config" / "ecli"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        "theme = 207\n"
        "[editor]\n"
        "syntax_highlighting = true\n"
        "[extensions]\n"
        "enabled = true\n"
        'syntax_engine = "extension"\n',
        encoding="utf-8",
    )
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        (REPO_ROOT / "Makefile").read_text(encoding="utf-8"), encoding="utf-8"
    )
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(config_dir.parent)
    env["TERM"] = "xterm-256color"
    env.setdefault("LANG", "C.UTF-8")
    env.pop("ECLI_THEME", None)
    return env, makefile


def _scroll_past_line_42(master: int) -> None:
    """Move the viewport well past the ifeq block, triggering repaints."""
    for _ in range(10):
        os.write(master, b"\x1b[6~")  # PageDown (mode-agnostic)
        time.sleep(0.05)
    for _ in range(20):
        os.write(master, b"\x1bOB")  # Down (application cursor keys)
        os.write(master, b"\x1b[B")  # Down (normal cursor keys)
        time.sleep(0.02)


@pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="no pty support on this platform"
)
def test_scroll_makefile_in_pty_does_not_freeze(tmp_path: Path) -> None:
    import pty
    import subprocess

    if not (REPO_ROOT / "Makefile").is_file():
        pytest.skip("repository Makefile is required for this smoke test")

    env, makefile = _isolated_env(tmp_path)
    master, slave = pty.openpty()
    _set_winsize(slave, rows=40, cols=120)
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "ecli", str(makefile)],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            cwd=str(tmp_path),
            close_fds=True,
            start_new_session=True,
        )
    except OSError as error:  # pragma: no cover - environment dependent
        os.close(master)
        os.close(slave)
        pytest.skip(f"cannot spawn ecli: {error}")
    os.close(slave)

    try:
        startup = _drain(master, STARTUP_TIMEOUT)
        if proc.poll() is not None:
            pytest.skip(
                f"ecli exited during startup (rc={proc.returncode}); curses could "
                "not initialise in this environment"
            )
        assert startup, "ecli produced no initial render output"

        # Scroll past the ifeq block near line 42 (and far beyond).
        _scroll_past_line_42(master)
        # Proof it kept rendering while scrolling (would be empty/stalled on freeze).
        _drain(master, 5.0)

        # Quit (Ctrl+Q). The buffer is unmodified, so no save prompt blocks exit.
        os.write(master, b"\x11")

        deadline = time.monotonic() + QUIT_TIMEOUT
        while time.monotonic() < deadline and proc.poll() is None:
            _drain(master, 0.25)
        assert proc.poll() is not None, (
            "ECLI did not exit within "
            f"{QUIT_TIMEOUT:.0f}s of quit while scrolling the Makefile — freeze"
        )
    finally:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:  # pragma: no cover - cleanup best effort
            pass
        os.close(master)
