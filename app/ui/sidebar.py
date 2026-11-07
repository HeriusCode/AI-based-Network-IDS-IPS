"""Modern responsive sidebar navigation with cyber SOC styling."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.navigation import NAV_ITEMS
from app.ui.icons import icon


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class HoverIconButton(QPushButton):
    """Button that dynamically changes its SVG icon color upon hover."""

    def __init__(
        self,
        icon_name: str,
        normal_color: str,
        hover_color: str,
        size: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon_name = icon_name
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.icon_size = size
        self.setIcon(icon(icon_name, normal_color, size))
        self.setIconSize(QSize(size, size))

    def enterEvent(self, event) -> None:
        self.setIcon(icon(self.icon_name, self.hover_color, self.icon_size))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setIcon(icon(self.icon_name, self.normal_color, self.icon_size))
        super().leaveEvent(event)


class AccountTextProxy(QLabel):
    """Proxy maintaining backwards compatibility for window.sidebar.account_text.setText(...)."""

    def __init__(self, name_label: QLabel, role_label: QLabel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name_label = name_label
        self._role_label = role_label
        self.hide()

    def setText(self, text: str) -> None:
        super().setText(text)
        cleaned = text.replace("<span>", "").replace("</span>", "").replace("<b>", "").replace("</b>", "")
        parts = cleaned.replace("<br>", "\n").replace("<br/>", "\n").split("\n")
        name = parts[0].strip() if len(parts) > 0 and parts[0].strip() else "admin"
        role = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "Quản trị viên"
        self._name_label.setText(name)
        self._role_label.setText(role)


class Sidebar(QFrame):
    page_selected = Signal(str)
    logout_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(280)
        self._collapsed = False
        self._selected = "dashboard"
        self._buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 16, 0, 16)
        outer.setSpacing(6)

        # 1. Brand Header (Logo lớn nổi bật, Tên CYBERA cân đối & Khẩu hiệu hoạt động)
        self.brand_container = QWidget()
        self.brand_container.setObjectName("sidebarBrandContainer")
        self.brand_layout = QVBoxLayout(self.brand_container)
        self.brand_layout.setContentsMargins(18, 12, 16, 10)
        self.brand_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        self.logo = ClickableLabel()
        self.logo.setPixmap(icon("logo", "#8B5CF6", 52).pixmap(52, 52))
        self.logo.setFixedSize(54, 54)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logo.setToolTip("Thu gọn / Mở rộng menu")
        self.logo.clicked.connect(self.toggle_collapsed)
        top_row.addWidget(self.logo)

        brand_copy = QVBoxLayout()
        brand_copy.setContentsMargins(0, 0, 0, 0)
        brand_copy.setSpacing(2)
        brand_copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.brand_text = ClickableLabel("CYBERA")
        self.brand_text.setObjectName("brandText")
        self.brand_text.setCursor(Qt.CursorShape.PointingHandCursor)
        self.brand_text.setToolTip("Thu gọn / Mở rộng menu")
        self.brand_text.clicked.connect(self.toggle_collapsed)

        self.brand_sub = QLabel("Cybersecurity AI System")
        self.brand_sub.setObjectName("brandSubtitle")

        brand_copy.addWidget(self.brand_text)
        brand_copy.addWidget(self.brand_sub)
        top_row.addLayout(brand_copy, 1)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("sidebarCollapse")
        self.toggle_btn.setIcon(icon("chevron", "#8E8BA7", 16))
        self.toggle_btn.setFixedSize(32, 32)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setToolTip("Thu gọn menu")
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        top_row.addWidget(self.toggle_btn)

        self.brand_layout.addLayout(top_row)

        # Khẩu hiệu hoạt động của ứng dụng
        self.brand_slogan = QLabel("“ Bảo vệ mạng lưới bằng sức mạnh của AI ”")
        self.brand_slogan.setObjectName("brandSlogan")
        self.brand_slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_slogan.setWordWrap(True)
        self.brand_layout.addWidget(self.brand_slogan)

        outer.addWidget(self.brand_container)

        # 2. Header Divider
        brand_sep = QFrame()
        brand_sep.setObjectName("sidebarDivider")
        brand_sep.setFixedHeight(1)
        outer.addWidget(brand_sep)
        outer.addSpacing(6)

        # 3. Middle Scrollable Navigation List (Giữ nguyên danh sách liền mạch, không chia nhóm)
        scroll = QScrollArea()
        scroll.setObjectName("sidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        nav_content = QWidget()
        nav_content.setObjectName("sidebarNavContent")
        self.nav_layout = QVBoxLayout(nav_content)
        self.nav_layout.setContentsMargins(0, 4, 0, 4)
        self.nav_layout.setSpacing(4)

        for item in NAV_ITEMS:
            btn = self._make_button(item.key, item.title, item.icon)
            self.nav_layout.addWidget(btn)

        self.nav_layout.addStretch(1)
        scroll.setWidget(nav_content)
        outer.addWidget(scroll, 1)

        # 4. Footer Divider
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)
        outer.addSpacing(6)

        # 5. User Account Card (Thẻ thông tin người dùng rộng rãi + Nút Đăng xuất)
        self.account = QFrame()
        self.account.setObjectName("accountCard")
        self.account.setFixedHeight(74)
        self.account_layout = QHBoxLayout(self.account)
        self.account_layout.setContentsMargins(14, 8, 12, 8)
        self.account_layout.setSpacing(12)

        avatar = QLabel()
        avatar.setObjectName("avatar")
        avatar.setPixmap(icon("user", "#8B5CF6", 24).pixmap(24, 24))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(44, 44)
        self.avatar = avatar
        self.account_layout.addWidget(avatar)

        # Tên người dùng và vai trò nằm trên 2 dòng tách biệt
        self.account_info = QWidget()
        info_layout = QVBoxLayout(self.account_info)
        info_layout.setContentsMargins(0, 2, 0, 2)
        info_layout.setSpacing(2)

        self.account_name = QLabel("admin")
        self.account_name.setObjectName("accountName")

        self.account_role = QLabel("Quản trị viên")
        self.account_role.setObjectName("accountRole")

        info_layout.addWidget(self.account_name)
        info_layout.addWidget(self.account_role)
        self.account_layout.addWidget(self.account_info, 1)

        # Proxy giữ tương thích ngược
        self.account_text = AccountTextProxy(self.account_name, self.account_role, self)

        # Nút Đăng xuất tiện dụng
        self.logout_button = HoverIconButton(
            icon_name="logout",
            normal_color="#8E8BA7",
            hover_color="#EF4444",
            size=18,
        )
        self.logout_button.setObjectName("sidebarLogout")
        self.logout_button.setFixedSize(34, 34)
        self.logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_button.setToolTip("Đăng xuất tài khoản")
        self.logout_button.clicked.connect(self.logout_requested)
        self.account_layout.addWidget(self.logout_button)

        outer.addWidget(self.account)
        self.select("dashboard")

    def set_user_info(self, name: str, role: str = "Quản trị viên") -> None:
        """Update displayed user name and role on two distinct lines."""
        self.account_name.setText(name)
        self.account_role.setText(role)

    def _make_button(self, key: str, title: str, icon_name: str) -> QPushButton:
        button = QPushButton(f"   {title}".replace("&", "&&"))
        button.setObjectName("navButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(icon(icon_name, "#8E8BA7", 22))
        button.setIconSize(QSize(22, 22))
        button.setFixedHeight(48)
        button.setToolTip(title)
        button.clicked.connect(lambda checked=False, page=key: self._activate(page))
        self._buttons[key] = button
        return button

    def select(self, key: str) -> None:
        if key not in self._buttons:
            return
        self._selected = key
        for item in NAV_ITEMS:
            if item.key not in self._buttons:
                continue
            button = self._buttons[item.key]
            active = item.key == key
            button.setProperty("active", active)
            button.setIcon(icon(item.icon, "#FFFFFF" if active else "#8E8BA7", 22))
            button.style().unpolish(button)
            button.style().polish(button)

    def _activate(self, key: str) -> None:
        """Activate selected page without collapsing the sidebar."""
        if key != self._selected:
            self.page_selected.emit(key)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        width = 80 if collapsed else 280
        self.setFixedWidth(width)

        # Header elements
        self.brand_text.setVisible(not collapsed)
        self.brand_sub.setVisible(not collapsed)
        self.brand_slogan.setVisible(not collapsed)
        self.toggle_btn.setVisible(not collapsed)
        self.brand_layout.setContentsMargins(13 if collapsed else 18, 10 if collapsed else 12, 13 if collapsed else 16, 8 if collapsed else 10)

        # Navigation buttons
        for item in NAV_ITEMS:
            if item.key not in self._buttons:
                continue
            btn = self._buttons[item.key]
            btn.setText("" if collapsed else f"   {item.title}".replace("&", "&&"))
            btn.setToolTip(item.title)
            btn.setProperty("collapsed", collapsed)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Account card
        self.account_info.setVisible(not collapsed)
        self.logout_button.setVisible(not collapsed)
        self.account_layout.setContentsMargins(18 if collapsed else 14, 8, 18 if collapsed else 12, 8)

        self.setProperty("collapsed", collapsed)
        self.style().unpolish(self)
        self.style().polish(self)
