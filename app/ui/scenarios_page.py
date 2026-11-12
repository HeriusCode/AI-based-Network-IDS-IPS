"""Preset bounded traffic scenarios."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.widgets import Card


class ScenariosPage(QWidget):
    scenario_selected = Signal(str)

    SCENARIOS = (
        (
            "Normal Traffic",
            "NORMAL",
            "TCP/UDP ổn định ở tốc độ cấu hình. Phù hợp tạo baseline lưu lượng bình thường.",
            "#34D399",
        ),
        (
            "Traffic Burst",
            "BURST",
            "Tăng tốc theo ba giai đoạn: khởi động, tải cao giới hạn và giảm tải.",
            "#FBBF24",
        ),
        (
            "Connection Burst",
            "CONNECTION_BURST",
            "Tạo một số lượng kết nối TCP đồng thời có giới hạn và tự động đóng.",
            "#FB7185",
        ),
        (
            "Custom Traffic",
            "CUSTOM",
            "Tự chọn protocol, IP, port, thời lượng, packet rate và packet size.",
            "#A78BFA",
        ),
    )

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)
        title = QLabel("Traffic Scenarios")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Các kịch bản có giới hạn dành cho môi trường lab được cấp phép")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(14)
        for index, (name, code, description, color) in enumerate(self.SCENARIOS):
            card = Card(name)
            tag = QLabel(f"●  {code}")
            tag.setStyleSheet(f"color: {color}; font-weight: 800; font-size: 12px;")
            card.box.addWidget(tag)
            text = QLabel(description)
            text.setObjectName("muted")
            text.setWordWrap(True)
            card.box.addWidget(text)
            constraints = QLabel("Tự dừng khi hết thời gian · STOP tức thời · Không cho phép IP công cộng")
            constraints.setObjectName("hint")
            constraints.setWordWrap(True)
            card.box.addWidget(constraints)
            button = QPushButton("Chọn kịch bản")
            button.setObjectName("primaryButton")
            button.clicked.connect(lambda _=False, value=code: self.scenario_selected.emit(value))
            card.box.addWidget(button)
            grid.addWidget(card, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)
        root.addStretch()
