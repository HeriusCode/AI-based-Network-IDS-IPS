"""Unified responsive authentication window (Login & Register) for the IDS/IPS workspace.

Hosts both Login and Register stages inside a single top-level frameless window using
a QStackedWidget. This completely eliminates native window flickering and avoids
Windows DWM window-state corruption/resets (such as losing maximized state or shrinking)
when navigating between Login and Register.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    QRect,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import WINDOW_TITLE
from app.services.auth_service import authenticate_user, register_user
from app.ui.icons import icon

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "images"


class RememberCheckBox(QCheckBox):
    """Styled checkbox that draws a purple tick without a filled background."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#8B5CF6"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(
            indicator.left() + 4,
            indicator.center().y(),
            indicator.center().x() - 1,
            indicator.bottom() - 4,
        )
        painter.drawLine(
            indicator.center().x() - 1,
            indicator.bottom() - 4,
            indicator.right() - 3,
            indicator.top() + 4,
        )


class ResponsivePixmapLabel(QLabel):
    """Keep a source pixmap fitted to the label from the very first layout pass."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_pixmap = pixmap
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _fit_pixmap(self) -> None:
        if self._source_pixmap.isNull() or self.width() <= 1 or self.height() <= 1:
            return
        self.setPixmap(
            self._source_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_pixmap()
        QTimer.singleShot(0, self._fit_pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_pixmap()


class LoginBrandPanel(QWidget):
    """Illustrated product introduction shown beside the login form."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("loginBrandPanel")
        self.setMinimumWidth(480)
        self.hero = QPixmap(str(ASSET_DIR / "security_login_hero.png"))
        self.earth = QPixmap(str(ASSET_DIR / "digital_earth.png"))
        self._angle = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._rotate_earth)
        self._timer.start()

    def _rotate_earth(self) -> None:
        if not self.isVisible():
            return
        self._angle = (self._angle + 0.22) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.earth.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        diameter = self.width() * 1.30
        center_x = self.width() / 2.0
        center_y = self.height() - diameter * 0.30 + diameter / 2.0

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self._angle)
        painter.setOpacity(0.24)
        target = QRectF(-diameter / 2.0, -diameter / 2.0, diameter, diameter)
        painter.drawPixmap(target.toRect(), self.earth)
        painter.restore()


class NetworkBackground(QWidget):
    """Subtle deterministic network illustration used by the auth screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        generator = random.Random(19)
        self.nodes = [(generator.random(), generator.random(), generator.uniform(1.2, 3.5)) for _ in range(58)]
        self.links = [(index, (index + generator.randint(1, 7)) % len(self.nodes)) for index in range(len(self.nodes))]

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#061424"))
        gradient.setColorAt(0.55, QColor("#030F1E"))
        gradient.setColorAt(1, QColor("#06192B"))
        painter.fillRect(self.rect(), gradient)
        points = [QPointF(x * self.width(), y * self.height()) for x, y, _ in self.nodes]
        painter.setPen(QPen(QColor(20, 114, 194, 35), 1))
        for first, second in self.links:
            painter.drawLine(points[first], points[second])
        painter.setPen(Qt.PenStyle.NoPen)
        for point, (_, _, radius) in zip(points, self.nodes):
            painter.setBrush(QColor(15, 129, 236, 85))
            painter.drawEllipse(point, radius, radius)


class RegisterBrandPanel(QWidget):
    """Registration brand area matching the login screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("registerBrandPanel")
        self.setMinimumWidth(480)
        self.earth = QPixmap(str(ASSET_DIR / "digital_earth.png"))
        self._angle = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._rotate_earth)
        self._timer.start()

    def _rotate_earth(self) -> None:
        if not self.isVisible():
            return
        self._angle = (self._angle + 0.22) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.earth.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        diameter = self.width() * 1.30
        center_x = self.width() / 2.0
        center_y = self.height() - diameter * 0.30 + diameter / 2.0

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self._angle)
        painter.setOpacity(0.24)
        target = QRectF(-diameter / 2.0, -diameter / 2.0, diameter, diameter)
        painter.drawPixmap(target.toRect(), self.earth)
        painter.restore()
        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(575, 780)


class RegistrationHeroWidget(QWidget):
    """Generated blue Wi-Fi illustration used only by registration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("registerIdentityHero")
        self.setMinimumHeight(245)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image = QPixmap(str(ASSET_DIR / "register_wifi_hero.png"))

    def paintEvent(self, event) -> None:
        del event
        if self.image.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        fitted = self.image.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - fitted.width()) // 2
        y = (self.height() - fitted.height()) // 2
        painter.drawPixmap(x, y, fitted)


class AuthTitleBar(QFrame):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("authTitleBar")
        self.setFixedHeight(58)
        row = QHBoxLayout(self)
        row.setContentsMargins(26, 0, 12, 0)
        row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icon("logo", "#8B5CF6", 37).pixmap(37, 37))
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(logo)
        name = QLabel("CYBERA")
        name.setObjectName("authBrandName")
        row.addWidget(name)
        row.addStretch()
        for icon_name, tooltip, signal, object_name in [
            ("minimize", "Thu nhỏ", self.minimize_requested, "authWindowButton"),
            ("maximize", "Phóng to", self.maximize_requested, "authWindowButton"),
            ("close", "Đóng", self.close_requested, "authCloseButton"),
        ]:
            button = QPushButton()
            button.setObjectName(object_name)
            button.setIcon(icon(icon_name, "#8E8BA7", 15))
            button.setIconSize(QSize(15, 15))
            button.setToolTip(tooltip)
            button.clicked.connect(signal)
            row.addWidget(button)
            if icon_name == "maximize":
                self.maximize_button = button

    def set_maximized(self, maximized: bool) -> None:
        self.maximize_button.setIcon(icon("restore" if maximized else "maximize", "#8E8BA7", 15))
        self.maximize_button.setToolTip("Khôi phục" if maximized else "Phóng to")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
            event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)


class AuthResizeHandle(QWidget):
    """Transparent resize target for a frameless authentication window."""

    def __init__(self, edge: Qt.Edge, cursor: Qt.CursorShape, parent: QWidget) -> None:
        super().__init__(parent)
        self.edge = edge
        self.setCursor(QCursor(cursor))
        self.setObjectName("authResizeHandle")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemResize(self.edge):
                event.accept()
                return
        super().mousePressEvent(event)


class AuthWindowMixin:
    GRIP = 8
    CORNER = 16

    def _create_resize_handles(self) -> dict[str, AuthResizeHandle]:
        return {
            "top": AuthResizeHandle(Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor, self),
            "bottom": AuthResizeHandle(Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor, self),
            "left": AuthResizeHandle(Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor, self),
            "right": AuthResizeHandle(Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor, self),
            "top_left": AuthResizeHandle(Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeFDiagCursor, self),
            "top_right": AuthResizeHandle(Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeBDiagCursor, self),
            "bottom_left": AuthResizeHandle(Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeBDiagCursor, self),
            "bottom_right": AuthResizeHandle(Qt.Edge.BottomEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeFDiagCursor, self),
        }

    def _position_resize_handles(self) -> None:
        width, height = self.width(), self.height()
        grip, corner = self.GRIP, self.CORNER
        positions = {
            "top": QRect(corner, 0, max(0, width - corner * 2), grip),
            "bottom": QRect(corner, height - grip, max(0, width - corner * 2), grip),
            "left": QRect(0, corner, grip, max(0, height - corner * 2)),
            "right": QRect(width - grip, corner, grip, max(0, height - corner * 2)),
            "top_left": QRect(0, 0, corner, corner),
            "top_right": QRect(width - corner, 0, corner, corner),
            "bottom_left": QRect(0, height - corner, corner, corner),
            "bottom_right": QRect(width - corner, height - corner, corner, corner),
        }
        visible = not self.isMaximized() and not self.isFullScreen()
        for name, handle in self._resize_handles.items():
            handle.setGeometry(positions[name])
            handle.setVisible(visible)
            if visible:
                handle.raise_()

    def minimize_window(self) -> None:
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMinimized)

    def toggle_maximize(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()
        self.titlebar.set_maximized(self.isMaximized())
        self._position_resize_handles()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_resize_handles"):
            self.titlebar.set_maximized(self.isMaximized())
            self._position_resize_handles()


class _LoginTaskSignals(QObject):
    finished = Signal(bool, str, object)


class _LoginTask(QRunnable):
    """Run the database round-trip and password hashing away from the UI thread."""

    def __init__(self, account: str, password: str) -> None:
        super().__init__()
        self.account = account
        self.password = password
        self.signals = _LoginTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = authenticate_user(self.account, self.password)
        except Exception as error:
            result = False, f"Không thể đăng nhập: {error}", None
        self.signals.finished.emit(*result)


class LoginStage(QWidget):
    authenticated = Signal(str, str)
    register_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auth_in_progress = False
        self._login_task: _LoginTask | None = None
        self.setObjectName("loginStage")
        self.stage_layout = QHBoxLayout(self)
        self.stage_layout.setContentsMargins(54, 32, 54, 38)
        self.stage_layout.setSpacing(54)
        self.stage_layout.addStretch(1)
        self.stage_layout.addWidget(self._brand_panel(), 11)
        self.stage_layout.addWidget(self._login_panel(), 8)
        self.stage_layout.addStretch(1)

    def update_layout(self, width: int, height: int) -> None:
        side = max(20, min(54, (width - 1000) // 2))
        self.stage_layout.setContentsMargins(side, 18 if height < 820 else 32, side, 20 if height < 820 else 38)
        self.stage_layout.setSpacing(max(24, min(54, (width - 1000) // 5)))

    def _brand_panel(self) -> LoginBrandPanel:
        panel = LoginBrandPanel()
        layout = QVBoxLayout(panel)
        panel.layout_box = layout
        layout.setContentsMargins(34, 14, 20, 12)
        layout.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(18)
        logo = QLabel()
        logo.setPixmap(icon("logo", "#8B5CF6", 82).pixmap(82, 82))
        logo.setFixedSize(86, 86)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)
        copy_widget = QWidget()
        copy = QVBoxLayout(copy_widget)
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(3)
        copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title = QLabel("CYBERA")
        title.setObjectName("loginProductTitle")
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        subtitle = QLabel("Cybersecurity AI System  •  Hệ thống AI giám sát và phòng vệ an ninh mạng")
        subtitle.setObjectName("loginProductSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        brand_row.addWidget(copy_widget, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(brand_row)

        hero = ResponsivePixmapLabel(panel.hero)
        panel.hero_label = hero
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
            badge.setPixmap(icon(icon_name, "#A78BFA", 29).pixmap(29, 29))
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
        logo.setPixmap(icon("logo", "#8B5CF6", 70).pixmap(70, 70))
        logo.setFixedSize(74, 74)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_row.addWidget(logo)
        heading_copy_widget = QWidget()
        heading_copy = QVBoxLayout(heading_copy_widget)
        heading_copy.setContentsMargins(0, 0, 0, 0)
        heading_copy.setSpacing(2)
        heading_copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        heading = QLabel("Đăng nhập")
        heading.setObjectName("loginHeading")
        heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        subheading = QLabel("Chào mừng trở lại! Vui lòng đăng nhập để tiếp tục.")
        subheading.setObjectName("loginSubheading")
        subheading.setWordWrap(True)
        subheading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        heading_copy.addWidget(heading, 0, Qt.AlignmentFlag.AlignBottom)
        heading_copy.addWidget(subheading, 0, Qt.AlignmentFlag.AlignTop)
        heading_row.addWidget(heading_copy_widget, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(heading_row)
        layout.addSpacing(14)

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
        self.remember = RememberCheckBox("Ghi nhớ đăng nhập")
        self.remember.setObjectName("loginRemember")
        self.remember.setChecked(True)
        options.addWidget(self.remember)
        options.addStretch()
        forgot = QPushButton("Quên mật khẩu?")
        forgot.setObjectName("loginForgot")
        forgot.clicked.connect(self.show_forgot_message)
        self.forgot_button = forgot
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
        self.submit_button = submit
        self._submit_text = submit.text()
        layout.addWidget(submit)

        divider = QHBoxLayout()
        left_line = QFrame()
        left_line.setObjectName("loginDivider")
        left_line.setFixedHeight(1)
        divider.addWidget(left_line, 1)
        or_label = QLabel("Hoặc")
        or_label.setObjectName("loginOr")
        divider.addWidget(or_label)
        right_line = QFrame()
        right_line.setObjectName("loginDivider")
        right_line.setFixedHeight(1)
        divider.addWidget(right_line, 1)
        layout.addLayout(divider)

        register = QPushButton("  Đăng ký tài khoản")
        register.setObjectName("loginRegister")
        register.setIcon(icon("user_add", "#A8C8EF"))
        register.clicked.connect(self.register_requested.emit)
        self.register_button = register
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
        badge.setPixmap(icon(icon_name, "#A78BFA", 22).pixmap(22, 22))
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
        if self._auth_in_progress:
            return

        account = self.account.text().strip()
        password = self.password.text()
        if not account:
            self.status.setText("Vui lòng nhập tài khoản hoặc email.")
            self.status.setProperty("valid", False)
            self._refresh_status()
            return
        if not password:
            self.status.setText("Vui lòng nhập mật khẩu.")
            self.status.setProperty("valid", False)
            self._refresh_status()
            return

        self._set_auth_busy(True)
        self.status.setText("Đang xác thực tài khoản...")
        self.status.setProperty("valid", True)
        self._refresh_status()

        task = _LoginTask(account, password)
        self._login_task = task
        task.signals.finished.connect(self._on_auth_finished)
        QThreadPool.globalInstance().start(task)

    @Slot(bool, str, object)
    def _on_auth_finished(self, success: bool, msg: str, user: object) -> None:
        self._login_task = None
        self._set_auth_busy(False)
        if success and user is not None:
            self.status.setText(f"Đăng nhập thành công! Xin chào, {user.full_name}.")
            self.status.setProperty("valid", True)
            self._refresh_status()
            QTimer.singleShot(0, lambda: self.authenticated.emit(user.full_name, user.role))
            return

        self.status.setText(msg)
        self.status.setProperty("valid", False)
        self._refresh_status()

    def _set_auth_busy(self, busy: bool) -> None:
        self._auth_in_progress = busy
        self.account.setEnabled(not busy)
        self.password.setEnabled(not busy)
        self.remember.setEnabled(not busy)
        self.forgot_button.setEnabled(not busy)
        self.register_button.setEnabled(not busy)
        self.submit_button.setEnabled(not busy)
        self.submit_button.setText("  Đang đăng nhập..." if busy else self._submit_text)

    def _refresh_status(self) -> None:
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


class RegisterStage(QWidget):
    registration_completed = Signal(str, str)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("registerStage")
        self.stage_layout = QHBoxLayout(self)
        self.stage_layout.setContentsMargins(54, 32, 54, 38)
        self.stage_layout.setSpacing(54)
        self.stage_layout.addStretch(1)
        self.stage_layout.addWidget(self._brand_panel(), 11)

        card = QFrame()
        card.setObjectName("registerCard")
        card.setMinimumWidth(410)
        card.setMaximumWidth(540)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        form_scroll = QScrollArea()
        form_scroll.setObjectName("registerFormScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setWidget(self._form_panel())
        card_layout.addWidget(form_scroll)
        self.stage_layout.addWidget(card, 8)
        self.stage_layout.addStretch(1)

    def update_layout(self, width: int, height: int) -> None:
        side = max(20, min(54, (width - 1000) // 2))
        self.stage_layout.setContentsMargins(side, 18 if height < 820 else 32, side, 20 if height < 820 else 38)
        self.stage_layout.setSpacing(max(24, min(54, (width - 1000) // 5)))

    def _brand_panel(self) -> RegisterBrandPanel:
        panel = RegisterBrandPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 14, 20, 12)
        layout.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(18)
        logo = QLabel()
        logo.setPixmap(icon("logo", "#8B5CF6", 82).pixmap(82, 82))
        logo.setFixedSize(86, 86)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)

        copy_widget = QWidget()
        copy = QVBoxLayout(copy_widget)
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(3)
        copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title = QLabel("CYBERA")
        title.setObjectName("registerProductTitle")
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        subtitle = QLabel("Cybersecurity AI System  •  Hệ thống AI giám sát và phòng vệ an ninh mạng")
        subtitle.setObjectName("registerProductSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        brand_row.addWidget(copy_widget, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(brand_row)

        identity_hero = RegistrationHeroWidget()
        layout.addWidget(identity_hero, 4)

        benefits = QHBoxLayout()
        benefits.setSpacing(10)
        for icon_name, title_text, description in [
            ("user_add", "Tài khoản riêng", "Danh tính bảo mật"),
            ("shield", "Bảo vệ tức thì", "Kích hoạt sau đăng ký"),
            ("activity", "Theo dõi 24/7", "Cảnh báo liên tục"),
        ]:
            card = QFrame()
            card.setObjectName("registerBenefitCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 9)
            card_layout.setSpacing(3)
            badge = QLabel()
            badge.setObjectName("registerBenefitIcon")
            badge.setPixmap(icon(icon_name, "#C4B5FD", 22).pixmap(22, 22))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(34, 34)
            card_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
            benefit_title = QLabel(title_text)
            benefit_title.setObjectName("registerBenefitTitle")
            benefit_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(benefit_title)
            benefit_text = QLabel(description)
            benefit_text.setObjectName("registerBenefitText")
            benefit_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            benefit_text.setWordWrap(True)
            card_layout.addWidget(benefit_text)
            benefits.addWidget(card, 1)
        layout.addLayout(benefits)
        layout.addSpacing(10)

        quote = QLabel("“ Bắt đầu an toàn. Kết nối thông minh.\nPhát triển không giới hạn cùng CYBERA. ”")
        quote.setObjectName("registerQuote")
        layout.addWidget(quote)
        layout.addStretch(1)
        return panel

    def _form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("registerFormPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(48, 38, 48, 34)
        layout.setSpacing(6)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(20)
        heading_icon = QLabel()
        heading_icon.setPixmap(icon("logo", "#8B5CF6", 70).pixmap(70, 70))
        heading_icon.setFixedSize(74, 74)
        heading_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_row.addWidget(heading_icon)

        heading_copy_widget = QWidget()
        heading_copy = QVBoxLayout(heading_copy_widget)
        heading_copy.setContentsMargins(0, 0, 0, 0)
        heading_copy.setSpacing(2)
        heading_copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        heading = QLabel("Đăng ký tài khoản")
        heading.setObjectName("registerHeading")
        heading.setWordWrap(True)
        heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        subheading = QLabel("Tạo tài khoản để bắt đầu sử dụng hệ thống")
        subheading.setObjectName("registerSubheading")
        subheading.setWordWrap(True)
        subheading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        heading_copy.addWidget(heading, 0, Qt.AlignmentFlag.AlignBottom)
        heading_copy.addWidget(subheading, 0, Qt.AlignmentFlag.AlignTop)
        heading_row.addWidget(heading_copy_widget, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(heading_row)
        layout.addSpacing(10)

        self.full_name = self._field(layout, "Họ và tên", "Nhập họ và tên của bạn", "user")
        self.email = self._field(layout, "Email", "Nhập email của bạn", "mail")
        self.username = self._field(layout, "Tên đăng nhập", "Nhập tên đăng nhập (tối thiểu 6 ký tự)", "user")
        self.password = self._field(layout, "Mật khẩu", "Nhập mật khẩu (tối thiểu 8 ký tự)", "lock", True)
        self.confirm_password = self._field(layout, "Xác nhận mật khẩu", "Nhập lại mật khẩu", "lock", True)

        self.status = QLabel("")
        self.status.setObjectName("registerStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        register_button = QPushButton("  Đăng ký")
        register_button.setObjectName("registerSubmit")
        register_button.setIcon(icon("user_add", "#FFFFFF"))
        register_button.clicked.connect(self.submit)
        layout.addWidget(register_button)

        divider = QHBoxLayout()
        left = QFrame()
        left.setObjectName("registerDivider")
        left.setFixedHeight(1)
        right = QFrame()
        right.setObjectName("registerDivider")
        right.setFixedHeight(1)
        or_label = QLabel("Hoặc")
        or_label.setObjectName("registerOr")
        divider.addWidget(left, 1)
        divider.addWidget(or_label)
        divider.addWidget(right, 1)
        layout.addLayout(divider)

        back = QPushButton("  Quay lại đăng nhập")
        back.setObjectName("registerBack")
        back.setIcon(icon("back", "#A9C7E8"))
        back.clicked.connect(self.back_requested.emit)
        layout.addWidget(back)

        layout.addStretch(1)
        footer = QLabel("🛡  Hệ thống giám sát và phát hiện bất thường lưu lượng mạng tích hợp AI")
        footer.setObjectName("registerFooter")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)
        return panel

    def _field(self, layout: QVBoxLayout, label: str, placeholder: str, icon_name: str, password: bool = False) -> QLineEdit:
        layout.addWidget(self._field_label(label, icon_name))
        field = QLineEdit()
        field.setObjectName("registerInput")
        field.setPlaceholderText(placeholder)
        field.setMinimumHeight(50)
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            action = field.addAction(icon("eye_off", "#8EAED2"), QLineEdit.ActionPosition.TrailingPosition)
            action.setToolTip("Hiện/ẩn mật khẩu")
            action.triggered.connect(lambda checked=False, target=field, control=action: self.toggle_password(target, control))
        layout.addWidget(field)
        return field

    @staticmethod
    def _field_label(text: str, icon_name: str) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(11)
        badge = QLabel()
        badge.setPixmap(icon(icon_name, "#A78BFA", 22).pixmap(22, 22))
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(badge)
        label = QLabel(text)
        label.setObjectName("registerFieldLabel")
        row.addWidget(label)
        row.addStretch()
        widget.setAccessibleName(text)
        return widget

    @staticmethod
    def toggle_password(field: QLineEdit, action) -> None:
        visible = field.echoMode() == QLineEdit.EchoMode.Normal
        field.setEchoMode(QLineEdit.EchoMode.Password if visible else QLineEdit.EchoMode.Normal)
        action.setIcon(icon("eye" if not visible else "eye_off", "#8EAED2"))

    def submit(self) -> None:
        name = self.full_name.text().strip()
        email = self.email.text().strip()
        username = self.username.text().strip()
        password = self.password.text()
        confirm = self.confirm_password.text()
        error = ""
        if not name:
            error = "Vui lòng nhập họ và tên."
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            error = "Email chưa đúng định dạng."
        elif len(username) < 6:
            error = "Tên đăng nhập phải có ít nhất 6 ký tự."
        elif len(password) < 8:
            error = "Mật khẩu phải có ít nhất 8 ký tự."
        elif password != confirm:
            error = "Mật khẩu xác nhận không khớp."
        if error:
            self.status.setText(error)
            self.status.setProperty("valid", False)
        else:
            success, msg, user = register_user(name, email, username, password)
            if success and user is not None:
                self.status.setText("Đăng ký thành công! Đang mở hệ thống...")
                self.status.setProperty("valid", True)
                self.status.style().unpolish(self.status)
                self.status.style().polish(self.status)
                self.registration_completed.emit(user.full_name, user.role)
                return
            self.status.setText(msg)
            self.status.setProperty("valid", False)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


class AuthWindow(AuthWindowMixin, QMainWindow):
    authenticated = Signal(str, str)
    registration_completed = Signal(str, str)
    register_requested = Signal()
    back_requested = Signal()

    def __init__(self, initial_mode: str = "login", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Đăng nhập | " + WINDOW_TITLE)
        self.resize(1366, 768)
        self.setMinimumSize(1000, 650)
        self._centered_on_screen = False

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

        self.stack = QStackedWidget()
        shell.addWidget(self.stack, 1)

        self.login_stage = LoginStage()
        self.register_stage = RegisterStage()
        self.stack.addWidget(self.login_stage)
        self.stack.addWidget(self.register_stage)

        self.login_stage.authenticated.connect(self.authenticated.emit)
        self.login_stage.register_requested.connect(self.show_register)

        self.register_stage.registration_completed.connect(self.registration_completed.emit)
        self.register_stage.back_requested.connect(self.show_login)

        self._resize_handles = self._create_resize_handles()
        self._position_resize_handles()

        if initial_mode == "register":
            self.show_register()
        else:
            self.show_login()

    def show_register(self) -> None:
        self.stack.setCurrentWidget(self.register_stage)
        self.setWindowTitle("Đăng ký tài khoản | " + WINDOW_TITLE)
        self.register_requested.emit()

    def show_login(self) -> None:
        self.stack.setCurrentWidget(self.login_stage)
        self.setWindowTitle("Đăng nhập | " + WINDOW_TITLE)
        self.back_requested.emit()

    def reset_state(self) -> None:
        self.login_stage.password.clear()
        self.login_stage.status.setText("")
        self.register_stage.password.clear()
        self.register_stage.confirm_password.clear()
        self.register_stage.status.setText("")
        self.show_login()

    # Backwards compatibility properties for LoginWindow
    @property
    def account(self) -> QLineEdit:
        return self.login_stage.account

    @property
    def password(self) -> QLineEdit:
        return self.login_stage.password

    @property
    def status(self) -> QLabel:
        return self.login_stage.status

    @property
    def remember(self) -> RememberCheckBox:
        return self.login_stage.remember

    def resizeEvent(self, event) -> None:
        width, height = self.width(), self.height()
        if hasattr(self, "login_stage"):
            self.login_stage.update_layout(width, height)
        if hasattr(self, "register_stage"):
            self.register_stage.update_layout(width, height)
        super().resizeEvent(event)
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._centered_on_screen and not self.isMaximized():
            self._centered_on_screen = True
            QTimer.singleShot(0, self._center_window)

    def _center_window(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None or self.isMaximized():
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())


class LoginWindow(AuthWindow):
    """Backwards-compatible LoginWindow alias."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(initial_mode="login", parent=parent)


class RegisterWindow(AuthWindow):
    """Backwards-compatible RegisterWindow alias."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(initial_mode="register", parent=parent)
