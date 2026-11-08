"""Compact, responsive frameless-window top bar for the IDS/IPS SOC dashboard."""

from __future__ import annotations

from PySide6.QtCore import QDateTime, QSize, Qt, QTimer, QTimeZone, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

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
        self.setFixedHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(10)

        # 1. Left Section: System Status Badges
        status_group = QWidget()
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)

        self.demo_status = QLabel("●  Hệ thống: Hoạt động")
        self.demo_status.setObjectName("liveStatus")
        self.demo_status.setFixedHeight(28)
        self.demo_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.demo_status)

        self.backend_status = QLabel("☁  Backend: Online")
        self.backend_status.setObjectName("onlineStatus")
        self.backend_status.setFixedHeight(28)
        self.backend_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.backend_status.setToolTip("Trạng thái mô phỏng; sẵn sàng kết nối dữ liệu.")
        status_layout.addWidget(self.backend_status)

        layout.addWidget(status_group, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Flexible Spacer (Wide drag area for moving the frameless window)
        layout.addStretch(1)

        # 3. Live Clock Card
        clock_card = QFrame()
        clock_card.setObjectName("topbarClockCard")
        clock_card.setFixedHeight(34)
        clock_layout = QHBoxLayout(clock_card)
        clock_layout.setContentsMargins(10, 2, 10, 2)
        clock_layout.setSpacing(8)

        clock_icon = QLabel()
        clock_icon.setPixmap(icon("clock", "#8B5CF6", 16).pixmap(16, 16))
        clock_icon.setFixedSize(16, 16)
        clock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock_layout.addWidget(clock_icon)

        clock_box = QHBoxLayout()
        clock_box.setContentsMargins(0, 0, 0, 0)
        clock_box.setSpacing(8)

        self.clock = QLabel()
        self.clock.setObjectName("topbarClock")
        self.clock.setFixedHeight(24)

        self.date = QLabel()
        self.date.setObjectName("topbarDate")
        self.date.setFixedHeight(24)

        clock_box.addWidget(self.clock, 0, Qt.AlignmentFlag.AlignVCenter)
        clock_box.addWidget(self.date, 0, Qt.AlignmentFlag.AlignVCenter)
        clock_layout.addLayout(clock_box)

        layout.addWidget(clock_card, 0, Qt.AlignmentFlag.AlignVCenter)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()

        # 4. Separator 1
        sep1 = QFrame()
        sep1.setObjectName("topbarSeparator")
        sep1.setFixedSize(1, 24)
        layout.addWidget(sep1, 0, Qt.AlignmentFlag.AlignVCenter)

        # 5. Quick Action Buttons
        actions_group = QWidget()
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        self.notification_button = self._icon_button("bell", "Thông báo")
        self.notification_button.clicked.connect(self.notifications_requested)
        actions_layout.addWidget(self.notification_button)

        self.settings_button = self._icon_button("settings", "Cài đặt hệ thống")
        self.settings_button.clicked.connect(self.settings_requested)
        actions_layout.addWidget(self.settings_button)

        layout.addWidget(actions_group, 0, Qt.AlignmentFlag.AlignVCenter)

        # 6. Separator 2
        sep2 = QFrame()
        sep2.setObjectName("topbarSeparator")
        sep2.setFixedSize(1, 24)
        layout.addWidget(sep2, 0, Qt.AlignmentFlag.AlignVCenter)

        # 7. Window Controls
        win_group = QWidget()
        win_layout = QHBoxLayout(win_group)
        win_layout.setContentsMargins(0, 0, 0, 0)
        win_layout.setSpacing(4)

        self.minimize_button = self._window_button("minimize", "Thu nhỏ")
        self.minimize_button.clicked.connect(self.minimize_requested)
        win_layout.addWidget(self.minimize_button)

        self.maximize_button = self._window_button("maximize", "Phóng to")
        self.maximize_button.clicked.connect(self.maximize_requested)
        win_layout.addWidget(self.maximize_button)

        self.close_button = self._window_button("close", "Đóng", close=True)
        self.close_button.clicked.connect(self.close_requested)
        win_layout.addWidget(self.close_button)

        layout.addWidget(win_group, 0, Qt.AlignmentFlag.AlignVCenter)

    @staticmethod
    def _icon_button(name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("topIconButton")
        button.setIcon(icon(name, "#8E8BA7"))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        return button

    @staticmethod
    def _window_button(name: str, tooltip: str, close: bool = False) -> QPushButton:
        button = QPushButton()
        button.setObjectName("closeWindowButton" if close else "windowButton")
        button.setIcon(icon(name, "#8E8BA7", 15))
        button.setIconSize(QSize(15, 15))
        button.setToolTip(tooltip)
        return button

    def set_maximized(self, maximized: bool) -> None:
        if maximized:
            self.maximize_button.setIcon(icon("restore", "#8E8BA7", 15))
            self.maximize_button.setToolTip("Khôi phục")
        else:
            self.maximize_button.setIcon(icon("maximize", "#8E8BA7", 15))
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
        """Page title is already rendered within each page content."""
        pass

    def set_compact(self, compact: bool) -> None:
        self.backend_status.setVisible(not compact)
        self.demo_status.setText("● Hoạt động" if compact else "●  Hệ thống: Hoạt động")

    def _update_clock(self) -> None:
        now = QDateTime.currentDateTimeUtc().toTimeZone(QTimeZone(b"Asia/Bangkok"))
        weekdays = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN")
        self.clock.setText(now.toString("HH:mm:ss"))
        self.date.setText(f"{weekdays[now.date().dayOfWeek() - 1]}, {now.toString('dd/MM/yyyy')}")
