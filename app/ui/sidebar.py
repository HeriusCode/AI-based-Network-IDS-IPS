"""Collapsible application navigation."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.navigation import NAV_ITEMS
from app.ui.icons import icon


class Sidebar(QFrame):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(252)
        self._collapsed = False
        self._selected = "dashboard"
        self._buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 20, 14, 18)
        outer.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        self.logo = QLabel()
        self.logo.setPixmap(icon("logo", "#60A5FA", 30).pixmap(30, 30))
        self.logo.setFixedSize(36, 36)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(self.logo)
        self.brand_text = QLabel("AI Network\nIDS/IPS")
        self.brand_text.setObjectName("brandText")
        brand.addWidget(self.brand_text, 1)
        outer.addLayout(brand)
        outer.addSpacing(24)

        section = QLabel("WORKSPACE")
        section.setObjectName("sectionLabel")
        self.section_label = section
        outer.addWidget(section)
        outer.addSpacing(4)

        for item in NAV_ITEMS:
            if item.key == "settings":
                continue
            button = self._make_button(item.key, item.title, item.icon)
            outer.addWidget(button)

        outer.addStretch(1)
        self.divider = QFrame()
        self.divider.setObjectName("sidebarDivider")
        self.divider.setFixedHeight(1)
        outer.addWidget(self.divider)
        outer.addSpacing(8)
        outer.addWidget(self._make_button("settings", "Settings", "settings"))

        self.collapse_button = QPushButton("Collapse sidebar")
        self.collapse_button.setObjectName("collapseButton")
        self.collapse_button.setIcon(icon("menu"))
        self.collapse_button.setIconSize(QSize(20, 20))
        self.collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_button.setToolTip("Thu gọn hoặc mở rộng thanh điều hướng")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        outer.addWidget(self.collapse_button)
        self.select("dashboard")

    def _make_button(self, key: str, title: str, icon_name: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("navButton")
        button.setProperty("pageKey", key)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(20, 20))
        button.setMinimumHeight(42)
        button.setToolTip(title)
        button.clicked.connect(lambda checked=False, page=key: self.page_selected.emit(page))
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
            button.setIcon(icon(item.icon, "#F8FAFC" if active else "#94A3B8"))
            button.style().unpolish(button)
            button.style().polish(button)

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.setFixedWidth(72 if self._collapsed else 252)
        self.brand_text.setVisible(not self._collapsed)
        self.section_label.setVisible(not self._collapsed)
        for item in NAV_ITEMS:
            self._buttons[item.key].setText("" if self._collapsed else item.title)
        self.collapse_button.setText("" if self._collapsed else "Collapse sidebar")
        self.collapse_button.setIcon(icon("chevron" if self._collapsed else "menu"))
        self.collapse_button.setToolTip("Mở rộng sidebar" if self._collapsed else "Thu gọn sidebar")
