"""Cyber SOC styled modal dialog for confirming user logout."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon


class LogoutConfirmDialog(QDialog):
    """Modern dark-themed confirmation modal with cyber styling."""

    def __init__(
        self,
        username: str = "admin",
        role: str = "Quản trị viên",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self._drag_pos: QPoint | None = None

        # Root layout for drop shadow breathing room
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)

        # Main Card
        card = QFrame()
        card.setObjectName("logoutModalCard")
        card.setFixedWidth(440)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(38)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 200))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 22, 28, 26)
        card_layout.setSpacing(16)

        # Top Bar: Close 'X' button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addStretch()

        close_btn = QPushButton()
        close_btn.setObjectName("logoutModalClose")
        close_btn.setIcon(icon("close", "#8E8BA7", 14))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Đóng")
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)
        card_layout.addLayout(top_bar)

        # Center Alert Icon Badge
        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge = QLabel()
        icon_badge.setObjectName("logoutModalBadge")
        icon_badge.setFixedSize(68, 68)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setPixmap(icon("logout", "#EF4444", 32).pixmap(32, 32))
        badge_row.addWidget(icon_badge)
        card_layout.addLayout(badge_row)

        # Title
        title = QLabel("Xác nhận đăng xuất")
        title.setObjectName("logoutModalTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        # Subtitle / Message
        msg = QLabel("Bạn có chắc chắn muốn kết thúc phiên làm việc hiện tại không?")
        msg.setObjectName("logoutModalMsg")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        card_layout.addWidget(msg)

        # Account Pill
        pill = QFrame()
        pill.setObjectName("logoutAccountPill")
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(14, 7, 14, 7)
        pill_layout.setSpacing(9)

        pill_icon = QLabel()
        pill_icon.setPixmap(icon("user", "#8B5CF6", 16).pixmap(16, 16))
        pill_icon.setFixedSize(18, 18)
        pill_layout.addWidget(pill_icon)

        pill_text = QLabel(f"Tài khoản: <b>{username}</b>  •  <span>{role}</span>")
        pill_text.setObjectName("logoutPillText")
        pill_layout.addWidget(pill_text, 1)

        card_layout.addWidget(pill)

        # Hint note
        hint = QLabel("Mọi tiến trình giám sát nền vẫn tiếp tục ghi nhận an toàn.")
        hint.setObjectName("logoutModalHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(hint)

        card_layout.addSpacing(6)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)

        cancel_btn = QPushButton("Ở lại")
        cancel_btn.setObjectName("logoutModalCancel")
        cancel_btn.setFixedHeight(44)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn, 1)

        confirm_btn = QPushButton("Đăng xuất")
        confirm_btn.setObjectName("logoutModalConfirm")
        confirm_btn.setIcon(icon("logout", "#FFFFFF", 16))
        confirm_btn.setIconSize(QSize(16, 16))
        confirm_btn.setFixedHeight(44)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setDefault(True)
        btn_layout.addWidget(confirm_btn, 1)

        card_layout.addLayout(btn_layout)
        root_layout.addWidget(card)

        # Center relative to parent
        if parent:
            self.adjustSize()
            parent_rect = parent.geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))

    # Support dragging dialog window
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

