"""Reports and system logs page using simulated security records."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.dashboard import DonutChart
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend


class DeviceEventRow(QWidget):
    def __init__(self, name: str, value: int, maximum: int, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        label = QLabel(name)
        label.setObjectName("reportDeviceName")
        label.setFixedWidth(92)
        row.addWidget(label)
        number = QLabel(f"{value:,}")
        number.setObjectName("reportDeviceValue")
        number.setFixedWidth(45)
        number.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(number)
        bar = QProgressBar()
        bar.setObjectName("reportDeviceBar")
        bar.setRange(0, maximum)
        bar.setValue(value)
        bar.setTextVisible(False)
        bar.setFixedHeight(13)
        bar.setStyleSheet(f"QProgressBar#reportDeviceBar::chunk {{ background:{color}; border-radius:5px; }}")
        row.addWidget(bar, 1)


class ReportsPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reportsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("reportsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)
        title = QLabel("Báo cáo & Nhật ký")
        title.setObjectName("reportsHeading")
        title.setMaximumWidth(550)
        intro.addWidget(title)
        subtitle = QLabel("Xem lịch sử hoạt động, tạo báo cáo thống kê và phân tích xu hướng an ninh mạng  •  Dữ liệu mô phỏng")
        subtitle.setObjectName("reportsSubtitle")
        subtitle.setMaximumWidth(620)
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro)
        header.addStretch()
        date = QPushButton("  24/04/2025 00:00    →    24/04/2025 23:59  ˅")
        date.setObjectName("reportsDate")
        date.setIcon(icon("calendar", "#AFC7E4"))
        date.setFixedWidth(320)
        header.addWidget(date)
        self.create_button = QPushButton("  Tạo báo cáo")
        self.create_button.setObjectName("createReportButton")
        self.create_button.setIcon(icon("document", "#FFFFFF"))
        self.create_button.clicked.connect(self.create_report)
        header.addWidget(self.create_button)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setSpacing(10)
        for column, data in enumerate([
            MonitorMetric("Tổng sự kiện", "5,281", "↑ 12.4%", "#229FFF", "document"),
            MonitorMetric("Sự kiện bất thường", "127", "↑ 25.7%", "#FF5260", "shield"),
            MonitorMetric("Sự kiện giảm thiểu", "82", "↑ 18.9%", "#A44EEF", "document"),
            MonitorMetric("Báo cáo đã tạo", "24", "↑ 33.3%", "#18DA8B", "check"),
        ]):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        overview = QGridLayout()
        overview.setSpacing(10)
        timeline = Panel("Số lượng sự kiện theo thời gian")
        timeline_legend = QHBoxLayout()
        timeline_legend.addStretch()
        for color, text in [("#2196F3", "Tổng"), ("#FF4C5E", "Bất thường"), ("#18D88B", "Giảm thiểu")]:
            timeline_legend.addWidget(legend(color, text))
        timeline.box.addLayout(timeline_legend)
        timeline.box.addWidget(Chart([
            ([44, 51, 68, 55, 66, 59, 74, 62, 91, 73, 110, 89, 121, 95, 149, 112, 139, 168, 124, 137, 154, 109, 82, 97, 79, 103, 71, 115, 126, 96, 68, 78], "#2196F3"),
            ([22, 31, 29, 42, 34, 38, 51, 41, 62, 48, 70, 53, 77, 59, 82, 61, 93, 66, 73, 58, 69, 52, 45, 51, 42, 60, 38, 65, 53, 47, 34, 41], "#FF4C5E"),
            ([11, 18, 14, 21, 17, 23, 19, 28, 22, 31, 24, 29, 22, 34, 27, 42, 31, 37, 29, 33, 25, 28, 19, 23, 18, 31, 21, 34, 24, 26, 17, 22], "#18D88B"),
        ], 200, ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]), 1)
        overview.addWidget(timeline, 0, 0, 1, 2)

        categories = Panel("Phân loại sự kiện")
        category_body = QHBoxLayout()
        category_body.addWidget(DonutChart([(52.3, "#2196F3"), (18.7, "#FF4250"), (15.5, "#18D88B"), (8.2, "#FFA22F"), (5.3, "#9FB2CF")], "", "5,281", "sự kiện"), 1)
        category_legend = QVBoxLayout()
        for color, text, value in [("#2196F3", "Giám sát lưu lượng", "52.3%"), ("#FF4250", "Trong phát hiện", "18.7%"), ("#18D88B", "Trong giảm thiểu", "15.5%"), ("#FFA22F", "Lỗi hệ thống", "8.2%"), ("#9FB2CF", "Khác", "5.3%")]:
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
        categories.box.addLayout(category_body, 1)
        overview.addWidget(categories, 0, 2)

        devices = Panel("Sự kiện theo loại thiết bị")
        for name, value, color in [("Firewall", 1842, "#2196F3"), ("Open vSwitch", 1231, "#9A4BE7"), ("Host", 987, "#FFA238"), ("SDN Controller", 632, "#18D88B"), ("Others", 589, "#91A9CD")]:
            devices.box.addWidget(DeviceEventRow(name, value, 1842, color))
        overview.addWidget(devices, 0, 3)
        for column in range(4):
            overview.setColumnStretch(column, 1)
        overview.setRowMinimumHeight(0, 205)
        root.addLayout(overview)
        root.addWidget(self._reports_panel())
        root.addWidget(self._logs_panel())
        self.setWidget(content)

    @staticmethod
    def _base_table(headers: list[str], rows: list[list[str]], height: int, object_name: str) -> QTableWidget:
        table = QTableWidget(len(rows), len(headers))
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(19)
        table.verticalHeader().setMinimumSectionSize(18)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setFixedHeight(height)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(value))
        return table

    def _reports_panel(self) -> Panel:
        panel = Panel("Danh sách báo cáo")
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        search = QLineEdit()
        search.setObjectName("reportSearch")
        search.setPlaceholderText("Tìm kiếm báo cáo...")
        search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search)
        report_type = QComboBox()
        report_type.setObjectName("reportCombo")
        report_type.addItem("Tất cả loại báo cáo")
        toolbar.addWidget(report_type)
        export = QPushButton("  Xuất CSV")
        export.setObjectName("reportExport")
        export.setIcon(icon("download", "#AFC8E3"))
        toolbar.addWidget(export)
        panel.box.addLayout(toolbar)
        rows = [
            ["#RPT024", "Báo cáo tổng quan ngày", "▣  Ngày", "24/04/2025 00:00", "24/04/2025 23:59", "5,281", "127", "82", "Hoàn thành", "◉   ⇩   ⋮"],
            ["#RPT023", "Báo cáo tấn công DDoS", "▣  Tấn công", "24/04/2025 08:00", "24/04/2025 12:00", "642", "35", "28", "Hoàn thành", "◉   ⇩   ⋮"],
            ["#RPT022", "Báo cáo lưu lượng mạng", "▣  Lưu lượng", "23/04/2025 00:00", "23/04/2025 23:59", "4,912", "101", "67", "Hoàn thành", "◉   ⇩   ⋮"],
            ["#RPT021", "Báo cáo giảm thiểu rủi ro", "▣  Giảm thiểu", "22/04/2025 00:00", "22/04/2025 23:59", "3,421", "89", "145", "Hoàn thành", "◉   ⇩   ⋮"],
            ["#RPT020", "Báo cáo hệ thống", "▣  Hệ thống", "21/04/2025 00:00", "21/04/2025 23:59", "2,983", "72", "41", "Hoàn thành", "◉   ⇩   ⋮"],
        ]
        table = self._base_table(["ID", "Tên báo cáo", "Loại báo cáo", "Thời gian bắt đầu", "Thời gian kết thúc", "Tổng sự kiện", "Bất thường", "Giảm thiểu", "Trạng thái", "Hành động"], rows, 140, "reportsTable")
        for row in range(len(rows)):
            table.item(row, 8).setForeground(QColor("#1DDB8C"))
        panel.box.addWidget(table)
        footer = QHBoxLayout()
        count = QLabel("Hiển thị 1–5 / 24 báo cáo")
        count.setObjectName("flowFooter")
        footer.addWidget(count)
        footer.addStretch()
        for page in ("‹", "1", "2", "3", "4", "5", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            footer.addWidget(button)
        panel.box.addLayout(footer)
        return panel

    def _logs_panel(self) -> Panel:
        panel = Panel("Nhật ký hệ thống")
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        search = QLineEdit()
        search.setObjectName("logSearch")
        search.setPlaceholderText("Tìm kiếm nhật ký...")
        search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search)
        for text in ("Tất cả mức độ", "Tất cả loại sự kiện"):
            combo = QComboBox()
            combo.setObjectName("reportCombo")
            combo.addItem(text)
            toolbar.addWidget(combo)
        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("reportExport")
        refresh.setIcon(icon("refresh", "#AFC8E3"))
        toolbar.addWidget(refresh)
        panel.box.addLayout(toolbar)
        rows = [
            ["▣", "24/04 14:32:11", "Cao", "Phát hiện bất thường", "192.168.1.10", "Phát hiện lưu lượng TCP bất thường (DDoS Attack)"],
            ["▣", "24/04 14:31:05", "Trung bình", "Giảm thiểu rủi ro", "Firewall", "Áp dụng rule chặn IP 10.0.0.23 (Thời gian: 30 phút)"],
            ["▣", "24/04 14:29:48", "Thấp", "Giám sát lưu lượng", "Open vSwitch", "Lưu lượng tăng đột biến (125.4 Mbps)"],
            ["▣", "24/04 14:28:17", "Cao", "Phát hiện bất thường", "192.168.1.77", "Phát hiện tấn công SQL Injection"],
            ["▣", "24/04 14:26:09", "Trung bình", "Hệ thống", "SDN Controller", "Kết nối tới 192.168.1.50 đến controller"],
            ["▣", "24/04 14:25:33", "Thấp", "Giám sát lưu lượng", "Host", "Lưu lượng UDP tăng (82.1 Mbps)"],
        ]
        table = self._base_table(["", "Thời gian", "Mức độ", "Loại sự kiện", "Thiết bị/Nguồn", "Mô tả"], rows, 145, "logsTable")
        for row, data in enumerate(rows):
            color = "#FF5360" if data[2] == "Cao" else "#FFB432" if data[2] == "Trung bình" else "#36A7FF"
            table.item(row, 0).setForeground(QColor(color))
            table.item(row, 2).setForeground(QColor(color))
        panel.box.addWidget(table)
        return panel

    def create_report(self) -> None:
        self.create_button.setText("  Đang tạo...")
        self.create_button.setEnabled(False)
        QTimer.singleShot(800, self._report_created)

    def _report_created(self) -> None:
        self.create_button.setText("  Đã tạo báo cáo mô phỏng")
        self.create_button.setEnabled(True)
