"""Interactive network-topology view for the desktop demo."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.monitoring import Chart, Panel, legend


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


DEVICES = [
    Device("controller", "SDN Controller", "192.168.1.10", "Controller", "server", "#FF5868", 500, 60),
    Device("switch", "s1 - Open vSwitch", "192.168.1.1", "Switch (Open vSwitch)", "switch", "#47A9FF", 500, 240),
    Device("client", "h1 - Normal Client", "192.168.1.100", "Host", "monitor", "#269FFF", 145, 240),
    Device("server", "h3 - Target Server", "192.168.1.200", "Host", "server", "#269FFF", 800, 240),
    Device("generator", "h2 - Traffic Generator", "192.168.1.150", "Host", "monitor", "#FF5868", 500, 410),
    Device("firewall", "Firewall", "192.168.1.254", "Firewall", "firewall", "#FFA235", 270, 385),
    Device("internet", "Internet", "0.0.0.0/0", "Cloud", "cloud", "#4AA8FF", 65, 400),
]


class TopologyCanvas(QWidget):
    node_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topologyCanvas")
        self.setMinimumHeight(480)
        self.zoom = 1.0
        self.selected = "switch"
        self._node_rects: dict[str, QRectF] = {}

    def zoom_in(self) -> None:
        self.zoom = min(1.35, self.zoom + 0.1)
        self.update()

    def zoom_out(self) -> None:
        self.zoom = max(0.75, self.zoom - 0.1)
        self.update()

    def reset_layout(self) -> None:
        self.zoom = 1.0
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#071829"))
        painter.setPen(QPen(QColor("#0E2940"), 1))
        for x in range(0, self.width(), 32):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 32):
            painter.drawLine(0, y, self.width(), y)

        scale = min(self.width() / 900, self.height() / 500) * self.zoom
        offset_x = (self.width() - 900 * scale) / 2
        offset_y = (self.height() - 500 * scale) / 2

        def point(x: float, y: float) -> QPointF:
            return QPointF(offset_x + x * scale, offset_y + y * scale)

        positions = {device.key: point(device.x, device.y) for device in DEVICES}
        links = [
            ("controller", "switch", "#FF4F61", Qt.PenStyle.DashLine, "OpenFlow"),
            ("client", "switch", "#18D792", Qt.PenStyle.SolidLine, "12.5 Mbps\n1,245 p/s"),
            ("switch", "server", "#20D996", Qt.PenStyle.SolidLine, "45.2 Mbps\n4,521 p/s"),
            ("switch", "generator", "#18D792", Qt.PenStyle.SolidLine, "78.6 Mbps"),
            ("internet", "firewall", "#FFA12F", Qt.PenStyle.SolidLine, "5.3 Mbps\n523 p/s"),
            ("firewall", "switch", "#50A8FF", Qt.PenStyle.SolidLine, "32.1 Mbps\n3,245 p/s"),
        ]
        for source, target, color, style, text in links:
            start, end = positions[source], positions[target]
            painter.setPen(QPen(QColor(color), max(2, int(2.5 * scale)), style))
            painter.drawLine(start, end)
            center = (start + end) / 2
            painter.setPen(QColor("#DDE8F4"))
            painter.setFont(QFont("Segoe UI", max(7, int(8 * scale))))
            painter.drawText(QRectF(center.x() - 46, center.y() - 25, 92, 40), Qt.AlignmentFlag.AlignCenter, text)

        self._node_rects.clear()
        for device in DEVICES:
            center = positions[device.key]
            card_w, card_h = 164 * scale, 68 * scale
            if device.key in ("switch", "firewall", "internet"):
                card_w = 118 * scale
            rect = QRectF(center.x() - card_w / 2, center.y() - card_h / 2, card_w, card_h)
            self._node_rects[device.key] = rect
            selected = device.key == self.selected
            painter.setPen(QPen(QColor("#65B9FF") if selected else QColor(device.color), 2.2 if selected else 1.4))
            painter.setBrush(QColor("#102940") if device.color == "#269FFF" else QColor("#182337"))
            painter.drawRoundedRect(rect, 10, 10)
            icon_rect = QRectF(rect.left() + 8 * scale, rect.top() + 8 * scale, 50 * scale, 50 * scale)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(device.color).darker(180))
            painter.drawRoundedRect(icon_rect, 9, 9)
            icon(device.icon_name, device.color, 27).paint(painter, icon_rect.toRect())
            painter.setPen(QColor("#F0F5FA"))
            name_font = QFont("Segoe UI", max(8, int(9 * scale)))
            name_font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(name_font)
            painter.drawText(QRectF(icon_rect.right() + 8, rect.top() + 8, rect.right() - icon_rect.right() - 12, 18 * scale), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, device.name)
            painter.setFont(QFont("Segoe UI", max(7, int(8 * scale))))
            painter.setPen(QColor("#AFC0D4"))
            painter.drawText(QRectF(icon_rect.right() + 8, rect.top() + 27 * scale, rect.right() - icon_rect.right() - 12, 16 * scale), device.ip)
            painter.setPen(QColor("#1DDB91"))
            painter.drawText(QRectF(icon_rect.right() + 8, rect.top() + 44 * scale, rect.right() - icon_rect.right() - 12, 16 * scale), "● Online")

        legend_box = QRectF(10, 10, 220, 138)
        painter.setPen(QPen(QColor("#1D3A54"), 1))
        painter.setBrush(QColor(8, 27, 44, 235))
        painter.drawRoundedRect(legend_box, 8, 8)
        painter.setFont(QFont("Segoe UI", 8))
        for index, (color, text, style) in enumerate([
            ("#18D792", "Lưu lượng bình thường", Qt.PenStyle.SolidLine),
            ("#FF4F61", "Lưu lượng bất thường", Qt.PenStyle.SolidLine),
            ("#FF4F61", "Kết nối điều khiển (OpenFlow)", Qt.PenStyle.DashLine),
            ("#269FFF", "Kết nối mạng", Qt.PenStyle.SolidLine),
            ("#FFA12F", "Kết nối Internet", Qt.PenStyle.SolidLine),
        ]):
            y = 29 + index * 24
            painter.setPen(QPen(QColor(color), 3, style))
            painter.drawLine(23, y, 52, y)
            painter.setPen(QColor("#AFC0D4"))
            painter.drawText(QRectF(63, y - 9, 155, 18), text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            for key, rect in self._node_rects.items():
                if rect.contains(event.position()):
                    self.selected = key
                    self.node_selected.emit(key)
                    self.update()
                    event.accept()
                    return
        super().mousePressEvent(event)


class MiniMap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(82)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#071829"))
        points = {d.key: QPointF(18 + d.x / 900 * (self.width() - 36), 8 + d.y / 500 * (self.height() - 16)) for d in DEVICES}
        for source, target, color in [("controller", "switch", "#FF4F61"), ("client", "switch", "#18D792"), ("switch", "server", "#18D792"), ("switch", "generator", "#18D792"), ("internet", "firewall", "#FFA12F"), ("firewall", "switch", "#269FFF")]:
            painter.setPen(QPen(QColor(color), 1.2))
            painter.drawLine(points[source], points[target])
        for device in DEVICES:
            painter.setBrush(QColor(device.color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(points[device.key], 6, 6)
        painter.setPen(QPen(QColor("#4B8DC7"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(8, 6, -8, -6))


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
        root.setSpacing(10)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Sơ đồ mạng")
        heading.setObjectName("topologyHeading")
        heading.setMaximumWidth(500)
        intro.addWidget(heading)
        subtitle = QLabel("Trực quan hóa topology mạng, trạng thái thiết bị và lưu lượng thời gian thực  •  Dữ liệu mô phỏng")
        subtitle.setObjectName("topologySubtitle")
        subtitle.setMaximumWidth(500)
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro)
        header.addStretch()
        mode_label = QLabel("Chế độ hiển thị:")
        mode_label.setFixedWidth(82)
        header.addWidget(mode_label)
        mode = QComboBox()
        mode.setObjectName("topologyCombo")
        mode.addItems(["Topology", "Logical", "Physical"])
        mode.setFixedWidth(112)
        header.addWidget(mode)
        arrange = QPushButton("Tự động sắp xếp")
        arrange.setObjectName("arrangeButton")
        arrange.setFixedWidth(112)
        header.addWidget(arrange)
        zoom_out = QPushButton()
        zoom_out.setObjectName("topologyTool")
        zoom_out.setIcon(icon("search", "#9FC4E7"))
        header.addWidget(zoom_out)
        zoom_in = QPushButton("+")
        zoom_in.setObjectName("topologyTool")
        header.addWidget(zoom_in)
        expand = QPushButton()
        expand.setObjectName("topologyTool")
        expand.setIcon(icon("expand", "#9FC4E7"))
        header.addWidget(expand)
        root.addLayout(header)

        upper = QGridLayout()
        upper.setSpacing(10)
        self.canvas = TopologyCanvas()
        self.canvas.node_selected.connect(self.update_details)
        arrange.clicked.connect(self.canvas.reset_layout)
        zoom_out.clicked.connect(self.canvas.zoom_out)
        zoom_in.clicked.connect(self.canvas.zoom_in)
        upper.addWidget(self.canvas, 0, 0, 2, 3)
        upper.addWidget(self._device_panel(), 0, 3)
        overview = Panel("Bản đồ tổng quan")
        overview.box.addWidget(MiniMap())
        upper.addWidget(overview, 1, 3)
        upper.setColumnStretch(0, 1)
        upper.setColumnStretch(1, 1)
        upper.setColumnStretch(2, 1)
        upper.setColumnStretch(3, 1)
        upper.setRowStretch(0, 3)
        upper.setRowStretch(1, 1)
        root.addLayout(upper)

        lower = QGridLayout()
        lower.setSpacing(10)
        lower.addWidget(self._device_table_panel(), 0, 0, 1, 3)
        traffic = Panel("Lưu lượng mạng theo thiết bị")
        selector = QComboBox()
        selector.setObjectName("topologyCombo")
        selector.addItems([device.name for device in DEVICES])
        selector.setCurrentIndex(1)
        traffic.box.addWidget(selector, 0, Qt.AlignmentFlag.AlignRight)
        chart_legend = QHBoxLayout()
        chart_legend.addStretch()
        chart_legend.addWidget(legend("#2196F3", "Lưu lượng vào"))
        chart_legend.addWidget(legend("#17D68A", "Lưu lượng ra"))
        traffic.box.addLayout(chart_legend)
        traffic.box.addWidget(Chart([
            ([98, 119, 151, 134, 166, 188, 163, 132, 147, 159, 171, 152, 183, 207, 161, 133, 155, 178, 169, 197, 189, 252, 196, 156, 179, 185, 197, 166, 148, 176, 142, 161], "#2196F3"),
            ([67, 88, 112, 97, 126, 135, 118, 104, 119, 127, 131, 114, 126, 112, 106, 96, 111, 102, 115, 101, 90, 151, 119, 96, 110, 123, 115, 98, 104, 121, 95, 116], "#17D68A"),
        ], 300, ["14:25", "14:27", "14:29", "14:31", "14:33", "14:35"]), 1)
        lower.addWidget(traffic, 0, 3)
        lower.setColumnStretch(0, 1)
        lower.setColumnStretch(1, 1)
        lower.setColumnStretch(2, 1)
        lower.setColumnStretch(3, 1)
        lower.setRowMinimumHeight(0, 260)
        root.addLayout(lower)
        self.setWidget(content)

    def _device_panel(self) -> Panel:
        panel = Panel("Thông tin thiết bị")
        panel.setObjectName("deviceDetailPanel")
        self.detail_name = QLabel("s1 - Open vSwitch")
        self.detail_name.setObjectName("deviceDetailName")
        panel.box.addWidget(self.detail_name)
        self.detail_status = QLabel("●  Online")
        self.detail_status.setObjectName("deviceOnline")
        panel.box.addWidget(self.detail_status)
        self.detail_values: dict[str, QLabel] = {}
        fields = [("kind", "Loại thiết bị", "Switch (Open vSwitch)"), ("ip", "Địa chỉ IP", "192.168.1.1"), ("mac", "MAC Address", "00:00:00:00:00:01"), ("openflow", "OpenFlow", "1.3"), ("ports", "Số cổng", "4"), ("flows", "Số flow hiện tại", "1,245"), ("incoming", "Lưu lượng vào", "125.4 Mbps"), ("outgoing", "Lưu lượng ra", "118.2 Mbps"), ("uptime", "Uptime", "2 ngày 5 giờ 32 phút")]
        for key, label_text, value in fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("deviceKey")
            row.addWidget(label)
            row.addStretch()
            value_label = QLabel(value)
            value_label.setObjectName("deviceValue")
            row.addWidget(value_label)
            panel.box.addLayout(row)
            self.detail_values[key] = value_label
        panel.box.addStretch()
        actions = QHBoxLayout()
        detail = QPushButton("Xem chi tiết")
        detail.setObjectName("devicePrimaryButton")
        actions.addWidget(detail)
        config = QPushButton("Cấu hình")
        config.setObjectName("deviceButton")
        actions.addWidget(config)
        panel.box.addLayout(actions)
        return panel

    def _device_table_panel(self) -> Panel:
        panel = Panel("Danh sách thiết bị trong mạng")
        rows = [
            ["SDN Controller", "192.168.1.10", "Controller", "● Online", "1.2 Mbps", "1.1 Mbps", "5"],
            ["s1 - Open vSwitch", "192.168.1.1", "Switch", "● Online", "125.4 Mbps", "118.2 Mbps", "1,245"],
            ["h1 - Normal Client", "192.168.1.100", "Host", "● Online", "12.5 Mbps", "1.3 Mbps", "245"],
            ["h2 - Traffic Generator", "192.168.1.150", "Host", "● Online", "78.6 Mbps", "5.4 Mbps", "632"],
            ["h3 - Target Server", "192.168.1.200", "Host", "● Online", "45.2 Mbps", "82.1 Mbps", "521"],
            ["Firewall", "192.168.1.254", "Firewall", "● Online", "32.1 Mbps", "28.4 Mbps", "324"],
            ["Internet", "0.0.0.0/0", "Cloud", "● Online", "5.3 Mbps", "4.8 Mbps", "156"],
        ]
        headers = ["Tên thiết bị", "Địa chỉ IP", "Loại thiết bị", "Trạng thái", "Lưu lượng vào", "Lưu lượng ra", "Số kết nối"]
        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("deviceTable")
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setFixedHeight(220)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                if c == 3:
                    item.setForeground(QColor("#1DDB91"))
                table.setItem(r, c, item)
        table.selectRow(1)
        panel.box.addWidget(table)
        return panel

    def update_details(self, key: str) -> None:
        device = next(item for item in DEVICES if item.key == key)
        self.detail_name.setText(device.name)
        self.detail_values["kind"].setText(device.kind)
        self.detail_values["ip"].setText(device.ip)
        defaults = {
            "controller": ("3", "5", "1.2 Mbps", "1.1 Mbps"), "switch": ("4", "1,245", "125.4 Mbps", "118.2 Mbps"),
            "client": ("1", "245", "12.5 Mbps", "1.3 Mbps"), "server": ("2", "521", "45.2 Mbps", "82.1 Mbps"),
            "generator": ("2", "632", "78.6 Mbps", "5.4 Mbps"), "firewall": ("4", "324", "32.1 Mbps", "28.4 Mbps"),
            "internet": ("1", "156", "5.3 Mbps", "4.8 Mbps"),
        }
        ports, flows, incoming, outgoing = defaults[key]
        self.detail_values["ports"].setText(ports)
        self.detail_values["flows"].setText(flows)
        self.detail_values["incoming"].setText(incoming)
        self.detail_values["outgoing"].setText(outgoing)
