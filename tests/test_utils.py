# tests/test_utils.py
# Project:ecli
# This file is part of the ecli project.
# It is subject to the license terms in the LICENSE file found in the top-level directory of this distribution.
# The full list of project contributors is contained in the AUTHORS file found in the same directory.
from ecli.utils import utils


def test_deep_merge():
    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"b": {"y": 99, "z": 100}, "c": 3}
    result = utils.deep_merge(base, override)
    expected = {"a": 1, "b": {"x": 10, "y": 99, "z": 100}, "c": 3}
    assert result == expected

def test_hex_to_xterm_valid_color():
    assert utils.hex_to_xterm("#ffffff") == 231
    assert utils.hex_to_xterm("000000") == 16

def test_hex_to_xterm_invalid_color():
    assert utils.hex_to_xterm("#zzz") == 255
    assert utils.hex_to_xterm("12") == 255

def test_safe_run_success():
    result = utils.safe_run(["echo", "hello"])
    assert result.returncode == 0
    assert "hello" in result.stdout

def test_safe_run_command_not_found():
    result = utils.safe_run(["non_existing_command"])
    assert result.returncode != 0
    assert "not found" in result.stderr.lower() or "No such file" in result.stderr or "unexpected error" in result.stderr.lower()
