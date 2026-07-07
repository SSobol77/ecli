# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/cli/test_main_preload_wrapper.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for ``ecli.__main__._preload_cli_document`` after the dead
fallback/probe cleanup.

``src/ecli/__main__.py`` is a true script entry point: it has unconditional
top-level side effects (argv-sensitive service-CLI dispatch that can call
``sys.exit()``, plus real config/logging setup) that run on any import. It is
not safe to ``import ecli.__main__`` directly from a test. Instead, this
module extracts the current ``_preload_cli_document`` function body straight
from the real source file via ``ast`` and executes only that function
definition in an isolated namespace -- so the test always exercises the real,
current implementation without triggering the rest of the module.

Covers:
- Delegates exactly once to ``editor.preload_cli_document(candidate)``.
- Calls no fallback/probe methods (open_or_create, open_file,
  create_empty_buffer_with_name, new_buffer_named, new_file_with_name,
  new_file).
- Does not swallow exceptions raised by the delegate.
- Nonexistent-path CLI argument: no disk write before an explicit save, clean
  unmodified buffer, filename set to the requested path.
- Existing-path CLI argument: content loads normally.
- No TypeError/Traceback logged from wrong method signatures.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Callable

import pytest

from ecli.core.Ecli import Ecli


REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_MODULE_PATH = REPO_ROOT / "src" / "ecli" / "__main__.py"


def _extract_preload_cli_document() -> Callable[[Any, Path], None]:
    """Compile and return the real, current ``_preload_cli_document`` function.

    Parses ``src/ecli/__main__.py``, isolates the single function definition,
    and execs it on its own (with ``from __future__ import annotations``
    preserved so the ``editor: Ecli`` / ``candidate: Path`` annotations stay
    postponed strings rather than requiring those names to exist in this
    minimal namespace). None of the module's other top-level code runs.
    """
    source = MAIN_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MAIN_MODULE_PATH))

    target: ast.FunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_preload_cli_document":
            target = node
            break
    assert target is not None, "_preload_cli_document not found in src/ecli/__main__.py"

    future_import = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    isolated = ast.Module(body=[future_import, target], type_ignores=[])
    ast.fix_missing_locations(isolated)

    code = compile(isolated, filename=str(MAIN_MODULE_PATH), mode="exec")
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102 - isolated, controlled source
    return namespace["_preload_cli_document"]


@pytest.fixture(scope="module")
def preload_cli_document_wrapper() -> Callable[[Any, Path], None]:
    return _extract_preload_cli_document()


# ---------------------------------------------------------------------------
# Spy-based unit tests: prove the wrapper is a single deterministic delegate
# with no fallback/probe logic left.
# ---------------------------------------------------------------------------


class _CallRecordingEditor:
    """Records every method call so tests can assert exactly one call fired."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def preload_cli_document(self, candidate: Path) -> None:
        self.calls.append(("preload_cli_document", (candidate,)))

    def _fail_if_called(self, name: str) -> Callable[..., None]:
        def _probe(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, args))
            raise AssertionError(f"dead fallback probe was called: {name}")

        return _probe

    def __getattr__(self, name: str) -> Callable[..., None]:
        # Any method other than preload_cli_document must never be touched.
        return self._fail_if_called(name)


def test_delegates_exactly_once_to_editor_preload_cli_document(
    preload_cli_document_wrapper: Callable[[Any, Path], None],
) -> None:
    editor = _CallRecordingEditor()
    candidate = Path("/tmp/some-cli-argument.py")

    preload_cli_document_wrapper(editor, candidate)

    assert editor.calls == [("preload_cli_document", (candidate,))]


def test_calls_no_fallback_probe_methods(
    preload_cli_document_wrapper: Callable[[Any, Path], None],
) -> None:
    """Regression: the removed probe loop tried open_or_create, open_file,
    create_empty_buffer_with_name, new_buffer_named, new_file_with_name, and
    new_file. None of those may be invoked any more.
    """
    editor = _CallRecordingEditor()
    candidate = Path("/tmp/no-fallback-probe.py")

    preload_cli_document_wrapper(editor, candidate)

    called_names = {name for name, _args in editor.calls}
    assert called_names == {"preload_cli_document"}
    for forbidden in (
        "open_or_create",
        "open_file",
        "create_empty_buffer_with_name",
        "new_buffer_named",
        "new_file_with_name",
        "new_file",
    ):
        assert forbidden not in called_names


def test_does_not_swallow_exceptions_from_delegate(
    preload_cli_document_wrapper: Callable[[Any, Path], None],
) -> None:
    """Regression: the removed code caught every exception from
    preload_cli_document() and silently tried fallbacks instead of
    propagating the real error.
    """

    class _RaisingEditor:
        def preload_cli_document(self, candidate: Path) -> None:
            raise TypeError("wrong signature")

    with pytest.raises(TypeError, match="wrong signature"):
        preload_cli_document_wrapper(_RaisingEditor(), Path("/tmp/whatever.py"))


# ---------------------------------------------------------------------------
# Real-editor integration tests: prove end-to-end CLI startup behavior is
# unchanged for existing files, nonexistent files, and error logging.
# ---------------------------------------------------------------------------


class FakeHistory:
    def clear(self) -> None:
        return None

    def add_action(self, _action: dict[str, Any]) -> None:
        return None


def make_lightweight_editor(initial_text: list[str] | None = None) -> Ecli:
    """Minimal lightweight Ecli instance, mirroring
    tests/core/test_file_open_safety.py's make_editor() helper.
    """
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
    editor.stdscr = None
    editor.run_lint_async = lambda *_a, **_k: False  # type: ignore[method-assign]
    return editor


def test_existing_file_cli_argument_loads_normally(
    preload_cli_document_wrapper: Callable[[Any, Path], None], tmp_path: Path
) -> None:
    src = tmp_path / "existing_main_wrapper.py"
    src.write_text("print('via main wrapper')\n", encoding="utf-8")

    editor = make_lightweight_editor()
    preload_cli_document_wrapper(editor, src)

    assert editor.text[0] == "print('via main wrapper')"
    assert editor.filename == str(src.resolve())
    assert editor.modified is False


def test_nonexistent_file_cli_argument_does_not_touch_disk_before_save(
    preload_cli_document_wrapper: Callable[[Any, Path], None], tmp_path: Path
) -> None:
    target = tmp_path / "main-wrapper-new-file.py"

    editor = make_lightweight_editor()
    preload_cli_document_wrapper(editor, target)

    assert not target.exists()
    assert editor.text == [""]
    assert editor.modified is False
    assert editor.filename == str(target.resolve())


def test_nonexistent_file_cli_argument_then_save_creates_file(
    preload_cli_document_wrapper: Callable[[Any, Path], None], tmp_path: Path
) -> None:
    target = tmp_path / "main-wrapper-then-save.py"

    editor = make_lightweight_editor()
    preload_cli_document_wrapper(editor, target)
    assert not target.exists()

    editor.text = ["print('saved via main wrapper')"]
    editor.modified = True
    editor.save_file()

    assert target.exists()
    assert "print('saved via main wrapper')" in target.read_text(encoding="utf-8")


def test_nonexistent_file_cli_argument_logs_no_type_error_traceback(
    preload_cli_document_wrapper: Callable[[Any, Path], None],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Regression: the removed probe loop blindly guessed method signatures
    (``meth(initial_path=...)`` then ``meth(...)``) and always raised
    ``TypeError`` against methods that do not accept those arguments.
    """
    target = tmp_path / "main-wrapper-no-traceback.py"
    editor = make_lightweight_editor()

    with caplog.at_level("DEBUG"):
        preload_cli_document_wrapper(editor, target)  # must not raise

    assert "TypeError" not in caplog.text
    assert "Traceback" not in caplog.text
