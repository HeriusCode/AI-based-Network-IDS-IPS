"""Explicit empty state for pages planned in later phases."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.core.navigation import NavItem
from app.ui.icons import icon


class PlaceholderPage(QScrollArea):
    def __init__(self, item: NavItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("pageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(22)

        intro = QVBoxLayout()
        intro.setSpacing(8)
        eyebrow = QLabel("AI NETWORK IDS/IPS  /  DESKTOP WORKSPACE")
        eyebrow.setObjectName("eyebrow")
        intro.addWidget(eyebrow)
        heading = QLabel(item.title)
        heading.setObjectName("pageHeading")
        intro.addWidget(heading)
        description = QLabel(item.description)
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        intro.addWidget(description)
        layout.addLayout(intro)

        panel = QFrame()
        panel.setObjectName("welcomePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(30, 30, 30, 30)
        panel_layout.setSpacing(18)
        top = QHBoxLayout()
        status = QLabel("GIAO DIỆN NỀN TẢNG ĐÃ SẴN SÀNG")
        status.setObjectName("readyBadge")
        top.addWidget(status)
        top.addStretch()
        phase = QLabel(item.phase.upper())
        phase.setObjectName("phaseBadge")
        top.addWidget(phase)
        panel_layout.addLayout(top)

        icon_label = QLabel()
        icon_label.setPixmap(icon(item.icon, "#60A5FA", 44).pixmap(44, 44))
        panel_layout.addWidget(icon_label)
        headline = QLabel("Không gian cho " + item.title)
        headline.setObjectName("panelHeading")
        headline.setWordWrap(True)
        panel_layout.addWidget(headline)
        detail = QLabel(
            "Trang này sẽ được hoàn thiện ở " + item.phase + ". "
            "Hiện chưa có dữ liệu mạng, kết quả AI hay chính sách IPS thực tế."
        )
        detail.setObjectName("panelDescription")
        detail.setWordWrap(True)
        panel_layout.addWidget(detail)
        layout.addWidget(panel)

        label = QLabel("THÀNH PHẦN DỰ KIẾN")
        label.setObjectName("eyebrow")
        layout.addWidget(label)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        for index, feature in enumerate(item.planned_features, 1):
            card = QFrame()
            card.setObjectName("featureCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            number = QLabel(f"0{index}")
            number.setObjectName("featureNumber")
            card_layout.addWidget(number)
            name = QLabel(feature)
            name.setObjectName("featureName")
            name.setWordWrap(True)
            card_layout.addWidget(name)
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        layout.addStretch(1)
        footer = QLabel("DEMO SHELL  •  NO LIVE NETWORK CONNECTION")
        footer.setObjectName("footerLabel")
        footer.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(footer)
        self.setWidget(content)
