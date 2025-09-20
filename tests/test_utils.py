# tests/test_utils.py
"""Unit tests for utility functions in the `ecli.utils` module.

Project: ecli
This file is part of the ecli project.
It is subject to the license terms in the LICENSE file found in the top-level directory of this distribution.
The full list of project contributors is contained in the AUTHORS file found in the same directory.
"""

from ecli.utils import utils


def test_deep_merge() -> None:
    """Verify that `deep_merge` correctly merges nested dictionaries.

    This test ensures:
    - Existing values are preserved if not overridden.
    - Nested dictionaries are merged recursively.
    - Conflicting keys are overridden by values from the second dictionary.
    """
    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"b": {"y": 99, "z": 100}, "c": 3}
    result = utils.deep_merge(base, override)
    expected = {"a": 1, "b": {"x": 10, "y": 99, "z": 100}, "c": 3}
    assert result == expected


def test_hex_to_xterm_valid_color() -> None:
    """Ensure `hex_to_xterm` returns the correct xterm color code for valid hex values.

    Examples tested:
    - White (`#ffffff`) should map to 231.
    - Black (`000000`) should map to 16.
    """
    assert utils.hex_to_xterm("#ffffff") == 231
    assert utils.hex_to_xterm("000000") == 16


def test_hex_to_xterm_invalid_color() -> None:
    """Verify that `hex_to_xterm` falls back to 255 for invalid hex strings.

    Examples tested:
    - `#zzz` (invalid characters).
    - `12` (too short).
    """
    assert utils.hex_to_xterm("#zzz") == 255
    assert utils.hex_to_xterm("12") == 255


def test_safe_run_success() -> None:
    """Check that `safe_run` executes a valid shell command successfully.

    Expected behavior:
    - Return code is 0 (success).
    - Standard output contains the expected string.
    """
    result = utils.safe_run(["echo", "hello"])
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_safe_run_command_not_found() -> None:
    """Ensure `safe_run` gracefully handles non-existent commands.

    Expected behavior:
    - Return code is non-zero (failure).
    - Standard error contains an appropriate error message such as:
      * "not found"
      * "No such file"
      * "unexpected error"
    """
    result = utils.safe_run(["non_existing_command"])
    assert result.returncode != 0
    assert (
        "not found" in result.stderr.lower()
        or "No such file" in result.stderr
        or "unexpected error" in result.stderr.lower()
    )


# def test_safe_run_timeout() -> None:
#     """Verify that `safe_run` handles command timeouts correctly.

#     Expected behavior:
#     - Return code is -1 (indicating a timeout).
#     - Standard error contains the message "Command timed out".
#     """
#     result = utils.safe_run(["sleep", "5"], timeout=1)
#     assert result.returncode == -1
#     assert "Command timed out" in result.stderr
