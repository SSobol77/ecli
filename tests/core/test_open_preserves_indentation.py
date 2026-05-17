# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: tests/core/test_open_preserves_indentation.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Regression coverage for source-file whitespace preservation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ecli.core.Ecli import Ecli


CYRILLIC_HEADER = (
    "# --- \u041f\u043e\u0442\u043e\u043a\u043e\u0431\u0435\u0437\u043e"
    "\u043f\u0430\u0441\u043d\u044b\u0439 \u043c\u0435\u043d\u0435"
    "\u0434\u0436\u0435\u0440 \u0441\u043e\u0441\u0442\u043e\u044f"
    "\u043d\u0438\u0439 ---"
)
CYRILLIC_DOC = (
    "    \u041a\u043b\u0430\u0441\u0441 \u0434\u043b\u044f \u0443"
    "\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f \u0441"
    "\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435\u043c \u0443"
    "\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432 \u0432 \u043f"
    "\u0430\u043c\u044f\u0442\u0438. \u041f\u043e\u0442\u043e\u043a"
    "\u043e\u0431\u0435\u0437\u043e\u043f\u0430\u0441\u0435\u043d."
)
CYRILLIC_STATIC_COMMENT = (
    "        # \u0421\u0442\u0430\u0442\u0438\u0447\u0435\u0441"
    "\u043a\u0430\u044f \u0438\u043d\u0444\u043e\u0440\u043c"
    "\u0430\u0446\u0438\u044f \u043e\u0431 \u0443\u0441\u0442"
    "\u0440\u043e\u0439\u0441\u0442\u0432\u0430\u0445"
)
CYRILLIC_DYNAMIC_COMMENT = (
    "        # \u0414\u0438\u043d\u0430\u043c\u0438\u0447\u0435"
    "\u0441\u043a\u043e\u0435 \u0441\u043e\u0441\u0442\u043e"
    "\u044f\u043d\u0438\u0435"
)
CYRILLIC_HEADER_FRAGMENT = (
    "\u041f\u043e\u0442\u043e\u043a\u043e\u0431\u0435\u0437\u043e"
    "\u043f\u0430\u0441\u043d\u044b\u0439 \u043c\u0435\u043d\u0435"
    "\u0434\u0436\u0435\u0440"
)
CYRILLIC_DOC_FRAGMENT = (
    "\u041a\u043b\u0430\u0441\u0441 \u0434\u043b\u044f \u0443"
    "\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f \u0441"
    "\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435\u043c \u0443"
    "\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432"
)
CYRILLIC_STATIC_FRAGMENT = (
    "\u0421\u0442\u0430\u0442\u0438\u0447\u0435\u0441\u043a"
    "\u0430\u044f \u0438\u043d\u0444\u043e\u0440\u043c\u0430"
    "\u0446\u0438\u044f"
)
CYRILLIC_DYNAMIC_FRAGMENT = (
    "\u0414\u0438\u043d\u0430\u043c\u0438\u0447\u0435\u0441"
    "\u043a\u043e\u0435 \u0441\u043e\u0441\u0442\u043e\u044f"
    "\u043d\u0438\u0435"
)


class FakeHistory:
    def clear(self) -> None:
        return None

    def add_action(self, _action: dict[str, Any]) -> None:
        return None


def make_editor() -> Ecli:
    editor = Ecli.__new__(Ecli)
    editor.text = [""]
    editor.cursor_x = 0
    editor.cursor_y = 0
    editor.scroll_top = 0
    editor.scroll_left = 0
    editor.modified = False
    editor.encoding = "utf-8"
    editor.filename = None
    editor.status_message = "Ready"
    editor.is_selecting = False
    editor.selection_start = None
    editor.selection_end = None
    editor.highlighted_matches = []
    editor.search_matches = []
    editor.search_term = ""
    editor.current_match_idx = -1
    editor.history = FakeHistory()
    editor.git = None
    editor._lexer = None
    editor.current_language = None
    editor.custom_syntax_patterns = []
    editor.colors = {"default": 0}
    editor.config = {}
    editor.is_256_color_terminal = True
    editor._force_full_redraw = False
    editor._file_loaded_from_disk = False
    editor._file_had_final_newline = False
    return editor


def test_open_preserves_source_indentation_and_save_without_edit(
    tmp_path: Path,
) -> None:
    expected_lines = [
        "# --- Thread-safe state manager ---",
        "class DeviceManager:",
        '    """',
        "    Class for managing device state in memory.",
        "    Thread-safe.",
        '    """',
        "    def __init__(self, device_config):",
        "        self.lock = threading.Lock()",
        "        # Static device information",
        "        self.devices_config = {d['name']: d for d in device_config}",
        "        # Dynamic state",
        "        self.clients = {}",
        "        self.last_telemetry = {}",
        '        self.statuses = {name: "offline" for name in self.devices_config}',
        "",
        "    def get_all_statuses(self):",
        "        with self.lock:",
        "            return list(self.statuses.items())",
        "",
        "    def get_full_device_data(self):",
        "        with self.lock:",
        "            data = []",
        "            for name, config in self.devices_config.items():",
        "                device_data = config.copy()",
        "                device_data['status'] = self.statuses.get(name, \"offline\")",
        "                data.append(device_data)",
        "            return data",
        "\t# tab-indented line is preserved",
        "\t    mixed_tab_space_indent()",
        "    ",
        "        trailing_spaces_are_preserved = True    ",
    ]
    original_bytes = ("\n".join(expected_lines) + "\n").encode("utf-8")
    source_file = tmp_path / "manager.py"
    source_file.write_bytes(original_bytes)

    editor = make_editor()

    assert editor.open_file(str(source_file)) is True
    assert editor.text == expected_lines
    assert editor.text[7].startswith("        ")
    assert editor.text[17].startswith("            ")
    assert editor.text[27].startswith("\t")
    assert editor.text[28].startswith("\t    ")
    assert editor.text[29] == "    "
    assert editor.text[30].endswith("    ")

    for line in editor.text:
        if line[:1] in {" ", "\t"}:
            assert line != line.lstrip()

    highlighted = editor.apply_syntax_highlighting_with_pygments(
        ["        return data", "\t    mixed_indent()"],
        [0, 1],
    )
    assert ["".join(token for token, _attr in line) for line in highlighted] == [
        "        return data",
        "\t    mixed_indent()",
    ]

    assert editor.save_file() is True
    assert source_file.read_bytes() == original_bytes


def test_open_utf8_cyrillic_source_uses_utf8_and_preserves_indentation(
    tmp_path: Path,
) -> None:
    expected_lines = [
        CYRILLIC_HEADER,
        "class DeviceManager:",
        '    """',
        CYRILLIC_DOC,
        '    """',
        "    def __init__(self, device_config):",
        "        self.lock = threading.Lock()",
        CYRILLIC_STATIC_COMMENT,
        "        self.devices_config = {d['name']: d for d in device_config}",
        CYRILLIC_DYNAMIC_COMMENT,
        "        self.clients = {}",
    ]
    original_bytes = ("\n".join(expected_lines) + "\n").encode("utf-8")
    source_file = tmp_path / "manager_ru.py"
    source_file.write_bytes(original_bytes)
    editor = make_editor()

    assert editor.open_file(str(source_file)) is True

    assert editor.encoding == "UTF-8"
    assert editor.encoding != "MACROMAN"
    assert editor.text == expected_lines
    assert CYRILLIC_HEADER_FRAGMENT in editor.text[0]
    assert CYRILLIC_DOC_FRAGMENT in editor.text[3]
    assert CYRILLIC_STATIC_FRAGMENT in editor.text[7]
    assert CYRILLIC_DYNAMIC_FRAGMENT in editor.text[9]
    assert editor.text[3].startswith("    ")
    assert editor.text[6].startswith("        ")
    assert source_file.read_bytes() == original_bytes
