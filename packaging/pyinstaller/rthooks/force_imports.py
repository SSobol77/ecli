# packaging/pyinstaller/rthooks/force_imports.py
"""Runtime hook to force-import critical dependencies without crashing.

- Mandatory imports: must exist in the bundled app (build guarantees that).
- Optional imports: attempted, but ignored if missing.
"""

import sys
import os
from importlib import import_module

# Hard requirements for startup (imported at top-level by your code)
MANDATORY = [
    # core config/deps
    "dotenv",
    "toml",
    # aiohttp stack
    "aiohttp",
    "aiosignal",
    "yarl",
    "multidict",
    "frozenlist",
    # extra mandatory discovered from logs
    "chardet",
]

# Best-effort extras (do not crash if absent)
OPTIONAL = [
    "aiohappyeyeballs",
    "attrs",
    "idna",
    "charset_normalizer",
]

for name in MANDATORY:
    import_module(name)

for name in OPTIONAL:
    try:
        import_module(name)
    except Exception:
        pass


# Curses setup for FreeBSD
try:
    import curses
    # Ensure terminfo is found
    if hasattr(curses, 'setupterm'):
        try:
            curses.setupterm()
        except:
            pass
except ImportError:
    pass

# Locale setup
try:
    import locale
    locale.setlocale(locale.LC_ALL, '')
except:
    pass
