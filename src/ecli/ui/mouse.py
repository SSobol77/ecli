# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/ui/mouse.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Mouse model and hit-testing for the ECLI split-layout UI.

This is the *architecture* layer for mouse support: a terminal-agnostic model
(``MouseEvent``, ``MouseButton``, ``MouseAction``, ``FocusRegion``,
``HitTarget``) plus pure functions (``hit_test``, ``decode_curses_mouse``) that
turn a screen coordinate / curses button-state into an addressable region and a
high-level action. It deliberately performs **no** editor mutation and triggers
**no** action — the live handler in ``Ecli`` applies only safe, non-destructive
intents (focus + scroll + selection) and remains opt-in.

Every drawn region is addressable via the existing ``ecli.ui.geometry`` rects:
editor, gutter, side panel, global header/status/footer, and centered modals.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from enum import Enum, IntEnum

from ecli.ui.geometry import LayoutGeometry, Rect


class MouseButton(IntEnum):
    """Logical mouse buttons (wheel is modelled as up/down 'buttons')."""

    NONE = 0
    LEFT = 1
    MIDDLE = 2
    RIGHT = 3
    WHEEL_UP = 4
    WHEEL_DOWN = 5


class MouseAction(Enum):
    """High-level mouse action, decoded from raw curses button state."""

    PRESS = "press"
    RELEASE = "release"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"
    WHEEL = "wheel"
    UNKNOWN = "unknown"


class FocusRegion(Enum):
    """Addressable UI regions a click can land in."""

    EDITOR = "editor"
    GUTTER = "gutter"
    PANEL = "panel"
    HEADER = "header"
    STATUS = "status"
    FOOTER = "footer"
    MODAL = "modal"
    OUTSIDE = "outside"


@dataclass(frozen=True)
class MouseEvent:
    """A decoded mouse event in absolute terminal coordinates."""

    x: int
    y: int
    button: MouseButton
    action: MouseAction

    @property
    def is_wheel(self) -> bool:
        """True for wheel-scroll events."""
        return self.action is MouseAction.WHEEL

    @property
    def wheel_delta(self) -> int:
        """+1 to scroll up, -1 to scroll down, 0 if not a wheel event."""
        if self.button is MouseButton.WHEEL_UP:
            return 1
        if self.button is MouseButton.WHEEL_DOWN:
            return -1
        return 0


@dataclass(frozen=True)
class HitTarget:
    """Result of hit-testing: which region, its rect, and local coordinates."""

    region: FocusRegion
    rect: Rect | None
    local_x: int
    local_y: int


def _bit(name: str) -> int:
    """Resolve a curses mouse-state constant, or 0 when unavailable."""
    return int(getattr(curses, name, 0) or 0)


def decode_curses_mouse(bstate: int) -> tuple[MouseButton, MouseAction]:
    """Decode a curses ``getmouse`` button-state bitmask defensively.

    Unknown / unsupported states (e.g. terminals without wheel reporting) map to
    ``(NONE, UNKNOWN)`` so callers never crash. Wheel is detected first because
    several terminals report it via BUTTON4/BUTTON5 press bits.
    """
    if bstate & _bit("BUTTON4_PRESSED"):
        return MouseButton.WHEEL_UP, MouseAction.WHEEL
    if bstate & _bit("BUTTON5_PRESSED"):
        return MouseButton.WHEEL_DOWN, MouseAction.WHEEL

    actions = (
        ("DOUBLE_CLICKED", MouseAction.DOUBLE_CLICK),
        ("CLICKED", MouseAction.CLICK),
        ("PRESSED", MouseAction.PRESS),
        ("RELEASED", MouseAction.RELEASE),
    )
    for button, prefix in (
        (MouseButton.LEFT, "BUTTON1"),
        (MouseButton.MIDDLE, "BUTTON2"),
        (MouseButton.RIGHT, "BUTTON3"),
    ):
        for suffix, mapped in actions:
            if bstate & _bit(f"{prefix}_{suffix}"):
                return button, mapped

    return MouseButton.NONE, MouseAction.UNKNOWN


def hit_test(
    geometry: LayoutGeometry,
    x: int,
    y: int,
    *,
    gutter_width: int = 0,
    modal_rect: Rect | None = None,
) -> HitTarget:
    """Map an absolute ``(x, y)`` to a UI region using the layout geometry.

    When ``modal_rect`` is given, a point inside it is ``MODAL`` and a point
    outside is ``OUTSIDE`` (so the caller can implement click-outside-to-close).
    Otherwise the global header/status/footer, the side panel (if any) and the
    editor (split into ``GUTTER`` / ``EDITOR``) are tested in z-order.
    """

    def target(region: FocusRegion, rect: Rect | None) -> HitTarget:
        if rect is None:
            return HitTarget(region, None, x, y)
        return HitTarget(region, rect, x - rect.x, y - rect.y)

    if modal_rect is not None:
        inside = modal_rect.contains(x, y)
        return target(
            *(
                (FocusRegion.MODAL, modal_rect)
                if inside
                else (FocusRegion.OUTSIDE, None)
            )
        )

    chrome = (
        (FocusRegion.HEADER, geometry.header),
        (FocusRegion.STATUS, geometry.status),
        (FocusRegion.FOOTER, geometry.footer),
        (FocusRegion.PANEL, geometry.panel),
    )
    for region, rect in chrome:
        if rect is not None and rect.height and rect.contains(x, y):
            return target(region, rect)

    if geometry.editor.contains(x, y):
        in_gutter = bool(gutter_width) and x < geometry.editor.x + gutter_width
        region = FocusRegion.GUTTER if in_gutter else FocusRegion.EDITOR
        return target(region, geometry.editor)
    return target(FocusRegion.OUTSIDE, None)
