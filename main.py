"""Entry point for the AI Network IDS/IPS desktop demo."""

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import APP_NAME
from app.core.theme import load_stylesheet
from app.services.auth_service import ensure_default_admin
from app.services.database import init_db
from app.ui.auth_window import AuthWindow
from app.ui.icons import icon
from app.ui.main_window import MainWindow

def main() -> int:
    # Attempt to initialize PostgreSQL tables and default administrator
    db_ok, db_msg = init_db()
    if db_ok:
        print(f"[Database] {db_msg}")
        admin_ok, admin_msg = ensure_default_admin()
        print(f"[Auth] {admin_msg}")
    else:
        print(f"[Database] {db_msg}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(icon("logo", "#8B5CF6", 64))
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())

    auth = AuthWindow()
    windows = {"auth": auth, "login": auth, "main": None}

    def open_workspace(display_name: str = "admin", role: str = "Quản trị viên") -> None:
        window = MainWindow()
        window.sidebar.set_user_info(display_name, role)
        windows["main"] = window

        def handle_logout() -> None:
            auth.reset_state()
            window.close()
            windows["main"] = None
            auth.show()
            auth.raise_()
            auth.activateWindow()

        window.logout_requested.connect(handle_logout)
        window.show()
        auth.hide()

    auth.authenticated.connect(open_workspace)
    auth.registration_completed.connect(open_workspace)
    auth.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
