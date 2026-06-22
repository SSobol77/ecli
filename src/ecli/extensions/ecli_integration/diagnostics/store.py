# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/ecli_integration/diagnostics/store.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Bounded, revision-aware cache for diagnostics results (#104).

The store keeps the most recent :class:`~.model.DiagnosticsState` per cache key
(provider + file) together with a *revision* token. A lookup only returns a
cached state when the supplied revision still matches, so stale results are
never served after the buffer or file changes. Capacity is bounded with simple
LRU eviction so long editing sessions cannot grow the cache without limit.

This module is pure data structure code: no curses, no external process, no
threads.
"""

from __future__ import annotations

from collections import OrderedDict

from .model import DiagnosticsState


__all__ = ["DiagnosticsStore"]

DEFAULT_MAX_ENTRIES = 64


class DiagnosticsStore:
    """A small, bounded LRU cache of ``(revision, state)`` keyed by a string."""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        """Create a store holding at most *max_entries* results (minimum 1)."""
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[str, tuple[str, DiagnosticsState]] = OrderedDict()

    def __len__(self) -> int:
        """Return the number of cached entries."""
        return len(self._entries)

    @property
    def max_entries(self) -> int:
        """Return the configured maximum number of entries."""
        return self._max_entries

    def get(self, key: str, revision: str) -> DiagnosticsState | None:
        """Return the cached state for *key* iff its revision matches.

        A revision mismatch (file/buffer changed) is treated as a miss and the
        stale entry is dropped.
        """
        entry = self._entries.get(key)
        if entry is None:
            return None
        cached_revision, state = entry
        if cached_revision != revision:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return state

    def put(self, key: str, revision: str, state: DiagnosticsState) -> None:
        """Insert or refresh the cached state for *key*, evicting LRU as needed."""
        self._entries[key] = (revision, state)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """Drop the cached entry for *key* if present."""
        self._entries.pop(key, None)

    def clear(self) -> None:
        """Remove every cached entry."""
        self._entries.clear()
