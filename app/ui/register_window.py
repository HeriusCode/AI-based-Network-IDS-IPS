"""Account registration window shown before the IDS/IPS workspace."""

from __future__ import annotations

import random
import re
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, Signal
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
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.config import WINDOW_TITLE
from app.ui.icons import icon


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


class BrandPanel(QWidget):
    """Brand area with a generated Earth illustration below the feature row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("registerBrandPanel")
        self.setMinimumWidth(480)
        self.features_widget: QWidget | None = None
        self._compact = False
        asset = Path(__file__).resolve().parents[1] / "assets" / "images" / "digital_earth.png"
        self.earth = QPixmap(str(asset))

    def resizeEvent(self, event) -> None:
        compact = self.height() < 720
        if compact != self._compact and hasattr(self, "brand_layout"):
            self._compact = compact
            self.brand_layout.setContentsMargins(30, 30 if compact else 64, 30, 22 if compact else 50)
            logo_size = 105 if compact else 130
            self.logo_label.setPixmap(icon("logo", "#159BFF", logo_size).pixmap(logo_size, logo_size))
            self.logo_label.setFixedHeight(logo_size)
            self.features_widget.setFixedHeight(100 if compact else 116)
        super().resizeEvent(event)

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
        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(575, 780)


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
        logo.setPixmap(icon("logo", "#38A9FF", 37).pixmap(37, 37))
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(logo)
        name = QLabel("AI Network IDS/IPS")
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
            button.setIcon(icon(icon_name, "#B8CCE5", 15))
            button.setIconSize(QSize(15, 15))
            button.setToolTip(tooltip)
            button.clicked.connect(signal)
            row.addWidget(button)
            if icon_name == "maximize":
                self.maximize_button = button

    def set_maximized(self, maximized: bool) -> None:
        self.maximize_button.setIcon(icon("restore" if maximized else "maximize", "#B8CCE5", 15))
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


class RegisterWindow(AuthWindowMixin, QMainWindow):
    registration_completed = Signal(str)
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Đăng ký tài khoản | " + WINDOW_TITLE)
        self.resize(1536, 960)
        self.setMinimumSize(1040, 720)

        root = NetworkBackground()
        root.setObjectName("registerRoot")
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
        stage_layout = QHBoxLayout(stage)
        self.stage_layout = stage_layout
        stage_layout.setContentsMargins(78, 34, 78, 54)
        stage_layout.addStretch(1)
        card = QFrame()
        card.setObjectName("registerCard")
        card.setMaximumWidth(1195)
        card.setMinimumWidth(900)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(45)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 150))
        card.setGraphicsEffect(shadow)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self._brand_panel(), 1)
        form_scroll = QScrollArea()
        form_scroll.setObjectName("registerFormScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setWidget(self._form_panel())
        card_layout.addWidget(form_scroll, 1)
        stage_layout.addWidget(card, 100)
        stage_layout.addStretch(1)
        shell.addWidget(stage, 1)
        self._resize_handles = self._create_resize_handles()
        self._position_resize_handles()

    def resizeEvent(self, event) -> None:
        width, height = self.width(), self.height()
        side = max(18, min(78, (width - 1000) // 2))
        top, bottom = (18, 18) if height < 850 else (34, 54)
        if hasattr(self, "stage_layout"):
            self.stage_layout.setContentsMargins(side, top, side, bottom)
        super().resizeEvent(event)
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()

    def _brand_panel(self) -> BrandPanel:
        panel = BrandPanel()
        layout = QVBoxLayout(panel)
        panel.brand_layout = layout
        layout.setContentsMargins(42, 64, 42, 50)
        layout.setSpacing(12)
        logo = QLabel()
        panel.logo_label = logo
        logo.setPixmap(icon("logo", "#159BFF", 130).pixmap(130, 130))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(130)
        layout.addWidget(logo)
        layout.addSpacing(24)
        title = QLabel("AI Network IDS/IPS")
        title.setObjectName("registerProductTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(40)
        layout.addWidget(title)
        subtitle = QLabel("Giám sát - Phát hiện - Dự đoán - Giảm thiểu rủi ro")
        subtitle.setObjectName("registerProductSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFixedHeight(24)
        layout.addWidget(subtitle)
        layout.addSpacing(14)
        features_widget = QWidget(panel)
        panel.features_widget = features_widget
        features = QHBoxLayout(features_widget)
        features.setContentsMargins(0, 0, 0, 0)
        features.setSpacing(16)
        for icon_name, text in [
            ("eye", "Giám sát\nmạng"), ("brain", "Phát hiện\nbất thường"),
            ("trend", "Dự đoán\nlưu lượng"), ("shield", "Giảm thiểu\nrủi ro"),
        ]:
            item = QVBoxLayout()
            badge = QLabel()
            badge.setObjectName("registerFeatureIcon")
            badge.setPixmap(icon(icon_name, "#36AAFF", 28).pixmap(28, 28))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(62, 62)
            item.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
            label = QLabel(text)
            label.setObjectName("registerFeatureText")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item.addWidget(label)
            features.addLayout(item, 1)
        features_widget.setFixedHeight(116)
        layout.addWidget(features_widget)
        layout.addSpacing(18)
        quote = QLabel("“ Bảo vệ mạng lưới của bạn\nbằng sức mạnh của AI ”")
        panel.quote_label = quote
        quote.setObjectName("registerQuote")
        quote.setWordWrap(True)
        quote.setMaximumWidth(310)
        layout.addWidget(quote)
        layout.addStretch(1)
        return panel

    def _form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("registerFormPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(48, 40, 42, 38)
        layout.setSpacing(6)
        heading_row = QHBoxLayout()
        heading_row.setSpacing(20)
        heading_icon = QLabel()
        heading_icon.setPixmap(icon("user_add", "#3BA9FF", 55).pixmap(55, 55))
        heading_icon.setFixedSize(66, 66)
        heading_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_row.addWidget(heading_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(2)
        heading_copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        heading = QLabel("Đăng ký tài khoản")
        heading.setObjectName("registerHeading")
        heading.setWordWrap(True)
        heading_copy.addWidget(heading)
        subheading = QLabel("Tạo tài khoản để bắt đầu sử dụng hệ thống")
        subheading.setObjectName("registerSubheading")
        subheading.setWordWrap(True)
        heading_copy.addWidget(subheading)
        heading_row.addLayout(heading_copy, 1)
        layout.addLayout(heading_row)
        layout.addSpacing(8)

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
        back.clicked.connect(self.back_requested)
        layout.addWidget(back)
        return panel

    def _field(self, layout: QVBoxLayout, label: str, placeholder: str, icon_name: str, password: bool = False) -> QLineEdit:
        layout.addWidget(self._field_label(label, icon_name))
        field = QLineEdit()
        field.setObjectName("registerInput")
        field.setPlaceholderText(placeholder)
        field.setMinimumHeight(45)
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
        row.setSpacing(9)
        badge = QLabel()
        badge.setPixmap(icon(icon_name, "#71AFFF", 19).pixmap(19, 19))
        badge.setFixedSize(22, 22)
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
            self.status.setText("Đăng ký thành công. Đang mở hệ thống...")
            self.status.setProperty("valid", True)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.registration_completed.emit(name)
            return
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

