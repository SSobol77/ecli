# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_file_open_safety.py
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for open_file safety gates introduced in ECLI 0.2.3.

Covers:
- Binary file rejection (NUL byte, high control-byte ratio)
- Large-file rejection in non-interactive mode
- Nonexistent path → new clean buffer with filename preserved
- Permission / read errors → buffer preserved, modified unchanged
- Normal UTF-8 file still opens correctly
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest

from ecli.core.Ecli import _BINARY_CONTROL_RATIO, _LARGE_FILE_BYTES, Ecli


# ---------------------------------------------------------------------------
# Shared test double helpers
# ---------------------------------------------------------------------------


class FakeHistory:
    def clear(self) -> None:
        return None

    def add_action(self, _action: dict[str, Any]) -> None:
        return None


def make_editor(initial_text: list[str] | None = None) -> Ecli:
    """Return a minimal lightweight Ecli instance for open_file tests."""
    editor = Ecli.__new__(Ecli)
    editor.text = list(initial_text) if initial_text else ["existing content"]
    editor.cursor_x = 0
    editor.cursor_y = 0
    editor.scroll_top = 0
    editor.scroll_left = 0
    editor.modified = False
    editor.encoding = "utf-8"
    editor.filename = None
    editor.status_message = "Ready"
    editor._sticky_status = None
    editor.is_selecting = False
    editor.selection_start = None
    editor.selection_end = None
    editor.highlighted_matches = []
    editor.search_matches = []
    editor.search_term = ""
    editor.current_match_idx = -1
    editor.history = FakeHistory()
    editor.git = None
    editor.git_panel_instance = None
    editor._lexer = None
    editor.current_language = None
    editor.custom_syntax_patterns = []
    editor.colors = {"default": 0}
    editor.config = {}
    editor.is_256_color_terminal = True
    editor._force_full_redraw = False
    editor._file_loaded_from_disk = False
    editor._file_had_final_newline = False
    editor.diagnostic_line_highlight = None
    editor.is_lightweight = True
    editor.stdscr = None  # non-interactive: no curses prompts
    # Silence lint async so it never blocks the test.
    editor.run_lint_async = lambda *_a, **_k: False  # type: ignore[method-assign]
    return editor


# ---------------------------------------------------------------------------
# _is_likely_binary unit tests
# ---------------------------------------------------------------------------


def test_is_likely_binary_detects_nul_byte() -> None:
    assert Ecli._is_likely_binary(b"hello\x00world") is True


def test_is_likely_binary_rejects_clean_utf8() -> None:
    assert Ecli._is_likely_binary(b"import os\nprint('hello')\n") is False


def test_is_likely_binary_rejects_empty_sample() -> None:
    assert Ecli._is_likely_binary(b"") is False


def test_is_likely_binary_detects_high_control_ratio() -> None:
    # Build a sample with >2 % suspicious control bytes.
    payload = bytes([0x01, 0x02, 0x03]) * 10 + b"a" * 100
    assert Ecli._is_likely_binary(payload) is True


def test_is_likely_binary_allows_low_control_ratio() -> None:
    # A few TAB / LF / CR bytes are fine.
    payload = b"line1\tfield\n" * 50
    assert Ecli._is_likely_binary(payload) is False


# ---------------------------------------------------------------------------
# P0 – Binary file gate
# ---------------------------------------------------------------------------


def test_open_file_rejects_nul_byte_file(tmp_path: Path) -> None:
    bad = tmp_path / "binary.bin"
    bad.write_bytes(b"normal text\x00more text")

    editor = make_editor()
    result = editor.open_file(str(bad))

    assert result is True
    assert "binary" in editor.status_message.lower()
    # Buffer must remain untouched.
    assert editor.text == ["existing content"]
    assert editor.modified is False


def test_open_file_rejects_high_control_byte_file(tmp_path: Path) -> None:
    payload = bytes([0x01] * 30 + [0x61] * 70)  # 30 % control bytes
    bad = tmp_path / "control.bin"
    bad.write_bytes(payload)

    editor = make_editor()
    result = editor.open_file(str(bad))

    assert result is True
    assert "binary" in editor.status_message.lower()
    assert editor.text == ["existing content"]
    assert editor.modified is False


def test_open_file_accepts_normal_utf8_source_file(tmp_path: Path) -> None:
    src = tmp_path / "good.py"
    src.write_text("import os\n\nprint('hello')\n", encoding="utf-8")

    editor = make_editor()
    result = editor.open_file(str(src))

    assert result is True
    assert editor.text[0] == "import os"
    assert editor.modified is False


# ---------------------------------------------------------------------------
# P0 – Large-file gate (non-interactive mode)
# ---------------------------------------------------------------------------


def test_open_file_rejects_large_file_in_non_interactive_mode(tmp_path: Path) -> None:
    large = tmp_path / "huge.txt"
    # Write more than _LARGE_FILE_BYTES.
    chunk = b"A" * (1024 * 1024)  # 1 MiB per write
    writes_needed = (_LARGE_FILE_BYTES // len(chunk)) + 2
    with large.open("wb") as fh:
        for _ in range(writes_needed):
            fh.write(chunk)

    editor = make_editor()
    # is_lightweight=True and stdscr=None → non-interactive gate applies.
    result = editor.open_file(str(large))

    assert result is True
    assert (
        "large" in editor.status_message.lower()
        or "too large" in editor.status_message.lower()
    )
    assert editor.text == ["existing content"]
    assert editor.modified is False


# ---------------------------------------------------------------------------
# P2 – open_or_create (the real CLI-startup entry point for file arguments)
# must reach the same clean-buffer behavior as open_file, without touching
# the path into existence on disk first.
# ---------------------------------------------------------------------------


def test_open_or_create_nonexistent_path_does_not_touch_disk(tmp_path: Path) -> None:
    target = tmp_path / "not_yet_created.py"

    editor = make_editor()
    editor.open_or_create(str(target))

    assert not target.exists()
    assert editor.text == [""]
    assert editor.modified is False


def test_open_or_create_nonexistent_path_sets_filename(tmp_path: Path) -> None:
    target = tmp_path / "clean_new_file.txt"

    editor = make_editor()
    editor.open_or_create(str(target))

    assert editor.filename == str(target.resolve())


def test_open_or_create_nonexistent_path_raises_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Regression: the old buffer-creation probe always raised TypeError."""
    target = tmp_path / "no_traceback_here.py"
    editor = make_editor()

    with caplog.at_level("DEBUG"):
        editor.open_or_create(str(target))  # must not raise

    assert "TypeError" not in caplog.text
    assert "Traceback" not in caplog.text


def test_open_or_create_existing_file_opens_its_content(tmp_path: Path) -> None:
    src = tmp_path / "existing.py"
    src.write_text("print(1)\n", encoding="utf-8")

    editor = make_editor()
    editor.open_or_create(str(src))

    assert editor.text[0] == "print(1)"
    assert editor.filename == str(src.resolve())


# ---------------------------------------------------------------------------
# P2 – Nonexistent path opens a clean new buffer
# ---------------------------------------------------------------------------


def test_open_nonexistent_file_creates_empty_clean_buffer(tmp_path: Path) -> None:
    target = str(tmp_path / "brand_new.py")

    editor = make_editor()
    result = editor.open_file(target)

    assert result is True
    assert editor.filename == target
    assert editor.text == [""]
    assert editor.modified is False


def test_open_nonexistent_file_status_says_new_file(tmp_path: Path) -> None:
    target = str(tmp_path / "new_script.py")

    editor = make_editor()
    editor.open_file(target)

    msg = editor.status_message.lower()
    assert "new file" in msg or "not yet saved" in msg


def test_open_nonexistent_file_does_not_show_error_in_status(tmp_path: Path) -> None:
    target = str(tmp_path / "fresh.py")

    editor = make_editor()
    editor.open_file(target)

    # Must not say "Error" or "not found" — it's a new buffer, not an error.
    msg = editor.status_message.lower()
    assert "error" not in msg
    assert "not found" not in msg


def test_open_nonexistent_file_then_save_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "will_be_created.py"
    assert not target.exists()

    editor = make_editor()
    editor.open_file(str(target))

    # Simulate typing something (mark modified so save_file triggers write).
    editor.text = ["print('hello')"]
    editor.modified = True
    editor.save_file()

    assert target.exists()
    assert "print('hello')" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# P2 – Permission / read errors are sticky and preserve the buffer
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses file permissions")
def test_open_unreadable_file_preserves_buffer(tmp_path: Path) -> None:
    unreadable = tmp_path / "secret.txt"
    unreadable.write_text("private data", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        original_text = ["my precious buffer content"]
        editor = make_editor(initial_text=original_text)
        editor.open_file(str(unreadable))

        assert editor.text == original_text
    finally:
        unreadable.chmod(stat.S_IRUSR | stat.S_IWUSR)


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses file permissions")
def test_open_unreadable_file_does_not_mark_modified(tmp_path: Path) -> None:
    unreadable = tmp_path / "nope.txt"
    unreadable.write_text("private", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        editor = make_editor()
        editor.open_file(str(unreadable))

        assert editor.modified is False
    finally:
        unreadable.chmod(stat.S_IRUSR | stat.S_IWUSR)


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses file permissions")
def test_open_unreadable_file_sets_sticky_error_message(tmp_path: Path) -> None:
    unreadable = tmp_path / "locked.txt"
    unreadable.write_text("private", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        editor = make_editor()
        editor.open_file(str(unreadable))

        # Sticky status must be set and contain a permission hint.
        sticky = getattr(editor, "_sticky_status", None)
        assert sticky is not None
        assert "permission" in sticky.lower() or "error" in sticky.lower()
    finally:
        unreadable.chmod(stat.S_IRUSR | stat.S_IWUSR)


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses file permissions")
def test_open_unreadable_file_no_crash_without_curses(tmp_path: Path) -> None:
    """open_file must not raise even when stdscr is None (non-interactive)."""
    unreadable = tmp_path / "crash_check.txt"
    unreadable.write_text("x", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        editor = make_editor()
        assert editor.stdscr is None
        # Must not raise.
        editor.open_file(str(unreadable))
    finally:
        unreadable.chmod(stat.S_IRUSR | stat.S_IWUSR)
