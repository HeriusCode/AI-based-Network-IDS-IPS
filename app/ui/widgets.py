"""Reusable dashboard widgets."""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.ui.icons import icon


def format_bytes(value: float) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(18, 16, 18, 16)
        self.box.setSpacing(10)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            self.box.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("muted")
            subtitle_label.setWordWrap(True)
            self.box.addWidget(subtitle_label)


class MetricCard(Card):
    def __init__(self, title: str, value: str, accent: str, detail: str = "") -> None:
        super().__init__()
        head = QHBoxLayout()
        color = QColor(accent)
        badge = QLabel()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(icon(self._icon_for_title(title), accent, 18).pixmap(18, 18))
        badge.setStyleSheet(
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 28); "
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 80); "
            "border-radius: 9px;"
        )
        head.addWidget(badge)
        labels = QVBoxLayout()
        labels.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("metricLabel")
        labels.addWidget(label)
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("muted")
        labels.addWidget(self.detail_label)
        head.addLayout(labels)
        head.addStretch()
        self.box.addLayout(head)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        self.box.addWidget(self.value_label)

    @staticmethod
    def _icon_for_title(title: str) -> str:
        lowered = title.lower()
        if "connection" in lowered or "target" in lowered or "server" in lowered or "local" in lowered or "port" in lowered:
            return "connection"
        if "duration" in lowered:
            return "clock"
        if "scenario" in lowered or "protocol" in lowered:
            return "scenario"
        if "status" in lowered:
            return "shield"
        return "statistics"

    def set_value(self, value: str, detail: str | None = None) -> None:
        self.value_label.setText(value)
        if detail is not None:
            self.detail_label.setText(detail)


class StatusPill(QLabel):
    COLORS = {
        "Connected": ("#34D399", "rgba(16, 185, 129, 35)", "rgba(16, 185, 129, 90)"),
        "Running": ("#38BDF8", "rgba(56, 189, 248, 35)", "rgba(56, 189, 248, 90)"),
        "Completed": ("#34D399", "rgba(16, 185, 129, 35)", "rgba(16, 185, 129, 90)"),
        "Stopped": ("#FBBF24", "rgba(245, 158, 11, 35)", "rgba(245, 158, 11, 90)"),
        "Error": ("#FB7185", "rgba(244, 63, 94, 35)", "rgba(244, 63, 94, 90)"),
        "Idle": ("#A5B4FC", "rgba(99, 102, 241, 35)", "rgba(99, 102, 241, 90)"),
        "Preparing": ("#C4B5FD", "rgba(139, 92, 246, 35)", "rgba(139, 92, 246, 90)"),
        "Disconnected": ("#94A3B8", "rgba(100, 116, 139, 35)", "rgba(100, 116, 139, 90)"),
    }

    def __init__(self, text: str = "Idle") -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(text)

    def set_status(self, text: str) -> None:
        key = text if text in self.COLORS else "Error" if "error" in text.lower() else "Idle"
        foreground, background, border = self.COLORS[key]
        self.setText(f"●  {text}")
        self.setStyleSheet(
            f"color: {foreground}; background: {background}; border: 1px solid {border}; "
            "border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 700;"
        )


class LivePlot(pg.PlotWidget):
    def __init__(self, title: str, color: str = "#38BDF8", max_points: int = 120) -> None:
        super().__init__()
        self.max_points = max_points
        self.values: deque[float] = deque([0.0], maxlen=max_points)
        self.setBackground("#10192D")
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setTitle(title, color="#E2E8F0", size="11pt")
        self.getAxis("left").setTextPen("#94A3B8")
        self.getAxis("bottom").setTextPen("#94A3B8")
        self.getAxis("left").setPen("#233652")
        self.getAxis("bottom").setPen("#233652")
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.curve = self.plot([], [], pen=pg.mkPen(color, width=2))

    def append(self, value: float) -> None:
        self.values.append(float(value))
        data = list(self.values)
        self.curve.setData(range(len(data)), data)

    def reset(self) -> None:
        self.values.clear()
        self.values.append(0.0)
        self.curve.setData([0], [0.0])


class ProtocolBarChart(pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__()
        self.counts = {"TCP": 0, "UDP": 0, "ICMP": 0}
        self.setBackground("#10192D")
        self.showGrid(x=False, y=True, alpha=0.15)
        self.setTitle("Protocol Distribution", color="#E2E8F0", size="11pt")
        self.getAxis("bottom").setTicks([[(0, "TCP"), (1, "UDP"), (2, "ICMP")]])
        self.getAxis("left").setTextPen("#94A3B8")
        self.getAxis("bottom").setTextPen("#94A3B8")
        self.getAxis("left").setPen("#233652")
        self.getAxis("bottom").setPen("#233652")
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.bars = pg.BarGraphItem(
            x=[0, 1, 2],
            height=[0, 0, 0],
            width=0.55,
            brushes=["#38BDF8", "#34D399", "#A78BFA"],
        )
        self.addItem(self.bars)

    def set_protocol_value(self, protocol: str, packets: int) -> None:
        if protocol in self.counts:
            self.counts[protocol] = max(0, int(packets))
        self.bars.setOpts(height=[self.counts[name] for name in ("TCP", "UDP", "ICMP")])

    def reset(self) -> None:
        self.counts = {"TCP": 0, "UDP": 0, "ICMP": 0}
        self.bars.setOpts(height=[0, 0, 0])
