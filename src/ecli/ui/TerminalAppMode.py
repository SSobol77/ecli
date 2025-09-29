# src/ecli/ui/TerminalAppMode.py
from __future__ import annotations

import curses
import logging
from typing import Optional

try:
    from curses import tigetstr, setupterm, putp
except Exception:  # pragma: no cover
    tigetstr = None  # type: ignore[assignment]
    setupterm = None  # type: ignore[assignment]
    putp = None  # type: ignore[assignment]


class TerminalAppMode:
    """
    Put the terminal into an application-friendly state:

    - Alternate screen buffer (smcup/rmcup) so shell prompt is hidden.
    - Application cursor keys (smkx/rmkx) so arrows (and Shift/Ctrl/Alt variants)
      are delivered to the app, not handled by the terminal.
    - raw + noecho (+ cbreak fallback), keypad(True), optional meta(True).
    - Disable screen scrolling at curses level (scrollok(False)).

    Always pair `enter(stdscr)` with `exit()` (try/finally).
    """

    def __init__(self) -> None:
        self._entered: bool = False
        self._stdscr: Optional[curses.window] = None

    def enter(self, stdscr: curses.window) -> None:
        self._stdscr = stdscr

        # Ensure terminfo is initialized so tigetstr works where available.
        try:
            if setupterm:
                setupterm()
        except Exception as e:
            logging.debug("setupterm() failed or not required: %r", e)

        # Switch to alternate screen (smcup) BEFORE clearing.
        self._tputs("smcup")

        # Enable application cursor keys (smkx).
        self._tputs("smkx")

        # Input modes.
        try:
            curses.raw()  # deliver all control chars (including ^Z) to us
        except Exception:
            curses.cbreak()  # fallback if raw is unavailable
        curses.noecho()

        # Enable keypad/meta to decode function keys and send DECCKM.
        stdscr.keypad(True)
        try:
            curses.meta(stdscr, True)  # may not exist on some platforms
        except Exception:
            pass

        # Make ESC detection snappy while still allowing Alt chords.
        try:
            curses.set_escdelay(35)  # 25–50 ms is a good balance for TTYs
        except Exception:
            pass

        # Rendering hygiene.
        try:
            curses.use_default_colors()
        except Exception:
            pass

        stdscr.scrollok(False)
        stdscr.leaveok(False)
        stdscr.clearok(True)
        stdscr.erase()
        stdscr.refresh()

        self._entered = True
        logging.debug("TerminalAppMode: entered (alternate screen + app cursor keys).")

    def exit(self) -> None:
        if not self._entered:
            return

        try:
            if self._stdscr is not None:
                self._stdscr.keypad(False)
        except Exception:
            pass

        # Restore cooked modes.
        try:
            curses.noraw()
        except Exception:
            try:
                curses.nocbreak()
            except Exception:
                pass
        try:
            curses.echo()
        except Exception:
            pass

        # Disable application cursor keys (rmkx) and leave alternate screen (rmcup).
        self._tputs("rmkx")
        self._tputs("rmcup")

        self._entered = False
        logging.debug("TerminalAppMode: exited (restored terminal modes).")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _tputs(self, capname: str) -> None:
        try:
            if tigetstr and putp:
                s = tigetstr(capname)
                if s:
                    putp(s.decode("ascii", "ignore"))
        except Exception as e:
            # Non-fatal where capability is missing (FreeBSD console, etc.).
            logging.debug("tputs(%s) skipped: %r", capname, e)
