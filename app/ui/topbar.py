"""Search, service status, clock and global actions."""

from PySide6.QtCore import QDateTime, QSize, Qt, QTimer, QTimeZone, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.ui.icons import icon


class Topbar(QFrame):
    settings_requested = Signal()
    notifications_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(82, 0, 24, 0)
        layout.setSpacing(14)
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
        layout.addWidget(self.demo_status)
        self.backend_status = QLabel("☁  Kết nối: <b>Online</b>")
        self.backend_status.setObjectName("onlineStatus")
        self.backend_status.setToolTip("Trạng thái mô phỏng; chưa có kết nối backend thực tế.")
        layout.addWidget(self.backend_status)
        clock_icon = QLabel()
        clock_icon.setPixmap(icon("clock", "#9FB8D8", 20).pixmap(20, 20))
        layout.addWidget(clock_icon)
        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        self.clock = QLabel()
        self.clock.setObjectName("topbarClock")
        self.date = QLabel()
        self.date.setObjectName("topbarDate")
        clock_box.addWidget(self.clock)
        clock_box.addWidget(self.date)
        layout.addLayout(clock_box)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()
        self.notification_button = QPushButton()
        self.notification_button.setObjectName("topIconButton")
        self.notification_button.setIcon(icon("bell", "#AFC5E2"))
        self.notification_button.setIconSize(QSize(21, 21))
        self.notification_button.setToolTip("Thông báo")
        self.notification_button.clicked.connect(self.notifications_requested)
        layout.addWidget(self.notification_button)
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("topIconButton")
        self.settings_button.setIcon(icon("settings", "#AFC5E2"))
        self.settings_button.setIconSize(QSize(21, 21))
        self.settings_button.setToolTip("Mở cài đặt")
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_button)
        self.title = QLabel("Dashboard")
        self.title.hide()

    def set_page_title(self, title: str) -> None:
        self.title.setText(title)

    def set_compact(self, compact: bool) -> None:
        self.search.setFixedWidth(250 if compact else 380)
        self.backend_status.setVisible(not compact)
        self.demo_status.setVisible(not compact)

    def _update_clock(self) -> None:
        now = QDateTime.currentDateTimeUtc().toTimeZone(QTimeZone(b"Asia/Bangkok"))
        self.clock.setText(now.toString("HH:mm:ss"))
        self.date.setText(now.toString("ddd, dd/MM/yyyy"))
