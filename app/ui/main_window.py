"""Application shell with sidebar navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QCloseEvent, QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.ui.connection_page import ConnectionPage
from app.ui.dashboard import DashboardPage
from app.ui.generator_page import GeneratorPage
from app.ui.logs_page import LogsPage
from app.ui.scenarios_page import ScenariosPage
from app.ui.settings_page import SettingsPage
from app.ui.statistics_page import StatisticsPage
from app.ui.icons import icon
from app.ui.topbar import Topbar


class ResizeHandle(QWidget):
    """Transparent native resize target for one window edge or corner."""

    def __init__(self, edge: Qt.Edge, cursor: Qt.CursorShape, parent: QWidget) -> None:
        super().__init__(parent)
        self.edge = edge
        self.setCursor(QCursor(cursor))
        self.setObjectName("resizeHandle")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemResize(self.edge):
                event.accept()
                return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    GRIP = 7
    CORNER = 14
    NAV_ITEMS = (
        ("Dashboard", "dashboard"),
        ("Connection Settings", "connection"),
        ("Traffic Generator", "generator"),
        ("Traffic Scenarios", "scenario"),
        ("Traffic Statistics", "statistics"),
        ("Logs", "logs"),
        ("Cài đặt hệ thống", "settings"),
    )

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.controller = AppController(project_root)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Traffic Generator")
        self.resize(1536, 860)
        self.setMinimumSize(850, 560)

        central = QWidget()
        central.setObjectName("appRoot")
        shell = QHBoxLayout(central)
        shell.setContentsMargins(1, 1, 1, 1)
        shell.setSpacing(0)
        self.setCentralWidget(central)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(258)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 18, 16, 16)
        side.setSpacing(7)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        logo = QLabel()
        logo.setObjectName("brandLogo")
        logo.setPixmap(icon("logo", "#60A5FA", 31).pixmap(31, 31))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(52, 52)
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        name = QLabel("Traffic Generator")
        name.setObjectName("brandTitle")
        description = QLabel("SECURE NETWORK LAB")
        description.setObjectName("brandSubtitle")
        brand_text.addWidget(name)
        brand_text.addWidget(description)
        brand.addLayout(brand_text)
        side.addLayout(brand)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("sidebarSeparator")
        side.addWidget(separator)

        menu_label = QLabel("ĐIỀU KHIỂN TRAFFIC")
        menu_label.setObjectName("sidebarSection")
        side.addWidget(menu_label)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageContainer")
        self.dashboard_page = DashboardPage(self.controller)
        self.connection_page = ConnectionPage(self.controller)
        self.generator_page = GeneratorPage(self.controller)
        self.scenarios_page = ScenariosPage()
        self.statistics_page = StatisticsPage(self.controller)
        self.logs_page = LogsPage(self.controller)
        self.settings_page = SettingsPage(self.controller)
        self.pages = (
            self.dashboard_page,
            self.connection_page,
            self.generator_page,
            self.scenarios_page,
            self.statistics_page,
            self.logs_page,
            self.settings_page,
        )
        for page in self.pages:
            self.stack.addWidget(page)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, (label, icon_name) in enumerate(self.NAV_ITEMS):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setIcon(icon(icon_name, "#91A3BA", 19))
            button.setIconSize(QSize(19, 19))
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, page_index=index: self.navigate(page_index))
            self.nav_group.addButton(button, index)
            side.addWidget(button)
            if index == 0:
                button.setChecked(True)
        side.addStretch()

        scope = QFrame()
        scope.setObjectName("labScopeCard")
        scope_box = QHBoxLayout(scope)
        scope_box.setContentsMargins(11, 10, 11, 10)
        shield = QLabel()
        shield.setPixmap(icon("shield", "#34D399", 20).pixmap(20, 20))
        scope_box.addWidget(shield)
        scope_text = QVBoxLayout()
        scope_title = QLabel("AUTHORIZED LAB")
        scope_title.setObjectName("scopeTitle")
        scope_detail = QLabel("Bounded traffic · Safe stop")
        scope_detail.setObjectName("scopeDetail")
        scope_text.addWidget(scope_title)
        scope_text.addWidget(scope_detail)
        scope_box.addLayout(scope_text)
        side.addWidget(scope)

        right = QWidget()
        right.setObjectName("rightPane")
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(0)
        self.topbar = Topbar()
        self.topbar.settings_requested.connect(lambda: self.navigate(6))
        self.topbar.notifications_requested.connect(self.show_notifications)
        self.topbar.minimize_requested.connect(self.minimize_window)
        self.topbar.maximize_requested.connect(self.toggle_maximize)
        self.topbar.close_requested.connect(self.close)
        right_box.addWidget(self.topbar)
        right_box.addWidget(self.stack, 1)

        shell.addWidget(self.sidebar)
        shell.addWidget(right, 1)

        self.controller.traffic_status_changed.connect(self.topbar.set_engine_status)
        self.controller.connection_changed.connect(self.topbar.set_connection)
        self.dashboard_page.open_generator.connect(lambda: self.navigate(2))
        self.scenarios_page.scenario_selected.connect(self.select_scenario)
        self._resize_handles = self._create_resize_handles()
        self._position_resize_handles()

    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)
        if index == 5:
            self.logs_page.load_rows()

    def select_scenario(self, scenario: str) -> None:
        self.generator_page.set_scenario(scenario)
        self.navigate(2)

    def _create_resize_handles(self) -> dict[str, ResizeHandle]:
        return {
            "top": ResizeHandle(Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor, self),
            "bottom": ResizeHandle(Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor, self),
            "left": ResizeHandle(Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor, self),
            "right": ResizeHandle(Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor, self),
            "top_left": ResizeHandle(Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeFDiagCursor, self),
            "top_right": ResizeHandle(Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeBDiagCursor, self),
            "bottom_left": ResizeHandle(Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeBDiagCursor, self),
            "bottom_right": ResizeHandle(Qt.Edge.BottomEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeFDiagCursor, self),
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
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.topbar.set_maximized(self.isMaximized())
        self._position_resize_handles()

    def show_notifications(self) -> None:
        QMessageBox.information(
            self,
            "Thông báo Traffic Generator",
            "Không có thông báo mới. Các phiên traffic hoàn tất sẽ được lưu trong Logs.",
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.topbar.set_compact(self.width() < 1120)
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_resize_handles"):
            self.topbar.set_maximized(self.isMaximized())
            self._position_resize_handles()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.controller.is_running:
            answer = QMessageBox.question(
                self,
                "Traffic đang chạy",
                "Dừng phiên traffic và thoát ứng dụng?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.controller.stop_traffic()
            worker = self.controller.worker
            if worker is not None:
                worker.wait(1500)
        event.accept()
