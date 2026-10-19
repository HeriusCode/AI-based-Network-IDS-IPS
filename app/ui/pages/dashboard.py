"""Dashboard overview for the desktop IDS/IPS demo."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon


@dataclass(frozen=True)
class Metric:
    title: str
    value: str
    change: str
    color: str
    icon_name: str


class Sparkline(QWidget):
    def __init__(self, values: list[int], color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values = values
        self.color = QColor(color)
        self.setFixedHeight(30)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        count = len(self.values)
        gap = 3.0
        width = max(2.0, (self.width() - gap * (count - 1)) / count)
        maximum = max(self.values)
        for index, value in enumerate(self.values):
            height = (value / maximum) * (self.height() - 3)
            rect = QRectF(index * (width + gap), self.height() - height, width, height)
            painter.fillRect(rect, self.color)


class MetricCard(QFrame):
    def __init__(self, metric: Metric, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(126)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)

        badge = QLabel()
        badge.setObjectName("metricIcon")
        badge.setProperty("tone", metric.color)
        badge.setPixmap(icon(metric.icon_name, metric.color, 24).pixmap(24, 24))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(48, 48)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(3)
        title = QLabel(metric.title)
        title.setObjectName("metricTitle")
        title.setWordWrap(True)
        body.addWidget(title)
        value = QLabel(metric.value)
        value.setObjectName("metricValue")
        body.addWidget(value)
        change = QLabel(metric.change)
        change.setObjectName("metricChange")
        change.setStyleSheet(f"color: {metric.color};")
        body.addWidget(change)
        body.addStretch(1)
        spark = Sparkline([2, 4, 3, 7, 5, 9, 7, 12, 9, 14, 10, 18], metric.color)
        body.addWidget(spark)
        layout.addLayout(body, 1)

    def minimumSizeHint(self) -> QSize:
        return QSize(145, 126)

    def sizeHint(self) -> QSize:
        return QSize(190, 126)


class SystemCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(126)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        badge = QLabel()
        badge.setObjectName("metricIcon")
        badge.setPixmap(icon("shield", "#38A7FF", 24).pixmap(24, 24))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(48, 48)
        header.addWidget(badge)
        labels = QVBoxLayout()
        title = QLabel("Trạng thái hệ thống")
        title.setObjectName("metricTitle")
        labels.addWidget(title)
        value = QLabel("Hoạt động tốt")
        value.setObjectName("systemGood")
        labels.addWidget(value)
        header.addLayout(labels, 1)
        layout.addLayout(header)
        progress = QProgressBar()
        progress.setObjectName("healthProgress")
        progress.setRange(0, 100)
        progress.setValue(94)
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        layout.addStretch(1)
        layout.addWidget(progress)

    def minimumSizeHint(self) -> QSize:
        return QSize(155, 126)

    def sizeHint(self) -> QSize:
        return QSize(190, 126)


class TrafficChart(QWidget):
    incoming = [72, 112, 88, 148, 105, 120, 169, 143, 204, 129, 111, 134, 149, 113, 89, 137, 126, 158, 181, 175, 204, 119, 142, 163, 165, 116, 139, 121, 133, 110, 201, 148, 127, 142]
    outgoing = [51, 79, 93, 82, 122, 111, 75, 60, 83, 126, 89, 102, 77, 105, 84, 59, 96, 75, 101, 72, 137, 116, 81, 103, 114, 87, 75, 106, 93, 82, 139, 111, 75, 108]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, top, right, bottom = 42, 16, 10, 28
        chart = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#7890AA"))
        for step in range(7):
            y = chart.bottom() - chart.height() * step / 6
            painter.drawText(QRectF(0, y - 8, left - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(step * 50))
            painter.setPen(QPen(QColor("#213449"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
            painter.setPen(QColor("#7890AA"))
        for step, label in enumerate(["10:14", "10:16", "10:18", "10:20", "10:22", "10:24"]):
            x = chart.left() + chart.width() * step / 5
            painter.drawText(QRectF(x - 24, chart.bottom() + 8, 48, 18), Qt.AlignmentFlag.AlignCenter, label)

        self._draw_series(painter, chart, self.outgoing, QColor("#16D680"), True)
        self._draw_series(painter, chart, self.incoming, QColor("#2F9BFF"), False)

    @staticmethod
    def _draw_series(painter: QPainter, chart: QRectF, values: list[int], color: QColor, fill: bool) -> None:
        points = [
            QPointF(chart.left() + chart.width() * i / (len(values) - 1), chart.bottom() - chart.height() * value / 300)
            for i, value in enumerate(values)
        ]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if fill:
            area = QPainterPath(path)
            area.lineTo(chart.right(), chart.bottom())
            area.lineTo(chart.left(), chart.bottom())
            area.closeSubpath()
            gradient = QLinearGradient(0, chart.top(), 0, chart.bottom())
            gradient.setColorAt(0, QColor(22, 214, 128, 85))
            gradient.setColorAt(1, QColor(22, 214, 128, 4))
            painter.fillPath(area, gradient)
        painter.setPen(QPen(color, 2.2))
        painter.drawPath(path)


class DonutChart(QWidget):
    def __init__(self, segments: list[tuple[float, str]], center_top: str, center_value: str, center_bottom: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.segments = segments
        self.center_top = center_top
        self.center_value = center_value
        self.center_bottom = center_bottom
        self.setMinimumSize(170, 170)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) - 22
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        pen_width = max(18, int(side * 0.16))
        start = 90 * 16
        for percent, color in self.segments:
            painter.setPen(QPen(QColor(color), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            span = -percent * 360 * 16 / 100
            painter.drawArc(rect.adjusted(pen_width / 2, pen_width / 2, -pen_width / 2, -pen_width / 2), int(start), int(span))
            start += span
        center = rect.center()
        painter.setPen(QColor("#8393AA"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(center.x() - 70, center.y() - 36, 140, 20), Qt.AlignmentFlag.AlignCenter, self.center_top)
        painter.setPen(QColor("#F4F7FB"))
        font = QFont("Segoe UI", 12)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(QRectF(center.x() - 75, center.y() - 10, 150, 24), Qt.AlignmentFlag.AlignCenter, self.center_value)
        painter.setPen(QColor("#8393AA"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(center.x() - 70, center.y() + 16, 140, 20), Qt.AlignmentFlag.AlignCenter, self.center_bottom)


class Panel(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardPanel")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(16, 13, 16, 14)
        self.box.setSpacing(10)
        header = QLabel(title)
        header.setObjectName("panelTitle")
        self.box.addWidget(header)


def legend_row(color: str, label: str, value: str) -> QWidget:
    row = QWidget()
    row.setObjectName("legendRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    dot = QLabel()
    dot.setFixedSize(12, 12)
    dot.setStyleSheet(f"background:{color}; border-radius:3px;")
    layout.addWidget(dot)
    text = QLabel(label)
    text.setObjectName("legendLabel")
    layout.addWidget(text)
    layout.addStretch()
    number = QLabel(value)
    number.setObjectName("legendValue")
    layout.addWidget(number)
    return row


class StatusModule(QFrame):
    def __init__(self, title: str, subtitle: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("moduleCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        badge = QLabel()
        badge.setObjectName("moduleIcon")
        badge.setPixmap(icon(icon_name, "#22DB91", 25).pixmap(25, 25))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(50, 50)
        layout.addWidget(badge)
        copy = QVBoxLayout()
        name = QLabel(title)
        name.setObjectName("moduleTitle")
        copy.addWidget(name)
        sub = QLabel(subtitle)
        sub.setObjectName("moduleSubtitle")
        copy.addWidget(sub)
        layout.addLayout(copy, 1)
        state = QLabel("● Hoạt động")
        state.setObjectName("moduleState")
        layout.addWidget(state)

    def minimumSizeHint(self) -> QSize:
        return QSize(180, 74)

    def sizeHint(self) -> QSize:
        return QSize(260, 74)


class DashboardPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("dashboardContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(22, 16, 22, 20)
        root.setSpacing(12)

        heading = QLabel("Dashboard")
        heading.setObjectName("dashboardHeading")
        root.addWidget(heading)
        subheading = QLabel("Tổng quan hoạt động của hệ thống AI-based Network IDS/IPS  •  Dữ liệu mô phỏng")
        subheading.setObjectName("dashboardSubheading")
        root.addWidget(subheading)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        data = [
            Metric("Tổng gói tin", "1,248,536", "↑ 12.5%", "#36A1FF", "box"),
            Metric("Lưu lượng mạng", "245.6 Mbps", "↑ 8.3%", "#B15CFF", "nodes"),
            Metric("Kết nối đang hoạt động", "1,326", "↑ 5.1%", "#20DC89", "nodes"),
            Metric("Phát hiện bất thường", "27", "↑ 3.2%", "#FF5364", "warning"),
            Metric("Luồng bị chặn", "12", "20.0%", "#FF9B37", "blocked"),
        ]
        for index, metric in enumerate(data):
            metrics.addWidget(MetricCard(metric), 0, index)
            metrics.setColumnStretch(index, 1)
        metrics.addWidget(SystemCard(), 0, 5)
        metrics.setColumnStretch(5, 1)
        root.addLayout(metrics)

        charts = QGridLayout()
        charts.setSpacing(10)
        traffic = Panel("Lưu lượng mạng theo thời gian thực")
        legend = QHBoxLayout()
        legend.addStretch()
        legend.addWidget(legend_row("#2F9BFF", "Lưu lượng vào", ""))
        legend.addWidget(legend_row("#16D680", "Lưu lượng ra", ""))
        traffic.box.addLayout(legend)
        traffic.box.addWidget(TrafficChart(), 1)
        charts.addWidget(traffic, 0, 0, 1, 2)

        ratio = Panel("Tỷ lệ lưu lượng")
        ratio.box.addWidget(DonutChart([(92.4, "#2F9BFF"), (7.6, "#FB4456")], "Tổng", "1,248,536", "gói tin"), 1)
        ratio.box.addWidget(legend_row("#2F9BFF", "Lưu lượng bình thường", "92.4%"))
        ratio.box.addWidget(legend_row("#FB4456", "Lưu lượng bất thường", "7.6%"))
        charts.addWidget(ratio, 0, 2)

        protocols = Panel("Phân bố giao thức")
        proto_body = QHBoxLayout()
        proto_body.addWidget(DonutChart([(48.2, "#2F9BFF"), (32.7, "#FF9B37"), (8.1, "#1ED28A"), (6.3, "#9551E8"), (2.8, "#F4C440"), (1.9, "#7671BF")], "", "1,248,536", "gói tin"), 1)
        proto_legend = QVBoxLayout()
        for color, label, value in [
            ("#2F9BFF", "TCP", "48.2%"), ("#FF9B37", "UDP", "32.7%"),
            ("#1ED28A", "ICMP", "8.1%"), ("#9551E8", "HTTP", "6.3%"),
            ("#F4C440", "DNS", "2.8%"), ("#7671BF", "Khác", "1.9%"),
        ]:
            proto_legend.addWidget(legend_row(color, label, value))
        proto_legend.addStretch()
        proto_body.addLayout(proto_legend)
        protocols.box.addLayout(proto_body, 1)
        charts.addWidget(protocols, 0, 3)
        charts.setColumnStretch(0, 2)
        charts.setColumnStretch(1, 2)
        charts.setColumnStretch(2, 2)
        charts.setColumnStretch(3, 2)
        charts.setRowMinimumHeight(0, 270)
        root.addLayout(charts)

        tables = QGridLayout()
        tables.setSpacing(10)
        alerts = Panel("Cảnh báo an ninh gần đây")
        alerts.box.addWidget(self._alert_table())
        tables.addWidget(alerts, 0, 0, 1, 3)
        top_ips = Panel("Top 5 nguồn IP theo lưu lượng")
        top_ips.box.addWidget(self._ip_table())
        tables.addWidget(top_ips, 0, 3, 1, 2)
        tables.setColumnStretch(0, 1)
        tables.setColumnStretch(1, 1)
        tables.setColumnStretch(2, 1)
        tables.setColumnStretch(3, 1)
        tables.setColumnStretch(4, 1)
        root.addLayout(tables)

        status = Panel("Trạng thái các thành phần hệ thống")
        modules = QHBoxLayout()
        modules.setSpacing(10)
        for args in [
            ("Giám sát mạng", "(Monitoring)", "activity"),
            ("Phát hiện bất thường", "(Detection)", "shield"),
            ("Dự đoán lưu lượng", "(Prediction)", "trend"),
            ("Giảm thiểu rủi ro", "(Mitigation)", "lock"),
        ]:
            modules.addWidget(StatusModule(*args), 1)
        status.box.addLayout(modules)
        root.addWidget(status)
        self.setWidget(content)

    @staticmethod
    def _table(headers: list[str], rows: list[list[str]]) -> QTableWidget:
        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("dashboardTable")
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setFixedHeight(174)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                if column_index in (0, 1):
                    item.setForeground(QColor("#C8D4E5"))
                table.setItem(row_index, column_index, item)
        return table

    def _alert_table(self) -> QTableWidget:
        return self._table(
            ["Thời gian", "Loại cảnh báo", "Nguồn IP", "Đích IP", "Mức độ", "Trạng thái"],
            [
                ["10:24:12", "⚠  Port Scan", "192.168.1.100", "192.168.1.10", "Cao", "Chưa xử lý"],
                ["10:23:45", "⚠  DDoS Attack", "10.0.0.23", "192.168.1.10", "Nghiêm trọng", "Chưa xử lý"],
                ["10:22:18", "⚠  Abnormal Traffic", "192.168.1.50", "8.8.8.8", "Trung bình", "Đã xử lý"],
                ["10:21:05", "⚠  Brute Force", "203.113.5.21", "192.168.1.10", "Cao", "Chưa xử lý"],
                ["10:19:37", "♲  Suspicious DNS", "192.168.1.77", "1.1.1.1", "Thấp", "Đã xử lý"],
            ],
        )

    def _ip_table(self) -> QTableWidget:
        return self._table(
            ["IP nguồn", "Gói tin", "Lưu lượng (MB)", "Tỷ lệ"],
            [
                ["192.168.1.100", "245,632", "125.6", "19.7%"],
                ["10.0.0.23", "198,456", "98.2", "15.9%"],
                ["192.168.1.50", "156,789", "76.3", "12.6%"],
                ["203.113.5.21", "123,567", "60.1", "9.9%"],
                ["192.168.1.77", "98,234", "45.7", "7.9%"],
            ],
        )
