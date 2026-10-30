"""Responsive login window for the IDS/IPS workspace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.config import WINDOW_TITLE
from app.ui.icons import icon
from app.ui.register_window import AuthTitleBar, AuthWindowMixin, NetworkBackground


ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "images"


class LoginBrandPanel(QWidget):
    """Illustrated product introduction shown beside the login form."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("loginBrandPanel")
        self.setMinimumWidth(480)
        self.hero = QPixmap(str(ASSET_DIR / "security_login_hero.png"))
        self.earth = QPixmap(str(ASSET_DIR / "digital_earth.png"))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.earth.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        diameter = self.width() * 1.30
        globe = QRectF(
            (self.width() - diameter) / 2,
            self.height() - diameter * 0.30,
            diameter,
            diameter,
        )
        painter.setOpacity(0.18)
        painter.drawPixmap(globe.toRect(), self.earth)


class LoginWindow(AuthWindowMixin, QMainWindow):
    authenticated = Signal(str)
    register_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Đăng nhập | " + WINDOW_TITLE)
        self.resize(1536, 960)
        self.setMinimumSize(1040, 720)

        root = NetworkBackground()
        root.setObjectName("loginRoot")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.titlebar = AuthTitleBar()
        self.titlebar.minimize_requested.connect(self.minimize_window)
        self.titlebar.maximize_requested.connect(self.toggle_maximize)
        self.titlebar.close_requested.connect(self.close)
        shell.addWidget(self.titlebar)

        stage = QWidget()
        self.stage_layout = QHBoxLayout(stage)
        self.stage_layout.setContentsMargins(54, 32, 54, 38)
        self.stage_layout.setSpacing(54)
        self.stage_layout.addStretch(1)
        self.stage_layout.addWidget(self._brand_panel(), 11)
        self.stage_layout.addWidget(self._login_panel(), 8)
        self.stage_layout.addStretch(1)
        shell.addWidget(stage, 1)

        self._resize_handles = self._create_resize_handles()
        self._position_resize_handles()

    def _brand_panel(self) -> LoginBrandPanel:
        panel = LoginBrandPanel()
        layout = QVBoxLayout(panel)
        panel.layout_box = layout
        layout.setContentsMargins(34, 14, 20, 12)
        layout.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(18)
        logo = QLabel()
        logo.setPixmap(icon("logo", "#169DFF", 82).pixmap(82, 82))
        logo.setFixedSize(86, 86)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel("AI Network IDS/IPS")
        title.setObjectName("loginProductTitle")
        subtitle = QLabel("Giám sát - Phát hiện - Dự đoán - Giảm thiểu rủi ro")
        subtitle.setObjectName("loginProductSubtitle")
        subtitle.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        brand_row.addLayout(copy, 1)
        layout.addLayout(brand_row)

        hero = QLabel()
        panel.hero_label = hero
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hero.setMinimumHeight(250)
        layout.addWidget(hero, 4)

        features = QHBoxLayout()
        features.setSpacing(18)
        for icon_name, text in [
            ("eye", "Giám sát\nlưu lượng"),
            ("brain", "Phát hiện\nbất thường"),
            ("trend", "Dự đoán\nrủi ro"),
            ("shield", "Giảm thiểu\nrủi ro"),
        ]:
            column = QVBoxLayout()
            badge = QLabel()
            badge.setObjectName("loginFeatureIcon")
            badge.setPixmap(icon(icon_name, "#89B9FF", 29).pixmap(29, 29))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(64, 64)
            column.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
            label = QLabel(text)
            label.setObjectName("loginFeatureText")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(label)
            features.addLayout(column, 1)
        layout.addLayout(features)
        layout.addSpacing(16)

        quote = QLabel("“ Bảo vệ mạng lưới của bạn\nbằng sức mạnh của AI ”")
        quote.setObjectName("loginQuote")
        layout.addWidget(quote)
        layout.addStretch(1)
        return panel

    def _login_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("loginCard")
        panel.setMinimumWidth(410)
        panel.setMaximumWidth(540)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(55, 48, 55, 42)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(20)
        logo = QLabel()
        logo.setPixmap(icon("logo", "#159BFF", 70).pixmap(70, 70))
        logo.setFixedSize(74, 74)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_row.addWidget(logo)
        heading_copy = QVBoxLayout()
        heading = QLabel("Đăng nhập")
        heading.setObjectName("loginHeading")
        subheading = QLabel("Chào mừng trở lại! Vui lòng đăng nhập để tiếp tục.")
        subheading.setObjectName("loginSubheading")
        subheading.setWordWrap(True)
        heading_copy.addWidget(heading)
        heading_copy.addWidget(subheading)
        heading_row.addLayout(heading_copy, 1)
        layout.addLayout(heading_row)
        layout.addSpacing(20)

        layout.addWidget(self._field_label("Tài khoản", "user"))
        self.account = QLineEdit()
        self.account.setObjectName("loginInput")
        self.account.setPlaceholderText("Nhập username hoặc email")
        self.account.setMinimumHeight(52)
        layout.addWidget(self.account)
        layout.addSpacing(12)

        layout.addWidget(self._field_label("Mật khẩu", "lock"))
        self.password = QLineEdit()
        self.password.setObjectName("loginInput")
        self.password.setPlaceholderText("Nhập mật khẩu")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        action = self.password.addAction(icon("eye_off", "#8EAED2"), QLineEdit.ActionPosition.TrailingPosition)
        action.triggered.connect(lambda: self._toggle_password(action))
        self.password.returnPressed.connect(self.submit)
        layout.addWidget(self.password)

        options = QHBoxLayout()
        self.remember = QCheckBox("Ghi nhớ đăng nhập")
        self.remember.setObjectName("loginRemember")
        self.remember.setChecked(True)
        options.addWidget(self.remember)
        options.addStretch()
        forgot = QPushButton("Quên mật khẩu?")
        forgot.setObjectName("loginForgot")
        forgot.clicked.connect(self.show_forgot_message)
        options.addWidget(forgot)
        layout.addLayout(options)

        self.status = QLabel("")
        self.status.setObjectName("loginStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        submit = QPushButton("  Đăng nhập")
        submit.setObjectName("loginSubmit")
        submit.setIcon(icon("logout", "#FFFFFF"))
        submit.setIconSize(QSize(20, 20))
        submit.clicked.connect(self.submit)
        layout.addWidget(submit)

        divider = QHBoxLayout()
        for position in (0, 2):
            line = QFrame()
            line.setObjectName("loginDivider")
            line.setFixedHeight(1)
            divider.insertWidget(position, line, 1)
        or_label = QLabel("Hoặc")
        or_label.setObjectName("loginOr")
        divider.insertWidget(1, or_label)
        layout.addLayout(divider)

        register = QPushButton("  Đăng ký tài khoản")
        register.setObjectName("loginRegister")
        register.setIcon(icon("user_add", "#A8C8EF"))
        register.clicked.connect(self.register_requested)
        layout.addWidget(register)
        layout.addStretch(1)

        footer = QLabel("🛡  Hệ thống giám sát và phát hiện bất thường lưu lượng mạng tích hợp AI")
        footer.setObjectName("loginFooter")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)
        return panel

    @staticmethod
    def _field_label(text: str, icon_name: str) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(11)
        badge = QLabel()
        badge.setPixmap(icon(icon_name, "#85B7FF", 22).pixmap(22, 22))
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(badge)
        label = QLabel(text)
        label.setObjectName("loginFieldLabel")
        row.addWidget(label)
        row.addStretch()
        return widget

    def _toggle_password(self, action) -> None:
        visible = self.password.echoMode() == QLineEdit.EchoMode.Normal
        self.password.setEchoMode(QLineEdit.EchoMode.Password if visible else QLineEdit.EchoMode.Normal)
        action.setIcon(icon("eye" if not visible else "eye_off", "#8EAED2"))

    def show_forgot_message(self) -> None:
        self.status.setText("Vui lòng liên hệ quản trị viên để đặt lại mật khẩu.")
        self.status.setProperty("valid", True)
        self._refresh_status()

    def submit(self) -> None:
        account = self.account.text().strip()
        if not account:
            self.status.setText("Vui lòng nhập tài khoản hoặc email.")
            self.status.setProperty("valid", False)
        elif not self.password.text():
            self.status.setText("Vui lòng nhập mật khẩu.")
            self.status.setProperty("valid", False)
        else:
            self.status.setText("Đăng nhập thành công. Đang mở hệ thống...")
            self.status.setProperty("valid", True)
            self._refresh_status()
            self.authenticated.emit(account)
            return
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def resizeEvent(self, event) -> None:
        width, height = self.width(), self.height()
        side = max(20, min(54, (width - 1000) // 2))
        self.stage_layout.setContentsMargins(side, 18 if height < 820 else 32, side, 20 if height < 820 else 38)
        self.stage_layout.setSpacing(max(24, min(54, (width - 1000) // 5)))
        super().resizeEvent(event)
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()

        panel = self.findChild(LoginBrandPanel)
        if panel and not panel.hero.isNull():
            target = panel.hero_label.size()
            panel.hero_label.setPixmap(
                panel.hero.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
