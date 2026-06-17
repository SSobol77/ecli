# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/core/test_color_mapping.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for hex -> xterm-256 colour mapping (grayscale-aware nearest)."""

from __future__ import annotations

import pytest

from ecli.utils.utils import WHITE_FG_IDX, hex_to_xterm


GRAY_RAMP = {16, 231} | set(range(232, 256))


@pytest.mark.parametrize(
    "hex_color",
    ["#161B22", "#0D1117", "#1A1A1A", "#282828", "#131721", "#30363D"],
)
def test_dark_near_neutral_maps_to_grey_not_saturated_cube(hex_color: str) -> None:
    # The previous cube-only mapping snapped these to dark-cyan (index 23);
    # they must now land on the grayscale ramp / black.
    assert hex_to_xterm(hex_color) in GRAY_RAMP


def test_pure_greys_stay_on_ramp() -> None:
    for value in (0x10, 0x40, 0x80, 0xC0, 0xF0):
        h = f"#{value:02X}{value:02X}{value:02X}"
        assert hex_to_xterm(h) in GRAY_RAMP


def test_vivid_primaries_map_to_cube_cells() -> None:
    assert hex_to_xterm("#FF0000") == 196  # red
    assert hex_to_xterm("#00FF00") == 46  # green
    assert hex_to_xterm("#0000FF") == 21  # blue
    assert hex_to_xterm("#FFFFFF") in (231, 255)
    assert hex_to_xterm("#000000") in (16, 232)


def test_malformed_input_falls_back() -> None:
    assert hex_to_xterm("#xyz") == WHITE_FG_IDX
    assert hex_to_xterm("#12345") == WHITE_FG_IDX
    assert hex_to_xterm("") == WHITE_FG_IDX
