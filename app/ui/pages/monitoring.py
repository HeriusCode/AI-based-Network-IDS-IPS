"""Live-style network monitoring page using safe simulated data."""

from __future__ import annotations

import random
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
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
from app.ui.pages.dashboard import (
    DonutChart,
    Sparkline,
    make_badge_cell,
    make_text_cell,
    protocol_bar_row,
)


@dataclass(frozen=True)
class MonitorMetric:
    title: str
    value: str
    change: str
    color: str
    icon_name: str


class MetricCard(QFrame):
    """Clean, balanced KPI card matching the modern Dashboard style."""

    def __init__(self, data: MonitorMetric, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorMetric")
        self.setFixedHeight(84)
        self.setMinimumWidth(130)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(8)

        # 1. Subtle, neutral icon container
        badge = QLabel()
        badge.setObjectName("metricIcon")
        badge.setStyleSheet("background: #232047; border: 1px solid #322D60; border-radius: 9px;")
        badge.setPixmap(icon(data.icon_name, "#9E9BB5", 16).pixmap(16, 16))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(36, 36)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Center: Title + Prominent Bold White Digits
        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(2)
        center.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = QLabel(data.title)
        title.setObjectName("monitorMetricTitle")
        title.setStyleSheet("color: #9E9BB5; font-size: 11px; font-weight: 500;")
        center.addWidget(title)

        val_lbl = QLabel(data.value)
        val_lbl.setObjectName("monitorMetricValue")
        val_lbl.setStyleSheet("color: #FFFFFF; font-size: 19px; font-weight: 700; letter-spacing: -0.3px;")
        center.addWidget(val_lbl)

        layout.addLayout(center, 1)

        # 3. Right: Trend pill on top + Sparkline below
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        pill = QLabel(data.change)
        pill.setObjectName("monitorMetricChange")
        pill.setStyleSheet(
            f"color: {data.color}; background: rgba(255, 255, 255, 0.06); border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
        )
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(pill, 0, Qt.AlignmentFlag.AlignRight)

        spark = Sparkline([2, 4, 3, 7, 5, 9, 7, 12, 9, 14, 10, 18], data.color)
        spark.setFixedSize(46, 18)
        right.addWidget(spark, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)


class Chart(QWidget):
    """Dynamic real-time wave chart with gradient fill and dash gridlines."""

    def __init__(self, series: list[tuple[list[int], str]], maximum: int, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.series = series
        self.maximum = maximum
        self.labels = labels
        # Calculate baseline (mean) for each series for natural mean-reverting oscillation
        self._baselines = [sum(vals) / max(1, len(vals)) for vals, _ in self.series]
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self) -> None:
        for i, (values, _) in enumerate(self.series):
            base = values[-1]
            baseline = self._baselines[i]
            # Mean-reverting pull towards natural baseline + organic noise
            pull = (baseline - base) * 0.22
            jitter = random.uniform(-0.11, 0.11) * self.maximum
            new_val = int(base + pull + jitter)
            # Safe clamp well inside bounds (14% - 85%) to prevent flatlining against ceiling
            low = int(self.maximum * 0.14)
            high = int(self.maximum * 0.85)
            new_val = max(low, min(high, new_val))
            values.append(new_val)
            del values[0]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        left_m = 48
        right_m = 32
        top_m = 18
        bottom_m = 34
        chart = QRectF(left_m, top_m, self.width() - left_m - right_m, self.height() - top_m - bottom_m)
        painter.setFont(QFont("Segoe UI", 8))

        # Horizontal dashed gridlines
        for step in range(6):
            y = chart.bottom() - chart.height() * step / 5
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(0, y - 8, left_m - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self.maximum * step // 5:,}")
            painter.setPen(QPen(QColor("#282452"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

        # Time labels on X-axis (evenly distributed, guaranteed not to clip right edge)
        for step, label in enumerate(self.labels):
            x = chart.left() + chart.width() * step / max(1, len(self.labels) - 1)
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(x - 28, chart.bottom() + 6, 56, 18), Qt.AlignmentFlag.AlignCenter, label)

        # Draw series wave paths with smooth gradients
        for index, (values, color_hex) in enumerate(reversed(self.series)):
            color = QColor(color_hex)
            points = [
                QPointF(
                    chart.left() + chart.width() * i / (len(values) - 1),
                    chart.bottom() - chart.height() * min(v, self.maximum) / self.maximum,
                )
                for i, v in enumerate(values)
            ]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)

            if index == len(self.series) - 1:
                area = QPainterPath(path)
                area.lineTo(chart.right(), chart.bottom())
                area.lineTo(chart.left(), chart.bottom())
                area.closeSubpath()
                gradient = QLinearGradient(0, chart.top(), 0, chart.bottom())
                gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 75))
                gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 2))
                painter.fillPath(area, gradient)

            painter.setPen(QPen(color, 2.0))
            painter.drawPath(path)


class Panel(QFrame):
    """Main card container for monitoring blocks."""

    def __init__(self, title: str, subtitle: str = "", extra_header: QWidget | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorPanel")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(16, 12, 16, 14)
        self.box.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        left_box = QVBoxLayout()
        left_box.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("monitorPanelTitle")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13.5px; font-weight: 700;")
        left_box.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("monitorPanelSubtitle")
            sub_label.setStyleSheet("color: #8E8BA7; font-size: 11px; font-weight: 400;")
            left_box.addWidget(sub_label)

        header_layout.addLayout(left_box, 1)

        if extra_header:
            header_layout.addWidget(extra_header, 0, Qt.AlignmentFlag.AlignVCenter)

        self.box.addLayout(header_layout)


def legend_chip(color: str, label: str) -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
    lay.addWidget(dot)
    text = QLabel(label)
    text.setStyleSheet("color: #9E9BB5; font-size: 11px; font-weight: 500;")
    lay.addWidget(text)
    return row


# Backward-compatible alias for other pages importing legend
legend = legend_chip


class InterfaceCard(QFrame):
    """Network Interface card with bandwidth rates and sparkline."""

    def __init__(self, name: str, subtitle: str, incoming: str, outgoing: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("interfaceCard")
        self.setStyleSheet("""
            QFrame#interfaceCard {
                background: #14122A;
                border: 1px solid #282452;
                border-radius: 10px;
            }
            QFrame#interfaceCard:hover {
                border-color: #6C5DD3;
                background: #1A1738;
            }
        """)
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(10)

        copy = QVBoxLayout()
        copy.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(6)
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")
        header.addWidget(name_label)

        sub = QLabel(f"({subtitle})")
        sub.setStyleSheet("color: #8E8BA7; font-size: 11px;")
        header.addWidget(sub)

        header.addStretch()

        state = QLabel("●  Up")
        state.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: 700;"
        )
        header.addWidget(state)
        copy.addLayout(header)

        speeds = QHBoxLayout()
        speeds.setSpacing(10)
        up = QLabel(f"↑  {incoming}")
        up.setStyleSheet("color: #A78BFA; font-size: 11px; font-weight: 600;")
        down = QLabel(f"↓  {outgoing}")
        down.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 600;")
        speeds.addWidget(up)
        speeds.addWidget(down)
        speeds.addStretch()
        copy.addLayout(speeds)

        root.addLayout(copy, 1)

        spark = Sparkline([5, 9, 7, 10, 6, 12, 8, 7, 11, 8, 14, 13, 18, 12, 10, 22], color)
        spark.setFixedSize(65, 22)
        root.addWidget(spark, 0, Qt.AlignmentFlag.AlignVCenter)


class TopIpRow(QWidget):
    """Ranked top IP row with progress bar and bandwidth."""

    def __init__(self, rank: int, ip: str, value: float, maximum: float, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(8)

        rank_lbl = QLabel(f"#{rank}")
        rank_lbl.setFixedWidth(22)
        rank_lbl.setStyleSheet("color: #8E8BA7; font-size: 11px; font-weight: 600;")
        row.addWidget(rank_lbl)

        ip_label = QLabel(ip)
        ip_label.setFixedWidth(102)
        ip_label.setStyleSheet("color: #FFFFFF; font-family: 'Consolas', monospace; font-size: 11px; font-weight: 600;")
        row.addWidget(ip_label)

        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(int(value / maximum * 1000))
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: #25224D;
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 2px;
            }}
        """)
        row.addWidget(bar, 1)

        number = QLabel(f"{value:.1f} MB")
        number.setFixedWidth(64)
        number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        number.setStyleSheet("color: #CBD5E1; font-size: 11px; font-weight: 600;")
        row.addWidget(number)


class MonitoringPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._paused = False

        content = QWidget()
        content.setObjectName("monitorContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 12, 18, 16)
        root.setSpacing(12)

        # 1. Header & Live Controls
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 2)
        header.setSpacing(12)

        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Giám sát mạng")
        heading.setObjectName("monitorHeading")
        heading.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;")
        intro.addWidget(heading)

        subtitle = QLabel("Theo dõi lưu lượng mạng theo thời gian thực  •  Dữ liệu trực tiếp & Mô phỏng AI")
        subtitle.setObjectName("monitorSubtitle")
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
        header.addLayout(intro, 1)

        # Controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        live_badge = QLabel("●  LIVE MONITORING")
        live_badge.setObjectName("liveBadge")
        live_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;"
        )
        controls.addWidget(live_badge)

        self.range_combo = QComboBox()
        self.range_combo.setObjectName("monitorCombo")
        self.range_combo.addItems(["10 phút gần nhất", "30 phút gần nhất", "1 giờ gần nhất"])
        self.range_combo.setFixedWidth(140)
        controls.addWidget(self.range_combo)

        self.pause_button = QPushButton("  Tạm dừng")
        self.pause_button.setObjectName("primaryMonitorButton")
        self.pause_button.setIcon(icon("pause", "#FFFFFF", 14))
        self.pause_button.setFixedWidth(110)
        self.pause_button.clicked.connect(self.toggle_pause)
        controls.addWidget(self.pause_button)

        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("monitorButton")
        refresh.setIcon(icon("refresh", "#B8CCE4", 14))
        refresh.setFixedWidth(100)
        refresh.clicked.connect(self.refresh_data)
        controls.addWidget(refresh)

        header.addLayout(controls)
        root.addLayout(header)

        # 2. Hàng 1: 5 Thẻ chỉ số băng thông cốt lõi (Trải đều, chữ số trắng to nổi bật, icon tối giản tinh tế)
        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(10)
        metric_grid.setVerticalSpacing(10)
        metrics = [
            MonitorMetric("Tổng gói tin", "1,248,536", "↑ 12.5%", "#8B5CF6", "box"),
            MonitorMetric("Tổng dữ liệu", "245.6 Mbps", "↑ 8.3%", "#A78BFA", "nodes"),
            MonitorMetric("Kết nối hoạt động", "1,326", "↑ 5.1%", "#10B981", "nodes"),
            MonitorMetric("Lưu lượng vào", "145.2 Mbps", "↑ 10.2%", "#FF5B79", "trend"),
            MonitorMetric("Lưu lượng ra", "100.4 Mbps", "↑ 6.7%", "#34D399", "trend"),
        ]
        for col_idx, item in enumerate(metrics):
            metric_grid.addWidget(MetricCard(item), 0, col_idx)
            metric_grid.setColumnStretch(col_idx, 1)
        root.addLayout(metric_grid)

        # 3. Hàng 2: 2 Biểu đồ sóng lưu lượng thời gian thực (50% : 50% - Cân đối vừa vặn khung nhìn)
        charts = QGridLayout()
        charts.setSpacing(12)

        # Biểu đồ 1: Lưu lượng gói tin (Packets/s)
        pkt_extra = QWidget()
        pkt_lay = QHBoxLayout(pkt_extra)
        pkt_lay.setContentsMargins(0, 0, 0, 0)
        pkt_lay.setSpacing(8)
        pkt_lay.addWidget(legend_chip("#8B5CF6", "Total"))
        pkt_lay.addWidget(legend_chip("#10B981", "TCP"))
        pkt_lay.addWidget(legend_chip("#FF8A4C", "UDP"))
        pkt_lay.addWidget(legend_chip("#C4B5FD", "ICMP"))
        pkt_badge = QLabel("2,050 pps")
        pkt_badge.setObjectName("panelChip")
        pkt_badge.setStyleSheet(
            "color: #8B5CF6; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        pkt_lay.addWidget(pkt_badge)

        packet_panel = Panel("Lưu lượng gói tin theo thời gian thực", "Tốc độ truyền gói tin trên giây (Packets/s) theo giao thức", pkt_extra)
        self.packet_chart = Chart([
            ([1050, 1420, 1160, 1480, 1210, 1700, 1310, 1600, 1580, 1850, 1410, 1250, 1900, 1510, 1840, 1580, 1100, 1450, 1510, 1680, 1490, 1880, 1550, 1930, 1690, 2200, 1720, 2050, 1650, 2010, 1510, 1700], "#8B5CF6"),
            ([760, 1040, 820, 1020, 900, 1210, 870, 1040, 850, 950, 790, 760, 1150, 1020, 1080, 900, 630, 980, 1040, 1240, 980, 1330, 1110, 1200, 1100, 1540, 1080, 1390, 950, 1320, 850, 1050], "#10B981"),
            ([260, 420, 330, 390, 350, 510, 320, 440, 310, 470, 350, 370, 520, 430, 490, 360, 300, 410, 350, 440, 320, 510, 340, 430, 370, 600, 360, 490, 330, 520, 280, 390], "#FF8A4C"),
            ([90, 150, 110, 180, 120, 220, 140, 170, 105, 160, 115, 130, 240, 170, 210, 155, 80, 170, 120, 190, 110, 210, 130, 180, 120, 260, 140, 220, 100, 190, 95, 140], "#C4B5FD"),
        ], 2500, ["14:25", "14:27", "14:29", "14:31", "14:33", "14:35"])
        self.packet_chart.setFixedHeight(380)
        packet_panel.box.addWidget(self.packet_chart, 1)
        charts.addWidget(packet_panel, 0, 0)

        # Biểu đồ 2: Lưu lượng dữ liệu (Throughput Mbps)
        data_extra = QWidget()
        data_lay = QHBoxLayout(data_extra)
        data_lay.setContentsMargins(0, 0, 0, 0)
        data_lay.setSpacing(8)
        data_lay.addWidget(legend_chip("#8B5CF6", "Tổng"))
        data_lay.addWidget(legend_chip("#10B981", "Vào"))
        data_lay.addWidget(legend_chip("#FF8A4C", "Ra"))
        data_badge = QLabel("245.6 Mbps")
        data_badge.setObjectName("panelChip")
        data_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        data_lay.addWidget(data_badge)

        data_panel = Panel("Lưu lượng dữ liệu theo thời gian thực", "Băng thông thông lượng mạng (Throughput Mbps)", data_extra)
        self.data_chart = Chart([
            ([110, 155, 150, 190, 165, 195, 165, 140, 170, 195, 245, 190, 135, 155, 130, 145, 118, 135, 127, 160, 185, 145, 130, 155, 148, 220, 165, 195, 150, 235, 185, 210], "#8B5CF6"),
            ([55, 75, 63, 58, 71, 67, 74, 78, 82, 95, 135, 108, 85, 92, 74, 99, 68, 73, 78, 110, 135, 122, 98, 129, 112, 142, 120, 137, 111, 168, 143, 151], "#10B981"),
            ([62, 87, 70, 82, 68, 72, 78, 83, 89, 105, 151, 113, 79, 97, 68, 90, 61, 69, 72, 103, 127, 115, 92, 121, 105, 133, 113, 130, 102, 148, 89, 111], "#FF8A4C"),
        ], 300, ["14:25", "14:27", "14:29", "14:31", "14:33", "14:35"])
        self.data_chart.setFixedHeight(380)
        data_panel.box.addWidget(self.data_chart, 1)
        charts.addWidget(data_panel, 0, 1)

        charts.setColumnStretch(0, 1)
        charts.setColumnStretch(1, 1)
        root.addLayout(charts)

        # 4. Hàng 3: 3 Khối phân tích chuyên sâu (Giao thức, Card mạng, Top 5 IP)
        row3 = QGridLayout()
        row3.setSpacing(12)

        # 4.1 Phân bố giao thức
        proto_badge = QLabel("6 Loại")
        proto_badge.setObjectName("panelChip")
        proto_badge.setStyleSheet(
            "color: #60A5FA; background: rgba(96, 165, 250, 0.15); "
            "border: 1px solid rgba(96, 165, 250, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        protocol_panel = Panel("Phân bố giao thức", "Tỷ trọng các giao thức truyền tải", proto_badge)
        proto_body = QHBoxLayout()
        proto_body.setSpacing(10)
        proto_body.addWidget(
            DonutChart(
                [(48.2, "#2F9BFF"), (32.7, "#FF9B37"), (8.1, "#1ED28A"), (6.3, "#9551E8"), (2.8, "#F4C440"), (1.9, "#7671BF")],
                "Giao thức", "6 loại", "1.25M gói"
            ),
            1,
        )
        proto_legend = QVBoxLayout()
        proto_legend.setSpacing(3)
        for color, name, value, percent in [
            ("#2F9BFF", "TCP", "48.2%", 48.2),
            ("#FF9B37", "UDP", "32.7%", 32.7),
            ("#1ED28A", "ICMP", "8.1%", 8.1),
            ("#9551E8", "HTTP", "6.3%", 6.3),
            ("#F4C440", "DNS", "2.8%", 2.8),
            ("#7671BF", "Khác", "1.9%", 1.9),
        ]:
            proto_legend.addWidget(protocol_bar_row(color, name, value, percent))
        proto_legend.addStretch()
        proto_body.addLayout(proto_legend, 1)
        protocol_panel.box.addLayout(proto_body, 1)
        row3.addWidget(protocol_panel, 0, 0)

        # 4.2 Trạng thái giao diện mạng
        row3.addWidget(self._interfaces_panel(), 0, 1)

        # 4.3 Top 5 IP nguồn
        row3.addWidget(self._top_ip_panel(), 0, 2)

        row3.setColumnStretch(0, 4)
        row3.setColumnStretch(1, 3)
        row3.setColumnStretch(2, 3)
        root.addLayout(row3)

        # 5. Hàng 4: Danh sách luồng mạng (Network Flows Table) - Trải rộng toàn phần
        root.addWidget(self._flow_panel())

        self.setWidget(content)

        # Dynamic simulation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1800)

    def _flow_panel(self) -> Panel:
        panel_chip = QLabel("Live 10 Flows")
        panel_chip.setObjectName("panelChip")
        panel_chip.setStyleSheet("color: #C4B5FD; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;")
        panel = Panel("Danh sách luồng mạng (Network Flows)", "Nhật ký phiên kết nối mạng L4/L7 thời gian thực", panel_chip)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 4)
        toolbar.setSpacing(8)

        search = QLineEdit()
        search.setObjectName("flowSearch")
        search.setPlaceholderText("Tìm kiếm IP, cổng, giao thức...")
        search.addAction(icon("search", "#8299B7", 14), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search, 1)

        for text, items in [
            ("Giao thức", ["Tất cả giao thức", "TCP", "UDP", "ICMP"]),
            ("Trạng thái", ["Tất cả trạng thái", "Bình thường", "Nghi vấn", "Bất thường"]),
        ]:
            combo = QComboBox()
            combo.setObjectName("flowCombo")
            combo.addItems(items)
            toolbar.addWidget(combo)

        export = QPushButton("  Xuất CSV")
        export.setObjectName("smallMonitorButton")
        export.setIcon(icon("download", "#B8CCE4", 13))
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
        headers = ["ID", "Thời gian", "IP nguồn", "Cổng N", "IP đích", "Cổng Đ", "Giao thức", "Gói tin", "Dung lượng", "Thời lượng", "Trạng thái"]

        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("dashboardTable")
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(430)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            if c in (0, 1, 3, 5, 6, 7, 8, 9, 10):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setHorizontalHeaderItem(c, item)

        header = table.horizontalHeader()
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
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Interactive)

        table.setColumnWidth(0, 65)   # ID
        table.setColumnWidth(1, 80)   # Thời gian
        # Col 2: Stretch (IP nguồn)
        table.setColumnWidth(3, 70)   # Cổng N
        # Col 4: Stretch (IP đích)
        table.setColumnWidth(5, 70)   # Cổng Đ
        table.setColumnWidth(6, 85)   # Giao thức
        table.setColumnWidth(7, 75)   # Gói tin
        table.setColumnWidth(8, 90)   # Dung lượng
        table.setColumnWidth(9, 80)   # Thời lượng
        table.setColumnWidth(10, 115) # Trạng thái ("Bình thường", "Nghi vấn", "Bất thường")

        status_colors = {
            "Bình thường": ("rgba(16, 185, 129, 0.18)", "#6EE7B7", "rgba(16, 185, 129, 0.35)"),
            "Nghi vấn": ("rgba(251, 191, 36, 0.18)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
            "Bất thường": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
        }

        proto_colors = {
            "TCP": ("rgba(47, 155, 255, 0.18)", "#60A5FA", "rgba(47, 155, 255, 0.35)"),
            "UDP": ("rgba(255, 155, 55, 0.18)", "#FDBA74", "rgba(255, 155, 55, 0.35)"),
            "ICMP": ("rgba(149, 81, 232, 0.18)", "#C4B5FD", "rgba(149, 81, 232, 0.35)"),
        }

        for r, row in enumerate(rows):
            table.setRowHeight(r, 38)

            # Col 0: ID
            table.setCellWidget(r, 0, make_text_cell(row[0], color="#8E8BA7", align_center=True))

            # Col 1: Thời gian
            table.setCellWidget(r, 1, make_text_cell(row[1], color="#CBD5E1", align_center=True))

            # Col 2: IP nguồn
            table.setCellWidget(r, 2, make_text_cell(row[2], color="#FFFFFF", is_mono=True, is_bold=True))

            # Col 3: Cổng nguồn
            table.setCellWidget(r, 3, make_text_cell(row[3], color="#9E9BB5", is_mono=True, align_center=True))

            # Col 4: IP đích
            table.setCellWidget(r, 4, make_text_cell(row[4], color="#C4B5FD", is_mono=True))

            # Col 5: Cổng đích
            table.setCellWidget(r, 5, make_text_cell(row[5], color="#9E9BB5", is_mono=True, align_center=True))

            # Col 6: Giao thức (Badge chip)
            p_bg, p_fg, p_bd = proto_colors.get(row[6], ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(r, 6, make_badge_cell(row[6], p_bg, p_fg, p_bd))

            # Col 7: Gói tin
            table.setCellWidget(r, 7, make_text_cell(row[7], color="#E2E8F0", align_center=True))

            # Col 8: Dung lượng (Badge chip)
            table.setCellWidget(r, 8, make_badge_cell(row[8], "rgba(139, 92, 246, 0.15)", "#C4B5FD", "rgba(139, 92, 246, 0.3)"))

            # Col 9: Thời lượng
            table.setCellWidget(r, 9, make_text_cell(row[9], color="#CBD5E1", align_center=True))

            # Col 10: Trạng thái (Badge chip)
            s_bg, s_fg, s_bd = status_colors.get(row[10], ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(r, 10, make_badge_cell(row[10], s_bg, s_fg, s_bd))

        panel.box.addWidget(table)

        # Pagination footer
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 0)
        shown = QLabel("Hiển thị 1–10 / 1,326 luồng")
        shown.setObjectName("flowFooter")
        shown.setStyleSheet("color: #8E8BA7; font-size: 11px;")
        footer.addWidget(shown)
        footer.addStretch()

        for page in ("‹", "1", "2", "3", "4", "5", "…", "133", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            button.setFixedSize(28, 28)
            if page == "1":
                button.setStyleSheet("background: #6C5DD3; color: #FFFFFF; border-radius: 6px; font-weight: 700; font-size: 11px; border: none;")
            else:
                button.setStyleSheet("background: #1B1938; color: #8E8BA7; border-radius: 6px; font-size: 11px; border: 1px solid #282452;")
            footer.addWidget(button)
        panel.box.addLayout(footer)

        return panel

    def _interfaces_panel(self) -> Panel:
        badge = QLabel("2 Active")
        badge.setObjectName("panelChip")
        badge.setStyleSheet("color: #10B981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;")
        panel = Panel("Giao diện mạng", "Card mạng vật lý & ảo trên hệ thống", badge)
        panel.box.addWidget(InterfaceCard("eth0", "Mininet", "145.2 Mbps", "100.4 Mbps", "#10B981"))
        panel.box.addWidget(InterfaceCard("lo", "Loopback", "1.2 Mbps", "1.2 Mbps", "#60A5FA"))
        panel.box.addStretch()
        return panel

    def _top_ip_panel(self) -> Panel:
        badge = QLabel("Top 5")
        badge.setObjectName("panelChip")
        badge.setStyleSheet("color: #C4B5FD; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;")
        panel = Panel("Top 5 IP theo lưu lượng", "Địa chỉ IP tiêu thụ băng thông lớn nhất", badge)
        for rank, (ip, value, color) in enumerate([
            ("192.168.1.100", 245.6, "#2F9BFF"),
            ("10.0.0.23", 198.4, "#10B981"),
            ("203.113.5.21", 156.2, "#FF8A4C"),
            ("192.168.1.77", 98.3, "#8B5CF6"),
            ("192.168.1.50", 76.5, "#FBBF24"),
        ], 1):
            panel.box.addWidget(TopIpRow(rank, ip, value, 245.6, color))
        panel.box.addStretch()
        return panel

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self.timer.stop()
            self.pause_button.setText("  Tiếp tục")
            self.pause_button.setIcon(icon("activity", "#FFFFFF", 14))
        else:
            self.timer.start(1800)
            self.pause_button.setText("  Tạm dừng")
            self.pause_button.setIcon(icon("pause", "#FFFFFF", 14))

    def refresh_data(self) -> None:
        self.packet_chart.refresh()
        self.data_chart.refresh()
