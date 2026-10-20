"""AI anomaly-detection dashboard backed by explicit simulated data."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
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


DETECTIONS = [
    ["#A1024", "24/04 14:32:11", "10.0.0.23", "192.168.1.10", "TCP", "DDoS Attack", "98.5%", "Cao", "Đang xử lý"],
    ["#A1023", "24/04 14:30:45", "203.113.5.21", "192.168.1.10", "UDP", "Port Scan", "95.2%", "Cao", "Đang xử lý"],
    ["#A1022", "24/04 14:28:17", "192.168.1.77", "1.1.1.1", "TCP", "Brute Force", "92.1%", "Trung bình", "Đã xác nhận"],
    ["#A1021", "24/04 14:26:09", "10.0.0.56", "192.168.1.10", "ICMP", "Protocol Anomaly", "91.4%", "Trung bình", "Đang giám sát"],
    ["#A1020", "24/04 14:23:33", "192.168.1.50", "8.8.8.8", "TCP", "SQL Injection", "97.6%", "Cao", "Đã xác nhận"],
    ["#A1019", "24/04 14:21:05", "203.113.5.21", "192.168.1.10", "UDP", "DDoS Attack", "96.8%", "Cao", "Đang xử lý"],
    ["#A1018", "24/04 14:19:27", "10.0.0.89", "192.168.1.20", "TCP", "Malware Traffic", "89.3%", "Thấp", "Đã xử lý"],
    ["#A1017", "24/04 14:16:44", "192.168.1.100", "203.113.5.21", "TCP", "Port Scan", "94.5%", "Cao", "Đã xác nhận"],
    ["#A1016", "24/04 14:14:23", "10.0.0.23", "192.168.1.10", "UDP", "Suspicious Traffic", "88.7%", "Trung bình", "Đang giám sát"],
    ["#A1015", "24/04 14:12:11", "192.168.1.77", "8.8.8.8", "TCP", "Brute Force", "93.1%", "Cao", "Đã xác nhận"],
]


class DetectionPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detectionScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("detectionContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Phát hiện bất thường")
        heading.setObjectName("detectionHeading")
        heading.setMaximumWidth(560)
        intro.addWidget(heading)
        subtitle = QLabel("Ứng dụng AI/Machine Learning để phát hiện các hành vi bất thường trong lưu lượng mạng  •  Dữ liệu mô phỏng")
        subtitle.setObjectName("detectionSubtitle")
        subtitle.setMaximumWidth(620)
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro)
        header.addStretch()
        self.date_button = QPushButton("  24/04/2025 00:00    →    24/04/2025 23:59  ˅")
        self.date_button.setObjectName("dateRangeButton")
        self.date_button.setIcon(icon("calendar", "#AFC7E4"))
        self.date_button.setFixedWidth(320)
        header.addWidget(self.date_button)
        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("detectionRefresh")
        refresh.setIcon(icon("refresh", "#FFFFFF"))
        refresh.clicked.connect(self.refresh_data)
        header.addWidget(refresh)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setSpacing(10)
        metric_data = [
            MonitorMetric("Tổng phát hiện", "27", "↑ 22.7%", "#FF5963", "warning"),
            MonitorMetric("Lưu lượng bình thường", "1,221", "↑ 5.3%", "#18DA8B", "shield"),
            MonitorMetric("Lưu lượng bất thường", "27", "↑ 22.7%", "#FF5058", "bug"),
            MonitorMetric("Độ tin cậy trung bình", "92.3%", "↑ 2.1%", "#A751F0", "brain"),
            MonitorMetric("Cảnh báo mức cao", "8", "↑ 33.3%", "#FF9D38", "siren"),
        ]
        for column, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        middle = QGridLayout()
        middle.setSpacing(10)
        trend_panel = Panel("Xu hướng phát hiện bất thường theo thời gian")
        trend_legend = QHBoxLayout()
        trend_legend.addStretch()
        trend_legend.addWidget(legend("#2F9BFF", "Bình thường"))
        trend_legend.addWidget(legend("#FF4F5E", "Bất thường"))
        trend_panel.box.addLayout(trend_legend)
        normal = [2, 3, 2, 4, 3, 4, 2, 3, 5, 4, 6, 5, 4, 6, 5, 7, 4, 5, 7, 4, 6, 5, 8, 6, 7, 5, 8, 6, 9, 7, 8, 5]
        anomaly = [1, 3, 2, 5, 2, 6, 3, 10, 4, 9, 3, 7, 13, 6, 5, 11, 19, 7, 5, 4, 3, 5, 2, 4, 3, 5, 2, 7, 3, 6, 4, 7]
        self.trend_chart = Chart([(normal, "#2F9BFF"), (anomaly, "#FF4F5E")], 25, ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"])
        self.trend_chart.setMinimumHeight(175)
        trend_panel.box.addWidget(self.trend_chart, 1)
        middle.addWidget(trend_panel, 0, 0, 1, 2)

        attack_panel = Panel("Phân loại loại tấn công")
        attack_body = QHBoxLayout()
        attack_body.addWidget(DonutChart([(37.0, "#FF4652"), (22.2, "#FF9B37"), (14.8, "#2F9BFF"), (11.1, "#A64BE6"), (7.4, "#1ED28A"), (7.4, "#F4DA54")], "Tổng", "27", "phát hiện"), 1)
        attack_legend = QVBoxLayout()
        for color, name, value in [("#FF4652", "DDoS", "37.0%"), ("#FF6B43", "Port Scan", "22.2%"), ("#2F9BFF", "Brute Force", "14.8%"), ("#B86AC9", "SQL Injection", "11.1%"), ("#F2C94C", "Malware", "7.4%"), ("#8C45DD", "Protocol Anomaly", "7.4%")]:
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(11, 11)
            swatch.setStyleSheet(f"background:{color}; border-radius:3px;")
            row.addWidget(swatch)
            name_label = QLabel(name)
            name_label.setObjectName("attackLegend")
            row.addWidget(name_label)
            row.addStretch()
            value_label = QLabel(value)
            value_label.setObjectName("attackLegend")
            row.addWidget(value_label)
            attack_legend.addLayout(row)
        attack_body.addLayout(attack_legend)
        attack_panel.box.addLayout(attack_body, 1)
        middle.addWidget(attack_panel, 0, 2)
        middle.setColumnStretch(0, 1)
        middle.setColumnStretch(1, 1)
        middle.setColumnStretch(2, 1)
        middle.setRowMinimumHeight(0, 238)
        root.addLayout(middle)

        bottom = QGridLayout()
        bottom.setSpacing(10)
        bottom.addWidget(self._detections_panel(), 0, 0, 1, 3)
        self.detail_panel = self._detail_panel()
        bottom.addWidget(self.detail_panel, 0, 3)
        bottom.setColumnStretch(0, 1)
        bottom.setColumnStretch(1, 1)
        bottom.setColumnStretch(2, 1)
        bottom.setColumnStretch(3, 1)
        root.addLayout(bottom)
        self.setWidget(content)

    def _detections_panel(self) -> Panel:
        panel = Panel("Danh sách các lưu lượng bất thường được phát hiện")
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        search = QLineEdit()
        search.setObjectName("detectionSearch")
        search.setPlaceholderText("Tìm kiếm...")
        search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search)
        for value in ("Tất cả loại tấn công", "Tất cả mức độ rủi ro"):
            combo = QComboBox()
            combo.setObjectName("detectionCombo")
            combo.addItem(value)
            toolbar.addWidget(combo)
        export = QPushButton("  Xuất CSV")
        export.setObjectName("smallMonitorButton")
        export.setIcon(icon("download", "#B8CCE4"))
        toolbar.addWidget(export)
        panel.box.addLayout(toolbar)

        headers = ["ID", "Thời gian", "IP nguồn", "IP đích", "Giao thức", "Loại bất thường", "Độ tin cậy", "Mức độ", "Trạng thái", "Hành động"]
        self.table = QTableWidget(len(DETECTIONS), len(headers))
        self.table.setObjectName("detectionTable")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setFixedHeight(292)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(DETECTIONS):
            for c, value in enumerate(row + ["◉   ⋮"]):
                item = QTableWidgetItem(value)
                if c == 4:
                    item.setForeground(QColor("#39AFFF" if value == "TCP" else "#FFAE40" if value == "UDP" else "#AE78FF"))
                elif c == 7:
                    item.setForeground(QColor("#FF6262" if value == "Cao" else "#FFB13B" if value == "Trung bình" else "#3CAFFF"))
                elif c == 8:
                    item.setForeground(QColor("#FF6262" if value == "Đang xử lý" else "#20D98B" if value in ("Đã xác nhận", "Đã xử lý") else "#38BCE8"))
                self.table.setItem(r, c, item)
        self.table.selectRow(0)
        self.table.cellClicked.connect(lambda row, column: self.update_detail(row))
        panel.box.addWidget(self.table)
        footer = QHBoxLayout()
        count = QLabel("Hiển thị 1–10 / 27 kết quả")
        count.setObjectName("flowFooter")
        footer.addWidget(count)
        footer.addStretch()
        for page in ("‹", "1", "2", "3", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            footer.addWidget(button)
        panel.box.addLayout(footer)
        return panel

    def _detail_panel(self) -> Panel:
        panel = Panel("Chi tiết phát hiện")
        panel.setObjectName("detectionDetail")
        self.detail_alert = QLabel("⚠  #A1024 - DDoS Attack")
        self.detail_alert.setObjectName("detailAlert")
        panel.box.addWidget(self.detail_alert)
        separator = QFrame()
        separator.setObjectName("detailSeparator")
        separator.setFixedHeight(1)
        panel.box.addWidget(separator)
        self.detail_fields: dict[str, QLabel] = {}
        for key, label, value in [
            ("time", "Thời gian", "24/04/2025 14:32:11"), ("source", "IP nguồn", "10.0.0.23"),
            ("destination", "IP đích", "192.168.1.10"), ("protocol", "Giao thức", "TCP"),
            ("source_port", "Cổng nguồn", "52341"), ("destination_port", "Cổng đích", "80"),
            ("risk", "Mức độ rủi ro", "Cao"), ("status", "Trạng thái", "Đang xử lý"),
        ]:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("detailKey")
            row.addWidget(name)
            row.addStretch()
            field = QLabel(value)
            field.setObjectName("detailValue")
            row.addWidget(field)
            panel.box.addLayout(row)
            self.detail_fields[key] = field
        confidence_label = QLabel("Độ tin cậy")
        confidence_label.setObjectName("detailKey")
        panel.box.addWidget(confidence_label)
        self.confidence = QProgressBar()
        self.confidence.setObjectName("confidenceBar")
        self.confidence.setRange(0, 1000)
        self.confidence.setValue(985)
        self.confidence.setTextVisible(False)
        self.confidence.setFixedHeight(8)
        panel.box.addWidget(self.confidence)
        description_title = QLabel("Mô tả")
        description_title.setObjectName("detailSectionTitle")
        panel.box.addWidget(description_title)
        description = QLabel("Phát hiện lưu lượng TCP tăng đột biến với số lượng kết nối lớn trong thời gian ngắn, có dấu hiệu tấn công từ chối dịch vụ (DDoS).")
        description.setObjectName("detailDescription")
        description.setWordWrap(True)
        panel.box.addWidget(description)
        panel.box.addStretch()
        actions = QHBoxLayout()
        self.block_button = QPushButton("  Chặn IP")
        self.block_button.setObjectName("blockIpButton")
        self.block_button.setIcon(icon("blocked", "#FFFFFF"))
        self.block_button.clicked.connect(self.simulate_block)
        actions.addWidget(self.block_button)
        details = QPushButton("  Xem chi tiết")
        details.setObjectName("viewDetailButton")
        details.setIcon(icon("eye", "#9FC8EE"))
        actions.addWidget(details)
        panel.box.addLayout(actions)
        return panel

    def update_detail(self, row: int) -> None:
        item = DETECTIONS[row]
        self.detail_alert.setText(f"⚠  {item[0]} - {item[5]}")
        self.detail_fields["time"].setText("24/04/2025 " + item[1].split(" ")[1])
        self.detail_fields["source"].setText(item[2])
        self.detail_fields["destination"].setText(item[3])
        self.detail_fields["protocol"].setText(item[4])
        self.detail_fields["risk"].setText(item[7])
        self.detail_fields["status"].setText(item[8])
        self.confidence.setValue(int(float(item[6].rstrip("%")) * 10))
        self.block_button.setText("  Chặn IP")
        self.block_button.setEnabled(True)

    def simulate_block(self) -> None:
        self.block_button.setText("  Đã chặn (mô phỏng)")
        self.block_button.setEnabled(False)

    def refresh_data(self) -> None:
        self.trend_chart.refresh()
