"""Traffic Generator desktop application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def fit_and_center_window(window: MainWindow, available: QRect) -> None:
    """Keep the complete frameless window inside the usable screen at any DPI."""
    margin = 12
    maximum_width = max(640, available.width() - margin * 2)
    maximum_height = max(480, available.height() - margin * 2)

    if window.minimumWidth() > maximum_width or window.minimumHeight() > maximum_height:
        window.setMinimumSize(
            min(window.minimumWidth(), maximum_width),
            min(window.minimumHeight(), maximum_height),
        )

    width = min(window.width(), maximum_width)
    height = min(window.height(), maximum_height)
    window.resize(width, height)

    x = available.x() + max(margin, (available.width() - width) // 2)
    y = available.y() + max(margin, (available.height() - height) // 2)
    x = min(x, available.right() - width - margin + 1)
    y = min(y, available.bottom() - height - margin + 1)
    window.move(max(available.x(), x), max(available.y(), y))


def main() -> int:
    project_root = Path(__file__).resolve().parent
    app = QApplication(sys.argv)
    app.setApplicationName("Traffic Generator")
    app.setOrganizationName("AI Network Lab")
    style_path = project_root / "app" / "resources" / "styles" / "dark_theme.qss"
    app.setStyleSheet(style_path.read_text(encoding="utf-8"))
    window = MainWindow(project_root)
    screen = app.primaryScreen()
    if screen is not None:
        fit_and_center_window(window, screen.availableGeometry())
    window.show()
    if screen is not None:
        QTimer.singleShot(0, lambda: fit_and_center_window(window, screen.availableGeometry()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
