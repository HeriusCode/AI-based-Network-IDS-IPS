"""Entry point for the AI Network IDS/IPS desktop demo."""

import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QApplication

from app.core.config import APP_NAME
from app.core.theme import load_stylesheet
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow
from app.ui.register_window import RegisterWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())
    login = LoginWindow()
    register = RegisterWindow()
    windows = {"login": login, "register": register, "main": None}
    animations: dict[str, QPropertyAnimation] = {}

    def switch_auth(source, target) -> None:
        running = animations.pop("auth", None)
        if running is not None:
            running.stop()
        login.setWindowOpacity(1.0)
        register.setWindowOpacity(1.0)
        target.setWindowOpacity(0.0)

        if source.isMaximized():
            target.setGeometry(source.normalGeometry())
            target.showMaximized()
        else:
            target.showNormal()
            target.setGeometry(source.geometry())

        target.raise_()
        target.activateWindow()

        animation = QPropertyAnimation(target, b"windowOpacity", app)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animations["auth"] = animation

        def finish_transition() -> None:
            source.hide()
            source.setWindowOpacity(1.0)
            target.setWindowOpacity(1.0)
            if animations.get("auth") is animation:
                animations.pop("auth", None)

        animation.finished.connect(finish_transition)
        animation.start()

    def open_register() -> None:
        switch_auth(login, register)

    def open_login() -> None:
        switch_auth(register, login)

    def open_workspace(display_name: str = "admin") -> None:
        window = MainWindow()
        window.sidebar.account_text.setText(f"{display_name}\n<span>Quản trị viên</span>")
        windows["main"] = window
        window.show()
        login.hide()
        register.hide()

    login.authenticated.connect(open_workspace)
    login.register_requested.connect(open_register)
    register.registration_completed.connect(open_workspace)
    register.back_requested.connect(open_login)
    login.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
