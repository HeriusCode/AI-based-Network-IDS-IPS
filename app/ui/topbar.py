"""Current page, honest demo status and global actions."""

from PySide6.QtCore import QDateTime, Qt, QTimer, QTimeZone, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from app.ui.icons import icon


class Topbar(QFrame):
    settings_requested = Signal()
    notifications_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(76)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(12)

        self.title = QLabel("Dashboard")
        self.title.setObjectName("topbarTitle")
        layout.addWidget(self.title)
        layout.addStretch(1)

        self.demo_status = QLabel("●  DEMO MODE")
        self.demo_status.setObjectName("demoStatus")
        layout.addWidget(self.demo_status, 0, Qt.AlignmentFlag.AlignVCenter)
        self.backend_status = QLabel("●  Backend disconnected")
        self.backend_status.setObjectName("backendStatus")
        self.backend_status.setToolTip("Chưa cấu hình kết nối backend; dữ liệu hiện tại chỉ là demo.")
        layout.addWidget(self.backend_status, 0, Qt.AlignmentFlag.AlignVCenter)

        self.clock = QLabel()
        self.clock.setObjectName("topbarClock")
        layout.addWidget(self.clock, 0, Qt.AlignmentFlag.AlignVCenter)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()

        self.notification_button = QPushButton()
        self.notification_button.setObjectName("iconButton")
        self.notification_button.setIcon(icon("bell", "#CBD5E1"))
        self.notification_button.setToolTip("Thông báo")
        self.notification_button.setAccessibleName("Thông báo")
        self.notification_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notification_button.clicked.connect(self.notifications_requested)
        layout.addWidget(self.notification_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.settings_button = QPushButton()
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setIcon(icon("settings", "#CBD5E1"))
        self.settings_button.setToolTip("Mở Settings")
        self.settings_button.setAccessibleName("Mở Settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_page_title(self, title: str) -> None:
        self.title.setText(title)

    def set_compact(self, compact: bool) -> None:
        self.backend_status.setVisible(not compact)
        self.demo_status.setText("●  DEMO" if compact else "●  DEMO MODE")
        self.clock.setVisible(not compact)

    def _update_clock(self) -> None:
        bangkok = QTimeZone(b"Asia/Bangkok")
        now = QDateTime.currentDateTimeUtc().toTimeZone(bangkok)
        self.clock.setText(now.toString("dd/MM/yyyy  HH:mm:ss 'ICT'"))
