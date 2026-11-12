"""Frameless-window top bar with live status and native window controls."""

from __future__ import annotations

from PySide6.QtCore import QDateTime, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

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
        self.setFixedHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 8, 0)
        layout.setSpacing(9)

        self.engine_status = QLabel("●  Traffic Engine: Idle")
        self._engine_state = "Idle"
        self.engine_status.setObjectName("engineStatus")
        self.engine_status.setFixedHeight(28)
        layout.addWidget(self.engine_status)

        self.connection_status = QLabel("●  Máy 2: Disconnected")
        self.connection_status.setObjectName("connectionOffline")
        self.connection_status.setFixedHeight(28)
        layout.addWidget(self.connection_status)
        layout.addStretch(1)

        clock_card = QFrame()
        clock_card.setObjectName("topbarClockCard")
        clock_card.setFixedHeight(34)
        clock_layout = QHBoxLayout(clock_card)
        clock_layout.setContentsMargins(10, 0, 10, 0)
        clock_layout.setSpacing(8)
        clock_icon = QLabel()
        clock_icon.setPixmap(icon("clock", "#60A5FA", 16).pixmap(16, 16))
        clock_layout.addWidget(clock_icon)
        self.clock = QLabel()
        self.clock.setObjectName("topbarClock")
        self.date = QLabel()
        self.date.setObjectName("topbarDate")
        clock_layout.addWidget(self.clock)
        clock_layout.addWidget(self.date)
        layout.addWidget(clock_card)

        timer = QTimer(self)
        timer.timeout.connect(self._update_clock)
        timer.start(1000)
        self._timer = timer
        self._update_clock()

        layout.addWidget(self._separator())
        notification = self._icon_button("bell", "Thông báo")
        notification.clicked.connect(self.notifications_requested)
        layout.addWidget(notification)
        settings = self._icon_button("settings", "Cài đặt")
        settings.clicked.connect(self.settings_requested)
        layout.addWidget(settings)
        layout.addWidget(self._separator())

        self.minimize_button = self._window_button("minimize", "Thu nhỏ")
        self.minimize_button.clicked.connect(self.minimize_requested)
        layout.addWidget(self.minimize_button)
        self.maximize_button = self._window_button("maximize", "Phóng to")
        self.maximize_button.clicked.connect(self.maximize_requested)
        layout.addWidget(self.maximize_button)
        close_button = self._window_button("close", "Đóng", close=True)
        close_button.clicked.connect(self.close_requested)
        layout.addWidget(close_button)

    @staticmethod
    def _separator() -> QFrame:
        frame = QFrame()
        frame.setObjectName("topbarSeparator")
        frame.setFixedSize(1, 24)
        return frame

    @staticmethod
    def _icon_button(name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("topIconButton")
        button.setIcon(icon(name, "#91A3BA", 17))
        button.setIconSize(QSize(17, 17))
        button.setToolTip(tooltip)
        return button

    @staticmethod
    def _window_button(name: str, tooltip: str, close: bool = False) -> QPushButton:
        button = QPushButton()
        button.setObjectName("closeWindowButton" if close else "windowButton")
        button.setIcon(icon(name, "#91A3BA", 15))
        button.setIconSize(QSize(15, 15))
        button.setToolTip(tooltip)
        return button

    def set_maximized(self, maximized: bool) -> None:
        name = "restore" if maximized else "maximize"
        tooltip = "Khôi phục" if maximized else "Phóng to"
        self.maximize_button.setIcon(icon(name, "#91A3BA", 15))
        self.maximize_button.setToolTip(tooltip)

    def set_connection(self, connected: bool, message: str = "") -> None:
        self.connection_status.setText(f"●  Máy 2: {'Connected' if connected else 'Disconnected'}")
        self.connection_status.setObjectName("connectionOnline" if connected else "connectionOffline")
        self.connection_status.setToolTip(message)
        self.connection_status.style().unpolish(self.connection_status)
        self.connection_status.style().polish(self.connection_status)

    def set_engine_status(self, status: str) -> None:
        self._engine_state = status
        self.engine_status.setText(f"●  Traffic Engine: {status}")

    def set_compact(self, compact: bool) -> None:
        self.connection_status.setVisible(not compact)
        self.engine_status.setText("●  Engine" if compact else f"●  Traffic Engine: {self._engine_state}")

    def _update_clock(self) -> None:
        now = QDateTime.currentDateTime()
        weekdays = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN")
        self.clock.setText(now.toString("HH:mm:ss"))
        self.date.setText(f"{weekdays[now.date().dayOfWeek() - 1]}, {now.toString('dd/MM/yyyy')}")

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)
