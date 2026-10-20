"""Application shell, frameless controls and resize behavior."""

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from app.core.config import WINDOW_TITLE
from app.core.navigation import NAV_ITEMS
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.detection import DetectionPage
from app.ui.pages.monitoring import MonitoringPage
from app.ui.pages.placeholder import PlaceholderPage
from app.ui.sidebar import Sidebar
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
            window = self.window()
            handle = window.windowHandle()
            if handle is not None and handle.startSystemResize(self.edge):
                event.accept()
                return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    GRIP = 7
    CORNER = 14

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1536, 960)
        self.setMinimumSize(850, 560)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(1, 1, 1, 1)
        shell.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_selected.connect(self.navigate)
        shell.addWidget(self.sidebar)

        right = QWidget()
        right.setObjectName("rightPane")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.topbar = Topbar()
        self.topbar.settings_requested.connect(lambda: self.navigate("settings"))
        self.topbar.notifications_requested.connect(self.show_notifications)
        self.topbar.minimize_requested.connect(self.minimize_window)
        self.topbar.maximize_requested.connect(self.toggle_maximize)
        self.topbar.close_requested.connect(self.close)
        right_layout.addWidget(self.topbar)

        self.pages = QStackedWidget()
        self._page_index: dict[str, int] = {}
        for item in NAV_ITEMS:
            if item.key == "dashboard":
                page = DashboardPage()
            elif item.key == "monitoring":
                page = MonitoringPage()
            elif item.key == "detection":
                page = DetectionPage()
            else:
                page = PlaceholderPage(item)
            self._page_index[item.key] = self.pages.addWidget(page)
        right_layout.addWidget(self.pages, 1)
        shell.addWidget(right, 1)

        self._resize_handles = self._create_resize_handles()
        self.navigate("dashboard")

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

    def navigate(self, key: str) -> None:
        if key not in self._page_index:
            return
        self.pages.setCurrentIndex(self._page_index[key])
        self.sidebar.select(key)
        self.topbar.set_page_title(next(item.title for item in NAV_ITEMS if item.key == key))

    def minimize_window(self) -> None:
        """Minimize after the button click has completed on frameless Windows."""
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMinimized)

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            # Keep the account card visible whenever entering the maximized layout.
            self.sidebar.set_collapsed(False)
            self.showMaximized()
        self.topbar.set_maximized(self.isMaximized())
        self._position_resize_handles()

    def show_notifications(self) -> None:
        QMessageBox.information(self, "Thông báo", "Bạn có 3 cảnh báo an ninh mới trong dữ liệu mô phỏng.")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.topbar.set_compact(self.width() < 1100)
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_resize_handles"):
            self.topbar.set_maximized(self.isMaximized())
            self.sidebar.account.setVisible(True)
            self._position_resize_handles()
