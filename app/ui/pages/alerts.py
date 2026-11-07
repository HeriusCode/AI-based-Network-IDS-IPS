"""Security alerts page with interactive triage, deep inspection, and simulated IPS response actions."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
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
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.dashboard import DonutChart, make_badge_cell, make_text_cell
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend_chip

# Backward compatible alias
legend = legend_chip


ALERTS = [
    ["#A1024", "24/04 14:32:11", "10.0.0.23", "192.168.1.10", "DDoS Attack", "Nghiêm trọng", "Lưu lượng TCP SYN tăng đột biến", "Đang xử lý"],
    ["#A1023", "24/04 14:30:45", "203.113.5.21", "192.168.1.10", "Port Scan", "Cao", "Quét cổng hàng loạt TCP/UDP", "Chưa xử lý"],
    ["#A1022", "24/04 14:28:17", "192.168.1.77", "1.1.1.1", "Brute Force", "Cao", "Đăng nhập SSH thất bại liên tục", "Đang xử lý"],
    ["#A1021", "24/04 14:26:09", "10.0.0.56", "192.168.1.10", "SQL Injection", "Trung bình", "Phát hiện payload UNION SELECT SQL", "Đã xử lý"],
    ["#A1020", "24/04 14:23:33", "192.168.1.50", "8.8.8.8", "Malware", "Cao", "Kết nối C2 domain mã độc botnet", "Chưa xử lý"],
    ["#A1019", "24/04 14:21:05", "203.113.5.21", "192.168.1.10", "DDoS Attack", "Nghiêm trọng", "Lưu lượng UDP Flood bất thường", "Đang xử lý"],
    ["#A1018", "24/04 14:19:27", "10.0.0.89", "192.168.1.20", "Port Scan", "Trung bình", "Dò quét cổng dịch vụ quản trị", "Đã xử lý"],
    ["#A1017", "24/04 14:16:44", "192.168.1.100", "203.113.5.21", "Suspicious Traffic", "Thấp", "Truy cập URL bất thường ngoài ca trực", "Đã xử lý"],
    ["#A1016", "24/04 14:14:23", "10.0.0.23", "192.168.1.10", "Brute Force", "Cao", "Nhiều lần thử mật khẩu FTP sai", "Chưa xử lý"],
    ["#A1015", "24/04 14:12:11", "192.168.1.77", "8.8.8.8", "Protocol Anomaly", "Trung bình", "Gói tin ICMP có trường padding lạ", "Đã xử lý"],
]

ALERT_DETAILS = [
    {
        "protocol": "TCP (SYN Flood)", "src_port": "52341", "dst_port": "80 (HTTP)",
        "incoming": "125.4 Mbps", "outgoing": "118.2 Mbps", "packets": "1,245,536",
        "duration": "2 phút 15 giây", "confidence": "98.5%",
        "analysis": "Phát hiện lưu lượng TCP SYN tăng đột biến từ địa chỉ 10.0.0.23 đến 192.168.1.10. Tỷ lệ gói tin SYN/ACK bất thường, có dấu hiệu làm cạn kiệt tài nguyên backlog của máy chủ đích.",
    },
    {
        "protocol": "TCP / UDP", "src_port": "44120", "dst_port": "1-1024",
        "incoming": "3.2 Mbps", "outgoing": "0.4 Mbps", "packets": "18,450",
        "duration": "1 phút 04 giây", "confidence": "94.2%",
        "analysis": "Phát hiện quét cổng tốc độ cao từ IP ngoại mạng 203.113.5.21. Địa chỉ nguồn gửi liên tục các gói probe thăm dò cổng dịch vụ nhằm tìm kiếm lỗ hổng chưa vá.",
    },
    {
        "protocol": "TCP (SSH)", "src_port": "51234", "dst_port": "22 (SSH)",
        "incoming": "1.8 Mbps", "outgoing": "0.2 Mbps", "packets": "9,240",
        "duration": "45 giây", "confidence": "92.1%",
        "analysis": "Ghi nhận 142 lần xác thực thất bại liên tục trong vòng 45 giây từ IP 192.168.1.77 vào dịch vụ SSH. Mô hình phát hiện hành vi tấn công từ điển mật khẩu brute-force.",
    },
    {
        "protocol": "TCP (HTTP)", "src_port": "49152", "dst_port": "80 (Web App)",
        "incoming": "4.5 Mbps", "outgoing": "1.1 Mbps", "packets": "12,180",
        "duration": "12 giây", "confidence": "97.6%",
        "analysis": "Phát hiện chuỗi payload SQL Injection trong tham số GET/POST của yêu cầu HTTP. Mô hình Deep Learning nhận diện cấu trúc tấn công vượt qua bộ lọc WAF.",
    },
    {
        "protocol": "DNS / UDP", "src_port": "53100", "dst_port": "53 (DNS)",
        "incoming": "12.8 Mbps", "outgoing": "8.4 Mbps", "packets": "45,200",
        "duration": "3 phút 40 giây", "confidence": "89.3%",
        "analysis": "Máy trạm 192.168.1.50 phát sinh nhiều truy vấn DNS bất thường đến các máy chủ Command & Control (C2) đã bị liệt vào danh sách đen độc hại toàn cầu.",
    },
    {
        "protocol": "UDP Flood", "src_port": "55432", "dst_port": "80 (HTTP)",
        "incoming": "98.2 Mbps", "outgoing": "84.1 Mbps", "packets": "950,420",
        "duration": "1 phút 50 giây", "confidence": "96.8%",
        "analysis": "Đợt tấn công từ chối dịch vụ phân tán sử dụng giao thức UDP Flood. Lưu lượng ngập tràn cổng dịch vụ làm giảm chất lượng đường truyền mạng nội bộ.",
    },
    {
        "protocol": "TCP (Syn-Ack)", "src_port": "42110", "dst_port": "21, 22, 80",
        "incoming": "2.1 Mbps", "outgoing": "0.3 Mbps", "packets": "14,300",
        "duration": "55 giây", "confidence": "91.4%",
        "analysis": "Phát hiện hành vi thăm dò cổng FTP, SSH và Web từ mạng máy khách nội bộ 10.0.0.89, nghi ngờ máy trạm đã bị xâm nhập và đang do thám mạng ngang hàng.",
    },
    {
        "protocol": "TCP (HTTPS)", "src_port": "56789", "dst_port": "443 (HTTPS)",
        "incoming": "0.8 Mbps", "outgoing": "0.5 Mbps", "packets": "5,120",
        "duration": "30 giây", "confidence": "88.7%",
        "analysis": "Lưu lượng truy cập cổng 443 ngoài khung giờ làm việc tiêu chuẩn có biểu hiện truyền tải dữ liệu kích thước lớn hơn bình thường đến máy chủ lạ.",
    },
    {
        "protocol": "TCP (FTP)", "src_port": "51239", "dst_port": "21 (FTP)",
        "incoming": "1.9 Mbps", "outgoing": "0.2 Mbps", "packets": "11,400",
        "duration": "1 phút 20 giây", "confidence": "93.1%",
        "analysis": "Hàng trăm lượt kết nối xác thực tài khoản quản trị FTP thất bại từ máy trạm 10.0.0.23, có dấu hiệu quét mật khẩu mặc định của thiết bị.",
    },
    {
        "protocol": "ICMP", "src_port": "N/A", "dst_port": "N/A",
        "incoming": "15.4 Mbps", "outgoing": "2.1 Mbps", "packets": "125,000",
        "duration": "4 phút 10 giây", "confidence": "85.2%",
        "analysis": "Lưu lượng gói tin ICMP Echo Request tăng vọt bất thường kèm kích thước payload không theo chuẩn RFC, nghi ngờ hành vi ICMP Tunneling truyền dữ liệu lén lút.",
    },
]

ALERT_TRAFFIC_SERIES: list[tuple[list[tuple[list[int], str]], int]] = [
    ([([75, 105, 145, 132, 165, 155, 185, 177, 211, 298, 188, 136, 152, 168, 139, 128], "#FF5B79"),
      ([68, 96, 126, 119, 141, 137, 158, 151, 178, 238, 158, 122, 139, 151, 126, 115], "#3B82F6")], 300),
    ([([5, 8, 12, 18, 24, 32, 45, 38, 52, 60, 48, 35, 28, 22, 18, 14], "#F59E0B"),
      ([2, 3, 4, 6, 8, 10, 14, 12, 16, 18, 15, 11, 9, 7, 5, 4], "#3B82F6")], 80),
    ([([8, 12, 15, 20, 28, 35, 42, 38, 45, 52, 48, 40, 32, 25, 18, 12], "#F59E0B"),
      ([3, 4, 5, 7, 9, 11, 13, 12, 14, 16, 15, 12, 10, 8, 6, 5], "#3B82F6")], 70),
    ([([12, 15, 18, 25, 35, 48, 62, 55, 70, 85, 72, 58, 42, 30, 22, 16], "#FBBF24"),
      ([6, 8, 10, 14, 18, 24, 30, 27, 34, 42, 36, 29, 21, 15, 11, 8], "#3B82F6")], 100),
    ([([20, 25, 32, 45, 58, 72, 88, 80, 95, 115, 98, 82, 65, 48, 35, 25], "#F59E0B"),
      ([15, 18, 24, 32, 42, 52, 64, 58, 70, 84, 72, 60, 48, 36, 26, 18], "#3B82F6")], 140),
    ([([85, 115, 160, 145, 180, 170, 210, 195, 240, 310, 220, 160, 175, 190, 155, 140], "#FF5B79"),
      ([75, 102, 138, 128, 155, 148, 175, 165, 198, 260, 180, 140, 152, 165, 138, 125], "#3B82F6")], 320),
    ([([6, 9, 14, 21, 28, 38, 48, 42, 55, 65, 52, 40, 31, 24, 19, 15], "#FBBF24"),
      ([2, 3, 5, 7, 9, 12, 15, 13, 17, 20, 16, 12, 10, 8, 6, 5], "#3B82F6")], 80),
    ([([4, 6, 8, 11, 15, 20, 26, 23, 30, 36, 28, 22, 17, 13, 10, 8], "#38BDF8"),
      ([3, 4, 6, 8, 11, 14, 18, 16, 21, 25, 20, 15, 12, 9, 7, 6], "#3B82F6")], 50),
    ([([9, 13, 17, 24, 32, 42, 54, 48, 62, 75, 60, 47, 36, 28, 21, 15], "#F59E0B"),
      ([3, 4, 6, 8, 11, 14, 18, 16, 20, 24, 20, 16, 12, 9, 7, 5], "#3B82F6")], 90),
    ([([25, 32, 42, 58, 75, 95, 120, 110, 135, 165, 140, 115, 90, 70, 50, 35], "#FBBF24"),
      ([8, 11, 15, 20, 26, 34, 42, 38, 48, 58, 49, 40, 31, 24, 18, 12], "#3B82F6")], 180),
]


class AlertTimelineChart(QWidget):
    low = [1, 2, 1, 2, 1, 2, 2, 1, 3, 2, 1, 2, 3, 2, 4, 2, 1, 3, 2, 1, 2, 3, 2, 1, 2, 3, 1, 2, 1, 2, 1, 2]
    medium = [2, 3, 2, 4, 3, 5, 3, 4, 6, 4, 3, 5, 4, 8, 6, 4, 5, 6, 4, 5, 3, 5, 7, 4, 6, 4, 3, 5, 3, 4, 3, 5]
    high = [3, 5, 4, 6, 4, 7, 5, 9, 6, 7, 5, 8, 6, 11, 7, 5, 8, 6, 7, 5, 6, 8, 15, 7, 5, 9, 6, 12, 7, 5, 4, 9]
    critical = [5, 4, 6, 4, 5, 7, 5, 8, 6, 10, 7, 9, 6, 14, 11, 20, 8, 14, 7, 9, 6, 8, 10, 15, 7, 6, 9, 7, 12, 8, 5, 10]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(185)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        chart = QRectF(40, 10, self.width() - 52, self.height() - 34)

        # 1. Horizontal gridlines & Y-Axis labels
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(6):
            y = chart.bottom() - chart.height() * step / 5
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(0, y - 8, 32, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(step * 5))
            painter.setPen(QPen(QColor(40, 36, 82, 160), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

        # 2. X-Axis labels
        for index, label in enumerate(["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]):
            x = chart.left() + chart.width() * index / 6
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(x - 24, chart.bottom() + 6, 48, 16), Qt.AlignmentFlag.AlignCenter, label)

        # 3. Wave curves with smooth gradient area fill
        curves = [
            (self.critical, "#FF5B79"),
            (self.high, "#F59E0B"),
            (self.medium, "#FBBF24"),
            (self.low, "#3B82F6"),
        ]

        for values, color_hex in curves:
            points = [
                QPointF(chart.left() + chart.width() * i / (len(values) - 1), chart.bottom() - chart.height() * value / 25)
                for i, value in enumerate(values)
            ]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)

            # Gradient area fill
            area = QPainterPath(path)
            area.lineTo(chart.right(), chart.bottom())
            area.lineTo(chart.left(), chart.bottom())
            area.closeSubpath()

            grad = QLinearGradient(0, chart.top(), 0, chart.bottom())
            top_col = QColor(color_hex)
            top_col.setAlpha(40)
            bot_col = QColor(color_hex)
            bot_col.setAlpha(4)
            grad.setColorAt(0.0, top_col)
            grad.setColorAt(1.0, bot_col)

            painter.fillPath(area, grad)
            painter.setPen(QPen(QColor(color_hex), 2.0))
            painter.drawPath(path)


class AlertsPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("alertsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        self.current_selected_row = 0

        # ---------------------------------------------------------------------
        # 1. HEADER (Title, Subtitle & SOC Action Controls)
        # ---------------------------------------------------------------------
        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)

        title = QLabel("Cảnh báo an ninh")
        title.setObjectName("alertsHeading")
        intro.addWidget(title)

        subtitle = QLabel("Hệ thống phát hiện sớm và giám sát toàn diện các sự kiện bất thường, mối đe dọa an ninh mạng thời gian thực")
        subtitle.setObjectName("alertsSubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro, stretch=1)

        # Status badge
        status_badge = QLabel("●  SOC MONITORING ACTIVE")
        status_badge.setStyleSheet(
            "background: rgba(16, 185, 129, 0.14); color: #34D399; "
            "border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 10px; "
            "padding: 6px 14px; font-weight: 700; font-size: 11px;"
        )
        header.addWidget(status_badge)

        date_btn = QPushButton("  24/04/2025 00:00  →  24/04/2025 23:59  ˅")
        date_btn.setObjectName("alertsDate")
        date_btn.setIcon(icon("calendar", "#A78BFA", 14))
        header.addWidget(date_btn)

        export_btn = QPushButton("Xuất CSV")
        export_btn.setObjectName("alertsExport")
        export_btn.setIcon(icon("download", "#FFFFFF", 14))
        header.addWidget(export_btn)

        root.addLayout(header)

        # ---------------------------------------------------------------------
        # 2. ROW 1: 5 THẺ CHỈ SỐ AN NINH (KPIs ngang toàn chiều rộng)
        # ---------------------------------------------------------------------
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Tổng cảnh báo", "127", "↑ 25.7%", "#FF5B79", "warning"),
            MonitorMetric("Mức nghiêm trọng", "18 Khẩn cấp", "↑ 50.0%", "#FF4F5D", "blocked"),
            MonitorMetric("Mức độ cao", "37 Rủi ro cao", "↑ 28.1%", "#F59E0B", "warning"),
            MonitorMetric("Đang can thiệp", "27 Đang xử lý", "↓ 8.2%", "#3B82F6", "activity"),
            MonitorMetric("Đã khắc phục", "82 Đã xử lý", "● 64.6%", "#10B981", "shield"),
        ]
        for column, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # ---------------------------------------------------------------------
        # 3. ROW 2: BIỂU ĐỒ THEO THỜI GIAN (62%) & PHÂN LOẠI CẢNH BÁO DONUT (38%)
        # ---------------------------------------------------------------------
        middle = QGridLayout()
        middle.setSpacing(12)

        # 3.1 Dòng thời gian cảnh báo 24h
        timeline = Panel("Số lượng cảnh báo theo thời gian (24 Giờ)")
        timeline_legend = QHBoxLayout()
        timeline_legend.setContentsMargins(0, 0, 0, 4)
        timeline_legend.addStretch()
        timeline_legend.addWidget(legend_chip("#FF5B79", "Nghiêm trọng"))
        timeline_legend.addWidget(legend_chip("#F59E0B", "Cao"))
        timeline_legend.addWidget(legend_chip("#FBBF24", "Trung bình"))
        timeline_legend.addWidget(legend_chip("#3B82F6", "Thấp"))
        timeline.box.addLayout(timeline_legend)
        self.timeline_chart = AlertTimelineChart()
        timeline.box.addWidget(self.timeline_chart, 1)
        middle.addWidget(timeline, 0, 0)

        # 3.2 Phân loại cảnh báo Donut Chart & Thống kê
        category = Panel("Phân loại cảnh báo theo hình thức tấn công")
        category_body = QHBoxLayout()
        category_body.setSpacing(14)
        category_body.addWidget(
            DonutChart(
                [
                    (28.3, "#FF5B79"),
                    (22.0, "#F59E0B"),
                    (15.0, "#6366F1"),
                    (12.6, "#10B981"),
                    (8.7, "#8B5CF6"),
                    (13.4, "#94A3B8"),
                ],
                "",
                "127",
                "cảnh báo",
            ),
            1,
        )

        category_legend = QVBoxLayout()
        category_legend.setSpacing(6)
        cat_items = [
            ("#FF5B79", "DDoS Attack", "28.3%"),
            ("#F59E0B", "Port Scan", "22.0%"),
            ("#6366F1", "Brute Force", "15.0%"),
            ("#10B981", "Malware C2", "12.6%"),
            ("#8B5CF6", "SQL Injection", "8.7%"),
            ("#94A3B8", "Khác / Anomaly", "13.4%"),
        ]
        for color, text, value in cat_items:
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(f"background: {color}; border-radius: 3px;")
            row.addWidget(swatch)

            lbl = QLabel(text)
            lbl.setStyleSheet("color: #E2E8F0; font-size: 11px; font-weight: 500;")
            row.addWidget(lbl)
            row.addStretch()

            val_chip = QLabel(value)
            val_chip.setStyleSheet("color: #A78BFA; font-weight: 700; font-size: 11px;")
            row.addWidget(val_chip)
            category_legend.addLayout(row)

        category_body.addLayout(category_legend)
        category.box.addLayout(category_body, 1)
        middle.addWidget(category, 0, 1)

        middle.setColumnStretch(0, 62)
        middle.setColumnStretch(1, 38)
        root.addLayout(middle)

        # ---------------------------------------------------------------------
        # 4. ROW 3: BẢNG CẢNH BÁO TOÀN CHIỀU RỘNG (FULL WIDTH)
        # Giúp hiển thị trọn vẹn 9 cột không bao giờ bị cắt chữ hay ép layout
        # ---------------------------------------------------------------------
        root.addWidget(self._alerts_table_panel())

        # ---------------------------------------------------------------------
        # 5. ROW 4: CHI TIẾT CẢNH BÁO (58%) & LƯU LƯỢNG TẤN CÔNG (42%)
        # ---------------------------------------------------------------------
        detail_row = QGridLayout()
        detail_row.setSpacing(12)

        self.detail_panel = self._detail_panel()
        detail_row.addWidget(self.detail_panel, 0, 0)

        self.traffic_panel = self._traffic_spike_panel()
        detail_row.addWidget(self.traffic_panel, 0, 1)

        detail_row.setColumnStretch(0, 58)
        detail_row.setColumnStretch(1, 42)
        root.addLayout(detail_row)

        self.setWidget(content)

        # Initialize selection to first alert
        self.update_detail(0)

    # -------------------------------------------------------------------------
    # ALERTS TABLE PANEL (FULL WIDTH)
    # -------------------------------------------------------------------------
    def _alerts_table_panel(self) -> Panel:
        panel = Panel("Danh sách cảnh báo an ninh")
        panel.box.setSpacing(8)

        # Toolbar: Search & Dynamic Filters
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("alertSearch")
        self.search_input.setPlaceholderText("Tìm kiếm IP, ID, mã cảnh báo...")
        self.search_input.addAction(icon("search", "#8E8BA7", 14), QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.apply_filters)
        toolbar.addWidget(self.search_input)

        self.combo_severity = QComboBox()
        self.combo_severity.setObjectName("alertCombo")
        self.combo_severity.addItems(["Tất cả mức độ", "Nghiêm trọng", "Cao", "Trung bình", "Thấp"])
        self.combo_severity.currentIndexChanged.connect(self.apply_filters)
        toolbar.addWidget(self.combo_severity)

        self.combo_attack = QComboBox()
        self.combo_attack.setObjectName("alertCombo")
        self.combo_attack.addItems([
            "Tất cả loại tấn công",
            "DDoS Attack",
            "Port Scan",
            "Brute Force",
            "SQL Injection",
            "Malware",
            "Suspicious Traffic",
            "Protocol Anomaly",
        ])
        self.combo_attack.currentIndexChanged.connect(self.apply_filters)
        toolbar.addWidget(self.combo_attack)

        self.combo_status = QComboBox()
        self.combo_status.setObjectName("alertCombo")
        self.combo_status.addItems(["Tất cả trạng thái", "Chưa xử lý", "Đang xử lý", "Đã xử lý"])
        self.combo_status.currentIndexChanged.connect(self.apply_filters)
        toolbar.addWidget(self.combo_status)

        toolbar.addStretch()
        panel.box.addLayout(toolbar)

        headers = [
            "ID",
            "Thời gian",
            "IP nguồn",
            "IP đích",
            "Loại tấn công",
            "Mức độ",
            "Mô tả sự kiện",
            "Trạng thái",
            "Hành động",
        ]
        self.table = QTableWidget(len(ALERTS), len(headers))
        self.table.setObjectName("alertsTable")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setFixedHeight(330)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setMinimumWidth(300)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Unified Midnight Highlight Palette
        palette = self.table.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2D255E"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.table.setPalette(palette)

        header = self.table.horizontalHeader()
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

        # Set section resize modes
        for c in range(len(headers)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Mô tả sự kiện giãn hết cỡ

        # Exact pixel calibration for all columns
        self.table.setColumnWidth(0, 75)   # ID
        self.table.setColumnWidth(1, 125)  # Thời gian
        self.table.setColumnWidth(2, 110)  # IP nguồn
        self.table.setColumnWidth(3, 110)  # IP đích
        self.table.setColumnWidth(4, 120)  # Loại tấn công
        self.table.setColumnWidth(5, 125)  # Mức độ (125px đảm bảo chữ Nghiêm trọng không bao giờ bị cắt)
        # col 6 = Stretch (Mô tả sự kiện thoải mái 250px - 500px+)
        self.table.setColumnWidth(7, 115)  # Trạng thái
        self.table.setColumnWidth(8, 95)   # Hành động

        for r, row in enumerate(ALERTS):
            self.table.setRowHeight(r, 28)
            # ID (#A1024)
            self.table.setCellWidget(r, 0, make_text_cell(row[0], "#A78BFA", is_mono=True, is_bold=True, align_center=True))
            # Time
            self.table.setCellWidget(r, 1, make_text_cell(row[1], "#CBD5E1"))
            # Source IP
            self.table.setCellWidget(r, 2, make_text_cell(row[2], "#FFFFFF", is_mono=True))
            # Destination IP
            self.table.setCellWidget(r, 3, make_text_cell(row[3], "#C4B5FD", is_mono=True))
            # Attack Type
            self.table.setCellWidget(r, 4, make_text_cell(row[4], "#E2E8F0", is_bold=True))

            # Severity Badge (rộng rãi, chữ rõ ràng)
            sev = row[5]
            if sev == "Nghiêm trọng":
                self.table.setCellWidget(r, 5, make_badge_cell(sev, "rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.4)"))
            elif sev == "Cao":
                self.table.setCellWidget(r, 5, make_badge_cell(sev, "rgba(245, 158, 11, 0.15)", "#F59E0B", "rgba(245, 158, 11, 0.4)"))
            elif sev == "Trung bình":
                self.table.setCellWidget(r, 5, make_badge_cell(sev, "rgba(251, 191, 36, 0.15)", "#FBBF24", "rgba(251, 191, 36, 0.4)"))
            else:
                self.table.setCellWidget(r, 5, make_badge_cell(sev, "rgba(56, 189, 248, 0.15)", "#38BDF8", "rgba(56, 189, 248, 0.4)"))

            # Description (cột Stretch giãn thoải mái, kèm tooltip khi hover)
            desc_widget = make_text_cell(row[6], "#94A3B8")
            desc_widget.setToolTip(row[6])
            self.table.setCellWidget(r, 6, desc_widget)

            # Status Badge
            st = row[7]
            if st == "Đã xử lý":
                self.table.setCellWidget(r, 7, make_badge_cell("● " + st, "rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.35)"))
            elif st == "Đang xử lý":
                self.table.setCellWidget(r, 7, make_badge_cell("● " + st, "rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.35)"))
            else:
                self.table.setCellWidget(r, 7, make_badge_cell("● " + st, "rgba(245, 158, 11, 0.15)", "#F59E0B", "rgba(245, 158, 11, 0.35)"))

            # Action button
            self.table.setCellWidget(r, 8, make_text_cell("👁 Chi tiết", "#8B5CF6", is_bold=True, align_center=True))

        self.table.selectRow(0)
        self.table.cellClicked.connect(lambda row, col: self.update_detail(row))
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        panel.box.addWidget(self.table)

        # Pagination footer
        footer = QHBoxLayout()
        self.counter_label = QLabel(f"Hiển thị 1–{len(ALERTS)} / 127 cảnh báo")
        self.counter_label.setObjectName("flowFooter")
        footer.addWidget(self.counter_label)
        footer.addStretch()

        for page in ("‹", "1", "2", "3", "4", "5", "…", "13", "›"):
            button = QPushButton(page)
            button.setObjectName("activePage" if page == "1" else "pageButton")
            footer.addWidget(button)
        panel.box.addLayout(footer)

        return panel

    def _on_table_selection_changed(self) -> None:
        selected_indexes = self.table.selectedIndexes()
        if selected_indexes:
            row = selected_indexes[0].row()
            if 0 <= row < len(ALERTS):
                self.update_detail(row)

    def apply_filters(self) -> None:
        search_txt = self.search_input.text().lower().strip()
        sev_filter = self.combo_severity.currentText()
        type_filter = self.combo_attack.currentText()
        status_filter = self.combo_status.currentText()

        visible_count = 0
        for r, data in enumerate(ALERTS):
            matches_search = (not search_txt) or any(search_txt in str(val).lower() for val in data)
            matches_sev = (sev_filter == "Tất cả mức độ") or (data[5] == sev_filter)
            matches_type = (type_filter == "Tất cả loại tấn công") or (data[4] == type_filter)
            matches_status = (status_filter == "Tất cả trạng thái") or (data[7] == status_filter)

            is_visible = matches_search and matches_sev and matches_type and matches_status
            self.table.setRowHidden(r, not is_visible)
            if is_visible:
                visible_count += 1

        self.counter_label.setText(f"Hiển thị {visible_count} / {len(ALERTS)} cảnh báo")

    # -------------------------------------------------------------------------
    # DETAIL INSPECTOR PANEL (ROW 4 - TRÁI 58%)
    # -------------------------------------------------------------------------
    def _detail_panel(self) -> Panel:
        panel = Panel("Chi tiết cảnh báo & Can thiệp")
        panel.setObjectName("alertDetailPanel")
        panel.box.setSpacing(8)

        # Alert Banner
        self.detail_title = QLabel("⚠  #A1024 - DDoS Attack")
        self.detail_title.setObjectName("alertDetailTitle")
        panel.box.addWidget(self.detail_title)

        # Sub-status bar
        sub_bar = QHBoxLayout()
        self.detail_severity = QLabel("Nghiêm trọng")
        self.detail_severity.setObjectName("criticalBadge")
        sub_bar.addWidget(self.detail_severity)

        sub_bar.addStretch()

        self.confidence_label = QLabel("Độ tin cậy AI: 98.5%")
        self.confidence_label.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 700;")
        sub_bar.addWidget(self.confidence_label)
        panel.box.addLayout(sub_bar)

        # Key-Value Grid Card
        grid_card = QFrame()
        grid_card.setStyleSheet("background: #14122A; border: 1px solid #282452; border-radius: 12px;")
        grid_lay = QVBoxLayout(grid_card)
        grid_lay.setContentsMargins(14, 10, 14, 10)
        grid_lay.setSpacing(6)

        self.detail_values: dict[str, QLabel] = {}
        fields = [
            ("time", "Thời gian", "24/04/2025 14:32:11"),
            ("source", "Nguồn IP", "10.0.0.23"),
            ("destination", "Đích IP", "192.168.1.10"),
            ("protocol", "Giao thức", "TCP (SYN Flood)"),
            ("source_port", "Cổng nguồn", "52341"),
            ("destination_port", "Cổng đích", "80 (HTTP)"),
            ("incoming", "Lưu lượng vào", "125.4 Mbps"),
            ("outgoing", "Lưu lượng ra", "118.2 Mbps"),
            ("packets", "Số gói tin", "1,245,536"),
            ("duration", "Thời gian kéo dài", "2 phút 15 giây"),
            ("status", "Trạng thái", "Đang xử lý"),
        ]

        for key, label_text, value in fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("alertDetailKey")
            row.addWidget(label)
            row.addStretch()

            field = QLabel(value)
            field.setObjectName("alertDetailValue")
            if key in ("source", "destination"):
                field.setStyleSheet("color: #C4B5FD; font-family: Consolas; font-weight: 700; font-size: 11px;")
            elif key == "protocol":
                field.setStyleSheet("color: #38BDF8; font-weight: 700; font-size: 11px;")
            elif key == "status":
                field.setStyleSheet("color: #FF5B79; font-weight: 700; font-size: 11px;")
            row.addWidget(field)
            grid_lay.addLayout(row)
            self.detail_values[key] = field

        panel.box.addWidget(grid_card)

        # Behavioral Description Section
        desc_heading = QLabel("Mô tả phân tích hành vi:")
        desc_heading.setObjectName("alertSectionTitle")
        panel.box.addWidget(desc_heading)

        self.description = QLabel(
            "Phát hiện lưu lượng TCP SYN tăng đột biến từ địa chỉ 10.0.0.23 đến 192.168.1.10. Tỷ lệ gói tin SYN/ACK bất thường, có dấu hiệu làm cạn kiệt tài nguyên backlog của máy chủ đích."
        )
        self.description.setObjectName("alertDescription")
        self.description.setWordWrap(True)
        panel.box.addWidget(self.description)

        # Action Buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.block_button = QPushButton("Chặn IP nguồn")
        self.block_button.setObjectName("alertBlockButton")
        self.block_button.setIcon(icon("blocked", "#FFFFFF", 14))
        self.block_button.clicked.connect(self.block_ip)
        actions.addWidget(self.block_button)

        self.resolve_button = QPushButton("Đánh dấu đã xử lý")
        self.resolve_button.setObjectName("alertResolveButton")
        self.resolve_button.setIcon(icon("check", "#C4B5FD", 14))
        self.resolve_button.clicked.connect(self.resolve_alert)
        actions.addWidget(self.resolve_button)

        panel.box.addLayout(actions)
        return panel

    # -------------------------------------------------------------------------
    # TRAFFIC SPIKE PANEL (ROW 4 - PHẢI 42%)
    # -------------------------------------------------------------------------
    def _traffic_spike_panel(self) -> Panel:
        panel = Panel("Lưu lượng tấn công quan sát được")
        panel.box.setSpacing(6)

        # Legend header
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 4)

        self.traffic_peak_chip = QLabel("Đỉnh lưu lượng: 125.4 Mbps")
        self.traffic_peak_chip.setStyleSheet(
            "background: rgba(255, 91, 121, 0.15); color: #FF5B79; "
            "border: 1px solid rgba(255, 91, 121, 0.35); border-radius: 6px; "
            "padding: 2px 8px; font-size: 10.5px; font-weight: 700;"
        )
        top_bar.addWidget(self.traffic_peak_chip)

        top_bar.addStretch()
        top_bar.addWidget(legend_chip("#FF5B79", "Lưu lượng vào"))
        top_bar.addWidget(legend_chip("#3B82F6", "Lưu lượng ra"))
        panel.box.addLayout(top_bar)

        default_series, default_max = ALERT_TRAFFIC_SERIES[0]
        self.traffic_chart = Chart(
            default_series,
            default_max,
            ["14:30", "14:31", "14:32", "14:33", "14:34"],
        )
        self.traffic_chart.setMinimumHeight(240)
        self.traffic_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.box.addWidget(self.traffic_chart)

        return panel

    def update_detail(self, row: int) -> None:
        if row < 0 or row >= len(ALERTS):
            return

        self.current_selected_row = row
        data = ALERTS[row]
        details = ALERT_DETAILS[row]

        # Header Title
        self.detail_title.setText(f"⚠  {data[0]} - {data[4]}")

        # Severity Badge
        sev = data[5]
        self.detail_severity.setText(sev)
        if sev == "Nghiêm trọng":
            self.detail_severity.setStyleSheet("color: #FF5B79; background: rgba(255, 91, 121, 0.16); border: 1px solid rgba(255, 91, 121, 0.4);")
        elif sev == "Cao":
            self.detail_severity.setStyleSheet("color: #F59E0B; background: rgba(245, 158, 11, 0.16); border: 1px solid rgba(245, 158, 11, 0.4);")
        elif sev == "Trung bình":
            self.detail_severity.setStyleSheet("color: #FBBF24; background: rgba(251, 191, 36, 0.16); border: 1px solid rgba(251, 191, 36, 0.4);")
        else:
            self.detail_severity.setStyleSheet("color: #38BDF8; background: rgba(56, 189, 248, 0.16); border: 1px solid rgba(56, 189, 248, 0.4);")

        # Confidence
        self.confidence_label.setText(f"Độ tin cậy AI: {details['confidence']}")

        # Properties
        self.detail_values["time"].setText("24/04/2025 " + data[1].split(" ")[1])
        self.detail_values["source"].setText(data[2])
        self.detail_values["destination"].setText(data[3])
        self.detail_values["protocol"].setText(details["protocol"])
        self.detail_values["source_port"].setText(details["src_port"])
        self.detail_values["destination_port"].setText(details["dst_port"])
        self.detail_values["incoming"].setText(details["incoming"])
        self.detail_values["outgoing"].setText(details["outgoing"])
        self.detail_values["packets"].setText(details["packets"])
        self.detail_values["duration"].setText(details["duration"])

        st = data[7]
        self.detail_values["status"].setText(st)
        if st == "Đã xử lý":
            self.detail_values["status"].setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px;")
        elif st == "Đang xử lý":
            self.detail_values["status"].setStyleSheet("color: #FF5B79; font-weight: 700; font-size: 11px;")
        else:
            self.detail_values["status"].setStyleSheet("color: #F59E0B; font-weight: 700; font-size: 11px;")

        # Analysis description
        self.description.setText(details["analysis"])

        # Update Traffic Chart & Peak chip
        if hasattr(self, "traffic_chart") and row < len(ALERT_TRAFFIC_SERIES):
            series_data, max_val = ALERT_TRAFFIC_SERIES[row]
            self.traffic_chart.series = series_data
            self.traffic_chart.maximum = max_val
            self.traffic_chart._baselines = [sum(vals) / max(1, len(vals)) for vals, _ in series_data]
            self.traffic_chart.update()
            if hasattr(self, "traffic_peak_chip"):
                self.traffic_peak_chip.setText(f"Đỉnh lưu lượng: {details['incoming']}")

        # Reset button states based on status
        if st == "Đã xử lý":
            self.block_button.setEnabled(False)
            self.block_button.setText("IP Đã Chặn")
            self.resolve_button.setEnabled(False)
            self.resolve_button.setText("Đã xử lý")
        else:
            self.block_button.setEnabled(True)
            self.block_button.setText("Chặn IP nguồn")
            self.resolve_button.setEnabled(True)
            self.resolve_button.setText("Đánh dấu đã xử lý")

    def block_ip(self) -> None:
        row = self.current_selected_row
        ALERTS[row][7] = "Đã xử lý"
        self.table.setCellWidget(
            row,
            7,
            make_badge_cell("● Đã xử lý", "rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.35)"),
        )
        self.detail_values["status"].setText("Đã xử lý")
        self.detail_values["status"].setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px;")
        self.block_button.setText("Đã chặn IP")
        self.block_button.setEnabled(False)
        self.resolve_button.setText("Đã xử lý")
        self.resolve_button.setEnabled(False)

    def resolve_alert(self) -> None:
        row = self.current_selected_row
        ALERTS[row][7] = "Đã xử lý"
        self.table.setCellWidget(
            row,
            7,
            make_badge_cell("● Đã xử lý", "rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.35)"),
        )
        self.detail_values["status"].setText("Đã xử lý")
        self.detail_values["status"].setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px;")
        self.resolve_button.setText("Đã xử lý")
        self.resolve_button.setEnabled(False)
