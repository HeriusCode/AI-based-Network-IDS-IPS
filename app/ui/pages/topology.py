"""Interactive network-topology view for the AI-based Network IDS/IPS platform."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.dashboard import make_badge_cell, make_text_cell
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend_chip

# Backward compatible alias
legend = legend_chip


@dataclass(frozen=True)
class Device:
    key: str
    name: str
    ip: str
    kind: str
    icon_name: str
    color: str
    x: float
    y: float
    mac: str = "00:00:00:00:00:01"
    openflow: str = "1.3"
    ports: str = "4"
    flows: str = "1,245"
    incoming: str = "125.4 Mbps"
    outgoing: str = "118.2 Mbps"
    uptime: str = "2 ngày 5 giờ"
    status: str = "Trực tuyến"


DEVICES: list[Device] = [
    Device(
        key="controller",
        name="SDN Controller",
        ip="192.168.1.10",
        kind="Controller (Ryu / ONOS)",
        icon_name="server",
        color="#8B5CF6",
        x=500,
        y=65,
        mac="00:00:00:00:00:10",
        openflow="1.3 (Master)",
        ports="3 Cổng",
        flows="5 Flow Rules",
        incoming="1.2 Mbps",
        outgoing="1.1 Mbps",
        uptime="5 ngày 12 giờ",
    ),
    Device(
        key="switch",
        name="s1 - Open vSwitch",
        ip="192.168.1.1",
        kind="Switch (Open vSwitch)",
        icon_name="switch",
        color="#3B82F6",
        x=500,
        y=245,
        mac="00:00:00:00:00:01",
        openflow="1.3 (OVS 2.17)",
        ports="4 Cổng Gigabit",
        flows="1,245 flows",
        incoming="125.4 Mbps",
        outgoing="118.2 Mbps",
        uptime="2 ngày 5 giờ",
    ),
    Device(
        key="client",
        name="h1 - Normal Client",
        ip="192.168.1.100",
        kind="Host (Client Workstation)",
        icon_name="monitor",
        color="#10B981",
        x=145,
        y=245,
        mac="00:00:00:00:00:02",
        openflow="N/A (Standard IP)",
        ports="1 Cổng",
        flows="245 flows",
        incoming="12.5 Mbps",
        outgoing="1.3 Mbps",
        uptime="1 ngày 8 giờ",
    ),
    Device(
        key="server",
        name="h3 - Target Server",
        ip="192.168.1.200",
        kind="Host (Web / Database)",
        icon_name="server",
        color="#6366F1",
        x=855,
        y=245,
        mac="00:00:00:00:00:03",
        openflow="N/A (Standard IP)",
        ports="2 Cổng",
        flows="521 flows",
        incoming="45.2 Mbps",
        outgoing="82.1 Mbps",
        uptime="7 ngày 3 giờ",
    ),
    Device(
        key="generator",
        name="h2 - Traffic Generator",
        ip="192.168.1.150",
        kind="Host (Trex / Scapy Bot)",
        icon_name="monitor",
        color="#FF5B79",
        x=500,
        y=425,
        mac="00:00:00:00:00:04",
        openflow="N/A (Standard IP)",
        ports="2 Cổng",
        flows="632 flows",
        incoming="78.6 Mbps",
        outgoing="5.4 Mbps",
        uptime="0 ngày 4 giờ",
    ),
    Device(
        key="firewall",
        name="Firewall (IPS Gateway)",
        ip="192.168.1.254",
        kind="Firewall (Suricata / IPTables)",
        icon_name="firewall",
        color="#F59E0B",
        x=275,
        y=395,
        mac="00:00:00:00:00:FE",
        openflow="Bypass / In-line",
        ports="4 Cổng",
        flows="324 flows",
        incoming="32.1 Mbps",
        outgoing="28.4 Mbps",
        uptime="14 ngày 2 giờ",
    ),
    Device(
        key="internet",
        name="Internet Gateway",
        ip="0.0.0.0/0",
        kind="Cloud (WAN Uplink)",
        icon_name="cloud",
        color="#38BDF8",
        x=65,
        y=410,
        mac="00:00:00:00:00:FF",
        openflow="BGP / OSPF",
        ports="1 Cổng WAN",
        flows="156 flows",
        incoming="5.3 Mbps",
        outgoing="4.8 Mbps",
        uptime="30 ngày 0 giờ",
    ),
]

DEVICE_TRAFFIC_SERIES: dict[str, tuple[list[tuple[list[int], str]], int, str, str]] = {
    "switch": (
        [
            ([98, 119, 151, 134, 166, 188, 163, 132, 147, 159, 171, 152, 183, 207, 161, 133, 155, 178, 169, 197, 189, 252, 196, 156, 179, 185, 197, 166, 148, 176, 142, 161], "#3B82F6"),
            ([67, 88, 112, 97, 126, 135, 118, 104, 119, 127, 131, 114, 126, 112, 106, 96, 111, 102, 115, 101, 90, 151, 119, 96, 110, 123, 115, 98, 104, 121, 95, 116], "#10B981"),
        ],
        300,
        "125.4 Mbps",
        "118.2 Mbps",
    ),
    "controller": (
        [
            ([1, 2, 1, 3, 2, 1, 2, 3, 2, 1, 2, 3, 2, 1, 2, 1, 2, 3, 2, 1, 2, 3, 2, 1, 2, 3, 2, 1, 2, 3, 2, 1], "#8B5CF6"),
            ([1, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 1], "#10B981"),
        ],
        10,
        "1.2 Mbps",
        "1.1 Mbps",
    ),
    "client": (
        [
            ([11, 13, 12, 15, 14, 12, 13, 16, 14, 13, 15, 12, 14, 17, 13, 12, 14, 15, 13, 16, 14, 18, 15, 13, 14, 16, 13, 12, 15, 14, 13, 13], "#3B82F6"),
            ([1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 1], "#10B981"),
        ],
        30,
        "12.5 Mbps",
        "1.3 Mbps",
    ),
    "server": (
        [
            ([35, 42, 38, 48, 52, 44, 46, 50, 43, 47, 51, 46, 49, 55, 42, 45, 48, 52, 47, 56, 49, 62, 53, 44, 48, 50, 46, 43, 49, 47, 44, 45], "#3B82F6"),
            ([68, 75, 72, 85, 91, 79, 82, 88, 80, 84, 89, 81, 86, 95, 78, 83, 87, 92, 85, 98, 89, 110, 93, 82, 86, 90, 84, 80, 88, 85, 81, 82], "#10B981"),
        ],
        150,
        "45.2 Mbps",
        "82.1 Mbps",
    ),
    "generator": (
        [
            ([65, 72, 70, 78, 82, 74, 76, 81, 75, 79, 83, 76, 80, 88, 73, 77, 81, 85, 79, 90, 82, 98, 85, 76, 80, 84, 78, 74, 82, 79, 75, 79], "#FF5B79"),
            ([4, 5, 4, 6, 5, 4, 5, 6, 5, 4, 5, 6, 5, 4, 5, 4, 5, 6, 5, 4, 5, 6, 5, 4, 5, 6, 5, 4, 5, 6, 5, 5], "#10B981"),
        ],
        120,
        "78.6 Mbps",
        "5.4 Mbps",
    ),
    "firewall": (
        [
            ([25, 29, 28, 33, 36, 31, 32, 35, 30, 34, 37, 32, 35, 40, 29, 33, 35, 38, 33, 41, 35, 46, 38, 32, 35, 37, 33, 31, 36, 34, 31, 32], "#F59E0B"),
            ([22, 26, 25, 30, 32, 28, 29, 31, 27, 30, 33, 29, 31, 35, 26, 29, 31, 34, 30, 36, 31, 40, 34, 28, 31, 33, 29, 27, 32, 30, 27, 28], "#10B981"),
        ],
        60,
        "32.1 Mbps",
        "28.4 Mbps",
    ),
    "internet": (
        [
            ([4, 5, 4, 6, 5, 4, 5, 6, 5, 4, 5, 6, 5, 4, 5, 4, 5, 6, 5, 4, 5, 6, 5, 4, 5, 6, 5, 4, 5, 6, 5, 5], "#38BDF8"),
            ([4, 4, 5, 4, 5, 4, 4, 5, 4, 5, 4, 4, 5, 4, 5, 4, 4, 5, 4, 5, 4, 4, 5, 4, 5, 4, 4, 5, 4, 5, 4, 5], "#10B981"),
        ],
        15,
        "5.3 Mbps",
        "4.8 Mbps",
    ),
}


class TopologyCanvas(QWidget):
    node_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topologyCanvas")
        self.setMinimumHeight(440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.zoom = 1.0
        self.selected = "switch"
        self._node_rects: dict[str, QRectF] = {}
        self.setMouseTracking(True)

    def zoom_in(self) -> None:
        self.zoom = min(1.35, self.zoom + 0.1)
        self.update()

    def zoom_out(self) -> None:
        self.zoom = max(0.75, self.zoom - 0.1)
        self.update()

    def reset_layout(self) -> None:
        self.zoom = 1.0
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        hovered = any(rect.contains(pos) for rect in self._node_rects.values())
        if hovered:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for key, rect in self._node_rects.items():
                if rect.contains(pos):
                    self.selected = key
                    self.node_selected.emit(key)
                    self.update()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Background fill & sleek midnight matrix grid
        painter.fillRect(self.rect(), QColor("#14122E"))
        grid_pen = QPen(QColor(36, 32, 78, 120), 1, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, self.width(), 36):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 36):
            painter.drawLine(0, y, self.width(), y)

        # 2. Scale & Center projection
        scale = min(self.width() / 940, self.height() / 500) * self.zoom
        offset_x = (self.width() - 940 * scale) / 2
        offset_y = (self.height() - 500 * scale) / 2

        def point(x: float, y: float) -> QPointF:
            return QPointF(offset_x + x * scale, offset_y + y * scale)

        positions = {device.key: point(device.x, device.y) for device in DEVICES}

        # 3. Network Links
        links = [
            ("controller", "switch", "#8B5CF6", Qt.PenStyle.DashLine, "OpenFlow 1.3\nControl Channel", 2.6),
            ("client", "switch", "#10B981", Qt.PenStyle.SolidLine, "12.5 Mbps\n1,245 p/s", 2.2),
            ("switch", "server", "#6366F1", Qt.PenStyle.SolidLine, "45.2 Mbps\n4,521 p/s", 2.2),
            ("switch", "generator", "#FF5B79", Qt.PenStyle.SolidLine, "78.6 Mbps\n8,920 p/s", 2.6),
            ("internet", "firewall", "#38BDF8", Qt.PenStyle.SolidLine, "5.3 Mbps\n523 p/s", 2.0),
            ("firewall", "switch", "#F59E0B", Qt.PenStyle.SolidLine, "32.1 Mbps\n3,245 p/s", 2.2),
        ]

        for source, target, color_str, style, text, thickness in links:
            start, end = positions[source], positions[target]

            # Link outer glow
            glow_col = QColor(color_str)
            glow_col.setAlpha(45)
            painter.setPen(QPen(glow_col, max(4, int(5.5 * scale)), style))
            painter.drawLine(start, end)

            # Core link
            painter.setPen(QPen(QColor(color_str), max(2, int(thickness * scale)), style))
            painter.drawLine(start, end)

            # Bandwidth & status badge
            center = (start + end) / 2
            bw = 92 * scale
            bh = 30 * scale
            badge_rect = QRectF(center.x() - bw / 2, center.y() - bh / 2, bw, bh)
            painter.setPen(QPen(QColor("#2E2760"), 1))
            painter.setBrush(QColor(22, 19, 48, 230))
            painter.drawRoundedRect(badge_rect, 6 * scale, 6 * scale)

            painter.setPen(QColor("#E2E8F0"))
            painter.setFont(QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.DemiBold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

        # 4. Draw Device Nodes
        self._node_rects.clear()
        for device in DEVICES:
            center = positions[device.key]
            card_w = 172 * scale
            card_h = 70 * scale
            if device.key in ("firewall", "internet"):
                card_w = 148 * scale

            rect = QRectF(center.x() - card_w / 2, center.y() - card_h / 2, card_w, card_h)
            self._node_rects[device.key] = rect
            is_selected = device.key == self.selected

            # Outer glow ring on selected node
            if is_selected:
                glow_rect = rect.adjusted(-4, -4, 4, 4)
                painter.setPen(QPen(QColor(139, 92, 246, 75), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(glow_rect, 14 * scale, 14 * scale)

                painter.setPen(QPen(QColor("#8B5CF6"), 2.2))
                painter.setBrush(QColor("#262054"))
            else:
                painter.setPen(QPen(QColor("#2E2760"), 1.4))
                painter.setBrush(QColor("#1B183E"))

            painter.drawRoundedRect(rect, 12 * scale, 12 * scale)

            # Icon badge box
            ib_size = 48 * scale
            icon_box = QRectF(rect.left() + 9 * scale, rect.top() + 11 * scale, ib_size, ib_size)
            tint = QColor(device.color)
            tint.setAlpha(35)
            painter.setPen(QPen(QColor(device.color).darker(110), 1))
            painter.setBrush(tint)
            painter.drawRoundedRect(icon_box, 9 * scale, 9 * scale)

            icon_size = max(16, int(22 * scale))
            icon(device.icon_name, device.color, icon_size).paint(painter, icon_box.toRect())

            # Labels
            text_x = icon_box.right() + 8 * scale
            text_w = rect.right() - text_x - 8 * scale

            # Name
            painter.setPen(QColor("#FFFFFF"))
            name_font = QFont("Segoe UI", max(8, int(9.5 * scale)), QFont.Weight.Bold)
            painter.setFont(name_font)
            painter.drawText(
                QRectF(text_x, rect.top() + 9 * scale, text_w, 18 * scale),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                device.name,
            )

            # IP
            painter.setPen(QColor("#A78BFA"))
            ip_font = QFont("Consolas", max(7, int(8.5 * scale)), QFont.Weight.DemiBold)
            painter.setFont(ip_font)
            painter.drawText(
                QRectF(text_x, rect.top() + 28 * scale, text_w, 16 * scale),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                device.ip,
            )

            # Status
            painter.setPen(QColor("#10B981"))
            st_font = QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.DemiBold)
            painter.setFont(st_font)
            painter.drawText(
                QRectF(text_x, rect.top() + 45 * scale, text_w, 16 * scale),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "● Trực tuyến",
            )

        # 5. Floating Semi-transparent Legend Box
        legend_box = QRectF(14, 14, 230, 162)
        painter.setPen(QPen(QColor("#2E2760"), 1))
        painter.setBrush(QColor(19, 17, 43, 230))
        painter.drawRoundedRect(legend_box, 10, 10)

        painter.setPen(QColor("#C4B5FD"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(24, 22, 208, 16), "CHÚ THÍCH LIÊN KẾT MẠNG")

        legend_items = [
            ("#10B981", "Lưu lượng chuẩn (Normal LAN)", Qt.PenStyle.SolidLine),
            ("#FF5B79", "Lưu lượng cao / Tấn công", Qt.PenStyle.SolidLine),
            ("#8B5CF6", "Kênh điều khiển (OpenFlow)", Qt.PenStyle.DashLine),
            ("#6366F1", "Truy cập máy chủ (Server Link)", Qt.PenStyle.SolidLine),
            ("#38BDF8", "Đường truyền Internet / WAN", Qt.PenStyle.SolidLine),
        ]
        painter.setFont(QFont("Segoe UI", 8))
        for index, (col, lbl, sty) in enumerate(legend_items):
            ly = 48 + index * 22
            painter.setPen(QPen(QColor(col), 2.5, sty))
            painter.drawLine(24, ly, 52, ly)
            painter.setPen(QColor("#CBD5E1"))
            painter.drawText(QRectF(60, ly - 9, 160, 18), lbl)


class MiniMap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(115)
        self.setFixedHeight(115)
        self.selected = "switch"

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor("#161434"))
        painter.setPen(QPen(QColor("#282452"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        # Points
        points = {
            d.key: QPointF(20 + d.x / 940 * (self.width() - 40), 12 + d.y / 500 * (self.height() - 24))
            for d in DEVICES
        }

        # Links
        for s, t, col in [
            ("controller", "switch", "#8B5CF6"),
            ("client", "switch", "#10B981"),
            ("switch", "server", "#6366F1"),
            ("switch", "generator", "#FF5B79"),
            ("internet", "firewall", "#38BDF8"),
            ("firewall", "switch", "#F59E0B"),
        ]:
            painter.setPen(QPen(QColor(col), 1.2))
            painter.drawLine(points[s], points[t])

        # Nodes
        for device in DEVICES:
            pt = points[device.key]
            if device.key == self.selected:
                painter.setPen(QPen(QColor("#8B5CF6"), 1.8))
                painter.setBrush(QColor(device.color))
                painter.drawEllipse(pt, 5.5, 5.5)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(device.color))
                painter.drawEllipse(pt, 4, 4)

        # Viewport border
        painter.setPen(QPen(QColor("#6C5DD3"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(6, 6, -6, -6), 6, 6)


class TopologyPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topologyScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("topologyContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        self.selected_key = "switch"

        # ---------------------------------------------------------------------
        # 1. HEADER (Title, Subtitle & SOC Action Controls)
        # ---------------------------------------------------------------------
        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)

        heading = QLabel("Sơ đồ mạng")
        heading.setObjectName("topologyHeading")
        intro.addWidget(heading)

        subtitle = QLabel(
            "Trực quan hóa cấu trúc topology OpenFlow SDN, trạng thái kết nối thời gian thực và luồng dữ liệu an ninh mạng"
        )
        subtitle.setObjectName("topologySubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro, stretch=1)

        # SDN Engine Active Badge
        status_badge = QLabel("●  SDN OPENFLOW ACTIVE")
        status_badge.setStyleSheet(
            "background: rgba(139, 92, 246, 0.14); color: #C4B5FD; "
            "border: 1px solid rgba(139, 92, 246, 0.35); border-radius: 10px; "
            "padding: 6px 14px; font-weight: 700; font-size: 11px;"
        )
        header.addWidget(status_badge)

        mode_label = QLabel("Chế độ:")
        mode_label.setStyleSheet("color: #8E8BA7; font-size: 11px; font-weight: 500;")
        header.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("topologyCombo")
        self.mode_combo.addItems(["Topology Logic", "OpenFlow SDN", "Mô hình Vật lý"])
        header.addWidget(self.mode_combo)

        arrange = QPushButton("Tự động sắp xếp")
        arrange.setObjectName("arrangeButton")
        arrange.setIcon(icon("refresh", "#FFFFFF", 14))
        header.addWidget(arrange)

        zoom_out = QPushButton("-")
        zoom_out.setObjectName("topologyTool")
        header.addWidget(zoom_out)

        zoom_in = QPushButton("+")
        zoom_in.setObjectName("topologyTool")
        header.addWidget(zoom_in)

        expand = QPushButton()
        expand.setObjectName("topologyTool")
        expand.setIcon(icon("expand", "#A78BFA", 14))
        header.addWidget(expand)

        root.addLayout(header)

        # ---------------------------------------------------------------------
        # 2. ROW 1: 5 THẺ CHỈ SỐ MẠNG (KPIs)
        # ---------------------------------------------------------------------
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Tổng số thiết bị", "7 Nodes", "100% Kết nối", "#3B82F6", "nodes"),
            MonitorMetric("Thiết bị trực tuyến", "7 Online", "● 0 Ngoại tuyến", "#10B981", "check"),
            MonitorMetric("Liên kết mạng (Links)", "6 Active", "OpenFlow 1.3", "#8B5CF6", "switch"),
            MonitorMetric("Băng thông toàn mạng", "178.6 Mbps", "↑ 8.4%", "#FBBF24", "activity"),
            MonitorMetric("Cảnh báo Topology", "0 Sự cố", "● Toàn vẹn", "#10B981", "shield"),
        ]
        for column, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # ---------------------------------------------------------------------
        # 3. ROW 2: TOPOLOGY CANVAS (68%) & DEVICE INSPECTOR (32%)
        # ---------------------------------------------------------------------
        upper = QGridLayout()
        upper.setSpacing(12)

        self.canvas = TopologyCanvas()
        self.canvas.node_selected.connect(lambda k: self.select_device(k, source="canvas"))
        arrange.clicked.connect(self.canvas.reset_layout)
        zoom_out.clicked.connect(self.canvas.zoom_out)
        zoom_in.clicked.connect(self.canvas.zoom_in)
        expand.clicked.connect(self.canvas.reset_layout)
        upper.addWidget(self.canvas, 0, 0)

        upper.addWidget(self._device_panel(), 0, 1)
        upper.setColumnStretch(0, 68)
        upper.setColumnStretch(1, 32)
        root.addLayout(upper)

        # ---------------------------------------------------------------------
        # 4. ROW 3: BẢNG THIẾT BỊ (58%) & BIỂU ĐỒ LƯU LƯỢNG (42%)
        # ---------------------------------------------------------------------
        lower = QGridLayout()
        lower.setSpacing(12)
        lower.addWidget(self._device_table_panel(), 0, 0)
        lower.addWidget(self._device_traffic_panel(), 0, 1)
        lower.setColumnStretch(0, 58)
        lower.setColumnStretch(1, 42)
        root.addLayout(lower)

        self.setWidget(content)

        # Initialize default selection to Switch
        self.select_device("switch", source="internal")

    # -------------------------------------------------------------------------
    # DEVICE INSPECTOR PANEL & MINIMAP
    # -------------------------------------------------------------------------
    def _device_panel(self) -> Panel:
        panel = Panel("Thông tin thiết bị")
        panel.setObjectName("deviceDetailPanel")
        panel.box.setSpacing(8)

        # Device Header card
        header_widget = QWidget()
        header_lay = QHBoxLayout(header_widget)
        header_lay.setContentsMargins(0, 0, 0, 4)
        header_lay.setSpacing(10)

        self.detail_icon_badge = QLabel()
        self.detail_icon_badge.setFixedSize(36, 36)
        self.detail_icon_badge.setStyleSheet(
            "background: rgba(59, 130, 246, 0.16); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 8px;"
        )
        self.detail_icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_lay.addWidget(self.detail_icon_badge)

        name_box = QVBoxLayout()
        name_box.setSpacing(1)
        self.detail_name = QLabel("s1 - Open vSwitch")
        self.detail_name.setObjectName("deviceDetailName")
        name_box.addWidget(self.detail_name)

        self.detail_status = QLabel("●  Trực tuyến")
        self.detail_status.setObjectName("deviceOnline")
        name_box.addWidget(self.detail_status)
        header_lay.addLayout(name_box, stretch=1)

        panel.box.addWidget(header_widget)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #24204A; background: #24204A; max-height: 1px;")
        panel.box.addWidget(sep)

        # Properties
        self.detail_values: dict[str, QLabel] = {}
        fields = [
            ("kind", "Loại thiết bị", "Switch (Open vSwitch)"),
            ("ip", "Địa chỉ IP", "192.168.1.1"),
            ("mac", "Địa chỉ MAC", "00:00:00:00:00:01"),
            ("openflow", "Giao thức SDN", "1.3 (OVS 2.17)"),
            ("ports", "Số cổng mạng", "4 Cổng Gigabit"),
            ("flows", "Số luồng (Flows)", "1,245 flows"),
            ("incoming", "Lưu lượng vào", "125.4 Mbps"),
            ("outgoing", "Lưu lượng ra", "118.2 Mbps"),
            ("uptime", "Thời gian chạy", "2 ngày 5 giờ"),
        ]

        for key, label_text, value in fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("deviceKey")
            row.addWidget(label)
            row.addStretch()

            value_label = QLabel(value)
            value_label.setObjectName("deviceValue")
            if key == "ip":
                value_label.setStyleSheet("color: #C4B5FD; font-family: Consolas; font-weight: 700; font-size: 11px;")
            elif key == "incoming":
                value_label.setStyleSheet("color: #38BDF8; font-weight: 700; font-size: 11px;")
            elif key == "outgoing":
                value_label.setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px;")
            row.addWidget(value_label)
            panel.box.addLayout(row)
            self.detail_values[key] = value_label

        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.setContentsMargins(0, 4, 0, 4)

        detail_btn = QPushButton("Xem chi tiết")
        detail_btn.setObjectName("devicePrimaryButton")
        detail_btn.setIcon(icon("eye", "#FFFFFF", 14))
        actions.addWidget(detail_btn)

        config_btn = QPushButton("Cấu hình")
        config_btn.setObjectName("deviceButton")
        config_btn.setIcon(icon("settings", "#A78BFA", 14))
        actions.addWidget(config_btn)
        panel.box.addLayout(actions)

        # MiniMap inside panel
        mm_title = QLabel("Bản đồ thu nhỏ (MiniMap)")
        mm_title.setStyleSheet("color: #8E8BA7; font-size: 10px; font-weight: 600; padding-top: 2px;")
        panel.box.addWidget(mm_title)

        self.minimap = MiniMap()
        panel.box.addWidget(self.minimap)

        return panel

    # -------------------------------------------------------------------------
    # DEVICE TABLE PANEL
    # -------------------------------------------------------------------------
    def _device_table_panel(self) -> Panel:
        panel = Panel("Danh sách thiết bị trong mạng")

        # Badge counter in title
        badge = QLabel("7 Thiết bị")
        badge.setStyleSheet(
            "background: rgba(108, 93, 211, 0.15); color: #C4B5FD; "
            "border: 1px solid rgba(108, 93, 211, 0.35); border-radius: 8px; "
            "padding: 3px 10px; font-weight: 700; font-size: 10.5px;"
        )
        panel.box.addWidget(badge, 0, Qt.AlignmentFlag.AlignRight)

        headers = [
            "Tên thiết bị",
            "Địa chỉ IP",
            "Loại thiết bị",
            "Trạng thái",
            "Lưu lượng vào",
            "Lưu lượng ra",
            "Số kết nối",
        ]
        self.device_table = QTableWidget(len(DEVICES), len(headers))
        self.device_table.setObjectName("deviceTable")
        self.device_table.setHorizontalHeaderLabels(headers)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.setShowGrid(False)
        self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.device_table.setFixedHeight(230)
        self.device_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.device_table.setMinimumWidth(260)

        # Unified Midnight Palette Highlight
        palette = self.device_table.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2D255E"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.device_table.setPalette(palette)

        header = self.device_table.horizontalHeader()
        header.setStyleSheet(
            "QHeaderView { background: #181533; background-color: #181533; border: none; } "
            "QHeaderView::section { background: #181533; background-color: #181533; color: #8E8BA7; font-weight: 700; "
            "border: none; border-bottom: 1px solid #282452; padding: 6px 4px; font-size: 11px; }"
        )
        hpal = header.palette()
        hpal.setColor(QPalette.ColorRole.Window, QColor("#181533"))
        hpal.setColor(QPalette.ColorRole.Base, QColor("#181533"))
        hpal.setColor(QPalette.ColorRole.Button, QColor("#181533"))
        header.setPalette(hpal)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self.device_table.setColumnWidth(0, 130)
        self.device_table.setColumnWidth(1, 105)
        self.device_table.setColumnWidth(2, 95)
        self.device_table.setColumnWidth(3, 100)
        self.device_table.setColumnWidth(4, 95)
        self.device_table.setColumnWidth(5, 95)

        for r, dev in enumerate(DEVICES):
            self.device_table.setRowHeight(r, 26)
            self.device_table.setCellWidget(r, 0, make_text_cell(dev.name, "#FFFFFF", is_bold=True))
            self.device_table.setCellWidget(r, 1, make_text_cell(dev.ip, "#C4B5FD", is_mono=True))
            self.device_table.setCellWidget(r, 2, make_text_cell(dev.kind.split(" ")[0], "#94A3B8"))
            self.device_table.setCellWidget(
                r,
                3,
                make_badge_cell(
                    "● Trực tuyến", "rgba(16, 185, 129, 0.14)", "#10B981", "rgba(16, 185, 129, 0.35)"
                ),
            )
            self.device_table.setCellWidget(r, 4, make_text_cell(dev.incoming, "#38BDF8", align_center=True))
            self.device_table.setCellWidget(r, 5, make_text_cell(dev.outgoing, "#818CF8", align_center=True))
            self.device_table.setCellWidget(r, 6, make_text_cell(dev.flows, "#FBBF24", align_center=True))

        self.device_table.itemSelectionChanged.connect(self._on_table_row_selected)
        panel.box.addWidget(self.device_table)
        return panel

    def _on_table_row_selected(self) -> None:
        selected_rows = self.device_table.selectedIndexes()
        if selected_rows:
            row_idx = selected_rows[0].row()
            if 0 <= row_idx < len(DEVICES):
                dev = DEVICES[row_idx]
                self.select_device(dev.key, source="table")

    # -------------------------------------------------------------------------
    # DEVICE TRAFFIC MONITORING PANEL
    # -------------------------------------------------------------------------
    def _device_traffic_panel(self) -> Panel:
        panel = Panel("Lưu lượng mạng theo thiết bị")
        panel.box.setSpacing(6)

        # Control & Legend Top Bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 2)

        self.device_combo = QComboBox()
        self.device_combo.setObjectName("topologyCombo")
        self.device_combo.addItems([d.name for d in DEVICES])
        self.device_combo.setCurrentIndex(1)  # switch
        self.device_combo.currentIndexChanged.connect(self._on_combo_index_changed)
        top_bar.addWidget(self.device_combo)

        top_bar.addSpacing(10)

        self.traffic_in_chip = QLabel("Vào: 125.4 Mbps")
        self.traffic_in_chip.setStyleSheet(
            "background: rgba(59, 130, 246, 0.15); color: #60A5FA; "
            "border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; "
            "padding: 2px 7px; font-size: 10px; font-weight: 600;"
        )
        top_bar.addWidget(self.traffic_in_chip)

        self.traffic_out_chip = QLabel("Ra: 118.2 Mbps")
        self.traffic_out_chip.setStyleSheet(
            "background: rgba(16, 185, 129, 0.15); color: #34D399; "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; "
            "padding: 2px 7px; font-size: 10px; font-weight: 600;"
        )
        top_bar.addWidget(self.traffic_out_chip)

        top_bar.addStretch()
        top_bar.addWidget(legend_chip("#3B82F6", "Lưu lượng vào"))
        top_bar.addWidget(legend_chip("#10B981", "Lưu lượng ra"))
        panel.box.addLayout(top_bar)

        # Real-time traffic chart
        default_series, default_max, _, _ = DEVICE_TRAFFIC_SERIES["switch"]
        self.traffic_chart = Chart(
            default_series,
            default_max,
            ["14:25", "14:27", "14:29", "14:31", "14:33", "14:35"],
        )
        self.traffic_chart.setMinimumHeight(185)
        self.traffic_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.box.addWidget(self.traffic_chart)

        return panel

    def _on_combo_index_changed(self, index: int) -> None:
        if 0 <= index < len(DEVICES):
            dev = DEVICES[index]
            self.select_device(dev.key, source="combo")

    # -------------------------------------------------------------------------
    # MASTER SELECTION & SYNCHRONIZATION
    # -------------------------------------------------------------------------
    def select_device(self, key: str, source: str = "internal") -> None:
        device = next((item for item in DEVICES if item.key == key), None)
        if not device:
            return

        self.selected_key = key

        # 1. Update Canvas selection
        self.canvas.selected = key
        self.canvas.update()

        # 2. Update MiniMap selection
        if hasattr(self, "minimap"):
            self.minimap.selected = key
            self.minimap.update()

        # 3. Update Inspector Details
        self.update_details(key)

        # 4. Sync Table Row Selection
        if source != "table" and hasattr(self, "device_table"):
            self.device_table.blockSignals(True)
            for r, d in enumerate(DEVICES):
                if d.key == key:
                    self.device_table.selectRow(r)
                    break
            self.device_table.blockSignals(False)

        # 5. Sync Combo Index
        if source != "combo" and hasattr(self, "device_combo"):
            self.device_combo.blockSignals(True)
            for idx, d in enumerate(DEVICES):
                if d.key == key:
                    self.device_combo.setCurrentIndex(idx)
                    break
            self.device_combo.blockSignals(False)

        # 6. Update Traffic Chart
        if hasattr(self, "traffic_chart") and key in DEVICE_TRAFFIC_SERIES:
            series_data, max_val, inc, outg = DEVICE_TRAFFIC_SERIES[key]
            self.traffic_chart.series = series_data
            self.traffic_chart.maximum = max_val
            self.traffic_chart._baselines = [sum(vals) / max(1, len(vals)) for vals, _ in series_data]
            if hasattr(self, "traffic_in_chip"):
                self.traffic_in_chip.setText(f"Vào: {inc}")
            if hasattr(self, "traffic_out_chip"):
                self.traffic_out_chip.setText(f"Ra: {outg}")
            self.traffic_chart.update()

    def update_details(self, key: str) -> None:
        device = next((item for item in DEVICES if item.key == key), None)
        if not device:
            return

        if hasattr(self, "detail_name"):
            self.detail_name.setText(device.name)
            self.detail_values["kind"].setText(device.kind)
            self.detail_values["ip"].setText(device.ip)
            self.detail_values["mac"].setText(device.mac)
            self.detail_values["openflow"].setText(device.openflow)
            self.detail_values["ports"].setText(device.ports)
            self.detail_values["flows"].setText(device.flows)
            self.detail_values["incoming"].setText(device.incoming)
            self.detail_values["outgoing"].setText(device.outgoing)
            self.detail_values["uptime"].setText(device.uptime)

            # Update icon badge
            pix = icon(device.icon_name, device.color, 20).pixmap(20, 20)
            self.detail_icon_badge.setPixmap(pix)
            self.detail_icon_badge.setStyleSheet(
                f"background: rgba(43, 39, 87, 0.4); border: 1px solid {device.color}; border-radius: 8px;"
            )
