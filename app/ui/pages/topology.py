"""Interactive network-topology view for the AI-based Network IDS/IPS platform."""

from __future__ import annotations

import math
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QTimer
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
from app.services.network_metrics import NetworkMetricsCollector, NetworkSnapshot
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
    mac: str = "—"
    openflow: str = "Không áp dụng"
    ports: str = "—"
    flows: str = "—"
    incoming: str = "0.00 Mbps"
    outgoing: str = "0.00 Mbps"
    uptime: str = "—"
    status: str = "Không xác định"


DEVICES: list[Device] = []

DEVICE_TRAFFIC_SERIES: dict[str, tuple[list[tuple[list[float], str]], int, str, str]] = {}

TOPOLOGY_LINKS: list[tuple[str, str, str, Qt.PenStyle, str, float]] = []


def _load_operating_system_topology(snapshot: NetworkSnapshot) -> None:
    """Replace all demo topology data with interfaces reported by the OS."""
    global DEVICES, DEVICE_TRAFFIC_SERIES, TOPOLOGY_LINKS

    previous_traffic = DEVICE_TRAFFIC_SERIES
    interfaces = list(snapshot.interfaces)
    primary_ip = next((item.ip for item in interfaces if item.ip not in ("—", "127.0.0.1")), "—")
    total_in = snapshot.incoming_mbps
    total_out = snapshot.outgoing_mbps
    devices = [
        Device(
            key="local-host",
            name=socket.gethostname() or "Máy cục bộ",
            ip=primary_ip,
            kind="Máy cục bộ",
            icon_name="monitor",
            color="#8B5CF6",
            x=470,
            y=250,
            flows=f"{snapshot.active_connections:,} kết nối",
            incoming=f"{total_in:.2f} Mbps",
            outgoing=f"{total_out:.2f} Mbps",
            status="Trực tuyến" if snapshot.available else "Không có dữ liệu",
        )
    ]

    colors = ("#3B82F6", "#10B981", "#F59E0B", "#38BDF8", "#FF5B79", "#6366F1", "#14B8A6", "#A78BFA")
    links: list[tuple[str, str, str, Qt.PenStyle, str, float]] = []
    traffic: dict[str, tuple[list[tuple[list[int], str]], int, str, str]] = {}
    count = max(1, len(interfaces))
    for index, interface in enumerate(interfaces):
        angle = -math.pi / 2 + 2 * math.pi * index / count
        key = f"interface-{index}"
        color = colors[index % len(colors)]
        incoming = f"{interface.incoming_mbps:.2f} Mbps"
        outgoing = f"{interface.outgoing_mbps:.2f} Mbps"
        devices.append(
            Device(
                key=key,
                name=interface.name,
                ip=interface.ip,
                kind="Giao diện mạng hệ điều hành",
                icon_name="switch",
                color=color,
                x=470 + 330 * math.cos(angle),
                y=250 + 180 * math.sin(angle),
                mac=interface.mac,
                incoming=incoming,
                outgoing=outgoing,
                status="Trực tuyến" if interface.is_up else "Ngoại tuyến",
            )
        )
        links.append(
            (
                "local-host", key, color, Qt.PenStyle.SolidLine,
                f"Vào {incoming}\nRa {outgoing}", 2.0,
            )
        )
        previous_series = previous_traffic.get(key, ([([0.0] * 32, "#3B82F6"), ([0.0] * 32, "#10B981")], 1, "", ""))[0]
        previous_series[0][0].append(interface.incoming_mbps)
        del previous_series[0][0][0]
        previous_series[1][0].append(interface.outgoing_mbps)
        del previous_series[1][0][0]
        traffic[key] = (
            previous_series,
            max(1, int(max(max(previous_series[0][0]), max(previous_series[1][0])) * 1.25)),
            incoming,
            outgoing,
        )

    host_series = previous_traffic.get("local-host", ([([0.0] * 32, "#3B82F6"), ([0.0] * 32, "#10B981")], 1, "", ""))[0]
    host_series[0][0].append(total_in)
    del host_series[0][0][0]
    host_series[1][0].append(total_out)
    del host_series[1][0][0]
    traffic["local-host"] = (
        host_series,
        max(1, int(max(max(host_series[0][0]), max(host_series[1][0])) * 1.25)),
        f"{total_in:.2f} Mbps",
        f"{total_out:.2f} Mbps",
    )
    DEVICES = devices
    TOPOLOGY_LINKS = links
    DEVICE_TRAFFIC_SERIES = traffic


class TopologyCanvas(QWidget):
    node_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topologyCanvas")
        self.setMinimumHeight(440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.zoom = 1.0
        self.pan = QPointF(0.0, 0.0)
        self.selected = ""
        self._node_rects: dict[str, QRectF] = {}
        self._drag_origin: QPointF | None = None
        self._pan_origin = QPointF(0.0, 0.0)
        self._dragging = False
        self.setMouseTracking(True)

    def zoom_in(self) -> None:
        self._set_zoom(self.zoom * 1.15, QPointF(self.width() / 2, self.height() / 2))
        self.update()

    def zoom_out(self) -> None:
        self._set_zoom(self.zoom / 1.15, QPointF(self.width() / 2, self.height() / 2))
        self.update()

    def reset_layout(self) -> None:
        self.zoom = 1.0
        self.pan = QPointF(0.0, 0.0)
        self.update()

    def _set_zoom(self, value: float, anchor: QPointF) -> None:
        old_zoom = self.zoom
        new_zoom = max(0.45, min(2.5, value))
        if abs(new_zoom - old_zoom) < 0.0001:
            return
        center = QPointF(self.width() / 2, self.height() / 2)
        relative = anchor - center - self.pan
        self.pan = anchor - center - relative * (new_zoom / old_zoom)
        self.zoom = new_zoom

    def wheelEvent(self, event) -> None:
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        self._set_zoom(self.zoom * factor, event.position())
        self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and self._drag_origin is not None:
            self.pan = self._pan_origin + event.position() - self._drag_origin
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            event.accept()
            return
        pos = event.position()
        hovered = any(rect.contains(pos) for rect in self._node_rects.values())
        if hovered:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
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
            self._drag_origin = event.position()
            self._pan_origin = QPointF(self.pan)
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
        offset_x = (self.width() - 940 * scale) / 2 + self.pan.x()
        offset_y = (self.height() - 500 * scale) / 2 + self.pan.y()

        def point(x: float, y: float) -> QPointF:
            return QPointF(offset_x + x * scale, offset_y + y * scale)

        positions = {device.key: point(device.x, device.y) for device in DEVICES}

        # 3. Network Links
        for source, target, color_str, style, text, thickness in TOPOLOGY_LINKS:
            if source not in positions or target not in positions:
                continue
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
            status_color = "#10B981" if device.status == "Trực tuyến" else "#FF5B79"
            painter.setPen(QColor(status_color))
            st_font = QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.DemiBold)
            painter.setFont(st_font)
            painter.drawText(
                QRectF(text_x, rect.top() + 45 * scale, text_w, 16 * scale),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"● {device.status}",
            )

        # 5. Canvas interaction help.
        legend_box = QRectF(14, 14, 250, 66)
        painter.setPen(QPen(QColor("#2E2760"), 1))
        painter.setBrush(QColor(19, 17, 43, 230))
        painter.drawRoundedRect(legend_box, 10, 10)

        painter.setPen(QColor("#C4B5FD"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(24, 22, 228, 16), "ĐIỀU KHIỂN SƠ ĐỒ")
        painter.setPen(QColor("#CBD5E1"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(24, 42, 228, 18), "Kéo nền để di chuyển  •  Lăn chuột để zoom")


class MiniMap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(115)
        self.setFixedHeight(115)
        self.selected = ""

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
        for s, t, col, _style, _text, _thickness in TOPOLOGY_LINKS:
            if s not in points or t not in points:
                continue
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
        self.collector = NetworkMetricsCollector()
        self._last_snapshot = self.collector.sample()
        _load_operating_system_topology(self._last_snapshot)

        content = QWidget()
        content.setObjectName("topologyContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        self.selected_key = DEVICES[0].key if DEVICES else ""

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
            "Trực quan hóa máy cục bộ và các giao diện mạng do hệ điều hành phát hiện"
        )
        subtitle.setObjectName("topologySubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro, stretch=1)

        status_badge = QLabel("●  DỮ LIỆU HỆ ĐIỀU HÀNH")
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
        self.mode_combo.addItems(["Giao diện hệ điều hành"])
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
            MonitorMetric("Tổng số nút", f"{len(DEVICES)}", "HĐH", "#3B82F6", "nodes"),
            MonitorMetric("Giao diện trực tuyến", f"{sum(1 for item in self._last_snapshot.interfaces if item.is_up)}", "Live", "#10B981", "check"),
            MonitorMetric("Liên kết mạng", f"{len(TOPOLOGY_LINKS)}", "Cục bộ", "#8B5CF6", "switch"),
            MonitorMetric("Băng thông hiện tại", f"{self._last_snapshot.incoming_mbps + self._last_snapshot.outgoing_mbps:.2f} Mbps", "Live", "#FBBF24", "activity"),
            MonitorMetric("Cảnh báo topology", "0", "Chưa có nguồn", "#10B981", "shield"),
        ]
        self.metric_cards: list[MetricCard] = []
        for column, data in enumerate(metric_data):
            card = MetricCard(data)
            self.metric_cards.append(card)
            metrics.addWidget(card, 0, column)
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

        if DEVICES:
            self.select_device(DEVICES[0].key, source="internal")

        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.refresh_topology_data)
        self.live_timer.start(1800)

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
        self.detail_name = QLabel("Chưa chọn thiết bị")
        self.detail_name.setObjectName("deviceDetailName")
        name_box.addWidget(self.detail_name)

        self.detail_status = QLabel("●  Chưa có dữ liệu")
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
            ("kind", "Loại thiết bị", "—"),
            ("ip", "Địa chỉ IP", "—"),
            ("mac", "Địa chỉ MAC", "—"),
            ("openflow", "Giao thức SDN", "—"),
            ("ports", "Số cổng mạng", "—"),
            ("flows", "Số kết nối", "—"),
            ("incoming", "Lưu lượng vào", "0.00 Mbps"),
            ("outgoing", "Lưu lượng ra", "0.00 Mbps"),
            ("uptime", "Thời gian chạy", "—"),
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
        self.device_badge = QLabel(f"{len(DEVICES)} thiết bị")
        badge = self.device_badge
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
                    f"● {dev.status}",
                    "rgba(16, 185, 129, 0.14)" if dev.status == "Trực tuyến" else "rgba(255, 91, 121, 0.14)",
                    "#10B981" if dev.status == "Trực tuyến" else "#FF5B79",
                    "rgba(16, 185, 129, 0.35)" if dev.status == "Trực tuyến" else "rgba(255, 91, 121, 0.35)",
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
        self.device_combo.setCurrentIndex(0 if DEVICES else -1)
        self.device_combo.currentIndexChanged.connect(self._on_combo_index_changed)
        top_bar.addWidget(self.device_combo)

        top_bar.addSpacing(10)

        self.traffic_in_chip = QLabel("Vào: 0.00 Mbps")
        self.traffic_in_chip.setStyleSheet(
            "background: rgba(59, 130, 246, 0.15); color: #60A5FA; "
            "border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; "
            "padding: 2px 7px; font-size: 10px; font-weight: 600;"
        )
        top_bar.addWidget(self.traffic_in_chip)

        self.traffic_out_chip = QLabel("Ra: 0.00 Mbps")
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
        default_key = DEVICES[0].key if DEVICES else ""
        default_series, default_max, _, _ = DEVICE_TRAFFIC_SERIES.get(
            default_key,
            ([([0.0] * 32, "#3B82F6"), ([0.0] * 32, "#10B981")], 1, "0.00 Mbps", "0.00 Mbps"),
        )
        now = datetime.now()
        self.traffic_chart = Chart(
            default_series,
            default_max,
            [(now - timedelta(minutes=2 * (5 - index))).strftime("%H:%M") for index in range(6)],
        )
        self.traffic_chart.setMinimumHeight(185)
        self.traffic_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.box.addWidget(self.traffic_chart)

        return panel

    def refresh_topology_data(self) -> None:
        snapshot = self.collector.sample()
        self._last_snapshot = snapshot
        selected_key = self.selected_key
        _load_operating_system_topology(snapshot)

        total_mbps = snapshot.incoming_mbps + snapshot.outgoing_mbps
        values = (
            (f"{len(DEVICES)}", "HĐH", len(DEVICES)),
            (f"{sum(1 for item in snapshot.interfaces if item.is_up)}", "Live", len(snapshot.interfaces)),
            (f"{len(TOPOLOGY_LINKS)}", "Cục bộ", len(TOPOLOGY_LINKS)),
            (f"{total_mbps:.2f} Mbps", "Live", total_mbps),
            ("0", "Chưa có nguồn", 0.0),
        )
        for card, (value, change, spark) in zip(self.metric_cards, values):
            card.set_data(value, change, float(spark))

        self.device_badge.setText(f"{len(DEVICES)} thiết bị")
        self.device_table.blockSignals(True)
        self.device_table.clearContents()
        self.device_table.setRowCount(len(DEVICES))
        for row, device in enumerate(DEVICES):
            self.device_table.setRowHeight(row, 26)
            self.device_table.setCellWidget(row, 0, make_text_cell(device.name, "#FFFFFF", is_bold=True))
            self.device_table.setCellWidget(row, 1, make_text_cell(device.ip, "#C4B5FD", is_mono=True))
            self.device_table.setCellWidget(row, 2, make_text_cell(device.kind.split(" ")[0], "#94A3B8"))
            online = device.status == "Trực tuyến"
            self.device_table.setCellWidget(
                row, 3,
                make_badge_cell(
                    f"● {device.status}",
                    "rgba(16, 185, 129, 0.14)" if online else "rgba(255, 91, 121, 0.14)",
                    "#10B981" if online else "#FF5B79",
                    "rgba(16, 185, 129, 0.35)" if online else "rgba(255, 91, 121, 0.35)",
                ),
            )
            self.device_table.setCellWidget(row, 4, make_text_cell(device.incoming, "#38BDF8", align_center=True))
            self.device_table.setCellWidget(row, 5, make_text_cell(device.outgoing, "#818CF8", align_center=True))
            self.device_table.setCellWidget(row, 6, make_text_cell(device.flows, "#FBBF24", align_center=True))
        self.device_table.blockSignals(False)

        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItems([device.name for device in DEVICES])
        self.device_combo.blockSignals(False)

        if not any(device.key == selected_key for device in DEVICES):
            selected_key = DEVICES[0].key if DEVICES else ""
        self.selected_key = selected_key
        self.canvas.selected = selected_key
        self.canvas.update()
        self.minimap.selected = selected_key
        self.minimap.update()
        if selected_key:
            self.select_device(selected_key, source="internal")

        now = datetime.now()
        self.traffic_chart.labels = [
            (now - timedelta(minutes=2 * (5 - index))).strftime("%H:%M") for index in range(6)
        ]

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
            self.detail_status.setText(f"●  {device.status}")
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
