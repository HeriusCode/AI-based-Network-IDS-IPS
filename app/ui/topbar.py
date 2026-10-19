"""Compact frameless-window top bar for the IDS/IPS dashboard."""

from PySide6.QtCore import QDateTime, QSize, Qt, QTimer, QTimeZone, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.ui.icons import icon


class Topbar(QFrame):
    settings_requested = Signal()
    notifications_requested = Signal()
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(78, 0, 8, 0)
        layout.setSpacing(9)

        self.search = QLineEdit()
        self.search.setObjectName("globalSearch")
        self.search.setPlaceholderText("Tìm kiếm...")
        self.search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(380)
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        layout.addStretch(1)

        self.demo_status = QLabel("●  Hệ thống: <b>Đang hoạt động</b>")
        self.demo_status.setObjectName("liveStatus")
        self.demo_status.setFixedHeight(28)
        self.demo_status.setMaximumWidth(158)
        layout.addWidget(self.demo_status, 0, Qt.AlignmentFlag.AlignVCenter)

        self.backend_status = QLabel("☁  Kết nối: <b>Online</b>")
        self.backend_status.setObjectName("onlineStatus")
        self.backend_status.setFixedHeight(28)
        self.backend_status.setMaximumWidth(116)
        self.backend_status.setToolTip("Trạng thái mô phỏng; chưa có kết nối backend thực tế.")
        layout.addWidget(self.backend_status, 0, Qt.AlignmentFlag.AlignVCenter)

        separator = QFrame()
        separator.setObjectName("topbarSeparator")
        separator.setFixedSize(1, 28)
        layout.addWidget(separator)

        clock_icon = QLabel()
        clock_icon.setPixmap(icon("clock", "#9FB8D8", 18).pixmap(18, 18))
        clock_icon.setFixedSize(22, 28)
        clock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(clock_icon)

        clock_group = QWidget()
        clock_group.setFixedSize(104, 30)
        clock_box = QVBoxLayout(clock_group)
        clock_box.setContentsMargins(0, 0, 0, 0)
        clock_box.setSpacing(0)
        self.clock = QLabel()
        self.clock.setObjectName("topbarClock")
        self.clock.setFixedHeight(17)
        self.date = QLabel()
        self.date.setObjectName("topbarDate")
        self.date.setFixedHeight(13)
        clock_box.addWidget(self.clock)
        clock_box.addWidget(self.date)
        layout.addWidget(clock_group, 0, Qt.AlignmentFlag.AlignVCenter)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()

        separator2 = QFrame()
        separator2.setObjectName("topbarSeparator")
        separator2.setFixedSize(1, 28)
        layout.addWidget(separator2)

        self.notification_button = self._icon_button("bell", "Thông báo")
        self.notification_button.clicked.connect(self.notifications_requested)
        layout.addWidget(self.notification_button)
        self.settings_button = self._icon_button("settings", "Mở cài đặt")
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_button)

        separator3 = QFrame()
        separator3.setObjectName("topbarSeparator")
        separator3.setFixedSize(1, 28)
        layout.addWidget(separator3)

        self.minimize_button = self._window_button("minimize", "Thu nhỏ")
        self.minimize_button.clicked.connect(self.minimize_requested)
        layout.addWidget(self.minimize_button)
        self.maximize_button = self._window_button("maximize", "Phóng to")
        self.maximize_button.clicked.connect(self.maximize_requested)
        layout.addWidget(self.maximize_button)
        self.close_button = self._window_button("close", "Đóng", close=True)
        self.close_button.clicked.connect(self.close_requested)
        layout.addWidget(self.close_button)

        self.title = QLabel("Dashboard")
        self.title.hide()

    @staticmethod
    def _icon_button(name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("topIconButton")
        button.setIcon(icon(name, "#AFC5E2"))
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tooltip)
        return button

    @staticmethod
    def _window_button(name: str, tooltip: str, close: bool = False) -> QPushButton:
        button = QPushButton()
        button.setObjectName("closeWindowButton" if close else "windowButton")
        button.setIcon(icon(name, "#AFC5E2", 15))
        button.setIconSize(QSize(15, 15))
        button.setToolTip(tooltip)
        return button

    def set_maximized(self, maximized: bool) -> None:
        if maximized:
            self.maximize_button.setIcon(icon("restore", "#AFC5E2", 15))
            self.maximize_button.setToolTip("Khôi phục")
        else:
            self.maximize_button.setIcon(icon("maximize", "#AFC5E2", 15))
            self.maximize_button.setToolTip("Phóng to")

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def set_page_title(self, title: str) -> None:
        self.title.setText(title)

    def set_compact(self, compact: bool) -> None:
        self.search.setFixedWidth(250 if compact else 380)
        self.backend_status.setVisible(not compact)
        self.demo_status.setVisible(not compact)

    def _update_clock(self) -> None:
        now = QDateTime.currentDateTimeUtc().toTimeZone(QTimeZone(b"Asia/Bangkok"))
        weekdays = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN")
        self.clock.setText(now.toString("HH:mm:ss"))
        self.date.setText(f"{weekdays[now.date().dayOfWeek() - 1]}, {now.toString('dd/MM/yyyy')}")
