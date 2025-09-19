
# tests/test_get_file_icon.py
from ecli.utils.utils import get_file_icon


sample_config = {
    "file_icons": {
        "default": "❓",
        "text":    "📝",
        "python":  "🐍",
        "docs":    "📘",        # ← новая группа с синей книжкой
    },
    "supported_formats": {
        "python": ["py", "pyw"],
        "text":   ["txt", "log"],
        # точные имена (без точки) + расширения, которым хотим дать 📘
        "docs":   ["readme", "md", "rst", "guide", "manual"],
    }
}

def test_icon_for_exact_filename():
    assert get_file_icon("readme", sample_config) == "📘"
    assert get_file_icon("README.md", sample_config) == "📘"
