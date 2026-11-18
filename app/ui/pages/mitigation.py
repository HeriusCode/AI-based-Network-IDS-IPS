"""IPS mitigation policy page without fabricated rules or enforcement events."""

from __future__ import annotations

from datetime import datetime, timedelta

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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.dashboard import DonutChart, make_badge_cell, make_text_cell, protocol_bar_row
from app.ui.pages.monitoring import MetricCard, MonitorMetric, Panel, legend_chip
from app.services.mitigation_service import MitigationService


# Backward compatible alias
legend = legend_chip


RULES: list[list[str]] = []


class MitigationChart(QWidget):
    """Dual-curve comparison illustrating network traffic before vs after IPS mitigation enforcement."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.before = [0.0] * 31
        self.after = [0.0] * 31
        self.has_enforcement = False
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        chart = QRectF(44, 12, self.width() - 54, self.height() - 38)
        if chart.width() <= 10 or chart.height() <= 10:
            return

        # 1. Background grid lines & Y labels (0 - 300 Mbps)
        painter.setFont(QFont("Segoe UI", 8))
        max_y = 300.0
        y_steps = 6
        for step in range(y_steps + 1):
            y = chart.bottom() - chart.height() * (step / y_steps)
            val = int(step * (max_y / y_steps))

            painter.setPen(QPen(QColor("#24204A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(
                QRectF(0, y - 8, 38, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{val}",
            )

        # 2. X-axis time marks
        now = datetime.now()
        labels = [(now - timedelta(minutes=5 * (5 - index))).strftime("%H:%M") for index in range(6)]
        for index, label in enumerate(labels):
            x = chart.left() + chart.width() * index / (len(labels) - 1)
            painter.setPen(QPen(QColor("#1E1B3E"), 1, Qt.PenStyle.SolidLine))
            painter.drawLine(QPointF(x, chart.bottom()), QPointF(x, chart.bottom() + 4))

            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(
                QRectF(x - 22, chart.bottom() + 6, 44, 16),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

        # 3. Before mitigation curve (Red/Rose #FF5B79 with gradient area)
        self._draw_curve(painter, chart, self.before, max_y, QColor("#FF5B79"), fill=True)

        # 4. After mitigation curve (Blue #3B82F6 with subtle gradient)
        self._draw_curve(painter, chart, self.after, max_y, QColor("#3B82F6"), fill=True, fill_alpha=40)

        if not self.has_enforcement:
            return

        # 5. Enforcement divider line at 58%.
        apply_x = chart.left() + chart.width() * 0.58
        painter.setPen(QPen(QColor("#8B5CF6"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(apply_x, chart.top()), QPointF(apply_x, chart.bottom()))

        pill_w, pill_h = 100, 20
        pill_rect = QRectF(apply_x - pill_w / 2, chart.top() + 4, pill_w, pill_h)
        painter.setBrush(QColor("#1E1B40"))
        painter.setPen(QPen(QColor("#8B5CF6"), 1))
        painter.drawRoundedRect(pill_rect, 5, 5)
        painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
        painter.setPen(QColor("#C4B5FD"))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "● Kích hoạt rule")

    @staticmethod
    def _draw_curve(painter: QPainter, chart: QRectF, values: list[int], max_y: float, color: QColor, fill: bool = False, fill_alpha: int = 75) -> None:
        points = [
            QPointF(
                chart.left() + chart.width() * i / (len(values) - 1),
                chart.bottom() - chart.height() * (val / max_y),
            )
            for i, val in enumerate(values)
        ]
        path = QPainterPath(points[0])
        for pt in points[1:]:
            path.lineTo(pt)

        if fill:
            area = QPainterPath(path)
            area.lineTo(chart.right(), chart.bottom())
            area.lineTo(chart.left(), chart.bottom())
            area.closeSubpath()
            grad = QLinearGradient(0, chart.top(), 0, chart.bottom())
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), fill_alpha))
            grad.setColorAt(0.8, QColor(color.red(), color.green(), color.blue(), int(fill_alpha * 0.2)))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillPath(area, grad)

        painter.setPen(QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)


class HistoryRow(QFrame):
    """Audit log item displaying mitigation actions taken."""

    def __init__(self, icon_name: str, color: str, title: str, subtitle: str, timestamp: str, action_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyRow")
        self.setStyleSheet("""
            QFrame#historyRow {
                background: #201D42;
                border: 1px solid #2B2757;
                border-radius: 10px;
            }
            QFrame#historyRow:hover {
                border-color: #6C5DD3;
            }
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(10)

        badge = QLabel()
        badge.setObjectName("historyIcon")
        badge.setPixmap(icon(icon_name, color, 16).pixmap(16, 16))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(36, 36)
        badge.setStyleSheet(f"background: rgba(255, 255, 255, 0.05); border: 1px solid {color}40; border-radius: 8px;")
        row.addWidget(badge)

        copy = QVBoxLayout()
        copy.setSpacing(1)
        name = QLabel(title)
        name.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 600;")
        copy.addWidget(name)
        sub = QLabel(subtitle)
        sub.setStyleSheet("color: #8E8BA7; font-size: 10.5px;")
        copy.addWidget(sub)
        row.addLayout(copy, 1)

        chip = QLabel(action_label)
        chip.setStyleSheet(f"""
            color: {color};
            background: {color}20;
            border: 1px solid {color}40;
            border-radius: 5px;
            padding: 2px 7px;
            font-size: 10.5px;
            font-weight: 700;
        """)
        row.addWidget(chip)

        time_lbl = QLabel(timestamp)
        time_lbl.setStyleSheet("color: #9E9BB5; font-size: 11px; font-family: Consolas, Segoe UI Mono, monospace;")
        row.addWidget(time_lbl)


class MitigationPage(QScrollArea):
    """Modern IPS Mitigation page adhering to the Midnight Indigo SOC design system."""

    def __init__(self, parent: QWidget | None = None, mitigation_service: MitigationService | None = None) -> None:
        super().__init__(parent)
        self.mitigation_service = mitigation_service
        self._rules: list[dict] = []
        self.setObjectName("mitigationScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("mitigationContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 12, 18, 16)
        root.setSpacing(12)

        # 1. Header & Global IPS Controls
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 2)
        header.setSpacing(12)

        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Giảm thiểu rủi ro (IPS)")
        heading.setObjectName("mitigationHeading")
        heading.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;")
        intro.addWidget(heading)

        self.subtitle = QLabel("Quản lý chính sách bảo vệ mạng  •  Đang kết nối OS-Ken / Open vSwitch")
        self.subtitle.setObjectName("mitigationSubtitle")
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(self.subtitle)
        header.addLayout(intro, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.ips_toggle = QPushButton("●  CHƯA KẾT NỐI IPS")
        self.ips_toggle.setObjectName("ipsToggle")
        self.ips_toggle.setStyleSheet("""
            QPushButton#ipsToggle {
                min-width: 135px;
                height: 34px;
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 8px;
                color: #10B981;
                font-size: 11px;
                font-weight: 700;
                padding: 0 10px;
            }
        """)
        self.ips_toggle.setCheckable(True)
        self.ips_toggle.setChecked(False)
        self.ips_toggle.setEnabled(False)
        self.ips_toggle.clicked.connect(self.toggle_ips)
        controls.addWidget(self.ips_toggle)

        self.mode_button = QPushButton("  Chế độ: Chưa khả dụng")
        self.mode_button.setObjectName("dateRangeButton")
        self.mode_button.setIcon(icon("shield", "#AFC7E4", 13))
        self.mode_button.setFixedHeight(34)
        self.mode_button.setEnabled(False)
        controls.addWidget(self.mode_button)

        self.pause_button = QPushButton("  Tạm dừng IPS")
        self.pause_button.setObjectName("pauseIpsButton")
        self.pause_button.setIcon(icon("pause", "#FFFFFF", 13))
        self.pause_button.setFixedHeight(34)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_ips)
        controls.addWidget(self.pause_button)

        header.addLayout(controls)
        root.addLayout(header)

        # 2. Hàng 1: 5 Thẻ chỉ số hiệu năng giảm thiểu (KPIs)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Tổng rules hoạt động", "0", "Chưa có", "#10B981", "shield"),
            MonitorMetric("Lưu lượng bị chặn", "0 gói", "Chưa có", "#FF5B79", "blocked"),
            MonitorMetric("Lưu lượng bị giới hạn", "0 gói", "Chưa có", "#FBBF24", "speed"),
            MonitorMetric("Sự kiện giảm thiểu", "0", "Chưa có", "#3B82F6", "document"),
            MonitorMetric("Hiệu quả bảo vệ", "—", "Chưa có", "#A78BFA", "brain"),
        ]
        self.metric_cards: list[MetricCard] = []
        for column, data in enumerate(metric_data):
            card = MetricCard(data)
            self.metric_cards.append(card)
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # 3. Hàng 2: Biểu đồ tác động lưu lượng (62%) & Hiệu quả giảm thiểu Donut (38%)
        impact_row = QGridLayout()
        impact_row.setSpacing(12)

        # 3.1 Biểu đồ tác động
        chart_extra = QWidget()
        chart_extra_lay = QHBoxLayout(chart_extra)
        chart_extra_lay.setContentsMargins(0, 0, 0, 0)
        chart_extra_lay.setSpacing(8)
        chart_extra_lay.addWidget(legend_chip("#FF5B79", "Trước giảm thiểu"))
        chart_extra_lay.addWidget(legend_chip("#3B82F6", "Sau giảm thiểu"))
        chart_extra_lay.addWidget(legend_chip("#8B5CF6", "Áp dụng Rule"))

        traffic_panel = Panel(
            "Lưu lượng mạng trước & sau khi áp dụng chính sách",
            "Mức độ suy giảm lưu lượng độc hại ngay sau khi kích hoạt các bộ lọc IPS",
            chart_extra,
        )
        self.mitigation_chart = MitigationChart()
        traffic_panel.box.addWidget(self.mitigation_chart, 1)
        impact_row.addWidget(traffic_panel, 0, 0)

        # 3.2 Hiệu quả giảm thiểu Donut
        self.donut_badge = QLabel("Chưa có dữ liệu")
        self.donut_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        eff_panel = Panel("Hiệu quả giảm thiểu", "Tỷ trọng lưu lượng bất thường đã được xử lý", self.donut_badge)
        eff_body = QHBoxLayout()
        eff_body.setSpacing(12)
        self.efficiency_donut = DonutChart([], "Hiệu quả", "—", "chưa có dữ liệu")
        eff_body.addWidget(self.efficiency_donut, 4)

        eff_legend = QVBoxLayout()
        eff_legend.setSpacing(4)
        eff_legend.addStretch(1)
        self.efficiency_rows: list[QWidget] = []
        for color, label in [
            ("#FF5B79", "Lưu lượng bị chặn"),
            ("#FBBF24", "Lưu lượng bị giới hạn"),
            ("#10B981", "Lưu lượng an toàn"),
        ]:
            row = protocol_bar_row(color, label, "0.0%", 0.0)
            for text_label in row.findChildren(QLabel):
                if text_label.text() == label:
                    text_label.setMinimumWidth(145)
                    text_label.setMaximumWidth(16777215)
                    break
            self.efficiency_rows.append(row)
            eff_legend.addWidget(row)
        eff_legend.addStretch(1)
        eff_body.addLayout(eff_legend, 6)
        eff_panel.box.addLayout(eff_body, 1)
        impact_row.addWidget(eff_panel, 0, 1)

        impact_row.setColumnStretch(0, 60)
        impact_row.setColumnStretch(1, 40)
        root.addLayout(impact_row)

        # 4. Hàng 3: Bảng chính sách giảm thiểu (IPS Rules Table) - Trải rộng toàn phần (Full Width)
        # Giúp bảng 10 cột hiển thị thoáng đãng và không bao giờ bị che khuất khi mở rộng sidebar
        root.addWidget(self._rules_panel())

        # 5. Hàng 4: Thêm chính sách mới (50%) & Nhật ký thực thi giảm thiểu (50%)
        bottom_row = QGridLayout()
        bottom_row.setSpacing(12)
        bottom_row.addWidget(self._new_rule_panel(), 0, 0)
        bottom_row.addWidget(self._history_panel(), 0, 1)
        bottom_row.setColumnStretch(0, 52)
        bottom_row.setColumnStretch(1, 48)
        root.addLayout(bottom_row)

        self.setWidget(content)
        if self.mitigation_service is not None:
            self.mitigation_service.snapshot_changed.connect(self._snapshot_changed)
            self.mitigation_service.action_completed.connect(self._action_completed)
            self.mitigation_service.error.connect(self._service_error)
            self.mitigation_service.refresh_async()

    def _rules_panel(self) -> Panel:
        self.rules_badge = QLabel("0 rules")
        self.rules_badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Danh sách chính sách giảm thiểu (IPS Rules)", "Quy tắc OpenFlow đang thực thi trực tiếp trên Open vSwitch", self.rules_badge)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 4)
        toolbar.setSpacing(8)

        search = QLineEdit()
        search.setObjectName("ruleSearch")
        search.setPlaceholderText("Tìm kiếm IP, rule, cổng...")
        search.addAction(icon("search", "#8299B7", 13), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(search, 1)

        for value in ("Tất cả hành động", "Chặn", "Giới hạn"):
            combo = QComboBox()
            combo.setObjectName("ruleCombo")
            combo.addItem(value)
            toolbar.addWidget(combo)

        for value in ("Tất cả trạng thái", "Đang hoạt động", "Không hoạt động"):
            combo = QComboBox()
            combo.setObjectName("ruleCombo")
            combo.addItem(value)
            toolbar.addWidget(combo)

        refresh = QPushButton("  Làm mới")
        refresh.setObjectName("smallMonitorButton")
        refresh.setIcon(icon("refresh", "#FFFFFF", 13))
        if self.mitigation_service is not None:
            refresh.clicked.connect(self.mitigation_service.refresh_async)
        toolbar.addWidget(refresh)
        panel.box.addLayout(toolbar)

        headers = ["ID", "Nguồn IP", "Đích IP", "Giao thức", "Cổng", "Hành động", "Ưu tiên", "Thời gian còn lại", "Trạng thái", "Tác vụ"]
        self.rule_table = QTableWidget(0, len(headers))
        self.rule_table.setObjectName("ruleTable")
        self.rule_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.rule_table.setMinimumWidth(250)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.setShowGrid(False)
        self.rule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rule_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.rule_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rule_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rule_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.rule_table.setFixedHeight(265)

        pal = self.rule_table.palette()
        pal.setColor(self.rule_table.palette().ColorGroup.All, self.rule_table.palette().ColorRole.Highlight, QColor("#2D255E"))
        pal.setColor(self.rule_table.palette().ColorGroup.All, self.rule_table.palette().ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.rule_table.setPalette(pal)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if c in (0, 3, 4, 6, 7, 8, 9) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.rule_table.setHorizontalHeaderItem(c, item)

        hdr = self.rule_table.horizontalHeader()
        hdr.setStyleSheet(
            "QHeaderView { background: #181533; background-color: #181533; border: none; } "
            "QHeaderView::section { background: #181533; background-color: #181533; color: #8E8BA7; font-weight: 700; "
            "border: none; border-bottom: 1px solid #282452; padding: 6px 4px; font-size: 11px; }"
        )
        hpal = hdr.palette()
        hpal.setColor(QPalette.ColorRole.Window, QColor("#181533"))
        hpal.setColor(QPalette.ColorRole.Base, QColor("#181533"))
        hpal.setColor(QPalette.ColorRole.Button, QColor("#181533"))
        hdr.setPalette(hpal)
        hdr.setStretchLastSection(False)
        for c in range(len(headers)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.rule_table.setColumnWidth(0, 60)   # ID
        # Col 1: Stretch (Nguồn IP)
        self.rule_table.setColumnWidth(2, 105)  # Đích IP
        self.rule_table.setColumnWidth(3, 60)   # Giao thức
        self.rule_table.setColumnWidth(4, 50)   # Cổng
        self.rule_table.setColumnWidth(5, 115)  # Hành động
        self.rule_table.setColumnWidth(6, 55)   # Ưu tiên
        self.rule_table.setColumnWidth(7, 95)   # Thời gian còn lại
        self.rule_table.setColumnWidth(8, 115)  # Trạng thái
        self.rule_table.setColumnWidth(9, 55)   # Tác vụ

        panel.box.addWidget(self.rule_table)

        # Pagination
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 0)
        self.rule_count = QLabel("Đang tải chính sách từ OS-Ken")
        self.rule_count.setObjectName("flowFooter")
        self.rule_count.setStyleSheet("color: #8E8BA7; font-size: 11px;")
        footer.addWidget(self.rule_count)
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

    def _new_rule_panel(self) -> Panel:
        badge = QLabel("Tạo mới")
        badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Thêm chính sách mới", "Thiết lập quy tắc lọc và giới hạn băng thông", badge)
        panel.box.setSpacing(8)

        action_box = QVBoxLayout()
        action_box.setSpacing(2)
        action_label = QLabel("Hành động:")
        action_label.setObjectName("ruleFormLabel")
        action_box.addWidget(action_label)
        self.action_combo = QComboBox()
        self.action_combo.setObjectName("ruleFormCombo")
        self.action_combo.addItem("Chặn IP nguồn", "block_ip")
        self.action_combo.addItem("Chặn flow cụ thể", "block_flow")
        self.action_combo.addItem("Giới hạn tốc độ", "rate_limit")
        self.action_combo.addItem("Chỉ cảnh báo", "alert")
        action_box.addWidget(self.action_combo)
        panel.box.addLayout(action_box)

        self.source_input = self._field(panel, "Nguồn (Source IP):", "VD: 10.0.0.1")
        self.destination_input = self._field(panel, "Đích (Destination IP):", "VD: 10.0.0.3 hoặc any")

        protocol_row = QHBoxLayout()
        protocol_row.setSpacing(8)

        protocol_box = QVBoxLayout()
        protocol_box.setSpacing(2)
        lbl_proto = QLabel("Giao thức:")
        lbl_proto.setObjectName("ruleFormLabel")
        protocol_box.addWidget(lbl_proto)
        self.protocol_combo = QComboBox()
        self.protocol_combo.setObjectName("ruleFormCombo")
        self.protocol_combo.addItems(["Any", "TCP", "UDP", "ICMP"])
        protocol_box.addWidget(self.protocol_combo)
        protocol_row.addLayout(protocol_box)

        port_box = QVBoxLayout()
        port_box.setSpacing(2)
        lbl_port = QLabel("Cổng đích:")
        lbl_port.setObjectName("ruleFormLabel")
        port_box.addWidget(lbl_port)
        self.port_input = QLineEdit()
        self.port_input.setObjectName("ruleInput")
        self.port_input.setPlaceholderText("VD: 80 hoặc any")
        port_box.addWidget(self.port_input)
        protocol_row.addLayout(port_box)

        panel.box.addLayout(protocol_row)

        duration_box = QVBoxLayout()
        duration_box.setSpacing(2)
        lbl_dur = QLabel("Thời gian áp dụng:")
        lbl_dur.setObjectName("ruleFormLabel")
        duration_box.addWidget(lbl_dur)
        self.duration_combo = QComboBox()
        self.duration_combo.setObjectName("ruleFormCombo")
        for label, seconds in (("30 giây", 30), ("1 phút", 60), ("5 phút", 300), ("15 phút", 900), ("1 giờ", 3600)):
            self.duration_combo.addItem(label, seconds)
        duration_box.addWidget(self.duration_combo)
        panel.box.addLayout(duration_box)

        self.rate_input = self._field(panel, "Giới hạn tốc độ (Kbps):", "Mặc định: 256")

        self.reason_input = self._field(panel, "Lý do / Mô tả:", "Nhập lý do áp dụng chính sách...")

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.setContentsMargins(0, 4, 0, 0)

        add = QPushButton("  Thêm chính sách")
        add.setObjectName("addRuleButton")
        add.setIcon(icon("shield", "#FFFFFF", 13))
        add.clicked.connect(self.add_rule)
        actions.addWidget(add, 1)

        reset = QPushButton("  Đặt lại")
        reset.setObjectName("resetRuleButton")
        reset.setIcon(icon("refresh", "#C4B5FD", 13))
        reset.clicked.connect(self.reset_form)
        actions.addWidget(reset)

        panel.box.addLayout(actions)

        self.rule_status = QLabel("")
        self.rule_status.setObjectName("ruleFormStatus")
        self.rule_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel.box.addWidget(self.rule_status)

        return panel

    @staticmethod
    def _field(panel: Panel, label_text: str, placeholder: str) -> QLineEdit:
        box = QVBoxLayout()
        box.setSpacing(2)
        label = QLabel(label_text)
        label.setObjectName("ruleFormLabel")
        box.addWidget(label)
        field = QLineEdit()
        field.setObjectName("ruleInput")
        field.setPlaceholderText(placeholder)
        box.addWidget(field)
        panel.box.addLayout(box)
        return field

    def _history_panel(self) -> Panel:
        self.history_badge = QLabel("0 sự kiện")
        self.history_badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Nhật ký thực thi giảm thiểu gần đây (IPS Audit Log)", "Ghi nhận thao tác đã gửi thật tới OS-Ken và Open vSwitch", self.history_badge)

        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(6)
        self.history_empty = QLabel("Chưa có lịch sử thực thi từ IPS backend")
        self.history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_empty.setStyleSheet("color: #8E8BA7; font-size: 12px; padding: 28px 8px;")
        self.history_layout.addWidget(self.history_empty)
        panel.box.addWidget(self.history_container)

        return panel

    def toggle_ips(self) -> None:
        if self.mitigation_service is None:
            return
        active = not self.ips_toggle.isChecked() if self.sender() is self.pause_button else self.ips_toggle.isChecked()
        self.ips_toggle.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.mitigation_service.set_enabled_async(active)

    def add_rule(self) -> None:
        if not self.source_input.text().strip():
            self.rule_status.setText("⚠ Vui lòng nhập địa chỉ IP nguồn cần áp dụng.")
            self.rule_status.setProperty("valid", False)
        elif self.mitigation_service is None:
            self.rule_status.setText("⚠ Dịch vụ IPS chưa được khởi tạo.")
            self.rule_status.setProperty("valid", False)
        else:
            action = str(self.action_combo.currentData())
            port_text = self.port_input.text().strip().lower()
            rate_text = self.rate_input.text().strip()
            try:
                port = None if port_text in {"", "any", "*"} else int(port_text)
                rate = int(rate_text or "256")
            except ValueError:
                self.rule_status.setText("⚠ Cổng và tốc độ phải là số hợp lệ.")
                self.rule_status.setProperty("valid", False)
                self.rule_status.style().unpolish(self.rule_status)
                self.rule_status.style().polish(self.rule_status)
                return
            payload = {
                "action": action,
                "source_ip": self.source_input.text().strip(),
                "destination_ip": self.destination_input.text().strip() or None,
                "protocol": self.protocol_combo.currentText().lower(),
                "destination_port": port,
                "duration": int(self.duration_combo.currentData()),
                "rate_kbps": rate,
                "reason": self.reason_input.text().strip() or "Manual policy from IDS/IPS UI",
                "origin": "manual-ui",
            }
            self.rule_status.setText("Đang gửi chính sách tới OS-Ken...")
            self.rule_status.setProperty("valid", True)
            self.mitigation_service.add_rule_async(payload)
        self.rule_status.style().unpolish(self.rule_status)
        self.rule_status.style().polish(self.rule_status)

    def reset_form(self) -> None:
        self.source_input.clear()
        self.destination_input.clear()
        self.port_input.clear()
        self.rate_input.clear()
        self.reason_input.clear()
        self.rule_status.clear()

    def _set_mode_display(self, connected: bool, enabled: bool) -> None:
        self.ips_toggle.blockSignals(True)
        self.ips_toggle.setChecked(enabled)
        self.ips_toggle.blockSignals(False)
        self.ips_toggle.setEnabled(connected)
        self.pause_button.setEnabled(connected)
        self.mode_button.setEnabled(connected)
        if not connected:
            self.ips_toggle.setText("●  CHƯA KẾT NỐI IPS")
            self.mode_button.setText("  Chế độ: Không khả dụng")
            return
        self.ips_toggle.setText("●  IPS HOẠT ĐỘNG" if enabled else "●  IPS TẠM DỪNG")
        self.mode_button.setText("  Chế độ: Tự động theo AI" if enabled else "  Chế độ: Giám sát")
        self.pause_button.setText("  Tạm dừng IPS" if enabled else "  Kích hoạt IPS")
        self.pause_button.setIcon(icon("pause" if enabled else "activity", "#FFFFFF", 13))

    def _snapshot_changed(self, snapshot: dict) -> None:
        health = snapshot.get("health", {})
        connected = health.get("status") == "ok" and bool(health.get("ovs_connected"))
        enabled = bool(health.get("enabled"))
        self._set_mode_display(connected, enabled)
        self.subtitle.setText(
            "Quản lý chính sách bảo vệ mạng  •  OS-Ken + OVS OpenFlow 1.3 đã kết nối"
            if connected else "Quản lý chính sách bảo vệ mạng  •  Chưa có OVS kết nối OS-Ken"
        )
        rules = list(snapshot.get("rules", []))
        audit = list(snapshot.get("audit", []))
        self._render_rules(rules)
        self._render_audit(audit)
        active = sum(rule.get("status") == "active" for rule in rules)
        blocked = sum(
            rule.get("status") == "active" and rule.get("action") in {"block_ip", "block_flow"}
            for rule in rules
        )
        limited = sum(rule.get("status") == "active" and rule.get("action") == "rate_limit" for rule in rules)
        values = (
            (str(active), "OpenFlow", active),
            (str(blocked), "rules", blocked),
            (str(limited), "meters", limited),
            (str(len(audit)), "audit", len(audit)),
            ("100%" if connected else "—", "OVS", 100 if connected else 0),
        )
        for card, (value, label, spark) in zip(self.metric_cards, values):
            card.set_data(value, label, float(spark))
        self.mitigation_chart.has_enforcement = bool(active)
        self.mitigation_chart.update()

    def _render_rules(self, rules: list[dict]) -> None:
        self._rules = rules
        self.rule_table.clearContents()
        self.rule_table.setRowCount(len(rules))
        action_names = {"block_ip": "Chặn IP", "block_flow": "Chặn Flow", "rate_limit": "Rate Limit"}
        for row_index, rule in enumerate(rules):
            self.rule_table.setRowHeight(row_index, 36)
            protocol = str(rule.get("protocol") or "any").upper()
            action = action_names.get(str(rule.get("action")), str(rule.get("action")))
            status = "Đang hoạt động" if rule.get("status") == "active" else str(rule.get("status", "—"))
            values = (
                str(rule.get("id", ""))[:8], str(rule.get("source_ip", "—")),
                str(rule.get("destination_ip") or "any"), protocol,
                str(rule.get("destination_port") or "any"), action,
                str(rule.get("priority") or "—"), f"{int(rule.get('remaining_seconds', 0))}s", status,
            )
            for column, value in enumerate(values):
                self.rule_table.setCellWidget(
                    row_index, column,
                    make_text_cell(value, color="#FFFFFF" if column in {1, 5} else "#CBD5E1", align_center=column != 1),
                )
            delete = QPushButton("Gỡ")
            delete.setObjectName("smallMonitorButton")
            delete.setToolTip("Gỡ rule khỏi Open vSwitch")
            delete.clicked.connect(lambda _checked=False, rule_id=str(rule.get("id")): self._delete_rule(rule_id))
            self.rule_table.setCellWidget(row_index, 9, delete)
        active = sum(rule.get("status") == "active" for rule in rules)
        self.rules_badge.setText(f"{active} active")
        self.rule_count.setText(f"{len(rules)} chính sách từ OS-Ken · {active} đang thực thi")

    def _render_audit(self, events: list[dict]) -> None:
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        visible = events[:6]
        if not visible:
            self.history_empty = QLabel("Chưa có lịch sử thực thi từ IPS backend")
            self.history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_empty.setStyleSheet("color: #8E8BA7; font-size: 12px; padding: 28px 8px;")
            self.history_layout.addWidget(self.history_empty)
        event_names = {
            "rule_created": "Đã áp dụng rule OpenFlow", "rule_removed": "Đã gỡ rule",
            "rule_expired": "Rule đã hết hạn", "ips_enabled": "Đã kích hoạt IPS",
            "ips_paused": "Đã tạm dừng IPS", "alert": "AI cảnh báo",
        }
        for event in visible:
            timestamp = str(event.get("timestamp", ""))[11:19]
            name = event_names.get(str(event.get("event")), str(event.get("event", "IPS")))
            subtitle = f"{event.get('source_ip', '')}  {event.get('reason', '')}".strip()
            self.history_layout.addWidget(HistoryRow("shield", "#10B981", name, subtitle, timestamp, str(event.get("action") or "IPS")))
        self.history_badge.setText(f"{len(events)} sự kiện")

    def _delete_rule(self, rule_id: str) -> None:
        if self.mitigation_service is not None:
            self.mitigation_service.delete_rule_async(rule_id)

    def _action_completed(self, success: bool, message: str) -> None:
        self.rule_status.setText(("✓ " if success else "⚠ ") + message)
        self.rule_status.setProperty("valid", success)
        self.rule_status.style().unpolish(self.rule_status)
        self.rule_status.style().polish(self.rule_status)

    def _service_error(self, message: str) -> None:
        self._set_mode_display(False, False)
        self.subtitle.setText(f"Quản lý chính sách bảo vệ mạng  •  Lỗi kết nối: {message}")
