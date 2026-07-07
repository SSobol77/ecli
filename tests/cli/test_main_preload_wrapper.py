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
import copy
from pathlib import Path
from typing import Any, Callable

import pytest

from ecli.core.Ecli import Ecli


REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_MODULE_PATH = REPO_ROOT / "src" / "ecli" / "__main__.py"

PreloadWrapper = Callable[[Any, Path], None]


def _extract_preload_cli_document() -> PreloadWrapper:
    """Compile and return the real, current ``_preload_cli_document`` function.

    Parses ``src/ecli/__main__.py``, isolates the single function definition,
    and execs it on its own (with ``from __future__ import annotations``
    preserved so the ``editor: Ecli`` / ``candidate: Path`` annotations stay
    postponed strings rather than requiring those names to exist in this
    minimal namespace). None of the module's other top-level code runs, so
    exec() here only ever compiles and runs one isolated function definition
    extracted from a trusted, repository-local source file.
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
    exec(code, namespace)
    return namespace["_preload_cli_document"]


@pytest.fixture(scope="module")
def preload_cli_document_wrapper() -> PreloadWrapper:
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


def _record_call(wrapper: PreloadWrapper, candidate: Path) -> _CallRecordingEditor:
    """Invoke the wrapper against a fresh recording spy and return it."""
    editor = _CallRecordingEditor()
    wrapper(editor, candidate)
    return editor


def test_delegates_exactly_once_to_editor_preload_cli_document(
    preload_cli_document_wrapper: PreloadWrapper, tmp_path: Path
) -> None:
    candidate = tmp_path / "some-cli-argument.py"

    editor = _record_call(preload_cli_document_wrapper, candidate)

    assert editor.calls == [("preload_cli_document", (candidate,))]


def test_calls_no_fallback_probe_methods(
    preload_cli_document_wrapper: PreloadWrapper, tmp_path: Path
) -> None:
    """Regression: the removed probe loop tried open_or_create, open_file,
    create_empty_buffer_with_name, new_buffer_named, new_file_with_name, and
    new_file. None of those may be invoked any more.
    """
    candidate = tmp_path / "no-fallback-probe.py"

    editor = _record_call(preload_cli_document_wrapper, candidate)

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
    preload_cli_document_wrapper: PreloadWrapper, tmp_path: Path
) -> None:
    """Regression: the removed code caught every exception from
    preload_cli_document() and silently tried fallbacks instead of
    propagating the real error.
    """

    class _RaisingEditor:
        def preload_cli_document(self, candidate: Path) -> None:
            raise TypeError("wrong signature")

    editor = _RaisingEditor()
    candidate = tmp_path / "whatever.py"

    with pytest.raises(TypeError, match="wrong signature"):
        preload_cli_document_wrapper(editor, candidate)


# ---------------------------------------------------------------------------
# Real-editor integration tests: prove end-to-end CLI startup behavior is
# unchanged for existing files, nonexistent files, and error logging.
# ---------------------------------------------------------------------------


class FakeHistory:
    def clear(self) -> None:
        return None

    def add_action(self, _action: dict[str, Any]) -> None:
        return None


# Attribute defaults for a minimal lightweight Ecli instance, mirroring
# tests/core/test_file_open_safety.py's make_editor() helper. Mutable values
# are deep-copied per instance in make_lightweight_editor() below so editors
# never share list/dict state.
_LIGHTWEIGHT_EDITOR_DEFAULTS: dict[str, Any] = {
    "cursor_x": 0,
    "cursor_y": 0,
    "scroll_top": 0,
    "scroll_left": 0,
    "modified": False,
    "encoding": "utf-8",
    "filename": None,
    "status_message": "Ready",
    "_sticky_status": None,
    "is_selecting": False,
    "selection_start": None,
    "selection_end": None,
    "highlighted_matches": [],
    "search_matches": [],
    "search_term": "",
    "current_match_idx": -1,
    "git": None,
    "git_panel_instance": None,
    "_lexer": None,
    "current_language": None,
    "custom_syntax_patterns": [],
    "colors": {"default": 0},
    "config": {},
    "is_256_color_terminal": True,
    "_force_full_redraw": False,
    "_file_loaded_from_disk": False,
    "_file_had_final_newline": False,
    "diagnostic_line_highlight": None,
    "is_lightweight": True,
    "stdscr": None,
}


def make_lightweight_editor(initial_text: list[str] | None = None) -> Ecli:
    """Minimal lightweight Ecli instance for exercising open/preload/save
    without curses or a config-backed constructor.
    """
    editor = Ecli.__new__(Ecli)
    for attr, value in _LIGHTWEIGHT_EDITOR_DEFAULTS.items():
        setattr(editor, attr, copy.deepcopy(value))
    editor.text = list(initial_text) if initial_text else ["existing content"]
    editor.history = FakeHistory()
    editor.run_lint_async = lambda *_a, **_k: False  # type: ignore[method-assign]
    return editor


def _preload(wrapper: PreloadWrapper, candidate: Path) -> Ecli:
    """Build a fresh lightweight editor and invoke the wrapper against it."""
    editor = make_lightweight_editor()
    wrapper(editor, candidate)
    return editor


def test_existing_file_cli_argument_loads_normally(
    preload_cli_document_wrapper: PreloadWrapper, tmp_path: Path
) -> None:
    src = tmp_path / "existing_main_wrapper.py"
    src.write_text("print('via main wrapper')\n", encoding="utf-8")

    editor = _preload(preload_cli_document_wrapper, src)

    assert editor.text[0] == "print('via main wrapper')"
    assert editor.filename == str(src.resolve())
    assert editor.modified is False


def test_nonexistent_file_cli_argument_does_not_touch_disk_before_save(
    preload_cli_document_wrapper: PreloadWrapper, tmp_path: Path
) -> None:
    target = tmp_path / "main-wrapper-new-file.py"

    editor = _preload(preload_cli_document_wrapper, target)

    assert not target.exists()
    assert editor.text == [""]
    assert editor.modified is False
    assert editor.filename == str(target.resolve())


def test_nonexistent_file_cli_argument_then_save_creates_file(
    preload_cli_document_wrapper: PreloadWrapper, tmp_path: Path
) -> None:
    target = tmp_path / "main-wrapper-then-save.py"

    editor = _preload(preload_cli_document_wrapper, target)
    assert not target.exists()

    editor.text = ["print('saved via main wrapper')"]
    editor.modified = True
    editor.save_file()

    assert target.exists()
    assert "print('saved via main wrapper')" in target.read_text(encoding="utf-8")


def test_nonexistent_file_cli_argument_logs_no_type_error_traceback(
    preload_cli_document_wrapper: PreloadWrapper,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Regression: the removed probe loop blindly guessed method signatures
    (``meth(initial_path=...)`` then ``meth(...)``) and always raised
    ``TypeError`` against methods that do not accept those arguments.
    """
    target = tmp_path / "main-wrapper-no-traceback.py"

    with caplog.at_level("DEBUG"):
        _preload(preload_cli_document_wrapper, target)  # must not raise

    assert "TypeError" not in caplog.text
    assert "Traceback" not in caplog.text
