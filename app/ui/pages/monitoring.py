"""Live-style network monitoring page using safe simulated data."""

from __future__ import annotations

import random
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.dashboard import DonutChart, Sparkline


@dataclass(frozen=True)
class MonitorMetric:
    title: str
    value: str
    change: str
    color: str
    icon_name: str


class MetricCard(QFrame):
    def __init__(self, data: MonitorMetric, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorMetric")
        self.setMinimumHeight(108)
        box = QHBoxLayout(self)
        box.setContentsMargins(11, 12, 10, 10)
        box.setSpacing(10)
        badge = QLabel()
        badge.setObjectName("monitorMetricIcon")
        badge.setPixmap(icon(data.icon_name, data.color, 25).pixmap(25, 25))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(52, 52)
        box.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel(data.title)
        title.setObjectName("monitorMetricTitle")
        title.setWordWrap(True)
        copy.addWidget(title)
        value = QLabel(data.value)
        value.setObjectName("monitorMetricValue")
        copy.addWidget(value)
        change = QLabel(data.change)
        change.setObjectName("monitorMetricChange")
        change.setStyleSheet(f"color:{data.color};")
        copy.addWidget(change)
        copy.addStretch()
        copy.addWidget(Sparkline([2, 3, 5, 4, 8, 6, 10, 8, 13, 10, 16, 20], data.color))
        box.addLayout(copy, 1)

    def minimumSizeHint(self) -> QSize:
        return QSize(155, 108)

    def sizeHint(self) -> QSize:
        return QSize(210, 108)


class Chart(QWidget):
    def __init__(self, series: list[tuple[list[int], str]], maximum: int, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.series = series
        self.maximum = maximum
        self.labels = labels
        self.setMinimumHeight(165)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self) -> None:
        for values, _ in self.series:
            values.append(max(10, int(values[-1] * random.uniform(0.7, 1.35))))
            del values[0]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(47, 8, self.width() - 56, self.height() - 32)
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(6):
            y = chart.bottom() - chart.height() * step / 5
            painter.setPen(QColor("#8297B2"))
            painter.drawText(QRectF(0, y - 8, 39, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self.maximum * step // 5:,}")
            painter.setPen(QPen(QColor("#20364D"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
        for step, label in enumerate(self.labels):
            x = chart.left() + chart.width() * step / max(1, len(self.labels) - 1)
            painter.setPen(QColor("#8297B2"))
            painter.drawText(QRectF(x - 24, chart.bottom() + 6, 48, 17), Qt.AlignmentFlag.AlignCenter, label)
        for index, (values, color_hex) in enumerate(reversed(self.series)):
            color = QColor(color_hex)
            points = [QPointF(chart.left() + chart.width() * i / (len(values) - 1), chart.bottom() - chart.height() * min(v, self.maximum) / self.maximum) for i, v in enumerate(values)]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if index == len(self.series) - 1:
                area = QPainterPath(path)
                area.lineTo(chart.right(), chart.bottom())
                area.lineTo(chart.left(), chart.bottom())
                area.closeSubpath()
                gradient = QLinearGradient(0, chart.top(), 0, chart.bottom())
                gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 95))
                gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 3))
                painter.fillPath(area, gradient)
            painter.setPen(QPen(color, 2.0))
            painter.drawPath(path)


class Panel(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorPanel")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(13, 11, 13, 12)
        self.box.setSpacing(8)
        self.title = QLabel(title)
        self.title.setObjectName("monitorPanelTitle")
        self.box.addWidget(self.title)

    def minimumSizeHint(self) -> QSize:
        return QSize(210, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:
        return QSize(360, super().sizeHint().height())


def legend(color: str, label: str) -> QWidget:
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(5)
    dot = QLabel()
    dot.setFixedSize(14, 4)
    dot.setStyleSheet(f"background:{color}; border-radius:2px;")
    row.addWidget(dot)
    name = QLabel(label)
    name.setObjectName("monitorLegend")
    row.addWidget(name)
    return widget


class InterfaceCard(QFrame):
    def __init__(self, name: str, subtitle: str, incoming: str, outgoing: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("interfaceCard")
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        copy = QVBoxLayout()
        header = QHBoxLayout()
        name_label = QLabel(f"◉  {name} ({subtitle})")
        name_label.setObjectName("interfaceName")
        header.addWidget(name_label)
        header.addStretch()
        state = QLabel("●  Up")
        state.setObjectName("interfaceUp")
        header.addWidget(state)
        copy.addLayout(header)
        up = QLabel(f"↑  {incoming}")
        up.setObjectName("interfaceSpeed")
        down = QLabel(f"↓  {outgoing}")
        down.setObjectName("interfaceSpeed")
        copy.addWidget(up)
        copy.addWidget(down)
        root.addLayout(copy, 1)
        spark = Sparkline([5, 9, 7, 10, 6, 12, 8, 7, 11, 8, 14, 13, 18, 12, 10, 22], color)
        spark.setFixedWidth(140)
        root.addWidget(spark, 0, Qt.AlignmentFlag.AlignBottom)


class TopIpRow(QWidget):
    def __init__(self, ip: str, value: float, maximum: float, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        ip_label = QLabel(ip)
        ip_label.setObjectName("ipLabel")
        ip_label.setFixedWidth(86)
        row.addWidget(ip_label)
        bar = QProgressBar()
        bar.setObjectName("ipBar")
        bar.setRange(0, 1000)
        bar.setValue(int(value / maximum * 1000))
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        bar.setStyleSheet(f"QProgressBar#ipBar::chunk {{ background:{color}; border-radius:5px; }}")
        row.addWidget(bar, 1)
        number = QLabel(f"{value:.1f} MB")
        number.setObjectName("ipValue")
        number.setFixedWidth(60)
        number.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(number)


class MonitoringPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._paused = False

        content = QWidget()
        content.setObjectName("monitorContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 14, 20, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Giám sát mạng")
        heading.setObjectName("monitorHeading")
        heading.setMaximumWidth(430)
        intro.addWidget(heading)
        subtitle = QLabel("Theo dõi lưu lượng mạng theo thời gian thực  •  Dữ liệu mô phỏng")
        subtitle.setObjectName("monitorSubtitle")
        subtitle.setMaximumWidth(430)
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro)
        header.addStretch()
        range_label = QLabel("Khoảng thời gian:")
        range_label.setObjectName("controlLabel")
        range_label.setFixedWidth(90)
        range_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(range_label)
        self.range_combo = QComboBox()
        self.range_combo.setObjectName("monitorCombo")
        self.range_combo.addItems(["10 phút gần nhất", "30 phút gần nhất", "1 giờ gần nhất"])
        self.range_combo.setFixedWidth(150)
        header.addWidget(self.range_combo)
        self.pause_button = QPushButton("  Tạm dừng")
        self.pause_button.setObjectName("primaryMonitorButton")
        self.pause_button.setIcon(icon("pause", "#FFFFFF"))
        self.pause_button.setFixedWidth(105)
        self.pause_button.clicked.connect(self.toggle_pause)
        header.addWidget(self.pause_button)
        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("monitorButton")
        refresh.setIcon(icon("refresh", "#B8CCE4"))
        refresh.setFixedWidth(95)
        refresh.clicked.connect(self.refresh_data)
        header.addWidget(refresh)
        root.addLayout(header)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(10)
        metrics = [
            MonitorMetric("Tổng gói tin", "1,248,536", "↑ 12.5%", "#23A0FF", "activity"),
            MonitorMetric("Tổng dữ liệu", "245.6 Mbps", "↑ 8.3%", "#A958F5", "database"),
            MonitorMetric("Số kết nối đang hoạt động", "1,326", "↑ 5.1%", "#1FDC91", "nodes"),
            MonitorMetric("Lưu lượng vào (Mbps)", "145.2", "↑ 10.2%", "#FF5B5B", "arrow_up"),
            MonitorMetric("Lưu lượng ra (Mbps)", "100.4", "↑ 6.7%", "#2BA8FF", "arrow_down"),
        ]
        for column, item in enumerate(metrics):
            metric_grid.addWidget(MetricCard(item), 0, column)
            metric_grid.setColumnStretch(column, 1)
        root.addLayout(metric_grid)

        charts = QGridLayout()
        charts.setSpacing(10)
        packet_panel = Panel("Lưu lượng gói tin theo thời gian thực")
        packet_legend = QHBoxLayout()
        packet_legend.addStretch()
        for color, label_text in [("#2F9BFF", "Packets/s (Total)"), ("#19D68B", "TCP"), ("#FF9C35", "UDP"), ("#B967EB", "ICMP")]:
            packet_legend.addWidget(legend(color, label_text))
        packet_panel.box.addLayout(packet_legend)
        self.packet_chart = Chart([
            ([1050, 1420, 1160, 1480, 1210, 1700, 1310, 1600, 1580, 1850, 1410, 1250, 1900, 1510, 1840, 1580, 1100, 1450, 1510, 1680, 1490, 1880, 1550, 1930, 1690, 2200, 1720, 2050, 1650, 2010, 1510, 1700], "#2F9BFF"),
            ([760, 1040, 820, 1020, 900, 1210, 870, 1040, 850, 950, 790, 760, 1150, 1020, 1080, 900, 630, 980, 1040, 1240, 980, 1330, 1110, 1200, 1100, 1540, 1080, 1390, 950, 1320, 850, 1050], "#19D68B"),
            ([260, 420, 330, 390, 350, 510, 320, 440, 310, 470, 350, 370, 520, 430, 490, 360, 300, 410, 350, 440, 320, 510, 340, 430, 370, 600, 360, 490, 330, 520, 280, 390], "#FF9C35"),
            ([90, 150, 110, 180, 120, 220, 140, 170, 105, 160, 115, 130, 240, 170, 210, 155, 80, 170, 120, 190, 110, 210, 130, 180, 120, 260, 140, 220, 100, 190, 95, 140], "#B967EB"),
        ], 2500, ["14:25", "14:27", "14:29", "14:31", "14:33", "14:35"])
        packet_panel.box.addWidget(self.packet_chart, 1)
        charts.addWidget(packet_panel, 0, 0)

        data_panel = Panel("Lưu lượng dữ liệu theo thời gian thực")
        data_legend = QHBoxLayout()
        data_legend.addStretch()
        for color, label_text in [("#2F9BFF", "Tổng"), ("#19D68B", "Lưu lượng vào"), ("#FF9C35", "Lưu lượng ra")]:
            data_legend.addWidget(legend(color, label_text))
        data_panel.box.addLayout(data_legend)
        self.data_chart = Chart([
            ([110, 155, 150, 190, 165, 195, 165, 140, 170, 195, 245, 190, 135, 155, 130, 145, 118, 135, 127, 160, 185, 145, 130, 155, 148, 220, 165, 195, 150, 235, 185, 210], "#2F9BFF"),
            ([55, 75, 63, 58, 71, 67, 74, 78, 82, 95, 135, 108, 85, 92, 74, 99, 68, 73, 78, 110, 135, 122, 98, 129, 112, 142, 120, 137, 111, 168, 143, 151], "#19D68B"),
            ([62, 87, 70, 82, 68, 72, 78, 83, 89, 105, 151, 113, 79, 97, 68, 90, 61, 69, 72, 103, 127, 115, 92, 121, 105, 133, 113, 130, 102, 148, 89, 111], "#FF9C35"),
        ], 300, ["14:25", "14:27", "14:29", "14:31", "14:33", "14:35"])
        data_panel.box.addWidget(self.data_chart, 1)
        charts.addWidget(data_panel, 0, 1)

        protocol_panel = Panel("Phân bố giao thức")
        protocol_body = QHBoxLayout()
        protocol_body.addWidget(DonutChart([(48.2, "#2F9BFF"), (32.7, "#FF9B37"), (8.1, "#1ED28A"), (6.3, "#A24FEB"), (2.8, "#F4C440"), (1.9, "#7589B2")], "", "1,248,536", "gói tin"), 1)
        labels = QVBoxLayout()
        for color, name, value in [("#2F9BFF", "TCP", "48.2%"), ("#FF9B37", "UDP", "32.7%"), ("#1ED28A", "ICMP", "8.1%"), ("#A24FEB", "HTTP", "6.3%"), ("#F4C440", "DNS", "2.8%"), ("#7589B2", "Khác", "1.9%")]:
            line = QHBoxLayout()
            mark = QLabel()
            mark.setFixedSize(12, 12)
            mark.setStyleSheet(f"background:{color}; border-radius:3px;")
            line.addWidget(mark)
            line.addWidget(QLabel(name))
            line.addStretch()
            line.addWidget(QLabel(value))
            labels.addLayout(line)
        labels.addStretch()
        protocol_body.addLayout(labels)
        protocol_panel.box.addLayout(protocol_body, 1)
        charts.addWidget(protocol_panel, 0, 2)
        charts.setColumnStretch(0, 4)
        charts.setColumnStretch(1, 4)
        charts.setColumnStretch(2, 3)
        charts.setRowMinimumHeight(0, 245)
        root.addLayout(charts)

        lower = QGridLayout()
        lower.setSpacing(10)
        lower.addWidget(self._flow_panel(), 0, 0, 2, 3)
        lower.addWidget(self._interfaces_panel(), 0, 3)
        lower.addWidget(self._top_ip_panel(), 1, 3)
        lower.setColumnStretch(0, 1)
        lower.setColumnStretch(1, 1)
        lower.setColumnStretch(2, 1)
        lower.setColumnStretch(3, 1)
        root.addLayout(lower)
        self.setWidget(content)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1800)

    def _flow_panel(self) -> Panel:
        panel = Panel("Danh sách luồng mạng (Network Flows)")
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        search = QLineEdit()
        search.setObjectName("flowSearch")
        search.setPlaceholderText("Tìm kiếm IP, cổng, giao thức...")
        search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search)
        for text in ("Tất cả giao thức", "Tất cả trạng thái"):
            combo = QComboBox()
            combo.setObjectName("flowCombo")
            combo.addItem(text)
            toolbar.addWidget(combo)
        export = QPushButton("  Xuất CSV")
        export.setObjectName("smallMonitorButton")
        export.setIcon(icon("download", "#B8CCE4"))
        toolbar.addWidget(export)
        panel.box.addLayout(toolbar)
        rows = [
            ["#1001", "14:35:18", "192.168.1.100", "52341", "8.8.8.8", "53", "UDP", "1,245", "512 KB", "12s", "Bình thường"],
            ["#1002", "14:35:16", "10.0.0.23", "44521", "192.168.1.10", "80", "TCP", "3,452", "2.1 MB", "28s", "Bình thường"],
            ["#1003", "14:35:14", "203.113.5.21", "33567", "192.168.1.10", "443", "TCP", "8,921", "12.5 MB", "1m 12s", "Nghi vấn"],
            ["#1004", "14:35:12", "192.168.1.50", "50621", "8.8.4.4", "53", "UDP", "2,156", "986 KB", "35s", "Bình thường"],
            ["#1005", "14:35:10", "192.168.1.77", "49231", "1.1.1.1", "53", "UDP", "1,032", "421 KB", "18s", "Bình thường"],
            ["#1006", "14:35:08", "192.168.1.100", "63421", "203.113.5.21", "22", "TCP", "6,832", "8.7 MB", "55s", "Bất thường"],
            ["#1007", "14:35:05", "10.0.0.23", "38901", "192.168.1.10", "3389", "TCP", "4,215", "6.3 MB", "42s", "Bình thường"],
            ["#1008", "14:35:03", "192.168.1.50", "51234", "8.8.8.8", "53", "UDP", "1,876", "723 KB", "26s", "Bình thường"],
            ["#1009", "14:35:01", "203.113.5.21", "42105", "192.168.1.10", "80", "TCP", "9,543", "15.2 MB", "2m 3s", "Bất thường"],
            ["#1010", "14:34:59", "192.168.1.77", "49876", "1.0.0.1", "53", "UDP", "1,201", "498 KB", "21s", "Bình thường"],
        ]
        headers = ["ID", "Thời gian", "IP nguồn", "Cổng nguồn", "IP đích", "Cổng đích", "Giao thức", "Gói tin", "Dung lượng", "Thời lượng", "Trạng thái"]
        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("flowTable")
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setFixedHeight(295)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                if c == 6:
                    item.setForeground(QColor("#39AFFF" if value == "TCP" else "#FFAE40"))
                if c == 10:
                    item.setForeground(QColor("#20D98B" if value == "Bình thường" else "#FFB33C" if value == "Nghi vấn" else "#FF6262"))
                table.setItem(r, c, item)
        panel.box.addWidget(table)
        footer = QHBoxLayout()
        shown = QLabel("Hiển thị 1–10 / 1,326 luồng")
        shown.setObjectName("flowFooter")
        footer.addWidget(shown)
        footer.addStretch()
        for page in ("‹", "1", "2", "3", "4", "5", "…", "133", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            footer.addWidget(button)
        panel.box.addLayout(footer)
        return panel

    def _interfaces_panel(self) -> Panel:
        panel = Panel("Trạng thái giao diện mạng")
        panel.box.addWidget(InterfaceCard("eth0", "Mininet", "145.2 Mbps", "100.4 Mbps", "#16D787"))
        panel.box.addWidget(InterfaceCard("lo", "Loopback", "1.2 Mbps", "1.2 Mbps", "#239FFF"))
        return panel

    def _top_ip_panel(self) -> Panel:
        panel = Panel("Top 5 IP nguồn theo lưu lượng")
        for ip, value, color in [
            ("192.168.1.100", 245.6, "#2F9BFF"), ("10.0.0.23", 198.4, "#17D789"),
            ("203.113.5.21", 156.2, "#FFA23C"), ("192.168.1.77", 98.3, "#9B55E9"),
            ("192.168.1.50", 76.5, "#FFD12F"),
        ]:
            panel.box.addWidget(TopIpRow(ip, value, 245.6, color))
        return panel

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self.timer.stop()
            self.pause_button.setText("  Tiếp tục")
            self.pause_button.setIcon(icon("activity", "#FFFFFF"))
        else:
            self.timer.start(1800)
            self.pause_button.setText("  Tạm dừng")
            self.pause_button.setIcon(icon("pause", "#FFFFFF"))

    def refresh_data(self) -> None:
        self.packet_chart.refresh()
        self.data_chart.refresh()
