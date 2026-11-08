"""AI anomaly-detection dashboard without fabricated detection records."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
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
    make_badge_cell,
    make_text_cell,
    protocol_bar_row,
)
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend_chip


DETECTIONS: list[list[str]] = []
PORT_MAPPINGS: dict[str, tuple[str, str]] = {}
ATTACK_DESCRIPTIONS: dict[str, str] = {}


class DetectionPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detectionScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("detectionContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 12, 18, 16)
        root.setSpacing(12)

        # 1. Header & Date Controls
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 2)
        header.setSpacing(12)

        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Phát hiện bất thường")
        heading.setObjectName("detectionHeading")
        heading.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;")
        intro.addWidget(heading)

        subtitle = QLabel("Kết quả từ mô hình AI/Machine Learning  •  Không sử dụng dữ liệu cảnh báo giả lập")
        subtitle.setObjectName("detectionSubtitle")
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
        header.addLayout(intro, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        ai_badge = QLabel("●  CHƯA CÓ KẾT QUẢ AI")
        ai_badge.setObjectName("liveBadge")
        ai_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;"
        )
        controls.addWidget(ai_badge)

        today = datetime.now().strftime("%d/%m/%Y")
        self.date_button = QPushButton(f"  {today} 00:00   →   {today} 23:59  ˅")
        self.date_button.setObjectName("dateRangeButton")
        self.date_button.setIcon(icon("calendar", "#AFC7E4", 14))
        self.date_button.setFixedHeight(36)
        controls.addWidget(self.date_button)

        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("detectionRefresh")
        refresh.setIcon(icon("refresh", "#FFFFFF", 14))
        refresh.setFixedHeight(36)
        refresh.clicked.connect(self.refresh_data)
        controls.addWidget(refresh)

        header.addLayout(controls)
        root.addLayout(header)

        # 2. Hàng 1: 5 Thẻ chỉ số phát hiện bất thường (KPI Indicators)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Tổng phát hiện", "0", "Chưa có", "#FF5B79", "warning"),
            MonitorMetric("Lưu lượng bình thường", "0", "Chưa có", "#10B981", "shield"),
            MonitorMetric("Lưu lượng bất thường", "0", "Chưa có", "#FF5B79", "bug"),
            MonitorMetric("Độ tin cậy TB", "—", "Chưa có", "#A78BFA", "brain"),
            MonitorMetric("Cảnh báo mức cao", "0", "Chưa có", "#FBBF24", "siren"),
        ]
        self.metric_cards: list[MetricCard] = []
        for column, data in enumerate(metric_data):
            card = MetricCard(data)
            self.metric_cards.append(card)
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # 3. Hàng 2: Biểu đồ xu hướng (62%) & Phân loại tấn công Donut (38%)
        middle = QGridLayout()
        middle.setSpacing(12)

        # 3.1 Xu hướng phát hiện bất thường (Trend Chart)
        trend_extra = QWidget()
        trend_extra_lay = QHBoxLayout(trend_extra)
        trend_extra_lay.setContentsMargins(0, 0, 0, 0)
        trend_extra_lay.setSpacing(8)
        trend_extra_lay.addWidget(legend_chip("#60A5FA", "Bình thường"))
        trend_extra_lay.addWidget(legend_chip("#FF5B79", "Bất thường"))
        trend_badge = QLabel("24 giờ qua")
        trend_badge.setObjectName("panelChip")
        trend_badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        trend_extra_lay.addWidget(trend_badge)

        trend_panel = Panel(
            "Xu hướng phát hiện bất thường theo thời gian",
            "Biến động lưu lượng bình thường và các điểm xâm nhập bất thường theo mốc giờ",
            trend_extra,
        )
        normal = [0.0] * 32
        anomaly = [0.0] * 32
        self.trend_chart = Chart(
            [(normal, "#60A5FA"), (anomaly, "#FF5B79")],
            1,
            ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"],
        )
        self.trend_chart.setFixedHeight(300)
        trend_panel.box.addWidget(self.trend_chart, 1)
        middle.addWidget(trend_panel, 0, 0)

        # 3.2 Phân loại loại tấn công (Attack breakdown)
        self.attack_badge = QLabel("0 loại")
        attack_badge = self.attack_badge
        attack_badge.setObjectName("panelChip")
        attack_badge.setStyleSheet(
            "color: #FF5B79; background: rgba(255, 91, 121, 0.15); "
            "border: 1px solid rgba(255, 91, 121, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        attack_panel = Panel("Phân loại loại tấn công", "Tỷ trọng các mối đe dọa được nhận diện", attack_badge)
        attack_body = QHBoxLayout()
        attack_body.setSpacing(12)
        self.attack_donut = DonutChart([], "Tổng", "0", "phát hiện")
        attack_body.addWidget(self.attack_donut, 1)

        attack_legend = QVBoxLayout()
        attack_legend.setSpacing(3)
        attack_legend.addStretch(1)
        for color, name in [
            ("#FF5B79", "DDoS"),
            ("#FB923C", "Port Scan"),
            ("#60A5FA", "Brute Force"),
            ("#C084FC", "SQL Injection"),
            ("#FACC15", "Malware"),
            ("#10B981", "Protocol"),
        ]:
            attack_legend.addWidget(protocol_bar_row(color, name, "0.0%", 0.0))
        attack_legend.addStretch(1)
        attack_body.addLayout(attack_legend, 1)
        attack_panel.box.addLayout(attack_body, 1)
        middle.addWidget(attack_panel, 0, 1)

        middle.setColumnStretch(0, 5)
        middle.setColumnStretch(1, 3)
        root.addLayout(middle)

        # 4. Hàng 3: Danh sách phát hiện (mở rộng toàn bộ) & Panel chi tiết (cố định chuẩn 330px)
        bottom = QGridLayout()
        bottom.setSpacing(12)
        bottom.addWidget(self._detections_panel(), 0, 0)
        self.detail_panel = self._detail_panel()
        self.detail_panel.setFixedWidth(330)
        bottom.addWidget(self.detail_panel, 0, 1)
        self.show_empty_detail()

        bottom.setColumnStretch(0, 1)
        bottom.setColumnStretch(1, 0)
        root.addLayout(bottom)

        self.setWidget(content)

    def _detections_panel(self) -> Panel:
        self.detection_badge = QLabel("0 phát hiện")
        badge = self.detection_badge
        badge.setObjectName("panelChip")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Danh sách các lưu lượng bất thường được phát hiện",
            "Nhật ký các luồng mạng bị mô hình AI gắn cờ cảnh báo rủi ro",
            badge,
        )

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 4)
        toolbar.setSpacing(8)

        search = QLineEdit()
        search.setObjectName("detectionSearch")
        search.setPlaceholderText("Tìm kiếm IP, ID, loại bất thường...")
        search.addAction(icon("search", "#8299B7", 14), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search, 1)

        combo_attack = QComboBox()
        combo_attack.setObjectName("detectionCombo")
        combo_attack.addItems([
            "Tất cả loại tấn công",
            "DDoS Attack",
            "Port Scan",
            "Brute Force",
            "SQL Injection",
            "Malware Traffic",
            "Protocol Anomaly",
            "Suspicious Traffic",
        ])
        toolbar.addWidget(combo_attack)

        combo_risk = QComboBox()
        combo_risk.setObjectName("detectionCombo")
        combo_risk.addItems(["Tất cả mức độ", "Cao", "Trung bình", "Thấp"])
        toolbar.addWidget(combo_risk)

        export = QPushButton("  Xuất CSV")
        export.setObjectName("smallMonitorButton")
        export.setIcon(icon("download", "#B8CCE4", 13))
        toolbar.addWidget(export)
        panel.box.addLayout(toolbar)

        headers = ["ID", "Thời gian", "IP nguồn", "IP đích", "Giao thức", "Loại bất thường", "Độ tin cậy", "Mức độ", "Trạng thái", "Hành động"]
        self.table = QTableWidget(len(DETECTIONS), len(headers))
        self.table.setObjectName("detectionTable")
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setMinimumWidth(280)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setFixedHeight(415)
        self.table.setStyleSheet("""
            QTableWidget#detectionTable {
                background: transparent;
                border: none;
                color: #CBD5E1;
                font-size: 11px;
                selection-background-color: #2D255E;
                selection-color: #FFFFFF;
            }
            QTableWidget#detectionTable::item {
                border-bottom: 1px solid #24204A;
                padding: 4px 6px;
            }
            QTableWidget#detectionTable::item:selected,
            QTableWidget#detectionTable::item:selected:active,
            QTableWidget#detectionTable::item:selected:!active {
                background-color: #2D255E;
                color: #FFFFFF;
            }
            QTableWidget#detectionTable::item:selected:hover {
                background-color: #382E72;
            }
        """)

        pal = self.table.palette()
        pal.setColor(self.table.palette().ColorGroup.All, self.table.palette().ColorRole.Highlight, QColor("#2D255E"))
        pal.setColor(self.table.palette().ColorGroup.All, self.table.palette().ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.table.setPalette(pal)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            if c in (0, 1, 4, 5, 6, 7, 8, 9):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.setHorizontalHeaderItem(c, item)

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
        for c in range(10):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Loại bất thường co giãn tự do

        self.table.setColumnWidth(0, 60)   # ID
        self.table.setColumnWidth(1, 95)   # Thời gian
        self.table.setColumnWidth(2, 115)  # IP nguồn
        self.table.setColumnWidth(3, 115)  # IP đích
        self.table.setColumnWidth(4, 65)   # Giao thức
        # Col 5 = Stretch (Loại bất thường)
        self.table.setColumnWidth(6, 75)   # Độ tin cậy
        self.table.setColumnWidth(7, 85)   # Mức độ
        self.table.setColumnWidth(8, 105)  # Trạng thái
        self.table.setColumnWidth(9, 50)   # Hành động

        proto_colors = {
            "TCP": ("rgba(47, 155, 255, 0.18)", "#60A5FA", "rgba(47, 155, 255, 0.35)"),
            "UDP": ("rgba(255, 155, 55, 0.18)", "#FDBA74", "rgba(255, 155, 55, 0.35)"),
            "ICMP": ("rgba(149, 81, 232, 0.18)", "#C4B5FD", "rgba(149, 81, 232, 0.35)"),
        }

        attack_colors = {
            "DDoS Attack": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Port Scan": ("rgba(249, 115, 22, 0.18)", "#FB923C", "rgba(249, 115, 22, 0.35)"),
            "Brute Force": ("rgba(59, 130, 246, 0.18)", "#60A5FA", "rgba(59, 130, 246, 0.35)"),
            "SQL Injection": ("rgba(168, 85, 247, 0.18)", "#C084FC", "rgba(168, 85, 247, 0.35)"),
            "Malware Traffic": ("rgba(234, 179, 8, 0.18)", "#FACC15", "rgba(234, 179, 8, 0.35)"),
            "Protocol Anomaly": ("rgba(236, 72, 153, 0.18)", "#F472B6", "rgba(236, 72, 153, 0.35)"),
            "Suspicious Traffic": ("rgba(20, 184, 166, 0.18)", "#2DD4BF", "rgba(20, 184, 166, 0.35)"),
        }

        risk_colors = {
            "Cao": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Trung bình": ("rgba(251, 191, 36, 0.18)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
            "Thấp": ("rgba(16, 185, 129, 0.18)", "#34D399", "rgba(16, 185, 129, 0.35)"),
        }

        status_colors = {
            "Đang xử lý": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Đã xác nhận": ("rgba(139, 92, 246, 0.18)", "#C4B5FD", "rgba(139, 92, 246, 0.35)"),
            "Đang giám sát": ("rgba(56, 189, 248, 0.18)", "#38BDF8", "rgba(56, 189, 248, 0.35)"),
            "Đã xử lý": ("rgba(16, 185, 129, 0.18)", "#10B981", "rgba(16, 185, 129, 0.35)"),
        }

        for r, row in enumerate(DETECTIONS):
            self.table.setRowHeight(r, 37)

            # Col 0: ID
            self.table.setCellWidget(r, 0, make_text_cell(row[0], color="#8E8BA7", align_center=True))

            # Col 1: Thời gian
            self.table.setCellWidget(r, 1, make_text_cell(row[1], color="#CBD5E1", align_center=True))

            # Col 2: IP nguồn
            self.table.setCellWidget(r, 2, make_text_cell(row[2], color="#FFFFFF", is_mono=True, is_bold=True))

            # Col 3: IP đích
            self.table.setCellWidget(r, 3, make_text_cell(row[3], color="#C4B5FD", is_mono=True))

            # Col 4: Giao thức
            p_bg, p_fg, p_bd = proto_colors.get(row[4], ("#25224D", "#FFFFFF", "#383466"))
            self.table.setCellWidget(r, 4, make_badge_cell(row[4], p_bg, p_fg, p_bd))

            # Col 5: Loại bất thường
            a_bg, a_fg, a_bd = attack_colors.get(row[5], ("#25224D", "#FFFFFF", "#383466"))
            self.table.setCellWidget(r, 5, make_badge_cell(row[5], a_bg, a_fg, a_bd))

            # Col 6: Độ tin cậy
            self.table.setCellWidget(r, 6, make_badge_cell(row[6], "rgba(16, 185, 129, 0.15)", "#34D399", "rgba(16, 185, 129, 0.3)"))

            # Col 7: Mức độ
            r_bg, r_fg, r_bd = risk_colors.get(row[7], ("#25224D", "#FFFFFF", "#383466"))
            self.table.setCellWidget(r, 7, make_badge_cell(row[7], r_bg, r_fg, r_bd))

            # Col 8: Trạng thái
            s_bg, s_fg, s_bd = status_colors.get(row[8], ("#25224D", "#FFFFFF", "#383466"))
            self.table.setCellWidget(r, 8, make_badge_cell(row[8], s_bg, s_fg, s_bd))

            # Col 9: Hành động
            self.table.setCellWidget(r, 9, make_text_cell("◉  ⋮", color="#8E8BA7", align_center=True))

        if DETECTIONS:
            self.table.selectRow(0)
        self.table.cellClicked.connect(lambda row, column: self.update_detail(row))
        panel.box.addWidget(self.table)

        # Pagination footer
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 0)
        self.result_count = QLabel("Chưa có kết quả phát hiện từ mô hình AI")
        count = self.result_count
        count.setObjectName("flowFooter")
        count.setStyleSheet("color: #8E8BA7; font-size: 11px;")
        footer.addWidget(count)
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

    def _detail_panel(self) -> Panel:
        badge = QLabel("AI Analysis")
        badge.setObjectName("panelChip")
        badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 3px 9px; font-size: 11.5px; font-weight: 700;"
        )
        panel = Panel("Chi tiết phát hiện", "Phân tích chuyên sâu cảnh báo đã chọn", badge)
        panel.box.setContentsMargins(16, 14, 16, 16)
        panel.box.setSpacing(12)

        # 1. Alert Banner
        self.detail_alert = QLabel("Chưa chọn phát hiện")
        self.detail_alert.setObjectName("detailAlert")
        self.detail_alert.setStyleSheet(
            "color: #FF5B79; background: rgba(255, 91, 121, 0.14); "
            "border: 1px solid rgba(255, 91, 121, 0.35); border-radius: 12px; "
            "padding: 12px 14px; font-weight: 800; font-size: 14px; letter-spacing: -0.2px;"
        )
        panel.box.addWidget(self.detail_alert)

        # 2. Key-Value Grid Card (Dãn dòng thông thoáng, chữ to rõ nét)
        grid_card = QFrame()
        grid_card.setStyleSheet(
            "background: #14122A; border: 1px solid #282452; border-radius: 12px;"
        )
        grid_lay = QVBoxLayout(grid_card)
        grid_lay.setContentsMargins(16, 14, 16, 14)
        grid_lay.setSpacing(10)

        self.detail_fields: dict[str, QLabel] = {}
        for key, label, value in [
            ("time", "Thời gian", "—"),
            ("source", "IP nguồn", "—"),
            ("destination", "IP đích", "—"),
            ("protocol", "Giao thức", "—"),
            ("source_port", "Cổng nguồn", "—"),
            ("destination_port", "Cổng đích", "—"),
            ("risk", "Mức độ rủi ro", "—"),
            ("status", "Trạng thái", "—"),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name = QLabel(label)
            name.setStyleSheet("color: #9E9BB5; font-size: 12.5px; font-weight: 500;")
            row.addWidget(name)
            row.addStretch()

            field = QLabel(value)
            if label == "IP nguồn":
                field.setStyleSheet("color: #FFFFFF; font-family: 'Consolas', monospace; font-size: 13px; font-weight: 700;")
            elif label == "IP đích":
                field.setStyleSheet("color: #C4B5FD; font-family: 'Consolas', monospace; font-size: 13px; font-weight: 700;")
            elif "Cổng" in label:
                field.setStyleSheet("color: #FFFFFF; font-family: 'Consolas', monospace; font-size: 12.5px; font-weight: 600;")
            elif label == "Giao thức":
                field.setStyleSheet("color: #60A5FA; background: rgba(47, 155, 255, 0.15); border: 1px solid rgba(47, 155, 255, 0.3); border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;")
            elif "rủi ro" in label:
                field.setStyleSheet("color: #FF5B79; background: rgba(255, 91, 121, 0.15); border: 1px solid rgba(255, 91, 121, 0.3); border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;")
            elif "Trạng thái" in label:
                field.setStyleSheet("color: #FF5B79; background: rgba(255, 91, 121, 0.15); border: 1px solid rgba(255, 91, 121, 0.3); border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;")
            else:
                field.setStyleSheet("color: #E2E8F0; font-size: 12.5px; font-weight: 600;")
            row.addWidget(field)
            grid_lay.addLayout(row)
            self.detail_fields[key] = field

        panel.box.addWidget(grid_card)

        # 3. Confidence progress bar
        conf_box = QVBoxLayout()
        conf_box.setSpacing(6)
        conf_header = QHBoxLayout()
        conf_title = QLabel("Độ tin cậy nhận diện AI")
        conf_title.setStyleSheet("color: #CBD5E1; font-size: 12.5px; font-weight: 600;")
        conf_header.addWidget(conf_title)
        conf_header.addStretch()

        self.conf_percent = QLabel("—")
        self.conf_percent.setStyleSheet("color: #10B981; font-size: 14px; font-weight: 800;")
        conf_header.addWidget(self.conf_percent)
        conf_box.addLayout(conf_header)

        self.confidence = QProgressBar()
        self.confidence.setObjectName("confidenceBar")
        self.confidence.setRange(0, 1000)
        self.confidence.setValue(0)
        self.confidence.setTextVisible(False)
        self.confidence.setFixedHeight(9)
        self.confidence.setStyleSheet("""
            QProgressBar#confidenceBar {
                background: #25224D;
                border: none;
                border-radius: 4px;
            }
            QProgressBar#confidenceBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #34D399);
                border-radius: 4px;
            }
        """)
        conf_box.addWidget(self.confidence)
        panel.box.addLayout(conf_box)

        # 4. Description Box (Thoáng đãng, font chữ dễ đọc)
        desc_card = QFrame()
        desc_card.setStyleSheet("background: #14122A; border: 1px solid #282452; border-radius: 12px;")
        desc_lay = QVBoxLayout(desc_card)
        desc_lay.setContentsMargins(14, 12, 14, 12)
        desc_lay.setSpacing(6)

        desc_title = QLabel("Mô tả phân tích hành vi:")
        desc_title.setStyleSheet("color: #C4B5FD; font-size: 12.5px; font-weight: 700;")
        desc_lay.addWidget(desc_title)

        self.description = QLabel("Chưa có dữ liệu phân tích từ mô hình AI.")
        self.description.setStyleSheet("color: #D6D2EC; font-size: 12px; line-height: 1.5;")
        self.description.setWordWrap(True)
        desc_lay.addWidget(self.description)
        panel.box.addWidget(desc_card)

        panel.box.addSpacing(4)

        # 5. Action Buttons (Kích thước chuẩn, nổi bật)
        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.block_button = QPushButton("  Chặn IP")
        self.block_button.setObjectName("blockIpButton")
        self.block_button.setIcon(icon("blocked", "#FFFFFF", 15))
        self.block_button.setStyleSheet("""
            QPushButton#blockIpButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #EF4444);
                border: 1px solid #F87171;
                border-radius: 10px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 700;
                min-height: 40px;
            }
            QPushButton#blockIpButton:hover {
                background: #DC2626;
            }
            QPushButton#blockIpButton:disabled {
                background: #3B2433;
                border-color: #4D2D42;
                color: #8E7A86;
            }
        """)
        self.block_button.clicked.connect(self.simulate_block)
        self.block_button.setEnabled(False)
        actions.addWidget(self.block_button)

        details = QPushButton("  Xem chi tiết")
        details.setObjectName("viewDetailButton")
        details.setIcon(icon("eye", "#C4B5FD", 15))
        details.setStyleSheet("""
            QPushButton#viewDetailButton {
                background: #1B1938;
                border: 1px solid #383466;
                border-radius: 10px;
                color: #C4B5FD;
                font-size: 12px;
                font-weight: 700;
                min-height: 40px;
            }
            QPushButton#viewDetailButton:hover {
                background: #25224D;
                border-color: #6C5DD3;
                color: #FFFFFF;
            }
        """)
        actions.addWidget(details)
        panel.box.addLayout(actions)

        return panel

    def update_detail(self, row: int) -> None:
        if row < 0 or row >= len(DETECTIONS):
            self.show_empty_detail()
            return
        item = DETECTIONS[row]
        attack_type = item[5]
        self.detail_alert.setText(f"⚠  {item[0]} - {attack_type}")
        self.detail_fields["time"].setText(item[1])
        self.detail_fields["source"].setText(item[2])
        self.detail_fields["destination"].setText(item[3])

        # Protocol badge chip
        proto = item[4]
        self.detail_fields["protocol"].setText(proto)
        p_color = "#60A5FA" if proto == "TCP" else "#FDBA74" if proto == "UDP" else "#C4B5FD"
        p_bg = "rgba(47, 155, 255, 0.15)" if proto == "TCP" else "rgba(255, 155, 55, 0.15)" if proto == "UDP" else "rgba(149, 81, 232, 0.15)"
        p_bd = "rgba(47, 155, 255, 0.3)" if proto == "TCP" else "rgba(255, 155, 55, 0.3)" if proto == "UDP" else "rgba(149, 81, 232, 0.3)"
        self.detail_fields["protocol"].setStyleSheet(f"color: {p_color}; background: {p_bg}; border: 1px solid {p_bd}; border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;")

        s_port, d_port = PORT_MAPPINGS.get(item[0], ("—", "—"))
        self.detail_fields["source_port"].setText(s_port)
        self.detail_fields["destination_port"].setText(d_port)

        # Risk badge chip
        risk = item[7]
        self.detail_fields["risk"].setText(risk)
        r_color = "#FF5B79" if risk == "Cao" else "#FBBF24" if risk == "Trung bình" else "#34D399"
        r_bg = "rgba(255, 91, 121, 0.15)" if risk == "Cao" else "rgba(251, 191, 36, 0.15)" if risk == "Trung bình" else "rgba(16, 185, 129, 0.15)"
        r_bd = "rgba(255, 91, 121, 0.3)" if risk == "Cao" else "rgba(251, 191, 36, 0.3)" if risk == "Trung bình" else "rgba(16, 185, 129, 0.3)"
        self.detail_fields["risk"].setStyleSheet(f"color: {r_color}; background: {r_bg}; border: 1px solid {r_bd}; border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;")

        # Status badge chip
        status = item[8]
        self.detail_fields["status"].setText(status)
        s_color = "#FF5B79" if status == "Đang xử lý" else "#10B981" if status in ("Đã xác nhận", "Đã xử lý") else "#38BDF8"
        s_bg = "rgba(255, 91, 121, 0.15)" if status == "Đang xử lý" else "rgba(16, 185, 129, 0.15)" if status in ("Đã xác nhận", "Đã xử lý") else "rgba(56, 189, 248, 0.15)"
        s_bd = "rgba(255, 91, 121, 0.3)" if status == "Đang xử lý" else "rgba(16, 185, 129, 0.3)" if status in ("Đã xác nhận", "Đã xử lý") else "rgba(56, 189, 248, 0.3)"
        self.detail_fields["status"].setStyleSheet(f"color: {s_color}; background: {s_bg}; border: 1px solid {s_bd}; border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;")

        pct_val = float(item[6].rstrip("%"))
        self.conf_percent.setText(item[6])
        self.confidence.setValue(int(pct_val * 10))

        # Dynamic description
        self.description.setText(ATTACK_DESCRIPTIONS.get(attack_type, "Không có mô tả phân tích từ mô hình AI."))

        self.block_button.setText("  Chặn IP")
        self.block_button.setEnabled(True)

    def show_empty_detail(self) -> None:
        self.detail_alert.setText("Chưa có phát hiện bất thường")
        for field in self.detail_fields.values():
            field.setText("—")
        self.conf_percent.setText("—")
        self.confidence.setValue(0)
        self.description.setText("Chưa có dữ liệu phân tích từ mô hình AI.")
        self.block_button.setText("  Chặn IP")
        self.block_button.setEnabled(False)

    def simulate_block(self) -> None:
        self.block_button.setText("  Đã chặn")
        self.block_button.setEnabled(False)

    def refresh_data(self) -> None:
        # No detector/backend is connected yet. Keep the view honest and empty.
        for card, value in zip(self.metric_cards, ("0", "0", "0", "—", "0")):
            card.set_data(value, "Chưa có", 0.0)
        self.trend_chart.update()
        self.attack_donut.set_data([], "0", "phát hiện")
        self.attack_badge.setText("0 loại")
        self.detection_badge.setText("0 phát hiện")
        self.result_count.setText("Chưa có kết quả phát hiện từ mô hình AI")
        self.show_empty_detail()
