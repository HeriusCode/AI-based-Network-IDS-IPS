"""Reports and system logs page without fabricated security records."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPalette
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
from app.services.live_detection import LiveDetectionService
from app.services.mitigation_service import MitigationService
from app.ui.pages.dashboard import DonutChart, make_badge_cell, make_text_cell
from app.ui.pages.monitoring import Chart, MetricCard, MonitorMetric, Panel, legend_chip

# Backward compatible alias
legend = legend_chip


REPORTS_DATA: list[list[str]] = []

LOGS_DATA: list[list[str]] = []


def make_action_cell(actions: tuple[str, ...]) -> QWidget:
    """Build the compact icon-only action group used by report and log rows."""
    wrapper = QWidget()
    row = QHBoxLayout(wrapper)
    row.setContentsMargins(4, 0, 4, 0)
    row.setSpacing(2)
    row.setAlignment(Qt.AlignmentFlag.AlignCenter)

    action_specs = {
        "view": ("eye", "#C4B5FD", "Xem chi tiết"),
        "download": ("download", "#BFDBFE", "Tải báo cáo"),
        "more": ("more_vertical", "#93C5FD", "Tùy chọn khác"),
    }
    for action_name in actions:
        icon_name, color, tooltip = action_specs[action_name]
        button = QPushButton()
        button.setObjectName("tableActionButton")
        button.setIcon(icon(icon_name, color, 14))
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(25, 25)
        button.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 5px; padding: 3px; }"
            "QPushButton:hover { background: rgba(139, 92, 246, 0.20); }"
            "QPushButton:pressed { background: rgba(139, 92, 246, 0.30); }"
        )
        row.addWidget(button)
    return wrapper


class DeviceEventRow(QWidget):
    def __init__(self, name: str, value: int, maximum: int, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(10)

        label = QLabel(name)
        label.setObjectName("reportDeviceName")
        label.setFixedWidth(115)
        label.setStyleSheet("color: #CBD5E1; font-size: 12px; font-weight: 600;")
        row.addWidget(label)

        number = QLabel(f"{value:,}")
        number.setObjectName("reportDeviceValue")
        number.setFixedWidth(52)
        number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        number.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 700; font-family: 'Consolas', monospace;")
        row.addWidget(number)

        bar = QProgressBar()
        bar.setObjectName("reportDeviceBar")
        bar.setRange(0, maximum)
        bar.setValue(value)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        bar.setStyleSheet(f"QProgressBar {{ background: #25224D; border-radius: 5px; border: none; }} QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}")
        row.addWidget(bar, 1)


class ReportsPage(QScrollArea):
    def __init__(
        self,
        parent: QWidget | None = None,
        live_service: LiveDetectionService | None = None,
        mitigation_service: MitigationService | None = None,
    ) -> None:
        super().__init__(parent)
        self.live_service = live_service
        self.mitigation_service = mitigation_service
        self._flows: dict[str, dict[str, Any]] = {}
        self._audit_events: dict[str, dict[str, Any]] = {}
        self._known_log_ids: set[str] = set()
        REPORTS_DATA.clear()
        LOGS_DATA.clear()
        self.setObjectName("reportsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("reportsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(16)

        # ---------------------------------------------------------------------
        # 1. HEADER (Title, Subtitle & SOC Action Controls)
        # ---------------------------------------------------------------------
        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(2)

        title = QLabel("Báo cáo & Nhật ký")
        title.setObjectName("reportsHeading")
        intro.addWidget(title)

        subtitle = QLabel("Xem lịch sử hoạt động, báo cáo thống kê và nhật ký từ nguồn dữ liệu hệ thống")
        subtitle.setObjectName("reportsSubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro, stretch=1)

        # Status Badge
        self.status_badge = QLabel("●  CHƯA CÓ NGUỒN NHẬT KÝ")
        self.status_badge.setStyleSheet(
            "background: rgba(245, 158, 11, 0.14); color: #FBBF24; "
            "border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 10px; "
            "padding: 7px 16px; font-weight: 700; font-size: 11.5px;"
        )
        header.addWidget(self.status_badge)

        today = datetime.now().strftime("%d/%m/%Y")
        date_btn = QPushButton(f"  {today} 00:00  →  {today} 23:59  ▾")
        date_btn.setObjectName("reportsDate")
        date_btn.setIcon(icon("calendar", "#A78BFA", 14))
        header.addWidget(date_btn)

        self.create_button = QPushButton("Tạo báo cáo")
        self.create_button.setObjectName("createReportButton")
        self.create_button.setIcon(icon("document", "#FFFFFF", 14))
        self.create_button.clicked.connect(self.create_report)
        header.addWidget(self.create_button)

        root.addLayout(header)

        # ---------------------------------------------------------------------
        # 2. ROW 1: 5 THẺ CHỈ SỐ BÁO CÁO & NHẬT KÝ (KPIs toàn chiều rộng)
        # ---------------------------------------------------------------------
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Tổng sự kiện ghi nhận", "0 Logs", "Chưa có dữ liệu", "#3B82F6", "document"),
            MonitorMetric("Sự kiện bất thường", "0 Cảnh báo", "Chưa có dữ liệu", "#FF5B79", "warning"),
            MonitorMetric("Can thiệp giảm thiểu", "0 OpenFlow", "Chưa có dữ liệu", "#8B5CF6", "shield"),
            MonitorMetric("Lưu lượng phân tích", "0 B", "Chưa có dữ liệu", "#FBBF24", "activity"),
            MonitorMetric("Báo cáo tuân thủ", "0 Báo cáo", "Chưa có dữ liệu", "#10B981", "check"),
        ]
        self.metric_cards: list[MetricCard] = []
        for column, data in enumerate(metric_data):
            card = MetricCard(data)
            self.metric_cards.append(card)
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # ---------------------------------------------------------------------
        # 3. ROW 2: BIỂU ĐỒ THEO THỜI GIAN (54%) & PHÂN BỐ SỰ KIỆN + THIẾT BỊ (46%)
        # ---------------------------------------------------------------------
        overview = QGridLayout()
        overview.setSpacing(14)

        # 3.1 Dòng thời gian sự kiện (3 đường sóng)
        timeline = Panel(
            "Số lượng sự kiện theo thời gian",
            "Biến thiên số lượng log và cảnh báo theo chu kỳ 24h",
        )
        timeline_legend = QHBoxLayout()
        timeline_legend.setContentsMargins(0, 0, 0, 4)
        timeline_legend.addStretch()
        timeline_legend.addWidget(legend_chip("#3B82F6", "Tổng sự kiện"))
        timeline_legend.addWidget(legend_chip("#FF5B79", "Bất thường"))
        timeline_legend.addWidget(legend_chip("#10B981", "Giảm thiểu"))
        timeline.box.addLayout(timeline_legend)

        self.timeline_chart = Chart(
            [
                ([0.0] * 32, "#3B82F6"),
                ([0.0] * 32, "#FF5B79"),
                ([0.0] * 32, "#10B981"),
            ],
            1,
            ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"],
        )
        self.timeline_chart.setMinimumHeight(220)
        self.timeline_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        timeline.box.addWidget(self.timeline_chart, 1)
        overview.addWidget(timeline, 0, 0)

        # 3.2 Phân loại sự kiện (Donut) & Sự kiện theo thiết bị nguồn (Bars)
        self.dist_badge = QLabel("0 Thiết bị")
        self.dist_badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        dist_panel = Panel(
            "Phân bố sự kiện & Thiết bị ghi nhận",
            "Tỷ lệ cảnh báo và khối lượng xử lý theo từng node mạng",
            self.dist_badge,
        )

        dist_body = QHBoxLayout()
        dist_body.setSpacing(24)
        dist_body.setContentsMargins(6, 4, 10, 4)

        # Donut Chart - Pinned to top, perfectly sized
        self.event_donut = DonutChart(
            [],
            "",
            "0",
            "sự kiện",
        )
        self.event_donut.setFixedSize(170, 170)
        dist_body.addWidget(self.event_donut, 0, Qt.AlignmentFlag.AlignTop)

        # Device progress rows
        device_widget = QWidget()
        self.device_box = QVBoxLayout(device_widget)
        self.device_box.setContentsMargins(0, 0, 0, 0)
        self.device_box.setSpacing(9)

        dist_body.addWidget(device_widget, 1, Qt.AlignmentFlag.AlignTop)
        dist_panel.box.addLayout(dist_body)
        dist_panel.box.addStretch(1)  # Eliminates any vertical empty gap above the donut chart!
        overview.addWidget(dist_panel, 0, 1)

        overview.setColumnStretch(0, 54)
        overview.setColumnStretch(1, 46)
        root.addLayout(overview)

        # ---------------------------------------------------------------------
        # 4. ROW 3: DANH SÁCH BÁO CÁO (FULL WIDTH)
        # ---------------------------------------------------------------------
        root.addWidget(self._reports_panel())

        # ---------------------------------------------------------------------
        # 5. ROW 4: NHẬT KÝ HỆ THỐNG & SỰ KIỆN AN NINH (FULL WIDTH)
        # ---------------------------------------------------------------------
        root.addWidget(self._logs_panel())

        self.setWidget(content)
        if self.live_service is not None:
            self.live_service.changed.connect(self._ingest_live_flow)
            for flow in reversed(self.live_service.snapshot()):
                self._ingest_live_flow(flow, refresh=False)
        if self.mitigation_service is not None:
            self.mitigation_service.snapshot_changed.connect(self._ingest_ips_snapshot)
            self.mitigation_service.error.connect(self._on_ips_error)
            self.mitigation_service.refresh_async()
        self._refresh_views()

    # -------------------------------------------------------------------------
    # REPORTS TABLE PANEL (FULL WIDTH)
    # -------------------------------------------------------------------------
    def _reports_panel(self) -> Panel:
        self.report_badge = QLabel("0 Báo cáo")
        self.report_badge.setStyleSheet(
            "color: #60A5FA; background: rgba(59, 130, 246, 0.15); "
            "border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Danh sách báo cáo an ninh & tuân thủ",
            "Báo cáo định kỳ tự động và phân tích sự kiện an toàn thông tin",
            self.report_badge,
        )
        panel.box.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.report_search = QLineEdit()
        self.report_search.setObjectName("reportSearch")
        self.report_search.setPlaceholderText("Tìm kiếm báo cáo theo ID, tên...")
        self.report_search.addAction(icon("search", "#8E8BA7", 14), QLineEdit.ActionPosition.LeadingPosition)
        self.report_search.textChanged.connect(self.filter_reports)
        toolbar.addWidget(self.report_search)

        self.report_combo = QComboBox()
        self.report_combo.setObjectName("reportCombo")
        self.report_combo.addItems([
            "Tất cả loại báo cáo",
            "Định kỳ",
            "Tấn công",
            "Lưu lượng",
            "Giảm thiểu",
            "Hệ thống",
        ])
        self.report_combo.currentIndexChanged.connect(self.filter_reports)
        toolbar.addWidget(self.report_combo)

        toolbar.addStretch()

        export_btn = QPushButton("Xuất CSV")
        export_btn.setObjectName("reportExport")
        export_btn.setIcon(icon("download", "#A78BFA", 14))
        export_btn.clicked.connect(self.export_reports_csv)
        toolbar.addWidget(export_btn)
        panel.box.addLayout(toolbar)

        headers = [
            "Mã ID",
            "Tên báo cáo",
            "Loại báo cáo",
            "Thời gian bắt đầu",
            "Thời gian kết thúc",
            "Tổng sự kiện",
            "Bất thường",
            "Giảm thiểu",
            "Trạng thái",
            "Hành động",
        ]
        self.reports_table = QTableWidget(len(REPORTS_DATA), len(headers))
        self.reports_table.setObjectName("reportsTable")
        self.reports_table.setHorizontalHeaderLabels(headers)
        self.reports_table.verticalHeader().setVisible(False)
        self.reports_table.setShowGrid(False)
        self.reports_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.reports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reports_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.reports_table.setFixedHeight(110)
        self.reports_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.reports_table.setMinimumWidth(300)
        self.reports_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Highlight palette
        palette = self.reports_table.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2D255E"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.reports_table.setPalette(palette)

        header = self.reports_table.horizontalHeader()
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

        for c in range(len(headers)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Tên báo cáo co giãn tự do

        self.reports_table.setColumnWidth(0, 85)   # Mã ID
        self.reports_table.setColumnWidth(2, 115)  # Loại báo cáo
        self.reports_table.setColumnWidth(3, 130)  # Bắt đầu
        self.reports_table.setColumnWidth(4, 130)  # Kết thúc
        self.reports_table.setColumnWidth(5, 95)   # Tổng sự kiện
        self.reports_table.setColumnWidth(6, 95)   # Bất thường
        self.reports_table.setColumnWidth(7, 95)   # Giảm thiểu
        self.reports_table.setColumnWidth(8, 115)  # Trạng thái
        self.reports_table.setColumnWidth(9, 100)  # Hành động

        type_colors = {
            "Định kỳ": ("rgba(59, 130, 246, 0.15)", "#60A5FA", "rgba(59, 130, 246, 0.35)"),
            "Tấn công": ("rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Lưu lượng": ("rgba(251, 191, 36, 0.15)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
            "Giảm thiểu": ("rgba(139, 92, 246, 0.15)", "#A78BFA", "rgba(139, 92, 246, 0.35)"),
            "Hệ thống": ("rgba(16, 185, 129, 0.15)", "#34D399", "rgba(16, 185, 129, 0.35)"),
        }

        for r, row in enumerate(REPORTS_DATA):
            self.reports_table.setRowHeight(r, 34)
            # ID
            self.reports_table.setCellWidget(r, 0, make_text_cell(row[0], "#A78BFA", is_mono=True, is_bold=True, align_center=True))
            # Name
            self.reports_table.setCellWidget(r, 1, make_text_cell(row[1], "#FFFFFF", is_bold=True))
            # Type Badge (Clean & modern)
            t_bg, t_fg, t_bd = type_colors.get(row[2], ("rgba(148, 163, 184, 0.15)", "#94A3B8", "rgba(148, 163, 184, 0.35)"))
            self.reports_table.setCellWidget(r, 2, make_badge_cell(row[2], t_bg, t_fg, t_bd))
            # Start Time
            self.reports_table.setCellWidget(r, 3, make_text_cell(row[3], "#CBD5E1", is_mono=True))
            # End Time
            self.reports_table.setCellWidget(r, 4, make_text_cell(row[4], "#CBD5E1", is_mono=True))
            # Total Events
            self.reports_table.setCellWidget(r, 5, make_text_cell(row[5], "#FFFFFF", align_center=True))
            # Anomalies
            self.reports_table.setCellWidget(r, 6, make_text_cell(row[6], "#FF5B79", is_bold=True, align_center=True))
            # Mitigations
            self.reports_table.setCellWidget(r, 7, make_text_cell(row[7], "#8B5CF6", is_bold=True, align_center=True))
            # Status
            self.reports_table.setCellWidget(
                r,
                8,
                make_badge_cell("● " + row[8], "rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.35)"),
            )
            # View, download and overflow actions, matching the reference layout.
            self.reports_table.setCellWidget(r, 9, make_action_cell(("view", "download", "more")))

        if REPORTS_DATA:
            self.reports_table.selectRow(0)
        panel.box.addWidget(self.reports_table)

        # Footer
        footer = QHBoxLayout()
        self.report_count_label = QLabel("Chưa có báo cáo từ hệ thống")
        self.report_count_label.setObjectName("flowFooter")
        footer.addWidget(self.report_count_label)
        footer.addStretch()

        self.report_pages_layout = QHBoxLayout()
        self.report_pages_layout.setSpacing(4)
        footer.addLayout(self.report_pages_layout)
        self._update_report_pages(len(REPORTS_DATA))

        panel.box.addLayout(footer)
        return panel

    def _update_report_pages(self, total: int) -> None:
        while self.report_pages_layout.count() > 0:
            item = self.report_pages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pages = max(1, (total + 4) // 5)
        prev_btn = QPushButton("‹")
        prev_btn.setObjectName("pageButton")
        self.report_pages_layout.addWidget(prev_btn)

        for p in range(1, pages + 1):
            btn = QPushButton(str(p))
            btn.setObjectName("activePage" if p == 1 else "pageButton")
            self.report_pages_layout.addWidget(btn)

        next_btn = QPushButton("›")
        next_btn.setObjectName("pageButton")
        self.report_pages_layout.addWidget(next_btn)

    def filter_reports(self) -> None:
        txt = self.report_search.text().lower().strip()
        type_filter = self.report_combo.currentText()

        visible_count = 0
        for r, row in enumerate(REPORTS_DATA):
            matches_txt = (not txt) or any(txt in str(val).lower() for val in row)
            matches_type = (type_filter == "Tất cả loại báo cáo") or (type_filter == row[2])
            is_visible = matches_txt and matches_type
            self.reports_table.setRowHidden(r, not is_visible)
            if is_visible:
                visible_count += 1

        self.report_count_label.setText(
            f"Hiển thị {visible_count} / {len(REPORTS_DATA)} báo cáo"
            if REPORTS_DATA else "Chưa có báo cáo từ hệ thống"
        )
        # Dynamic table height: shrinks when few rows, expands when full
        self.reports_table.setFixedHeight(min(260, max(110, 38 + visible_count * 34)))
        self._update_report_pages(visible_count)

    def _render_report_row(self, row_index: int, row: list[str]) -> None:
        self.reports_table.setRowHeight(row_index, 34)
        self.reports_table.setCellWidget(row_index, 0, make_text_cell(row[0], "#A78BFA", is_mono=True, is_bold=True, align_center=True))
        self.reports_table.setCellWidget(row_index, 1, make_text_cell(row[1], "#FFFFFF", is_bold=True))
        type_colors = {
            "Định kỳ": ("rgba(59, 130, 246, 0.15)", "#60A5FA", "rgba(59, 130, 246, 0.35)"),
            "Tấn công": ("rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Lưu lượng": ("rgba(251, 191, 36, 0.15)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
            "Giảm thiểu": ("rgba(139, 92, 246, 0.15)", "#A78BFA", "rgba(139, 92, 246, 0.35)"),
            "Hệ thống": ("rgba(16, 185, 129, 0.15)", "#34D399", "rgba(16, 185, 129, 0.35)"),
        }
        self.reports_table.setCellWidget(row_index, 2, make_badge_cell(row[2], *type_colors.get(row[2], type_colors["Hệ thống"])))
        self.reports_table.setCellWidget(row_index, 3, make_text_cell(row[3], "#CBD5E1", is_mono=True))
        self.reports_table.setCellWidget(row_index, 4, make_text_cell(row[4], "#CBD5E1", is_mono=True))
        self.reports_table.setCellWidget(row_index, 5, make_text_cell(row[5], "#FFFFFF", align_center=True))
        self.reports_table.setCellWidget(row_index, 6, make_text_cell(row[6], "#FF5B79", is_bold=True, align_center=True))
        self.reports_table.setCellWidget(row_index, 7, make_text_cell(row[7], "#8B5CF6", is_bold=True, align_center=True))
        self.reports_table.setCellWidget(
            row_index, 8,
            make_badge_cell("● " + row[8], "rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.35)"),
        )
        actions = make_action_cell(("view", "download"))
        buttons = actions.findChildren(QPushButton)
        if buttons:
            buttons[0].clicked.connect(lambda _checked=False, index=row_index: self.show_report(index))
        if len(buttons) > 1:
            buttons[1].clicked.connect(lambda _checked=False: self.export_reports_csv())
        self.reports_table.setCellWidget(row_index, 9, actions)

    def _refresh_report_table(self) -> None:
        self.reports_table.clearContents()
        self.reports_table.setRowCount(len(REPORTS_DATA))
        for index, row in enumerate(REPORTS_DATA):
            self._render_report_row(index, row)
        if REPORTS_DATA:
            self.reports_table.selectRow(0)
        self.filter_reports()

    # -------------------------------------------------------------------------
    # SYSTEM LOGS PANEL (FULL WIDTH)
    # -------------------------------------------------------------------------
    def _logs_panel(self) -> Panel:
        self.log_badge = QLabel("0 Nhật ký")
        self.log_badge.setStyleSheet(
            "color: #A78BFA; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Nhật ký hệ thống & Audit Log thời gian thực",
            "Ghi nhận chi tiết luồng dữ liệu, cảnh báo và tác vụ can thiệp mạng",
            self.log_badge,
        )
        panel.box.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.log_search = QLineEdit()
        self.log_search.setObjectName("logSearch")
        self.log_search.setPlaceholderText("Tìm kiếm IP, nội dung log, sự kiện...")
        self.log_search.addAction(icon("search", "#8E8BA7", 14), QLineEdit.ActionPosition.LeadingPosition)
        self.log_search.textChanged.connect(self.filter_logs)
        toolbar.addWidget(self.log_search)

        self.log_severity = QComboBox()
        self.log_severity.setObjectName("reportCombo")
        self.log_severity.addItems(["Tất cả mức độ", "Cao", "Trung bình", "Thấp", "Thông tin"])
        self.log_severity.currentIndexChanged.connect(self.filter_logs)
        toolbar.addWidget(self.log_severity)

        self.log_category = QComboBox()
        self.log_category.setObjectName("reportCombo")
        self.log_category.addItems([
            "Tất cả loại sự kiện",
            "Phát hiện bất thường",
            "Giảm thiểu rủi ro",
            "Giám sát lưu lượng",
            "Hệ thống SDN",
            "Xác thực tài khoản",
            "Cảnh báo an ninh",
        ])
        self.log_category.currentIndexChanged.connect(self.filter_logs)
        toolbar.addWidget(self.log_category)

        toolbar.addStretch()

        refresh_btn = QPushButton("Làm mới")
        refresh_btn.setObjectName("reportExport")
        refresh_btn.setIcon(icon("refresh", "#A78BFA", 14))
        refresh_btn.clicked.connect(self.refresh_logs)
        toolbar.addWidget(refresh_btn)

        export_btn = QPushButton("Xuất nhật ký")
        export_btn.setObjectName("reportExport")
        export_btn.setIcon(icon("download", "#A78BFA", 14))
        export_btn.clicked.connect(self.export_logs_csv)
        toolbar.addWidget(export_btn)
        panel.box.addLayout(toolbar)

        headers = [
            "Mã Log",
            "Thời gian",
            "Mức độ",
            "Loại sự kiện",
            "Thiết bị / Nguồn",
            "Nội dung nhật ký",
            "Hành động",
        ]
        self.logs_table = QTableWidget(len(LOGS_DATA), len(headers))
        self.logs_table.setObjectName("logsTable")
        self.logs_table.setHorizontalHeaderLabels(headers)
        self.logs_table.verticalHeader().setVisible(False)
        self.logs_table.setShowGrid(False)
        self.logs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.logs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.logs_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.logs_table.setFixedHeight(110)
        self.logs_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.logs_table.setMinimumWidth(300)
        self.logs_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Highlight palette
        palette = self.logs_table.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2D255E"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.logs_table.setPalette(palette)

        header = self.logs_table.horizontalHeader()
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

        for c in range(len(headers)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Nội dung nhật ký co giãn tự do

        self.logs_table.setColumnWidth(0, 85)   # Mã Log
        self.logs_table.setColumnWidth(1, 125)  # Thời gian
        self.logs_table.setColumnWidth(2, 110)  # Mức độ
        self.logs_table.setColumnWidth(3, 140)  # Loại sự kiện
        self.logs_table.setColumnWidth(4, 130)  # Thiết bị / Nguồn
        # col 5 = Stretch (Nội dung nhật ký)
        self.logs_table.setColumnWidth(6, 70)   # Hành động

        for r, row in enumerate(LOGS_DATA):
            self.logs_table.setRowHeight(r, 32)
            # Log ID
            self.logs_table.setCellWidget(r, 0, make_text_cell(row[0], "#A78BFA", is_mono=True, is_bold=True, align_center=True))
            # Time
            self.logs_table.setCellWidget(r, 1, make_text_cell(row[1], "#CBD5E1", is_mono=True))

            # Severity badge
            sev = row[2]
            if sev == "Cao":
                self.logs_table.setCellWidget(r, 2, make_badge_cell(sev, "rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.4)"))
            elif sev == "Trung bình":
                self.logs_table.setCellWidget(r, 2, make_badge_cell(sev, "rgba(245, 158, 11, 0.15)", "#F59E0B", "rgba(245, 158, 11, 0.4)"))
            elif sev == "Thấp":
                self.logs_table.setCellWidget(r, 2, make_badge_cell(sev, "rgba(56, 189, 248, 0.15)", "#38BDF8", "rgba(56, 189, 248, 0.4)"))
            else:
                self.logs_table.setCellWidget(r, 2, make_badge_cell(sev, "rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.4)"))

            # Event type
            self.logs_table.setCellWidget(r, 3, make_text_cell(row[3], "#E2E8F0", is_bold=True))
            # Device / Source
            self.logs_table.setCellWidget(r, 4, make_text_cell(row[4], "#C4B5FD", is_mono=True))

            # Log message (Stretch with tooltip)
            desc_widget = make_text_cell(row[5], "#94A3B8")
            desc_widget.setToolTip(row[5])
            self.logs_table.setCellWidget(r, 5, desc_widget)

            # Use the same line-eye icon as the report action column.
            self.logs_table.setCellWidget(r, 6, make_action_cell(("view",)))

        if LOGS_DATA:
            self.logs_table.selectRow(0)
        panel.box.addWidget(self.logs_table)

        # Footer
        footer = QHBoxLayout()
        self.log_count_label = QLabel("Chưa có nhật ký hệ thống")
        self.log_count_label.setObjectName("flowFooter")
        footer.addWidget(self.log_count_label)
        footer.addStretch()

        self.log_pages_layout = QHBoxLayout()
        self.log_pages_layout.setSpacing(4)
        footer.addLayout(self.log_pages_layout)
        self._update_log_pages(len(LOGS_DATA))

        panel.box.addLayout(footer)
        return panel

    def _update_log_pages(self, total: int) -> None:
        while self.log_pages_layout.count() > 0:
            item = self.log_pages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pages = max(1, (total + 4) // 5)
        prev_btn = QPushButton("‹")
        prev_btn.setObjectName("pageButton")
        self.log_pages_layout.addWidget(prev_btn)

        for p in range(1, pages + 1):
            btn = QPushButton(str(p))
            btn.setObjectName("activePage" if p == 1 else "pageButton")
            self.log_pages_layout.addWidget(btn)

        next_btn = QPushButton("›")
        next_btn.setObjectName("pageButton")
        self.log_pages_layout.addWidget(next_btn)

    def filter_logs(self) -> None:
        txt = self.log_search.text().lower().strip()
        sev_filter = self.log_severity.currentText()
        cat_filter = self.log_category.currentText()

        visible_count = 0
        for r, row in enumerate(LOGS_DATA):
            matches_txt = (not txt) or any(txt in str(val).lower() for val in row)
            matches_sev = (sev_filter == "Tất cả mức độ") or (sev_filter == row[2])
            matches_cat = (cat_filter == "Tất cả loại sự kiện") or (cat_filter == row[3])
            is_visible = matches_txt and matches_sev and matches_cat
            self.logs_table.setRowHidden(r, not is_visible)
            if is_visible:
                visible_count += 1

        self.log_count_label.setText(
            f"Hiển thị {visible_count} / {len(LOGS_DATA)} nhật ký"
            if LOGS_DATA else "Chưa có nhật ký hệ thống"
        )
        self.logs_table.setFixedHeight(min(260, max(110, 38 + visible_count * 32)))
        self._update_log_pages(visible_count)

    def _render_log_row(self, row_index: int, row: list[str]) -> None:
        self.logs_table.setRowHeight(row_index, 32)
        self.logs_table.setCellWidget(row_index, 0, make_text_cell(row[0], "#A78BFA", is_mono=True, is_bold=True, align_center=True))
        self.logs_table.setCellWidget(row_index, 1, make_text_cell(row[1], "#CBD5E1", is_mono=True))
        severity_colors = {
            "Cao": ("rgba(255, 91, 121, 0.15)", "#FF5B79", "rgba(255, 91, 121, 0.4)"),
            "Trung bình": ("rgba(245, 158, 11, 0.15)", "#F59E0B", "rgba(245, 158, 11, 0.4)"),
            "Thấp": ("rgba(56, 189, 248, 0.15)", "#38BDF8", "rgba(56, 189, 248, 0.4)"),
            "Thông tin": ("rgba(16, 185, 129, 0.15)", "#10B981", "rgba(16, 185, 129, 0.4)"),
        }
        self.logs_table.setCellWidget(row_index, 2, make_badge_cell(row[2], *severity_colors.get(row[2], severity_colors["Thông tin"])))
        self.logs_table.setCellWidget(row_index, 3, make_text_cell(row[3], "#E2E8F0", is_bold=True))
        self.logs_table.setCellWidget(row_index, 4, make_text_cell(row[4], "#C4B5FD", is_mono=True))
        description = make_text_cell(row[5], "#94A3B8")
        description.setToolTip(row[5])
        self.logs_table.setCellWidget(row_index, 5, description)
        action = make_action_cell(("view",))
        button = action.findChild(QPushButton)
        if button is not None:
            button.clicked.connect(lambda _checked=False, index=row_index: self.show_log(index))
        self.logs_table.setCellWidget(row_index, 6, action)

    def _refresh_log_table(self) -> None:
        self.logs_table.clearContents()
        self.logs_table.setRowCount(len(LOGS_DATA))
        for index, row in enumerate(LOGS_DATA):
            self._render_log_row(index, row)
        if LOGS_DATA:
            self.logs_table.selectRow(0)
        self.filter_logs()

    def refresh_logs(self) -> None:
        self.log_search.clear()
        self.log_severity.setCurrentIndex(0)
        self.log_category.setCurrentIndex(0)
        if self.mitigation_service is not None:
            self.mitigation_service.refresh_async()
        self._refresh_views()

    def create_report(self) -> None:
        if not LOGS_DATA:
            self.create_button.setText("Chưa có dữ liệu")
            self.create_button.setEnabled(False)
            QTimer.singleShot(1800, self._reset_create_button)
            return
        now = datetime.now()
        report_id = f"RPT-{now:%Y%m%d-%H%M%S}"
        abnormal = sum(row[3] in {"Phát hiện bất thường", "Cảnh báo an ninh"} for row in LOGS_DATA)
        mitigated = sum(event.get("event") == "rule_created" for event in self._audit_events.values())
        REPORTS_DATA.insert(0, [
            report_id,
            f"Báo cáo phiên IDS/IPS {now:%d/%m/%Y %H:%M}",
            "Định kỳ",
            LOGS_DATA[-1][1],
            now.strftime("%d/%m/%Y %H:%M:%S"),
            str(len(LOGS_DATA)),
            str(abnormal),
            str(mitigated),
            "Hoàn tất",
        ])
        del REPORTS_DATA[100:]
        self.create_button.setText("✓ Tạo thành công!")
        self.create_button.setEnabled(False)
        self._refresh_views()
        QTimer.singleShot(1800, self._reset_create_button)

    def _report_created(self) -> None:
        self._refresh_views()

    def _reset_create_button(self) -> None:
        self.create_button.setText("Tạo báo cáo")
        self.create_button.setEnabled(True)

    @staticmethod
    def _identity(prefix: str, *parts: object) -> str:
        digest = hashlib.sha1(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:10].upper()
        return f"{prefix}-{digest}"

    @staticmethod
    def _time_text(value: object) -> str:
        raw = str(value or "")
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
            return moment.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            return raw or datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _flow_severity(flow: dict[str, Any]) -> str:
        if flow.get("label") != "ATTACK":
            return "Thông tin"
        risk = str(flow.get("risk_level") or "LOW").upper()
        if risk == "HIGH":
            return "Cao"
        if risk == "MEDIUM":
            return "Trung bình"
        return "Thấp"

    def _ingest_live_flow(self, flow: object, *, refresh: bool = True) -> None:
        if not isinstance(flow, dict):
            return
        identity = f"{flow.get('session_id', '')}:{flow.get('flow_id', '')}"
        if identity == ":":
            return
        self._flows[identity] = dict(flow)
        log_id = self._identity("LOG", "flow", identity)
        if log_id not in self._known_log_ids:
            self._known_log_ids.add(log_id)
            attack = flow.get("label") == "ATTACK"
            category = "Phát hiện bất thường" if attack else "Giám sát lưu lượng"
            attack_name = str(flow.get("attack_type") or "Chưa xác định")
            score = float(flow.get("attack_score", 0) or 0)
            protocol = str(flow.get("protocol") or "—")
            source = str(flow.get("source_ip") or "Mininet")
            destination = str(flow.get("destination_ip") or "—")
            packets = int(flow.get("packets", 0) or 0)
            if attack:
                message = f"AI phát hiện {attack_name}; score={score:.3f}; {protocol} {source} → {destination}; {packets} packets"
            else:
                message = f"AI xác nhận BENIGN; {protocol} {source} → {destination}; {packets} packets"
            LOGS_DATA.insert(0, [
                log_id,
                self._time_text(flow.get("timestamp")),
                self._flow_severity(flow),
                category,
                source,
                message,
            ])
            del LOGS_DATA[1000:]
            self.timeline_chart.append_values([1, 1 if attack else 0, 0])
        if refresh:
            self._refresh_views()

    @staticmethod
    def _audit_log(event: dict[str, Any]) -> tuple[str, str, str, str]:
        event_name = str(event.get("event") or "unknown")
        action = str(event.get("action") or "")
        source = str(event.get("source_ip") or "OS-Ken")
        rule_id = str(event.get("rule_id") or "")
        names = {
            "rule_created": "Đã áp dụng chính sách OpenFlow",
            "rule_removed": "Đã gỡ chính sách OpenFlow",
            "rule_expired": "Chính sách OpenFlow hết hạn",
            "ips_enabled": "Đã kích hoạt IPS tự động",
            "ips_paused": "Đã tạm dừng IPS tự động",
            "alert": "IPS ghi nhận cảnh báo từ AI",
        }
        category = "Giảm thiểu rủi ro" if event_name.startswith("rule_") else "Cảnh báo an ninh" if event_name == "alert" else "Hệ thống SDN"
        severity = "Cao" if event_name == "rule_created" and action in {"block_ip", "block_flow"} else "Trung bình" if event_name in {"rule_created", "alert"} else "Thông tin"
        detail = names.get(event_name, f"Sự kiện OS-Ken: {event_name}")
        suffix = "; ".join(part for part in (f"rule={rule_id}" if rule_id else "", f"action={action}" if action else "", f"source={source}" if source != "OS-Ken" else "") if part)
        return severity, category, source, f"{detail}{'; ' + suffix if suffix else ''}"

    def _ingest_ips_snapshot(self, snapshot: object) -> None:
        if not isinstance(snapshot, dict):
            return
        for event in reversed(snapshot.get("audit", [])):
            if not isinstance(event, dict):
                continue
            event_id = self._identity(
                "IPS", event.get("timestamp"), event.get("event"),
                event.get("rule_id"), event.get("action"), event.get("source_ip"),
            )
            self._audit_events[event_id] = dict(event)
            if event_id in self._known_log_ids:
                continue
            self._known_log_ids.add(event_id)
            severity, category, source, message = self._audit_log(event)
            LOGS_DATA.insert(0, [event_id, self._time_text(event.get("timestamp")), severity, category, source, message])
            self.timeline_chart.append_values([1, 1 if event.get("event") == "alert" else 0, 1 if str(event.get("event", "")).startswith("rule_") else 0])
        del LOGS_DATA[1000:]
        self._refresh_views()

    def _on_ips_error(self, message: str) -> None:
        self.status_badge.setText("●  AI LIVE • IPS KHÔNG KẾT NỐI")
        self.status_badge.setToolTip(message)

    @staticmethod
    def _format_bytes(value: float) -> str:
        amount = max(0.0, value)
        for unit in ("B", "KB", "MB", "GB"):
            if amount < 1024 or unit == "GB":
                return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
            amount /= 1024
        return "0 B"

    def _refresh_devices(self) -> None:
        while self.device_box.count():
            item = self.device_box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        devices = Counter(row[4] for row in LOGS_DATA if row[4] and row[4] != "—")
        colors = ("#3B82F6", "#FF5B79", "#8B5CF6", "#10B981", "#FBBF24")
        if devices:
            maximum = max(devices.values())
            for index, (name, count) in enumerate(devices.most_common(5)):
                self.device_box.addWidget(DeviceEventRow(name, count, maximum, colors[index % len(colors)]))
        else:
            empty = QLabel("Chưa có thiết bị ghi nhận sự kiện")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #8E8BA7; font-size: 12px;")
            self.device_box.addWidget(empty, 1)
        self.dist_badge.setText(f"{len(devices)} Thiết bị")

    def _refresh_views(self) -> None:
        attacks = sum(flow.get("label") == "ATTACK" for flow in self._flows.values())
        mitigated = sum(event.get("event") == "rule_created" for event in self._audit_events.values())
        analyzed_bytes = sum(
            max(0.0, float(flow.get("bytes_per_second", 0) or 0))
            * max(0.0, float(flow.get("flow_duration_us", 0) or 0)) / 1_000_000
            for flow in self._flows.values()
        )
        values = (
            (f"{len(LOGS_DATA)} Logs", "AI + OS-Ken", len(LOGS_DATA)),
            (f"{attacks} Cảnh báo", "AI detection", attacks),
            (f"{mitigated} OpenFlow", "block/rate-limit", mitigated),
            (self._format_bytes(analyzed_bytes), f"{len(self._flows)} flows", analyzed_bytes),
            (f"{len(REPORTS_DATA)} Báo cáo", "Phiên hiện tại", len(REPORTS_DATA)),
        )
        for card, (value, change, spark) in zip(self.metric_cards, values):
            card.set_data(str(value), str(change), float(spark))

        counts = Counter(row[3] for row in LOGS_DATA)
        total = len(LOGS_DATA)
        color_map = {
            "Phát hiện bất thường": "#FF5B79",
            "Giám sát lưu lượng": "#3B82F6",
            "Giảm thiểu rủi ro": "#8B5CF6",
            "Hệ thống SDN": "#10B981",
            "Cảnh báo an ninh": "#FBBF24",
        }
        segments = [(count * 100 / total, color_map.get(name, "#94A3B8")) for name, count in counts.items()] if total else []
        self.event_donut.set_data(segments, str(total), "sự kiện")
        self._refresh_devices()
        self.report_badge.setText(f"{len(REPORTS_DATA)} Báo cáo")
        self.log_badge.setText(f"{len(LOGS_DATA)} Nhật ký")
        if self.live_service is not None:
            ips_state = "IPS KẾT NỐI" if self.mitigation_service is not None and self.mitigation_service.connected else "ĐANG CHỜ IPS"
            self.status_badge.setText(f"●  AI LIVE • {ips_state}")
        else:
            self.status_badge.setText("●  CHƯA CÓ NGUỒN NHẬT KÝ")
        self._refresh_report_table()
        self._refresh_log_table()

    def show_report(self, index: int) -> None:
        if not 0 <= index < len(REPORTS_DATA):
            return
        row = REPORTS_DATA[index]
        QMessageBox.information(
            self, "Chi tiết báo cáo",
            f"{row[0]} — {row[1]}\n\nKhoảng thời gian: {row[3]} → {row[4]}\n"
            f"Tổng sự kiện: {row[5]}\nBất thường: {row[6]}\nGiảm thiểu: {row[7]}\nTrạng thái: {row[8]}",
        )

    def show_log(self, index: int) -> None:
        if not 0 <= index < len(LOGS_DATA):
            return
        row = LOGS_DATA[index]
        QMessageBox.information(self, "Chi tiết nhật ký", f"{row[0]} • {row[1]}\n\n{row[2]} — {row[3]}\nNguồn: {row[4]}\n\n{row[5]}")

    @staticmethod
    def _write_csv(path: str, headers: list[str], rows: list[list[str]]) -> None:
        with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)

    def export_reports_csv(self) -> None:
        if not REPORTS_DATA:
            QMessageBox.information(self, "Xuất báo cáo", "Chưa có báo cáo. Hãy bấm Tạo báo cáo trước.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất báo cáo CSV", f"ids-reports-{datetime.now():%Y%m%d-%H%M%S}.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            self._write_csv(path, ["ID", "Tên", "Loại", "Bắt đầu", "Kết thúc", "Tổng sự kiện", "Bất thường", "Giảm thiểu", "Trạng thái"], REPORTS_DATA)
        except OSError as error:
            QMessageBox.critical(self, "Không thể xuất báo cáo", str(error))
            return
        QMessageBox.information(self, "Xuất báo cáo", f"Đã xuất {len(REPORTS_DATA)} báo cáo tới:\n{path}")

    def export_logs_csv(self) -> None:
        if not LOGS_DATA:
            QMessageBox.information(self, "Xuất nhật ký", "Chưa có nhật ký để xuất.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất nhật ký CSV", f"ids-audit-log-{datetime.now():%Y%m%d-%H%M%S}.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            self._write_csv(path, ["ID", "Thời gian", "Mức độ", "Loại sự kiện", "Nguồn", "Nội dung"], LOGS_DATA)
        except OSError as error:
            QMessageBox.critical(self, "Không thể xuất nhật ký", str(error))
            return
        QMessageBox.information(self, "Xuất nhật ký", f"Đã xuất {len(LOGS_DATA)} nhật ký tới:\n{path}")
