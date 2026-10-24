"""Security alerts page with simulation-only response actions."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.dashboard import DonutChart
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend


ALERTS = [
    ["#A1024", "24/04 14:32:11", "10.0.0.23", "192.168.1.10", "DDoS Attack", "Nghiêm trọng", "Lưu lượng TCP tăng đột biến", "Đang xử lý"],
    ["#A1023", "24/04 14:30:45", "203.113.5.21", "192.168.1.10", "Port Scan", "Cao", "Quét cổng hàng loạt", "Chưa xử lý"],
    ["#A1022", "24/04 14:28:17", "192.168.1.77", "1.1.1.1", "Brute Force", "Cao", "Đăng nhập thất bại liên tục", "Đang xử lý"],
    ["#A1021", "24/04 14:26:09", "10.0.0.56", "192.168.1.10", "SQL Injection", "Trung bình", "Phát hiện payload SQL", "Đã xử lý"],
    ["#A1020", "24/04 14:23:33", "192.168.1.50", "8.8.8.8", "Malware", "Cao", "Kết nối đến domain độc hại", "Chưa xử lý"],
    ["#A1019", "24/04 14:21:05", "203.113.5.21", "192.168.1.10", "DDoS Attack", "Nghiêm trọng", "Lưu lượng UDP bất thường", "Đang xử lý"],
    ["#A1018", "24/04 14:19:27", "10.0.0.89", "192.168.1.20", "Port Scan", "Trung bình", "Quét nhiều cổng TCP", "Đã xử lý"],
    ["#A1017", "24/04 14:16:44", "192.168.1.100", "203.113.5.21", "Suspicious Traffic", "Thấp", "Kết nối có hành vi bất thường", "Đã xử lý"],
    ["#A1016", "24/04 14:14:23", "10.0.0.23", "192.168.1.10", "Brute Force", "Cao", "Nhiều lần đăng nhập sai", "Chưa xử lý"],
    ["#A1015", "24/04 14:12:11", "192.168.1.77", "8.8.8.8", "Protocol Anomaly", "Trung bình", "Lưu lượng ICMP bất thường", "Đã xử lý"],
]


class AlertTimelineChart(QWidget):
    low = [1, 2, 1, 2, 1, 2, 2, 1, 3, 2, 1, 2, 3, 2, 4, 2, 1, 3, 2, 1, 2, 3, 2, 1, 2, 3, 1, 2, 1, 2, 1, 2]
    medium = [2, 3, 2, 4, 3, 5, 3, 4, 6, 4, 3, 5, 4, 8, 6, 4, 5, 6, 4, 5, 3, 5, 7, 4, 6, 4, 3, 5, 3, 4, 3, 5]
    high = [3, 5, 4, 6, 4, 7, 5, 9, 6, 7, 5, 8, 6, 11, 7, 5, 8, 6, 7, 5, 6, 8, 15, 7, 5, 9, 6, 12, 7, 5, 4, 9]
    critical = [5, 4, 6, 4, 5, 7, 5, 8, 6, 10, 7, 9, 6, 14, 11, 20, 8, 14, 7, 9, 6, 8, 10, 15, 7, 6, 9, 7, 12, 8, 5, 10]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(175)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(42, 8, self.width() - 50, self.height() - 31)
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(6):
            y = chart.bottom() - chart.height() * step / 5
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(0, y - 8, 34, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(step * 5))
            painter.setPen(QPen(QColor("#20364D"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
        for index, label in enumerate(["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]):
            x = chart.left() + chart.width() * index / 6
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(x - 24, chart.bottom() + 6, 48, 16), Qt.AlignmentFlag.AlignCenter, label)
        for values, color in [(self.critical, "#FF414F"), (self.high, "#FF932E"), (self.medium, "#FFB52E"), (self.low, "#229BFF")]:
            points = [QPointF(chart.left() + chart.width() * i / (len(values) - 1), chart.bottom() - chart.height() * value / 25) for i, value in enumerate(values)]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            area = QPainterPath(path)
            area.lineTo(chart.right(), chart.bottom())
            area.lineTo(chart.left(), chart.bottom())
            area.closeSubpath()
            shade = QColor(color)
            shade.setAlpha(32)
            painter.fillPath(area, shade)
            painter.setPen(QPen(QColor(color), 1.8))
            painter.drawPath(path)


class AlertsPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("alertsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)
        title = QLabel("Cảnh báo an ninh")
        title.setObjectName("alertsHeading")
        intro.addWidget(title)
        subtitle = QLabel("Danh sách các sự kiện bất thường và mối đe dọa an ninh mạng được phát hiện  •  Dữ liệu mô phỏng")
        subtitle.setObjectName("alertsSubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro)
        header.addStretch()
        date = QPushButton("  24/04/2025 00:00    →    24/04/2025 23:59  ˅")
        date.setObjectName("alertsDate")
        date.setIcon(icon("calendar", "#AFC7E4"))
        date.setFixedWidth(320)
        header.addWidget(date)
        export = QPushButton("  Xuất CSV")
        export.setObjectName("alertsExport")
        export.setIcon(icon("download", "#FFFFFF"))
        header.addWidget(export)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setSpacing(10)
        for column, data in enumerate([
            MonitorMetric("Tổng cảnh báo", "127", "↑ 25.7%", "#FF5360", "warning"),
            MonitorMetric("Mức độ nghiêm trọng", "18", "↑ 50.0%", "#FF4F5D", "blocked"),
            MonitorMetric("Mức độ cao", "37", "↑ 28.1%", "#FFAE36", "warning"),
            MonitorMetric("Đã xử lý", "82", "↑ 12.3%", "#229FFF", "document"),
        ]):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        workspace = QGridLayout()
        workspace.setSpacing(10)
        timeline = Panel("Số lượng cảnh báo theo thời gian")
        timeline_legend = QHBoxLayout()
        timeline_legend.addStretch()
        for color, text in [("#229BFF", "Thấp"), ("#FFB52E", "Trung bình"), ("#FF932E", "Cao"), ("#FF414F", "Nghiêm trọng")]:
            timeline_legend.addWidget(legend(color, text))
        timeline.box.addLayout(timeline_legend)
        timeline.box.addWidget(AlertTimelineChart(), 1)
        workspace.addWidget(timeline, 0, 0, 1, 2)

        category = Panel("Phân loại cảnh báo")
        category_body = QHBoxLayout()
        category_body.addWidget(DonutChart([(28.3, "#FF414F"), (22.0, "#FFA02F"), (15.0, "#1E94F4"), (12.6, "#18D48A"), (8.7, "#9653DF"), (13.4, "#9FB2CF")], "", "127", "cảnh báo"), 1)
        category_legend = QVBoxLayout()
        for color, text, value in [("#FF414F", "DDoS", "28.3%"), ("#FFA02F", "Port Scan", "22.0%"), ("#1E94F4", "Brute Force", "15.0%"), ("#18D48A", "Malware", "12.6%"), ("#9653DF", "SQL Injection", "8.7%"), ("#9FB2CF", "Others", "13.4%")]:
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(11, 11)
            swatch.setStyleSheet(f"background:{color}; border-radius:3px;")
            row.addWidget(swatch)
            row.addWidget(QLabel(text))
            row.addStretch()
            row.addWidget(QLabel(value))
            category_legend.addLayout(row)
        category_body.addLayout(category_legend)
        category.box.addLayout(category_body, 1)
        workspace.addWidget(category, 0, 2)
        workspace.addWidget(self._alerts_table_panel(), 1, 0, 1, 3)
        workspace.addWidget(self._detail_panel(), 0, 3, 2, 1)
        for column in range(4):
            workspace.setColumnStretch(column, 1)
        workspace.setRowMinimumHeight(0, 225)
        root.addLayout(workspace)
        self.setWidget(content)

    def _alerts_table_panel(self) -> Panel:
        panel = Panel("Danh sách cảnh báo an ninh")
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        search = QLineEdit()
        search.setObjectName("alertSearch")
        search.setPlaceholderText("Tìm kiếm...")
        search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search)
        for text in ("Tất cả mức độ", "Tất cả loại tấn công", "Tất cả trạng thái"):
            combo = QComboBox()
            combo.setObjectName("alertCombo")
            combo.addItem(text)
            toolbar.addWidget(combo)
        panel.box.addLayout(toolbar)
        headers = ["ID", "Thời gian", "Nguồn IP", "Đích IP", "Loại tấn công", "Mức độ", "Mô tả", "Trạng thái", "Hành động"]
        self.table = QTableWidget(len(ALERTS), len(headers))
        self.table.setObjectName("alertsTable")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setFixedHeight(292)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(ALERTS):
            for c, value in enumerate(row + ["◉   ⋮"]):
                item = QTableWidgetItem(value)
                if c == 5:
                    item.setForeground(QColor("#FF5360" if value == "Nghiêm trọng" else "#FF992F" if value == "Cao" else "#FFB934" if value == "Trung bình" else "#38A8FF"))
                elif c == 7:
                    item.setForeground(QColor("#1DDB8C" if value == "Đã xử lý" else "#FF5360" if value == "Đang xử lý" else "#FF9D30"))
                self.table.setItem(r, c, item)
        self.table.selectRow(0)
        self.table.cellClicked.connect(lambda row, column: self.update_detail(row))
        panel.box.addWidget(self.table)
        footer = QHBoxLayout()
        count = QLabel("Hiển thị 1–10 / 127 cảnh báo")
        count.setObjectName("flowFooter")
        footer.addWidget(count)
        footer.addStretch()
        for page in ("‹", "1", "2", "3", "4", "5", "…", "13", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            footer.addWidget(button)
        panel.box.addLayout(footer)
        return panel

    def _detail_panel(self) -> Panel:
        panel = Panel("Chi tiết cảnh báo")
        panel.setObjectName("alertDetailPanel")
        self.detail_title = QLabel("⚠  #A1024 - DDoS Attack")
        self.detail_title.setObjectName("alertDetailTitle")
        panel.box.addWidget(self.detail_title)
        severity = QLabel("Nghiêm trọng")
        severity.setObjectName("criticalBadge")
        panel.box.addWidget(severity, 0, Qt.AlignmentFlag.AlignLeft)
        self.detail_values: dict[str, QLabel] = {}
        for key, label_text, value in [
            ("time", "Thời gian", "24/04/2025 14:32:11"), ("source", "Nguồn IP", "10.0.0.23"),
            ("destination", "Đích IP", "192.168.1.10"), ("protocol", "Giao thức", "TCP"),
            ("source_port", "Cổng nguồn", "52341"), ("destination_port", "Cổng đích", "80"),
            ("incoming", "Lưu lượng vào", "125.4 Mbps"), ("outgoing", "Lưu lượng ra", "118.2 Mbps"),
            ("packets", "Số gói tin", "1,245,536"), ("duration", "Thời gian", "2 phút 15 giây"),
            ("status", "Trạng thái", "Đang xử lý"),
        ]:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("alertDetailKey")
            row.addWidget(label)
            row.addStretch()
            field = QLabel(value)
            field.setObjectName("alertDetailValue")
            row.addWidget(field)
            panel.box.addLayout(row)
            self.detail_values[key] = field
        description_heading = QLabel("Mô tả")
        description_heading.setObjectName("alertSectionTitle")
        panel.box.addWidget(description_heading)
        self.description = QLabel("Phát hiện lưu lượng TCP tăng đột biến từ địa chỉ 10.0.0.23 đến 192.168.1.10. Có dấu hiệu tấn công từ chối dịch vụ (DDoS).")
        self.description.setObjectName("alertDescription")
        self.description.setWordWrap(True)
        panel.box.addWidget(self.description)
        chart_title = QLabel("Lưu lượng (Mbps)")
        chart_title.setObjectName("alertSectionTitle")
        panel.box.addWidget(chart_title)
        panel.box.addWidget(Chart([
            ([75, 105, 145, 132, 165, 155, 185, 177, 211, 298, 188, 136, 152, 168, 139, 128], "#FF4A58"),
            ([68, 96, 126, 119, 141, 137, 158, 151, 178, 238, 158, 122, 139, 151, 126, 115], "#249CFF"),
        ], 300, ["14:30", "14:31", "14:32", "14:33", "14:34"]), 1)
        actions = QHBoxLayout()
        self.block_button = QPushButton("  Chặn IP")
        self.block_button.setObjectName("alertBlockButton")
        self.block_button.setIcon(icon("blocked", "#FFFFFF"))
        self.block_button.clicked.connect(self.block_ip)
        actions.addWidget(self.block_button)
        self.resolve_button = QPushButton("  Đánh dấu đã xử lý")
        self.resolve_button.setObjectName("alertResolveButton")
        self.resolve_button.setIcon(icon("check", "#AFC8E3"))
        self.resolve_button.clicked.connect(self.resolve_alert)
        actions.addWidget(self.resolve_button)
        panel.box.addLayout(actions)
        return panel

    def update_detail(self, row: int) -> None:
        data = ALERTS[row]
        self.detail_title.setText(f"⚠  {data[0]} - {data[4]}")
        self.detail_values["time"].setText("24/04/2025 " + data[1].split(" ")[1])
        self.detail_values["source"].setText(data[2])
        self.detail_values["destination"].setText(data[3])
        self.detail_values["status"].setText(data[7])
        self.description.setText(data[6] + ". Sự kiện đang được theo dõi trong môi trường mô phỏng.")
        self.block_button.setText("  Chặn IP")
        self.block_button.setEnabled(True)
        self.resolve_button.setText("  Đánh dấu đã xử lý")
        self.resolve_button.setEnabled(True)

    def block_ip(self) -> None:
        self.block_button.setText("  Đã chặn (mô phỏng)")
        self.block_button.setEnabled(False)

    def resolve_alert(self) -> None:
        self.detail_values["status"].setText("Đã xử lý")
        self.resolve_button.setText("  Đã xử lý")
        self.resolve_button.setEnabled(False)
