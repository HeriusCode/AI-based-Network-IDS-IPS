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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

        subtitle = QLabel("Quản lý chính sách bảo vệ mạng  •  Chưa kết nối IPS backend")
        subtitle.setObjectName("mitigationSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
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
        for column, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(data), 0, column)
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
        donut_badge = QLabel("Chưa có dữ liệu")
        donut_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        eff_panel = Panel("Hiệu quả giảm thiểu", "Tỷ trọng lưu lượng bất thường đã được xử lý", donut_badge)
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

    def _rules_panel(self) -> Panel:
        badge = QLabel("0 rules")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Danh sách chính sách giảm thiểu (IPS Rules)", "Quy tắc lọc gói tin tự động và thủ công đang thực thi trên tường lửa", badge)

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
        toolbar.addWidget(refresh)
        panel.box.addLayout(toolbar)

        headers = ["ID", "Nguồn IP", "Đích IP", "Giao thức", "Cổng", "Hành động", "Ưu tiên", "Thời gian còn lại", "Trạng thái", "Tác vụ"]
        self.rule_table = QTableWidget(len(RULES), len(headers))
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

        for r, row in enumerate(RULES):
            self.rule_table.setRowHeight(r, 36)

            # Col 0: ID
            self.rule_table.setCellWidget(r, 0, make_text_cell(row[0], color="#9E9BB5", align_center=True))

            # Col 1: Nguồn IP
            self.rule_table.setCellWidget(r, 1, make_text_cell(row[1], color="#FFFFFF", is_mono=True, is_bold=True))

            # Col 2: Đích IP
            self.rule_table.setCellWidget(r, 2, make_text_cell(row[2], color="#C4B5FD", is_mono=True))

            # Col 3: Giao thức
            p_color = "#60A5FA" if row[3] == "TCP" else "#FDBA74" if row[3] == "UDP" else "#C4B5FD"
            p_bg = "rgba(47, 155, 255, 0.15)" if row[3] == "TCP" else "rgba(255, 155, 55, 0.15)" if row[3] == "UDP" else "rgba(149, 81, 232, 0.15)"
            p_bd = "rgba(47, 155, 255, 0.3)" if row[3] == "TCP" else "rgba(255, 155, 55, 0.3)" if row[3] == "UDP" else "rgba(149, 81, 232, 0.3)"
            self.rule_table.setCellWidget(r, 3, make_badge_cell(row[3], p_bg, p_color, p_bd))

            # Col 4: Cổng
            self.rule_table.setCellWidget(r, 4, make_text_cell(row[4], color="#9E9BB5", is_mono=True, align_center=True))

            # Col 5: Hành động
            act = row[5]
            if act == "Chặn":
                self.rule_table.setCellWidget(r, 5, make_badge_cell("Chặn", "rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"))
            else:
                self.rule_table.setCellWidget(r, 5, make_badge_cell(act, "rgba(251, 191, 36, 0.18)", "#FBBF24", "rgba(251, 191, 36, 0.35)"))

            # Col 6: Ưu tiên
            self.rule_table.setCellWidget(r, 6, make_badge_cell(f"P{row[6]}", "rgba(139, 92, 246, 0.15)", "#C4B5FD", "rgba(139, 92, 246, 0.3)"))

            # Col 7: Thời gian còn lại
            self.rule_table.setCellWidget(r, 7, make_text_cell(row[7], color="#CBD5E1", align_center=True))

            # Col 8: Trạng thái
            status = row[8]
            if status == "Đang hoạt động":
                self.rule_table.setCellWidget(r, 8, make_badge_cell("Đang hoạt động", "rgba(16, 185, 129, 0.18)", "#10B981", "rgba(16, 185, 129, 0.35)"))
            else:
                self.rule_table.setCellWidget(r, 8, make_badge_cell("Không hoạt động", "rgba(142, 139, 167, 0.15)", "#8E8BA7", "rgba(142, 139, 167, 0.3)"))

            # Col 9: Tác vụ
            self.rule_table.setCellWidget(r, 9, make_text_cell("✎   🗑", color="#8E8BA7", align_center=True))

        panel.box.addWidget(self.rule_table)

        # Pagination
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 0)
        count = QLabel("Chưa có chính sách từ IPS backend")
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

    def _new_rule_panel(self) -> Panel:
        badge = QLabel("Tạo mới")
        badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.15); "
            "border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Thêm chính sách mới", "Thiết lập quy tắc lọc và giới hạn băng thông", badge)
        panel.box.setSpacing(8)

        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        for index, text in enumerate(("Chặn lưu lượng", "Giới hạn tốc độ", "Tùy chỉnh")):
            button = QPushButton(text)
            button.setObjectName("activeRuleTab" if index == 0 else "ruleTab")
            tabs.addWidget(button)
        panel.box.addLayout(tabs)

        self.source_input = self._field(panel, "Nguồn (Source IP):", "VD: 192.168.1.100 hoặc 192.168.1.0/24")
        self.destination_input = self._field(panel, "Đích (Destination IP):", "VD: 192.168.1.10 hoặc any")

        protocol_row = QHBoxLayout()
        protocol_row.setSpacing(8)

        protocol_box = QVBoxLayout()
        protocol_box.setSpacing(2)
        lbl_proto = QLabel("Giao thức:")
        lbl_proto.setObjectName("ruleFormLabel")
        protocol_box.addWidget(lbl_proto)
        protocol = QComboBox()
        protocol.setObjectName("ruleFormCombo")
        protocol.addItems(["TCP", "UDP", "ICMP", "Any"])
        protocol_box.addWidget(protocol)
        protocol_row.addLayout(protocol_box)

        port_box = QVBoxLayout()
        port_box.setSpacing(2)
        lbl_port = QLabel("Cổng đích:")
        lbl_port.setObjectName("ruleFormLabel")
        port_box.addWidget(lbl_port)
        port = QLineEdit()
        port.setObjectName("ruleInput")
        port.setPlaceholderText("VD: 80, 443, any")
        port_box.addWidget(port)
        protocol_row.addLayout(port_box)

        panel.box.addLayout(protocol_row)

        duration_box = QVBoxLayout()
        duration_box.setSpacing(2)
        lbl_dur = QLabel("Thời gian áp dụng:")
        lbl_dur.setObjectName("ruleFormLabel")
        duration_box.addWidget(lbl_dur)
        duration = QComboBox()
        duration.setObjectName("ruleFormCombo")
        duration.addItems(["30 phút", "1 giờ", "3 giờ", "Vô thời hạn"])
        duration_box.addWidget(duration)
        panel.box.addLayout(duration_box)

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
        badge = QLabel("0 sự kiện")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Nhật ký thực thi giảm thiểu gần đây (IPS Audit Log)", "Ghi nhận toàn bộ thao tác kích hoạt, chỉnh sửa và gỡ bỏ chính sách bảo vệ", badge)

        empty = QLabel("Chưa có lịch sử thực thi từ IPS backend")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet("color: #8E8BA7; font-size: 12px; padding: 28px 8px;")
        panel.box.addWidget(empty)

        return panel

    def toggle_ips(self) -> None:
        active = not self.ips_toggle.isChecked() if self.sender() is self.pause_button else self.ips_toggle.isChecked()
        self.ips_toggle.setChecked(active)
        if active:
            self.ips_toggle.setText("●  IPS HOẠT ĐỘNG")
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
            self.pause_button.setText("  Tạm dừng IPS")
            self.pause_button.setIcon(icon("pause", "#FFFFFF", 13))
            self.pause_button.setStyleSheet("background: #DC2626;")
        else:
            self.ips_toggle.setText("●  IPS TẠM DỪNG")
            self.ips_toggle.setStyleSheet("""
                QPushButton#ipsToggle {
                    min-width: 135px;
                    height: 34px;
                    background: rgba(239, 68, 68, 0.12);
                    border: 1px solid rgba(239, 68, 68, 0.25);
                    border-radius: 8px;
                    color: #FF5B79;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0 10px;
                }
            """)
            self.pause_button.setText("  Kích hoạt IPS")
            self.pause_button.setIcon(icon("activity", "#FFFFFF", 13))
            self.pause_button.setStyleSheet("background: #10B981;")

    def add_rule(self) -> None:
        if not self.source_input.text().strip():
            self.rule_status.setText("⚠ Vui lòng nhập địa chỉ IP nguồn cần áp dụng.")
            self.rule_status.setProperty("valid", False)
        else:
            self.rule_status.setText("⚠ Chưa kết nối IPS backend nên chưa thể áp dụng chính sách.")
            self.rule_status.setProperty("valid", False)
        self.rule_status.style().unpolish(self.rule_status)
        self.rule_status.style().polish(self.rule_status)

    def reset_form(self) -> None:
        self.source_input.clear()
        self.destination_input.clear()
        self.reason_input.clear()
        self.rule_status.clear()
