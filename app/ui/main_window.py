"""Application shell: navigation, global status and page stack."""

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from app.core.config import WINDOW_TITLE
from app.core.navigation import NAV_ITEMS
from app.ui.pages.placeholder import PlaceholderPage
from app.ui.sidebar import Sidebar
from app.ui.topbar import Topbar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1320, 820)
        self.setMinimumSize(850, 560)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
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
        right_layout.addWidget(self.topbar)

        self.pages = QStackedWidget()
        self._page_index: dict[str, int] = {}
        for item in NAV_ITEMS:
            self._page_index[item.key] = self.pages.addWidget(PlaceholderPage(item))
        right_layout.addWidget(self.pages, 1)
        shell.addWidget(right, 1)
        self.navigate("dashboard")

    def navigate(self, key: str) -> None:
        if key not in self._page_index:
            return
        self.pages.setCurrentIndex(self._page_index[key])
        self.sidebar.select(key)
        self.topbar.set_page_title(next(item.title for item in NAV_ITEMS if item.key == key))

    def show_notifications(self) -> None:
        QMessageBox.information(
            self, "Thông báo", "Chưa có thông báo. Cảnh báo mô phỏng sẽ xuất hiện từ Bước 2."
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.topbar.set_compact(self.width() < 1100)
