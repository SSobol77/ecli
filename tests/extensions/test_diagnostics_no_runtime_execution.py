# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_no_runtime_execution.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Regression guards: the diagnostics layer performs no runtime execution (#104).

The framework must not run a VS Code extension host, ``package.json`` scripts,
``activationEvents``, a Copilot/Node runtime, a package manager, or any shell
command string. The only permitted external invocation is a linter executable
through a fixed argv, confined to ``command.py`` and ``providers/ruff.py``.

These tests inspect the layer's own *code* (docstrings and comments stripped via
:mod:`tokenize`) so that security prose in docstrings never masks — or trips —
the checks.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import ecli.extensions.ecli_integration.diagnostics as diagnostics_pkg


PACKAGE_DIR = Path(diagnostics_pkg.__file__).resolve().parent

# subprocess execution is allowed only in the command contract and the Ruff
# adapter — nowhere else in the framework.
_SUBPROCESS_ALLOWED = {"command.py", "providers/ruff.py"}


def _sources() -> dict[str, str]:
    return {
        path.relative_to(PACKAGE_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE_DIR.rglob("*.py"))
    }


def _code_names(source: str) -> set[str]:
    """Return the set of identifier (NAME) tokens, ignoring strings/comments."""
    names: set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.NAME:
                names.add(tok.string)
    except tokenize.TokenError:
        # Fall back to a whitespace split if tokenization fails.
        names.update(source.split())
    return names


def test_diagnostics_layer_lives_only_under_ecli_integration() -> None:
    parts = PACKAGE_DIR.parts
    assert "ecli_integration" in parts
    assert parts[-1] == "diagnostics"
    src_root = PACKAGE_DIR.parents[3]  # .../src
    assert not (src_root / "ecli" / "syntax" / "assets").exists()


def test_no_dangerous_execution_identifiers_in_code() -> None:
    forbidden = {"system", "Popen", "eval", "exec", "__import__", "compile"}
    for name, source in _sources().items():
        names = _code_names(source)
        offenders = names & forbidden
        assert not offenders, f"{offenders} used in {name}"


def test_no_shell_or_vscode_or_copilot_runtime_in_code() -> None:
    for name, source in _sources().items():
        assert "shell=True" not in source, name
        names = {token.lower() for token in _code_names(source)}
        for token in ("copilot", "vscode", "nodejs", "activationevents"):
            assert token not in names, f"{token!r} used in {name}"


def test_subprocess_is_confined_to_command_and_ruff() -> None:
    for name, source in _sources().items():
        if name in _SUBPROCESS_ALLOWED:
            continue
        assert "subprocess" not in _code_names(source), f"subprocess used in {name}"


def test_command_contract_uses_fixed_argv_without_shell() -> None:
    command = (PACKAGE_DIR / "command.py").read_text(encoding="utf-8")
    assert "subprocess.run(" in command
    assert "shell=True" not in command
    ruff = (PACKAGE_DIR / "providers" / "ruff.py").read_text(encoding="utf-8")
    # The Ruff argv is a fixed Python list literal, never a shell string.
    assert "return [" in ruff


def test_no_auto_install_command_strings() -> None:
    forbidden = ("pip install", "uv pip install", "npm install", "pipx install")
    for name, source in _sources().items():
        lowered = source.lower()
        for token in forbidden:
            assert token not in lowered, f"{token!r} found in {name}"
