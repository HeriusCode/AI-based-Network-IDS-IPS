"""Entry point for the AI Network IDS/IPS desktop demo."""

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import APP_NAME
from app.core.theme import load_stylesheet
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
