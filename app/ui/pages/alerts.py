"""Security alerts page without fabricated IDS/IPS events."""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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
from app.services.live_detection import LiveDetectionService
from app.services.mitigation_service import MitigationService
from app.ui.pages.dashboard import DonutChart, make_badge_cell, make_text_cell
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend_chip

# Backward compatible alias
legend = legend_chip


ALERTS: list[list[str]] = []

ALERT_DETAILS: list[dict[str, str]] = []

ALERT_TRAFFIC_SERIES: list[tuple[list[tuple[list[float], str]], int]] = []


class AlertTimelineChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.low = [0.0] * 32
        self.medium = [0.0] * 32
        self.high = [0.0] * 32
        self.critical = [0.0] * 32
        self.setMinimumHeight(185)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def append_severity(self, severity: str) -> None:
        mapping = {
            "Thấp": self.low,
            "Trung bình": self.medium,
            "Cao": self.high,
            "Nghiêm trọng": self.critical,
        }
        for values in (self.low, self.medium, self.high, self.critical):
            values.append(1.0 if values is mapping.get(severity) else 0.0)
            del values[0]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        chart = QRectF(40, 10, self.width() - 52, self.height() - 34)
        maximum = max(1.0, max(self.low + self.medium + self.high + self.critical, default=0.0))

        # 1. Horizontal gridlines & Y-Axis labels
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(6):
            y = chart.bottom() - chart.height() * step / 5
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(
                QRectF(0, y - 8, 32, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{maximum * step / 5:.1f}",
            )
            painter.setPen(QPen(QColor(40, 36, 82, 160), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

        # 2. X-Axis labels
        for index, label in enumerate(["-31", "-24", "-16", "-8", "-4", "-1", "Mới"]):
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
                QPointF(chart.left() + chart.width() * i / (len(values) - 1), chart.bottom() - chart.height() * value / maximum)
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
    def __init__(
        self,
        parent: QWidget | None = None,
        live_service: LiveDetectionService | None = None,
        mitigation_service: MitigationService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("alertsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.live_service = live_service
        self.mitigation_service = mitigation_service
        self.alert_status: dict[str, str] = {}
        self._known_alerts: set[str] = set()
        self._pending_block_alert = ""
        ALERTS.clear()
        ALERT_DETAILS.clear()
        ALERT_TRAFFIC_SERIES.clear()

        content = QWidget()
        content.setObjectName("alertsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        self.current_selected_row = -1

        # ---------------------------------------------------------------------
        # 1. HEADER (Title, Subtitle & SOC Action Controls)
        # ---------------------------------------------------------------------
        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)

        title = QLabel("Cảnh báo an ninh")
        title.setObjectName("alertsHeading")
        intro.addWidget(title)

        subtitle = QLabel("Danh sách sự kiện từ IDS/IPS  •  Không sử dụng cảnh báo giả lập")
        subtitle.setObjectName("alertsSubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro, stretch=1)

        # Status badge
        self.status_badge = QLabel("●  ĐANG CHỜ PHÁT HIỆN LIVE")
        self.status_badge.setStyleSheet(
            "background: rgba(245, 158, 11, 0.14); color: #FBBF24; "
            "border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 10px; "
            "padding: 6px 14px; font-weight: 700; font-size: 11px;"
        )
        header.addWidget(self.status_badge)

        today = datetime.now().strftime("%d/%m/%Y")
        date_btn = QPushButton(f"  {today} 00:00  →  {today} 23:59  ˅")
        date_btn.setObjectName("alertsDate")
        date_btn.setIcon(icon("calendar", "#A78BFA", 14))
        header.addWidget(date_btn)

        export_btn = QPushButton("Xuất CSV")
        export_btn.setObjectName("alertsExport")
        export_btn.setIcon(icon("download", "#FFFFFF", 14))
        export_btn.clicked.connect(self.export_csv)
        header.addWidget(export_btn)

        root.addLayout(header)

        # ---------------------------------------------------------------------
        # 2. ROW 1: 5 THẺ CHỈ SỐ AN NINH (KPIs ngang toàn chiều rộng)
        # ---------------------------------------------------------------------
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Tổng cảnh báo", "0", "Chưa có", "#FF5B79", "warning"),
            MonitorMetric("Mức nghiêm trọng", "0", "Chưa có", "#FF4F5D", "blocked"),
            MonitorMetric("Mức độ cao", "0", "Chưa có", "#F59E0B", "warning"),
            MonitorMetric("Đang can thiệp", "0", "Chưa có", "#3B82F6", "activity"),
            MonitorMetric("Đã khắc phục", "0", "Chưa có", "#10B981", "shield"),
        ]
        self.metric_cards: list[MetricCard] = []
        for column, data in enumerate(metric_data):
            card = MetricCard(data)
            self.metric_cards.append(card)
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # ---------------------------------------------------------------------
        # 3. ROW 2: BIỂU ĐỒ THEO THỜI GIAN (62%) & PHÂN LOẠI CẢNH BÁO DONUT (38%)
        # ---------------------------------------------------------------------
        middle = QGridLayout()
        middle.setSpacing(12)

        # 3.1 Dòng thời gian cảnh báo 24h
        timeline = Panel("Mức độ của 32 cảnh báo gần nhất")
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
        self.category_donut = DonutChart([], "", "0", "cảnh báo")
        category_body.addWidget(self.category_donut, 1)

        category_legend = QVBoxLayout()
        category_legend.setSpacing(6)
        cat_items = [
            ("#FF5B79", "DDoS Attack", "0.0%"),
            ("#FBBF24", "DoS Attack", "0.0%"),
            ("#F59E0B", "Port Scan", "0.0%"),
            ("#6366F1", "Brute Force", "0.0%"),
            ("#10B981", "Malware C2", "0.0%"),
            ("#8B5CF6", "SQL Injection", "0.0%"),
            ("#94A3B8", "Khác / Anomaly", "0.0%"),
        ]
        self.category_labels: dict[str, QLabel] = {}
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
            self.category_labels[text] = val_chip
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

        self.show_empty_detail()
        if self.live_service is not None:
            self.live_service.changed.connect(self._ingest_live_flow)
            for flow in reversed(self.live_service.snapshot()):
                self._ingest_live_flow(flow, refresh=False)
            self._refresh_views()
        if self.mitigation_service is not None:
            self.mitigation_service.action_completed.connect(self._mitigation_completed)

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
            "DoS Attack",
            "Port Scan",
            "Brute Force",
            "SQL Injection",
            "Malware C2",
            "Khác / Anomaly",
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
            # Alert ID
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

        if ALERTS:
            self.table.selectRow(0)
        self.table.cellClicked.connect(lambda row, col: self.update_detail(row))
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        panel.box.addWidget(self.table)

        # Pagination footer
        footer = QHBoxLayout()
        self.counter_label = QLabel("Chưa có cảnh báo từ IDS/IPS")
        self.counter_label.setObjectName("flowFooter")
        footer.addWidget(self.counter_label)
        footer.addStretch()

        for page in ("‹", "1", "›"):
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

    @staticmethod
    def _attack_category(value: str) -> str:
        name = value.strip().lower()
        if "ddos" in name:
            return "DDoS Attack"
        if name == "dos" or "denial" in name or "flood" in name:
            return "DoS Attack"
        if "port" in name and "scan" in name:
            return "Port Scan"
        if "brute" in name:
            return "Brute Force"
        if "sql" in name:
            return "SQL Injection"
        if any(token in name for token in ("malware", "botnet", "c2")):
            return "Malware C2"
        return "Khác / Anomaly"

    @staticmethod
    def _severity(flow: dict) -> str:
        risk = str(flow.get("risk_level", "LOW")).upper()
        score = float(flow.get("attack_score", 0) or 0)
        if risk == "HIGH":
            return "Nghiêm trọng" if score >= 0.9 else "Cao"
        if risk == "MEDIUM":
            return "Trung bình"
        return "Thấp"

    @staticmethod
    def _alert_id(flow: dict) -> str:
        identity = f"{flow.get('session_id', '')}:{flow.get('flow_id', '')}"
        return "ALT-" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:8].upper()

    @staticmethod
    def _time_text(value: object) -> str:
        raw = str(value or "")
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
            return moment.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            return raw or datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def _ingest_live_flow(self, flow: object, *, refresh: bool = True) -> None:
        if not isinstance(flow, dict) or flow.get("label") != "ATTACK":
            return
        alert_id = self._alert_id(flow)
        if alert_id in self._known_alerts:
            return
        self._known_alerts.add(alert_id)
        severity = self._severity(flow)
        category = self._attack_category(str(flow.get("attack_type") or "Chưa xác định"))
        score = float(flow.get("attack_score", 0) or 0)
        type_confidence = float(flow.get("type_confidence", 0) or 0)
        confidence = type_confidence if type_confidence > 0 else score
        status = self.alert_status.setdefault(alert_id, "Chưa xử lý")
        description = (
            f"AI gắn cờ {category} với attack score {score:.3f}; "
            f"model {flow.get('model_version', 'unknown')}, feature {flow.get('feature_quality', 'unknown')}."
        )
        row = [
            alert_id,
            self._time_text(flow.get("timestamp")),
            str(flow.get("source_ip") or "—"),
            str(flow.get("destination_ip") or "—"),
            category,
            severity,
            description,
            status,
            "Chi tiết",
        ]
        duration_us = float(flow.get("flow_duration_us", 0) or 0)
        bytes_per_second = float(flow.get("bytes_per_second", 0) or 0)
        observed_mbps = bytes_per_second * 8 / 1_000_000
        details = {
            "confidence": f"{confidence * 100:.1f}%",
            "protocol": str(flow.get("protocol") or "—"),
            "src_port": str(flow.get("source_port") or "—"),
            "dst_port": str(flow.get("destination_port") or "—"),
            "incoming": f"{observed_mbps:.3f} Mbps" if bytes_per_second else "—",
            "outgoing": "—",
            "packets": str(int(flow.get("packets", 0) or 0)),
            "duration": f"{duration_us / 1_000_000:.3f} giây" if duration_us else "—",
            "analysis": description,
        }
        series = [0.0] * 15 + [observed_mbps]
        ALERTS.insert(0, row)
        ALERT_DETAILS.insert(0, details)
        ALERT_TRAFFIC_SERIES.insert(0, ([
            (list(series), "#FF5B79"), ([0.0] * 16, "#3B82F6")
        ], max(1, int(observed_mbps * 1.25))))
        del ALERTS[500:]
        del ALERT_DETAILS[500:]
        del ALERT_TRAFFIC_SERIES[500:]
        self.timeline_chart.append_severity(severity)
        if refresh:
            self._refresh_views(select_alert_id=alert_id)

    def _render_alert_row(self, row_index: int, row: list[str]) -> None:
        self.table.setRowHeight(row_index, 32)
        colors = ("#A78BFA", "#CBD5E1", "#FFFFFF", "#C4B5FD", "#E2E8F0")
        for column in range(5):
            self.table.setCellWidget(
                row_index, column,
                make_text_cell(row[column], colors[column], is_mono=column in {0, 2, 3}, is_bold=column in {0, 4}, align_center=column == 0),
            )
        severity_colors = {
            "Nghiêm trọng": ("rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.4)"),
            "Cao": ("rgba(245, 158, 11, 0.15)", "#F59E0B", "rgba(245, 158, 11, 0.4)"),
            "Trung bình": ("rgba(251, 191, 36, 0.15)", "#FBBF24", "rgba(251, 191, 36, 0.4)"),
            "Thấp": ("rgba(56, 189, 248, 0.15)", "#38BDF8", "rgba(56, 189, 248, 0.4)"),
        }
        self.table.setCellWidget(row_index, 5, make_badge_cell(row[5], *severity_colors[row[5]]))
        description = make_text_cell(row[6], "#94A3B8")
        description.setToolTip(row[6])
        self.table.setCellWidget(row_index, 6, description)
        status_colors = {
            "Đã xử lý": ("rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.35)"),
            "Đang xử lý": ("rgba(59, 130, 246, 0.15)", "#60A5FA", "rgba(59, 130, 246, 0.35)"),
            "Chưa xử lý": ("rgba(245, 158, 11, 0.15)", "#F59E0B", "rgba(245, 158, 11, 0.35)"),
        }
        self.table.setCellWidget(row_index, 7, make_badge_cell("● " + row[7], *status_colors[row[7]]))
        action = QPushButton("Chi tiết")
        action.setObjectName("smallMonitorButton")
        action.clicked.connect(lambda _checked=False, index=row_index: self._select_row(index))
        self.table.setCellWidget(row_index, 8, action)

    def _select_row(self, row: int) -> None:
        if 0 <= row < len(ALERTS):
            self.table.selectRow(row)
            self.update_detail(row)

    def _refresh_views(self, select_alert_id: str = "") -> None:
        self.table.clearContents()
        self.table.setRowCount(len(ALERTS))
        for index, row in enumerate(ALERTS):
            row[7] = self.alert_status.get(row[0], row[7])
            self._render_alert_row(index, row)
        total = len(ALERTS)
        critical = sum(row[5] == "Nghiêm trọng" for row in ALERTS)
        high = sum(row[5] == "Cao" for row in ALERTS)
        intervening = sum(row[7] == "Đang xử lý" for row in ALERTS)
        resolved = sum(row[7] == "Đã xử lý" for row in ALERTS)
        values = (
            (str(total), "AI live", total),
            (str(critical), "critical", critical),
            (str(high), "high", high),
            (str(intervening), "IPS", intervening),
            (str(resolved), "analyst/IPS", resolved),
        )
        for card, (value, change, spark) in zip(self.metric_cards, values):
            card.set_data(value, change, float(spark))
        colors = {
            "DDoS Attack": "#FF5B79", "Port Scan": "#F59E0B",
            "Brute Force": "#6366F1", "Malware C2": "#10B981",
            "SQL Injection": "#8B5CF6", "Khác / Anomaly": "#94A3B8",
            "DoS Attack": "#FBBF24",
        }
        counts = {name: sum(row[4] == name for row in ALERTS) for name in colors}
        segments = [(count * 100 / total, colors[name]) for name, count in counts.items() if count and total]
        self.category_donut.set_data(segments, str(total), "cảnh báo")
        for name, label in self.category_labels.items():
            label.setText(f"{counts.get(name, 0) * 100 / total:.1f}%" if total else "0.0%")
        self.status_badge.setText(
            f"●  IDS/IPS LIVE • {total} CẢNH BÁO"
            if self.live_service is not None and total
            else "●  ĐANG CHỜ ATTACK LIVE"
            if self.live_service is not None
            else "●  CHƯA CÓ NGUỒN CẢNH BÁO"
        )
        self.apply_filters()
        if select_alert_id:
            index = next((i for i, row in enumerate(ALERTS) if row[0] == select_alert_id), -1)
            if index >= 0:
                self._select_row(index)
                return
        if ALERTS:
            self._select_row(0)
        else:
            self.show_empty_detail()

    def export_csv(self) -> None:
        if not ALERTS:
            QMessageBox.information(self, "Xuất cảnh báo", "Chưa có cảnh báo để xuất.")
            return
        default_name = f"security-alerts-{datetime.now():%Y%m%d-%H%M%S}.csv"
        path, _selected = QFileDialog.getSaveFileName(self, "Xuất cảnh báo CSV", default_name, "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["ID", "Thời gian", "IP nguồn", "IP đích", "Loại tấn công", "Mức độ", "Mô tả", "Trạng thái"])
                writer.writerows(row[:8] for row in ALERTS)
        except OSError as error:
            QMessageBox.critical(self, "Không thể xuất CSV", str(error))
            return
        QMessageBox.information(self, "Xuất cảnh báo", f"Đã xuất {len(ALERTS)} cảnh báo tới:\n{path}")

    # -------------------------------------------------------------------------
    # DETAIL INSPECTOR PANEL (ROW 4 - TRÁI 58%)
    # -------------------------------------------------------------------------
    def _detail_panel(self) -> Panel:
        panel = Panel("Chi tiết cảnh báo & Can thiệp")
        panel.setObjectName("alertDetailPanel")
        panel.box.setSpacing(8)

        # Alert Banner
        self.detail_title = QLabel("Chưa có cảnh báo được chọn")
        self.detail_title.setObjectName("alertDetailTitle")
        panel.box.addWidget(self.detail_title)

        # Sub-status bar
        sub_bar = QHBoxLayout()
        self.detail_severity = QLabel("—")
        self.detail_severity.setObjectName("criticalBadge")
        sub_bar.addWidget(self.detail_severity)

        sub_bar.addStretch()

        self.confidence_label = QLabel("Độ tin cậy AI: —")
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
            ("time", "Thời gian", "—"),
            ("source", "Nguồn IP", "—"),
            ("destination", "Đích IP", "—"),
            ("protocol", "Giao thức", "—"),
            ("source_port", "Cổng nguồn", "—"),
            ("destination_port", "Cổng đích", "—"),
            ("incoming", "Lưu lượng vào", "—"),
            ("outgoing", "Lưu lượng ra", "—"),
            ("packets", "Số gói tin", "—"),
            ("duration", "Thời gian kéo dài", "—"),
            ("status", "Trạng thái", "—"),
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

        self.description = QLabel("Chưa có dữ liệu phân tích từ IDS/IPS.")
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
        self.block_button.setEnabled(False)
        actions.addWidget(self.block_button)

        self.resolve_button = QPushButton("Đánh dấu đã xử lý")
        self.resolve_button.setObjectName("alertResolveButton")
        self.resolve_button.setIcon(icon("check", "#C4B5FD", 14))
        self.resolve_button.clicked.connect(self.resolve_alert)
        self.resolve_button.setEnabled(False)
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

        self.traffic_peak_chip = QLabel("Đỉnh lưu lượng: —")
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

        default_series, default_max = ([([0.0] * 16, "#FF5B79"), ([0.0] * 16, "#3B82F6")], 1)
        self.traffic_chart = Chart(
            default_series,
            default_max,
            ["—", "—", "—", "—", "—"],
        )
        self.traffic_chart.setMinimumHeight(240)
        self.traffic_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.box.addWidget(self.traffic_chart)

        return panel

    def update_detail(self, row: int) -> None:
        if row < 0 or row >= len(ALERTS):
            self.show_empty_detail()
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
        self.detail_values["time"].setText(data[1])
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
            self.traffic_chart.update()
            if hasattr(self, "traffic_peak_chip"):
                self.traffic_peak_chip.setText(f"Đỉnh lưu lượng: {details['incoming']}")

        # Reset button states based on status
        if st == "Đã xử lý":
            self.block_button.setEnabled(False)
            self.block_button.setText("Đã hoàn tất")
            self.resolve_button.setEnabled(False)
            self.resolve_button.setText("Đã xử lý")
        elif st == "Đang xử lý":
            self.block_button.setEnabled(False)
            self.block_button.setText("Đang gửi OS-Ken...")
            self.resolve_button.setEnabled(False)
            self.resolve_button.setText("Đang xử lý")
        else:
            self.block_button.setEnabled(True)
            self.block_button.setText("Chặn IP nguồn")
            self.resolve_button.setEnabled(True)
            self.resolve_button.setText("Đánh dấu đã xử lý")

    def show_empty_detail(self) -> None:
        self.current_selected_row = -1
        self.detail_title.setText("Chưa có cảnh báo được chọn")
        self.detail_severity.setText("—")
        self.confidence_label.setText("Độ tin cậy AI: —")
        for field in self.detail_values.values():
            field.setText("—")
        self.description.setText("Chưa có dữ liệu phân tích từ IDS/IPS.")
        self.traffic_peak_chip.setText("Đỉnh lưu lượng: —")
        self.block_button.setText("Chặn IP nguồn")
        self.block_button.setEnabled(False)
        self.resolve_button.setText("Đánh dấu đã xử lý")
        self.resolve_button.setEnabled(False)

    def block_ip(self) -> None:
        row = self.current_selected_row
        if row < 0 or row >= len(ALERTS):
            return
        if self.mitigation_service is None:
            QMessageBox.warning(self, "IPS chưa kết nối", "Không có dịch vụ IPS để chặn IP nguồn.")
            return
        alert_id, source_ip = ALERTS[row][0], ALERTS[row][2]
        if source_ip in {"", "—"}:
            QMessageBox.warning(self, "Không thể chặn", "Cảnh báo không có IP nguồn hợp lệ.")
            return
        self._pending_block_alert = alert_id
        self.alert_status[alert_id] = "Đang xử lý"
        self._refresh_views(select_alert_id=alert_id)
        self.block_button.setText("Đang gửi OS-Ken...")
        self.block_button.setEnabled(False)
        self.mitigation_service.block_ip_async(
            source_ip,
            reason=f"Security alert {alert_id}: {ALERTS[row][4]}",
        )

    def resolve_alert(self) -> None:
        row = self.current_selected_row
        if row < 0 or row >= len(ALERTS):
            return
        alert_id = ALERTS[row][0]
        self.alert_status[alert_id] = "Đã xử lý"
        self._refresh_views(select_alert_id=alert_id)

    def _mitigation_completed(self, success: bool, message: str) -> None:
        alert_id, self._pending_block_alert = self._pending_block_alert, ""
        if not alert_id:
            return
        self.alert_status[alert_id] = "Đã xử lý" if success else "Chưa xử lý"
        self._refresh_views(select_alert_id=alert_id)
        if not success:
            QMessageBox.warning(self, "IPS không áp dụng được rule", message)
