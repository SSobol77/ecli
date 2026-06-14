# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/characterization/test_existing_editor_entrypoints.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Characterization tests for existing editor/TUI import entrypoints."""

from __future__ import annotations

import importlib

from ecli.core.Ecli import Ecli
from ecli.ui.TerminalAppMode import TerminalAppMode


def test_existing_package_import_smoke_still_works() -> None:
    package = importlib.import_module("ecli")

    assert hasattr(package, "__version__")


def test_editor_and_tui_modules_import_without_constructing_runtime() -> None:
    modules = [
        "ecli.core.Ecli",
        "ecli.ui.KeyBinder",
        "ecli.ui.PanelManager",
        "ecli.ui.panels",
        "ecli.ui.DrawScreen",
        "ecli.ui.TerminalAppMode",
    ]

    imported = [importlib.import_module(module) for module in modules]

    assert [module.__name__ for module in imported] == modules


def test_existing_editor_methods_for_help_and_panels_are_present() -> None:
    expected_methods = (
        "show_help",
        "show_git_panel",
        "toggle_widget_panel",
        "select_ai_provider_and_ask",
        "toggle_file_browser",
        "toggle_system_doctor_panel",
        "show_command_plan_panel",
        "show_services_panel",
        "show_ai_panel",
        "toggle_focus",
    )

    for method_name in expected_methods:
        assert callable(getattr(Ecli, method_name))


def test_terminal_app_mode_entry_and_exit_methods_remain_available() -> None:
    mode = TerminalAppMode()

    assert callable(mode.enter)
    assert callable(mode.exit)
