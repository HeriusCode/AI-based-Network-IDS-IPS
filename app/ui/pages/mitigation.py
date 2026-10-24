"""IPS mitigation policy page using simulation-only actions."""

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
from app.ui.pages.monitoring import MetricCard, MonitorMetric, Panel, legend


RULES = [
    ["#R1024", "192.168.1.100", "any", "TCP", "80", "Chặn", "1", "28 phút", "Đang hoạt động"],
    ["#R1023", "10.0.0.23", "192.168.1.10", "UDP", "any", "Giới hạn (10 Mbps)", "2", "1 giờ 25 phút", "Đang hoạt động"],
    ["#R1022", "203.113.5.21", "any", "TCP", "443", "Chặn", "1", "15 phút", "Đang hoạt động"],
    ["#R1021", "192.168.1.50", "8.8.8.8", "ICMP", "any", "Giới hạn (5 Mbps)", "3", "40 phút", "Đang hoạt động"],
    ["#R1020", "192.168.1.77", "1.1.1.1", "TCP", "53", "Chặn", "2", "Đã hết hạn", "Không hoạt động"],
    ["#R1019", "any", "any", "TCP", "22", "Chặn", "1", "Vô thời hạn", "Đang hoạt động"],
    ["#R1018", "10.0.0.0/24", "any", "UDP", "any", "Giới hạn (2 Mbps)", "4", "3 giờ 10 phút", "Đang hoạt động"],
]


class MitigationChart(QWidget):
    before = [151, 173, 146, 153, 143, 162, 186, 168, 183, 170, 176, 195, 187, 211, 184, 207, 186, 199, 181, 193, 250, 198, 161, 149, 171, 191, 174, 186, 181, 193, 197]
    after = [72, 86, 75, 80, 91, 79, 86, 97, 83, 91, 79, 88, 104, 94, 102, 96, 107, 91, 98, 104, 83, 90, 76, 93, 88, 96, 84, 101, 91, 105, 88]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(43, 8, self.width() - 52, self.height() - 31)
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(7):
            y = chart.bottom() - chart.height() * step / 6
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(0, y - 8, 35, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(step * 50))
            painter.setPen(QPen(QColor("#20364D"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
        for index, label in enumerate(["14:10", "14:15", "14:20", "14:25", "14:30", "14:35"]):
            x = chart.left() + chart.width() * index / 5
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(x - 24, chart.bottom() + 6, 48, 16), Qt.AlignmentFlag.AlignCenter, label)
        self._series(painter, chart, self.before, QColor("#FF4653"), True)
        self._series(painter, chart, self.after, QColor("#249CFF"), False)
        apply_x = chart.left() + chart.width() * 0.59
        painter.setPen(QPen(QColor("#D8E2EC"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(apply_x, chart.top()), QPointF(apply_x, chart.bottom()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#516D8D"))
        painter.drawRoundedRect(QRectF(apply_x - 26, chart.top() + 4, 92, 23), 4, 4)
        painter.setPen(QColor("#F1F5F9"))
        painter.drawText(QRectF(apply_x - 26, chart.top() + 4, 92, 23), Qt.AlignmentFlag.AlignCenter, "Áp dụng chính sách")

    @staticmethod
    def _series(painter: QPainter, chart: QRectF, values: list[int], color: QColor, fill: bool) -> None:
        points = [QPointF(chart.left() + chart.width() * i / (len(values) - 1), chart.bottom() - chart.height() * value / 300) for i, value in enumerate(values)]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if fill:
            area = QPainterPath(path)
            area.lineTo(chart.right(), chart.bottom())
            area.lineTo(chart.left(), chart.bottom())
            area.closeSubpath()
            gradient = QLinearGradient(0, chart.top(), 0, chart.bottom())
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 100))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 5))
            painter.fillPath(area, gradient)
        painter.setPen(QPen(color, 2.0))
        painter.drawPath(path)


class HistoryRow(QFrame):
    def __init__(self, icon_name: str, color: str, title: str, timestamp: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 3, 4, 3)
        badge = QLabel()
        badge.setObjectName("historyIcon")
        badge.setPixmap(icon(icon_name, color, 17).pixmap(17, 17))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(32, 32)
        row.addWidget(badge)
        copy = QVBoxLayout()
        copy.setSpacing(0)
        name = QLabel(title)
        name.setObjectName("historyTitle")
        copy.addWidget(name)
        time = QLabel(timestamp)
        time.setObjectName("historyTime")
        copy.addWidget(time)
        row.addLayout(copy, 1)


class MitigationPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mitigationScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("mitigationContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 13, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Giảm thiểu rủi ro (IPS)")
        heading.setObjectName("mitigationHeading")
        intro.addWidget(heading)
        subtitle = QLabel("Quản lý và thực thi các chính sách bảo vệ mạng để giảm thiểu rủi ro an ninh mạng  •  Chế độ mô phỏng")
        subtitle.setObjectName("mitigationSubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro)
        header.addStretch()
        self.ips_toggle = QPushButton("●  IPS đang hoạt động")
        self.ips_toggle.setObjectName("ipsToggle")
        self.ips_toggle.setCheckable(True)
        self.ips_toggle.setChecked(True)
        self.ips_toggle.clicked.connect(self.toggle_ips)
        header.addWidget(self.ips_toggle)
        self.pause_button = QPushButton("  Tạm dừng IPS")
        self.pause_button.setObjectName("pauseIpsButton")
        self.pause_button.setIcon(icon("pause", "#FFFFFF"))
        self.pause_button.clicked.connect(self.toggle_ips)
        header.addWidget(self.pause_button)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setSpacing(10)
        for column, data in enumerate([
            MonitorMetric("Tổng số rule đang hoạt động", "12", "↑ 20.0%", "#17DB8C", "shield"),
            MonitorMetric("Lưu lượng bị chặn", "1,245", "↑ 35.2%", "#FF4E5C", "blocked"),
            MonitorMetric("Lưu lượng bị giới hạn", "856", "↑ 18.7%", "#FFA12F", "speed"),
            MonitorMetric("Tổng sự kiện giảm thiểu", "2,101", "↑ 22.5%", "#229FFF", "document"),
        ]):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        workspace = QGridLayout()
        workspace.setSpacing(10)
        traffic = Panel("Lưu lượng sau khi áp dụng chính sách")
        traffic_legend = QHBoxLayout()
        traffic_legend.addStretch()
        traffic_legend.addWidget(legend("#FF4653", "Trước khi giảm thiểu"))
        traffic_legend.addWidget(legend("#249CFF", "Sau khi giảm thiểu"))
        traffic_legend.addWidget(legend("#BCD5EC", "Thời điểm áp dụng"))
        traffic.box.addLayout(traffic_legend)
        traffic.box.addWidget(MitigationChart(), 1)
        workspace.addWidget(traffic, 0, 0, 1, 2)
        effectiveness = Panel("Hiệu quả giảm thiểu")
        effectiveness.box.addWidget(DonutChart([(45.2, "#16DA8B"), (23.2, "#2196F3"), (31.6, "#7185A9")], "", "68.4%", "lưu lượng bất thường\nđã được xử lý"), 1)
        for color, label_text, value in [("#16DA8B", "Lưu lượng bị chặn", "45.2%"), ("#2196F3", "Lưu lượng bị giới hạn", "23.2%"), ("#7185A9", "Lưu lượng còn lại", "31.6%")]:
            line = QHBoxLayout()
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background:{color}; border-radius:3px;")
            line.addWidget(dot)
            line.addWidget(QLabel(label_text))
            line.addStretch()
            line.addWidget(QLabel(value))
            effectiveness.box.addLayout(line)
        workspace.addWidget(effectiveness, 0, 2)
        workspace.addWidget(self._new_rule_panel(), 0, 3)
        workspace.addWidget(self._rules_panel(), 1, 0, 1, 3)
        workspace.addWidget(self._history_panel(), 1, 3)
        workspace.setColumnStretch(0, 1)
        workspace.setColumnStretch(1, 1)
        workspace.setColumnStretch(2, 1)
        workspace.setColumnStretch(3, 1)
        workspace.setRowMinimumHeight(0, 300)
        root.addLayout(workspace)
        self.setWidget(content)

    def _rules_panel(self) -> Panel:
        panel = Panel("Danh sách chính sách giảm thiểu (IPS Rules)")
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        search = QLineEdit()
        search.setObjectName("ruleSearch")
        search.setPlaceholderText("Tìm kiếm rule...")
        search.addAction(icon("search", "#8299B7"), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search)
        for value in ("Tất cả hành động", "Tất cả trạng thái"):
            combo = QComboBox()
            combo.setObjectName("ruleCombo")
            combo.addItem(value)
            toolbar.addWidget(combo)
        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("smallMonitorButton")
        refresh.setIcon(icon("refresh", "#AFC8E3"))
        toolbar.addWidget(refresh)
        panel.box.addLayout(toolbar)
        headers = ["ID", "Nguồn IP", "Đích IP", "Giao thức", "Cổng", "Hành động", "Ưu tiên", "Thời gian còn lại", "Trạng thái", "Tác vụ"]
        self.rule_table = QTableWidget(len(RULES), len(headers))
        self.rule_table.setObjectName("ruleTable")
        self.rule_table.setHorizontalHeaderLabels(headers)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.setShowGrid(False)
        self.rule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rule_table.setFixedHeight(220)
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(RULES):
            for c, value in enumerate(row + ["✎   ♲"]):
                item = QTableWidgetItem(value)
                if c == 5:
                    item.setForeground(QColor("#FF5A62" if value == "Chặn" else "#FFB12E"))
                elif c == 8:
                    item.setForeground(QColor("#1DDB8C" if value == "Đang hoạt động" else "#9AAABD"))
                elif c == 9:
                    item.setForeground(QColor("#279FFF"))
                self.rule_table.setItem(r, c, item)
        panel.box.addWidget(self.rule_table)
        footer = QHBoxLayout()
        count = QLabel("Hiển thị 1–7 / 12 rule")
        count.setObjectName("flowFooter")
        footer.addWidget(count)
        footer.addStretch()
        for page in ("‹", "1", "2", "3", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            footer.addWidget(button)
        panel.box.addLayout(footer)
        return panel

    def _new_rule_panel(self) -> Panel:
        panel = Panel("Thêm chính sách mới")
        panel.box.setSpacing(4)
        panel.box.setContentsMargins(12, 8, 12, 8)
        tabs = QHBoxLayout()
        for index, text in enumerate(("Chặn lưu lượng", "Giới hạn tốc độ", "Tùy chỉnh")):
            button = QPushButton(text)
            button.setObjectName("activeRuleTab" if index == 0 else "ruleTab")
            tabs.addWidget(button)
        panel.box.addLayout(tabs)
        self.source_input = self._field(panel, "Nguồn (Source IP)", "VD: 192.168.1.100 hoặc 192.168.1.0/24")
        self.destination_input = self._field(panel, "Đích (Destination IP)", "VD: 192.168.1.10 hoặc any")
        protocol_row = QHBoxLayout()
        protocol_box = QVBoxLayout()
        protocol_box.addWidget(QLabel("Giao thức"))
        protocol = QComboBox()
        protocol.setObjectName("ruleFormCombo")
        protocol.addItems(["TCP", "UDP", "ICMP", "Any"])
        protocol_box.addWidget(protocol)
        protocol_row.addLayout(protocol_box)
        port_box = QVBoxLayout()
        port_box.addWidget(QLabel("Cổng đích"))
        port = QLineEdit()
        port.setObjectName("ruleInput")
        port.setPlaceholderText("VD: 80, 443")
        port_box.addWidget(port)
        protocol_row.addLayout(port_box)
        panel.box.addLayout(protocol_row)
        duration_box = QVBoxLayout()
        duration_box.addWidget(QLabel("Thời gian áp dụng"))
        duration = QComboBox()
        duration.setObjectName("ruleFormCombo")
        duration.addItems(["30 phút", "1 giờ", "3 giờ", "Vô thời hạn"])
        duration_box.addWidget(duration)
        panel.box.addLayout(duration_box)
        self.reason_input = self._field(panel, "Lý do / Mô tả", "Nhập lý do áp dụng rule...")
        actions = QHBoxLayout()
        add = QPushButton("  Thêm rule")
        add.setObjectName("addRuleButton")
        add.setIcon(icon("shield", "#FFFFFF"))
        add.clicked.connect(self.add_rule)
        actions.addWidget(add)
        reset = QPushButton("  Đặt lại")
        reset.setObjectName("resetRuleButton")
        reset.setIcon(icon("refresh", "#AFC8E3"))
        reset.clicked.connect(self.reset_form)
        actions.addWidget(reset)
        panel.box.addLayout(actions)
        self.rule_status = QLabel("")
        self.rule_status.setObjectName("ruleFormStatus")
        panel.box.addWidget(self.rule_status)
        return panel

    @staticmethod
    def _field(panel: Panel, label_text: str, placeholder: str) -> QLineEdit:
        label = QLabel(label_text)
        label.setObjectName("ruleFormLabel")
        panel.box.addWidget(label)
        field = QLineEdit()
        field.setObjectName("ruleInput")
        field.setPlaceholderText(placeholder)
        panel.box.addWidget(field)
        return field

    def _history_panel(self) -> Panel:
        panel = Panel("Lịch sử giảm thiểu")
        for data in [
            ("blocked", "#FF4E5C", "Đã chặn lưu lượng từ 192.168.1.100", "24/04/2025 14:32:11"),
            ("speed", "#FFA12F", "Áp dụng giới hạn tốc độ (10 Mbps)", "24/04/2025 14:30:45"),
            ("blocked", "#FF4E5C", "Đã chặn tấn công DDoS", "24/04/2025 14:28:17"),
            ("check", "#18DA8B", "Gỡ rule #R1016 (hết hạn)", "24/04/2025 14:25:33"),
            ("speed", "#FFA12F", "Giới hạn lưu lượng bất thường", "24/04/2025 14:21:05"),
        ]:
            panel.box.addWidget(HistoryRow(*data))
        return panel

    def toggle_ips(self) -> None:
        active = not self.ips_toggle.isChecked() if self.sender() is self.pause_button else self.ips_toggle.isChecked()
        self.ips_toggle.setChecked(active)
        self.ips_toggle.setText("●  IPS đang hoạt động" if active else "●  IPS đang tạm dừng")
        self.pause_button.setText("  Tạm dừng IPS" if active else "  Tiếp tục IPS")
        self.pause_button.setIcon(icon("pause" if active else "activity", "#FFFFFF"))

    def add_rule(self) -> None:
        if not self.source_input.text().strip():
            self.rule_status.setText("Vui lòng nhập IP nguồn.")
            self.rule_status.setProperty("valid", False)
        else:
            self.rule_status.setText("Đã thêm rule mô phỏng thành công.")
            self.rule_status.setProperty("valid", True)
        self.rule_status.style().unpolish(self.rule_status)
        self.rule_status.style().polish(self.rule_status)

    def reset_form(self) -> None:
        self.source_input.clear()
        self.destination_input.clear()
        self.reason_input.clear()
        self.rule_status.clear()
