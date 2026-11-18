"""Network monitoring page backed by counters from the local operating system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

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
from app.services.network_metrics import NetworkMetricsCollector, NetworkSnapshot
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

        # 1. Color-coded icon container for fast KPI recognition.
        badge = QLabel()
        badge.setObjectName("metricIcon")
        accent = QColor(data.color)
        red, green, blue = accent.red(), accent.green(), accent.blue()
        badge.setStyleSheet(
            f"background: rgba({red}, {green}, {blue}, 0.16); "
            f"border: 1px solid rgba({red}, {green}, {blue}, 0.38); border-radius: 9px;"
        )
        badge.setPixmap(icon(data.icon_name, data.color, 17).pixmap(17, 17))
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

        self.value_label = QLabel(data.value)
        self.value_label.setObjectName("monitorMetricValue")
        self.value_label.setStyleSheet("color: #FFFFFF; font-size: 19px; font-weight: 700; letter-spacing: -0.3px;")
        center.addWidget(self.value_label)

        layout.addLayout(center, 1)

        # 3. Right: Trend pill on top + Sparkline below
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.change_label = QLabel(data.change)
        self.change_label.setObjectName("monitorMetricChange")
        self.change_label.setStyleSheet(
            f"color: {data.color}; background: rgba(255, 255, 255, 0.06); border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
        )
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.change_label, 0, Qt.AlignmentFlag.AlignRight)

        self.sparkline = Sparkline([0.0] * 12, data.color)
        self.sparkline.setFixedSize(46, 18)
        right.addWidget(self.sparkline, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)

    def set_data(self, value: str, change: str, spark_value: float) -> None:
        self.value_label.setText(value)
        self.change_label.setText(change)
        self.sparkline.append_value(spark_value)


class Chart(QWidget):
    """Dynamic real-time wave chart with gradient fill and dash gridlines."""

    def __init__(self, series: list[tuple[list[int], str]], maximum: int, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.series = series
        self.maximum = maximum
        self.labels = labels
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def append_values(self, values: list[float], labels: list[str] | None = None) -> None:
        for (series, _), value in zip(self.series, values):
            series.append(max(0.0, float(value)))
            del series[0]
        observed_max = max((max(series) for series, _ in self.series if series), default=1.0)
        self.maximum = max(1, int(observed_max * 1.2))
        if labels is not None:
            self.labels = labels
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


def _number_from_rate(text: str) -> float:
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return 0.0


# Backward-compatible alias for other pages importing legend
legend = legend_chip


class InterfaceCard(QFrame):
    """Network Interface card with bandwidth rates and sparkline."""

    def __init__(self, name: str, subtitle: str, incoming: str, outgoing: str, color: str, is_up: bool = True, parent: QWidget | None = None) -> None:
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

        state = QLabel("●  Up" if is_up else "●  Down")
        state_color = "#10B981" if is_up else "#FF5B79"
        state.setStyleSheet(
            f"color: {state_color}; background: rgba(255, 255, 255, 0.06); "
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

        spark = Sparkline([0.0] * 12, color)
        spark.append_value(max(_number_from_rate(incoming), _number_from_rate(outgoing)))
        spark.setFixedSize(65, 22)
        root.addWidget(spark, 0, Qt.AlignmentFlag.AlignVCenter)


class TopIpRow(QWidget):
    """Ranked top IP row with progress bar and bandwidth."""

    def __init__(self, rank: int, ip: str, value: float, maximum: float, color: str, unit: str = "kết nối", parent: QWidget | None = None) -> None:
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

        number = QLabel(f"{int(value):,} {unit}")
        number.setFixedWidth(82)
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
        self.collector = NetworkMetricsCollector()
        self._last_snapshot: NetworkSnapshot | None = None

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

        subtitle = QLabel("Theo dõi lưu lượng mạng theo thời gian thực  •  Dữ liệu trực tiếp từ hệ điều hành")
        subtitle.setObjectName("monitorSubtitle")
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
        header.addLayout(intro, 1)

        # Controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.live_badge = QLabel("●  LIVE MONITORING")
        live_badge = self.live_badge
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
            MonitorMetric("Tổng gói tin", "—", "HĐH", "#2F9BFF", "box"),
            MonitorMetric("Tổng dữ liệu", "—", "HĐH", "#9551E8", "database"),
            MonitorMetric("Kết nối hoạt động", "—", "Live", "#10B981", "nodes"),
            MonitorMetric("Lưu lượng vào", "—", "Live", "#FF5B79", "trend"),
            MonitorMetric("Lưu lượng ra", "—", "Live", "#34D399", "trend"),
        ]
        self.metric_cards: list[MetricCard] = []
        for col_idx, item in enumerate(metrics):
            card = MetricCard(item)
            self.metric_cards.append(card)
            metric_grid.addWidget(card, 0, col_idx)
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
        pkt_lay.addWidget(legend_chip("#8B5CF6", "Tổng"))
        pkt_lay.addWidget(legend_chip("#10B981", "Vào"))
        pkt_lay.addWidget(legend_chip("#FF8A4C", "Ra"))
        self.packet_badge = QLabel("0 pps")
        pkt_badge = self.packet_badge
        pkt_badge.setObjectName("panelChip")
        pkt_badge.setStyleSheet(
            "color: #8B5CF6; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        pkt_lay.addWidget(pkt_badge)

        packet_panel = Panel("Lưu lượng gói tin theo thời gian thực", "Tốc độ gói tin do hệ điều hành ghi nhận (Packets/s)", pkt_extra)
        self.packet_chart = Chart([
            ([0.0] * 32, "#8B5CF6"),
            ([0.0] * 32, "#10B981"),
            ([0.0] * 32, "#FF8A4C"),
        ], 1, self._time_labels())
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
        self.data_badge = QLabel("0.00 Mbps")
        data_badge = self.data_badge
        data_badge.setObjectName("panelChip")
        data_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        data_lay.addWidget(data_badge)

        data_panel = Panel("Lưu lượng dữ liệu theo thời gian thực", "Băng thông thông lượng mạng (Throughput Mbps)", data_extra)
        self.data_chart = Chart([
            ([0.0] * 32, "#8B5CF6"),
            ([0.0] * 32, "#10B981"),
            ([0.0] * 32, "#FF8A4C"),
        ], 1, self._time_labels())
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
        self.protocol_badge = QLabel("0 loại")
        proto_badge = self.protocol_badge
        proto_badge.setObjectName("panelChip")
        proto_badge.setStyleSheet(
            "color: #60A5FA; background: rgba(96, 165, 250, 0.15); "
            "border: 1px solid rgba(96, 165, 250, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        protocol_panel = Panel("Phân bố giao thức", "Tỷ trọng các giao thức truyền tải", proto_badge)
        proto_body = QHBoxLayout()
        proto_body.setSpacing(10)
        self.protocol_donut = DonutChart([], "Giao thức", "0", "kết nối")
        proto_body.addWidget(self.protocol_donut, 1)
        proto_legend = QVBoxLayout()
        proto_legend.setSpacing(3)
        proto_legend.addStretch(1)
        self.protocol_rows: dict[str, QWidget] = {}
        for color, name in [
            ("#2F9BFF", "TCP"),
            ("#FF9B37", "UDP"),
            ("#1ED28A", "ICMP"),
            ("#9551E8", "HTTP"),
            ("#F4C440", "DNS"),
            ("#7671BF", "Khác"),
        ]:
            row = protocol_bar_row(color, name, "0.0%", 0.0)
            self.protocol_rows[name] = row
            proto_legend.addWidget(row)
        proto_legend.addStretch(1)
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

        # Live operating-system counters.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1800)
        self.refresh_data()

    def _flow_panel(self) -> Panel:
        self.flow_badge = QLabel("0 kết nối")
        panel_chip = self.flow_badge
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

        rows: list[list[str]] = []
        headers = ["ID", "Thời gian", "IP nguồn", "Cổng N", "IP đích", "Cổng Đ", "Giao thức", "Gói tin", "Dung lượng", "Thời lượng", "Trạng thái"]

        table = QTableWidget(len(rows), len(headers))
        self.flow_table = table
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
        shown = QLabel("Chưa có kết nối từ hệ điều hành")
        self.flow_footer = shown
        shown.setObjectName("flowFooter")
        shown.setStyleSheet("color: #8E8BA7; font-size: 11px;")
        footer.addWidget(shown)
        footer.addStretch()

        for page in ("‹", "1", "›"):
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
        self.interface_badge = QLabel("0 hoạt động")
        badge = self.interface_badge
        badge.setObjectName("panelChip")
        badge.setStyleSheet("color: #10B981; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;")
        panel = Panel("Giao diện mạng", "Card mạng vật lý & ảo trên hệ thống", badge)
        self.interface_layout = panel.box
        panel.box.addStretch()
        return panel

    def _top_ip_panel(self) -> Panel:
        badge = QLabel("Top 5")
        badge.setObjectName("panelChip")
        badge.setStyleSheet("color: #C4B5FD; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;")
        panel = Panel("Top 5 IP đang kết nối", "Xếp hạng theo số phiên kết nối hệ điều hành ghi nhận", badge)
        self.top_ip_layout = panel.box
        panel.box.addStretch()
        return panel

    def _time_labels(self) -> list[str]:
        minutes = (10, 30, 60)[self.range_combo.currentIndex()] if hasattr(self, "range_combo") else 10
        now = datetime.now()
        return [
            (now - timedelta(minutes=minutes * (5 - index) / 5)).strftime("%H:%M")
            for index in range(6)
        ]

    @staticmethod
    def _format_bytes(value: int) -> str:
        amount = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1024.0 or unit == "TB":
                return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount):,} B"
            amount /= 1024.0
        return "0 B"

    def _update_protocols(self, snapshot: NetworkSnapshot) -> None:
        colors = {
            "TCP": "#2F9BFF", "UDP": "#FF9B37", "ICMP": "#1ED28A",
            "HTTP": "#9551E8", "DNS": "#F4C440", "Khác": "#7671BF",
        }
        total = sum(snapshot.protocol_counts.values())
        segments: list[tuple[float, str]] = []
        for name, row in self.protocol_rows.items():
            count = snapshot.protocol_counts.get(name, 0)
            percent = count * 100.0 / total if total else 0.0
            segments.append((percent, colors[name]))
            labels = row.findChildren(QLabel)
            if labels:
                labels[-1].setText(f"{percent:.1f}%")
            bars = row.findChildren(QProgressBar)
            if bars:
                bars[0].setValue(int(percent))
        kinds = sum(1 for value in snapshot.protocol_counts.values() if value)
        self.protocol_badge.setText(f"{kinds} loại")
        self.protocol_donut.set_data(segments, f"{total:,}", "kết nối")

    def _update_interfaces(self, snapshot: NetworkSnapshot) -> None:
        for widget in getattr(self, "_interface_widgets", []):
            self.interface_layout.removeWidget(widget)
            widget.deleteLater()
        self._interface_widgets = []

        active = sum(1 for interface in snapshot.interfaces if interface.is_up)
        self.interface_badge.setText(f"{active} hoạt động")
        colors = ("#10B981", "#60A5FA", "#8B5CF6", "#FF8A4C")
        visible = sorted(snapshot.interfaces, key=lambda item: item.incoming_mbps + item.outgoing_mbps, reverse=True)[:3]
        for index, interface in enumerate(visible):
            card = InterfaceCard(
                interface.name,
                "Hệ điều hành",
                f"{interface.incoming_mbps:.2f} Mbps",
                f"{interface.outgoing_mbps:.2f} Mbps",
                colors[index % len(colors)],
                interface.is_up,
            )
            self.interface_layout.insertWidget(self.interface_layout.count() - 1, card)
            self._interface_widgets.append(card)

    def _update_top_ips(self, snapshot: NetworkSnapshot) -> None:
        for widget in getattr(self, "_top_ip_widgets", []):
            self.top_ip_layout.removeWidget(widget)
            widget.deleteLater()
        self._top_ip_widgets = []

        colors = ("#2F9BFF", "#10B981", "#FF8A4C", "#8B5CF6", "#FBBF24")
        maximum = max((count for _, count in snapshot.top_remote_ips), default=1)
        for rank, (ip_address, count) in enumerate(snapshot.top_remote_ips, 1):
            row = TopIpRow(rank, ip_address, count, maximum, colors[(rank - 1) % len(colors)])
            self.top_ip_layout.insertWidget(self.top_ip_layout.count() - 1, row)
            self._top_ip_widgets.append(row)

    def _update_flows(self, snapshot: NetworkSnapshot) -> None:
        rows = snapshot.connections[:10]
        table = self.flow_table
        table.clearContents()
        table.setRowCount(len(rows))
        sampled_at = datetime.now().strftime("%H:%M:%S")
        protocol_colors = {
            "TCP": ("rgba(47, 155, 255, 0.18)", "#60A5FA", "rgba(47, 155, 255, 0.35)"),
            "UDP": ("rgba(255, 155, 55, 0.18)", "#FDBA74", "rgba(255, 155, 55, 0.35)"),
            "HTTP": ("rgba(149, 81, 232, 0.18)", "#C4B5FD", "rgba(149, 81, 232, 0.35)"),
            "DNS": ("rgba(244, 196, 64, 0.18)", "#F4C440", "rgba(244, 196, 64, 0.35)"),
        }
        for row_index, connection in enumerate(rows):
            table.setRowHeight(row_index, 38)
            values = (
                f"#{row_index + 1:04d}", sampled_at, connection.local_ip,
                str(connection.local_port or "—"), connection.remote_ip,
                str(connection.remote_port or "—"), connection.protocol,
                "—", "—", "—", connection.status,
            )
            table.setCellWidget(row_index, 0, make_text_cell(values[0], color="#8E8BA7", align_center=True))
            table.setCellWidget(row_index, 1, make_text_cell(values[1], color="#CBD5E1", align_center=True))
            table.setCellWidget(row_index, 2, make_text_cell(values[2], color="#FFFFFF", is_mono=True, is_bold=True))
            table.setCellWidget(row_index, 3, make_text_cell(values[3], color="#9E9BB5", is_mono=True, align_center=True))
            table.setCellWidget(row_index, 4, make_text_cell(values[4], color="#C4B5FD", is_mono=True))
            table.setCellWidget(row_index, 5, make_text_cell(values[5], color="#9E9BB5", is_mono=True, align_center=True))
            bg, fg, border = protocol_colors.get(connection.protocol, ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(row_index, 6, make_badge_cell(values[6], bg, fg, border))
            for column in (7, 8, 9):
                table.setCellWidget(row_index, column, make_text_cell("—", color="#8E8BA7", align_center=True))
            table.setCellWidget(row_index, 10, make_badge_cell(values[10], "#25224D", "#CBD5E1", "#383466"))

        total = len(snapshot.connections)
        self.flow_badge.setText(f"{total} kết nối")
        self.flow_footer.setText(
            f"Hiển thị 1–{len(rows)} / {total} kết nối hệ điều hành" if rows
            else "Chưa có kết nối mạng đang hoạt động"
        )

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
        snapshot = self.collector.sample()
        self._last_snapshot = snapshot
        if not snapshot.available:
            self.live_badge.setText("●  KHÔNG CÓ DỮ LIỆU")
            for card in self.metric_cards:
                card.set_data("—", "Offline", 0.0)
            return

        self.live_badge.setText("●  LIVE MONITORING")
        total_mbps = snapshot.incoming_mbps + snapshot.outgoing_mbps
        total_pps = snapshot.incoming_pps + snapshot.outgoing_pps
        values = (
            (f"{snapshot.total_packets:,}", "HĐH", float(snapshot.total_packets)),
            (self._format_bytes(snapshot.total_bytes), "HĐH", float(snapshot.total_bytes)),
            (f"{snapshot.active_connections:,}", "Live", float(snapshot.active_connections)),
            (f"{snapshot.incoming_mbps:.2f} Mbps", "Live", snapshot.incoming_mbps),
            (f"{snapshot.outgoing_mbps:.2f} Mbps", "Live", snapshot.outgoing_mbps),
        )
        for card, (value, change, spark_value) in zip(self.metric_cards, values):
            card.set_data(value, change, spark_value)

        labels = self._time_labels()
        self.packet_badge.setText(f"{total_pps:,.0f} pps")
        self.data_badge.setText(f"{total_mbps:.2f} Mbps")
        self.packet_chart.append_values([total_pps, snapshot.incoming_pps, snapshot.outgoing_pps], labels)
        self.data_chart.append_values([total_mbps, snapshot.incoming_mbps, snapshot.outgoing_mbps], labels)
        self._update_protocols(snapshot)
        self._update_interfaces(snapshot)
        self._update_top_ips(snapshot)
        self._update_flows(snapshot)
