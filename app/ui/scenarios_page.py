"""Preset bounded traffic scenarios."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.widgets import Card
from app.utils.constants import SCENARIO_PRESETS


class ScenariosPage(QWidget):
    scenario_selected = Signal(str)

    SCENARIOS = SCENARIO_PRESETS

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
        for index, (code, preset) in enumerate(self.SCENARIOS.items()):
            card = Card(str(preset["title"]))
            tag = QLabel(f"●  {code}")
            tag.setStyleSheet(f"color: {preset['color']}; font-weight: 800; font-size: 12px;")
            card.box.addWidget(tag)
            text = QLabel(str(preset["description"]))
            text.setObjectName("muted")
            text.setWordWrap(True)
            card.box.addWidget(text)
            constraints = QLabel(
                f"{preset['protocol']} · {preset['duration']} giây · "
                f"{preset['packet_rate']} lần/s · "
                f"{('h1+h2' if code == 'DDOS' else preset['source'])} → {preset['target']} · "
                f"port {preset.get('port', 'tùy chọn')} · AI: {preset.get('expected_label', '—')}"
            )
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
