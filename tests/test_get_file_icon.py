# tests/test_get_file_icon.py
"""Unit tests for the `get_file_icon` utility function.

This module verifies that the correct icon is returned based on
file names and extensions using a configurable mapping.
"""

from ecli.utils.utils import get_file_icon


# Sample configuration used across tests
sample_config = {
    "file_icons": {
        "default": "❓",  # Fallback icon for unsupported files
        "text": "📝",  # Icon for plain text files
        "python": "🐍",  # Icon for Python files
        "docs": "📘",  # New group: documentation files (blue book)
    },
    "supported_formats": {
        "python": ["py", "pyw"],
        "text": ["txt", "log"],
        # Exact names (case-insensitive, without extension) +
        # extensions to be associated with the documentation icon 📘
        "docs": ["readme", "md", "rst", "guide", "manual"],
    },
}


def test_icon_for_exact_filename() -> None:
    """Ensure that exact file names and extensions map to the docs icon.

    This test checks both:
    - A bare filename without extension (`readme`).
    - A common documentation file with extension (`README.md`).

    The expected icon for both is the 📘 documentation icon.
    """
    assert get_file_icon("readme", sample_config) == "📘"
    assert get_file_icon("README.md", sample_config) == "📘"
