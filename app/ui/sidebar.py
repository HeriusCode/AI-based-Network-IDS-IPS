

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.navigation import NAV_ITEMS
from app.ui.icons import icon


class Sidebar(QFrame):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(248)
        self._collapsed = False
        self._selected = "dashboard"
        self._buttons: dict[str, QPushButton] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 16, 0, 16)
        outer.setSpacing(6)

        brand = QHBoxLayout()
        brand.setContentsMargins(24, 0, 16, 0)
        brand.setSpacing(12)
        self.logo = QLabel()
        self.logo.setPixmap(icon("logo", "#3DA5FF", 44).pixmap(44, 44))
        self.logo.setFixedSize(50, 50)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(self.logo)
        self.brand_text = QLabel("AI Network IDS/IPS")
        self.brand_text.setObjectName("brandText")
        self.brand_text.setTextFormat(Qt.TextFormat.RichText)
        brand.addWidget(self.brand_text, 1)
        outer.addLayout(brand)
        outer.addSpacing(34)

        for item in NAV_ITEMS:
            outer.addWidget(self._make_button(item.key, item.title))
        outer.addStretch(1)
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        self.account = QFrame()
        self.account.setObjectName("accountCard")
        self.account.setFixedHeight(72)
        account_layout = QHBoxLayout(self.account)
        account_layout.setContentsMargins(22, 10, 18, 8)
        avatar = QLabel()
        avatar.setObjectName("avatar")
        avatar.setPixmap(icon("user", "#F5F8FC", 24).pixmap(24, 24))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(46, 46)
        account_layout.addWidget(avatar)
        self.account_text = QLabel("admin\n<span>Quản trị viên</span>")
        self.account_text.setObjectName("accountText")
        self.account_text.setTextFormat(Qt.TextFormat.RichText)
        account_layout.addWidget(self.account_text, 1)
        self.collapse_button = QPushButton()
        self.collapse_button.setObjectName("sidebarCollapse")
        self.collapse_button.setIcon(icon("logout", "#9CB1CC"))
        self.collapse_button.setToolTip("Thu gọn thanh điều hướng")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        account_layout.addWidget(self.collapse_button)
        outer.addWidget(self.account)
        self.select("dashboard")

    def _make_button(self, key: str, title: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("navButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(23, 23))
        button.setMinimumHeight(54)
        button.setToolTip(title)
        button.clicked.connect(lambda checked=False, page=key: self._activate(page))
        self._buttons[key] = button
        return button

    def select(self, key: str) -> None:
        if key not in self._buttons:
            return
        self._selected = key
        for item in NAV_ITEMS:
            button = self._buttons[item.key]
            active = item.key == key
            button.setProperty("active", active)
            button.setIcon(icon(item.icon, "#D9EDFF" if active else "#A8C2E2"))
            button.style().unpolish(button)
            button.style().polish(button)

    def _activate(self, key: str) -> None:
        """Navigate and toggle the sidebar, so every menu tab can open/close it."""
        self.page_selected.emit(key)
        self.toggle_collapsed()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setFixedWidth(76 if collapsed else 248)
        self.brand_text.setVisible(not collapsed)
        self.account_text.setVisible(not collapsed)
        for item in NAV_ITEMS:
            self._buttons[item.key].setText("" if collapsed else item.title)
        self.collapse_button.setIcon(icon("chevron" if collapsed else "logout", "#9CB1CC"))
        self.collapse_button.setToolTip("Mở rộng thanh điều hướng" if collapsed else "Thu gọn thanh điều hướng")
