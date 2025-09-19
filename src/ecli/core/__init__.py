# src/ecli/core/__init__.py  (или ecli/core/__init__.py, если не переходишь на src-layout)
"""Public facade for ecli.core: re-export main classes from CamelCase modules.

Keeps Java-like file names (AsyncEngine.py, History.py, ...),
but provides flat imports for convenience and stability.
"""

# Re-export classes/symbols from CamelCase modules
from .AsyncEngine import AsyncEngine  # noqa: F401
from .CodeCommenter import CodeCommenter  # noqa: F401
from .Ecli import Ecli  # noqa: F401
from .History import History  # noqa: F401


__all__ = [
    "AsyncEngine",
    "History",
    "Ecli",
    "CodeCommenter",
]
