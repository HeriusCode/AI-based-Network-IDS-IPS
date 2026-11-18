"""Load the QSS bundled with the application."""

from pathlib import Path


def load_stylesheet() -> str:
    path = Path(__file__).resolve().parents[1] / "assets" / "styles" / "dark.qss"
    return path.read_text(encoding="utf-8")
