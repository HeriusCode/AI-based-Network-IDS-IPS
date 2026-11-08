"""Traffic forecasting page with AI time-series models and early-warning intelligence."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from app.services.network_metrics import NetworkMetricsCollector, NetworkSnapshot
from app.ui.pages.dashboard import make_badge_cell, make_text_cell
from app.ui.pages.monitoring import MetricCard, MonitorMetric, Panel, legend_chip


# Backward compatible alias
legend = legend_chip


class ForecastChart(QWidget):
    """High-fidelity Time Series Forecasting canvas with 95% Confidence Interval ribbon."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.actual = [0.0] * 32
        self.forecast = [0.0] * 30
        self.has_forecast = False
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def append_actual(self, value: float) -> None:
        self.actual = [*self.actual[-31:], max(0.0, value)]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Coordinate rect with padding for axis numbers and labels
        chart = QRectF(44, 12, self.width() - 54, self.height() - 38)
        if chart.width() <= 10 or chart.height() <= 10:
            return

        # 1. Background subtle horizontal dashed grid lines & Y labels (0 - 300 Mbps)
        painter.setFont(QFont("Segoe UI", 8))
        max_y = 300.0
        y_steps = 6
        for step in range(y_steps + 1):
            y = chart.bottom() - chart.height() * (step / y_steps)
            val = int(step * (max_y / y_steps))

            # Dashed grid line
            painter.setPen(QPen(QColor("#24204A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

            # Y-axis label
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(
                QRectF(0, y - 8, 38, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{val}",
            )

        # 2. X-axis time marks
        now = datetime.now()
        labels = [(now + timedelta(minutes=30 * (index - 4))).strftime("%H:%M") for index in range(9)]
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

        # 3. Vertical Current Time Divider at 52% of chart width (14:30)
        divider_x = chart.left() + chart.width() * 0.52

        # Future forecast zone subtle glow tint
        future_rect = QRectF(divider_x, chart.top(), chart.right() - divider_x, chart.height())
        painter.fillRect(future_rect, QColor(108, 93, 211, 14))

        # Divider dashed line
        painter.setPen(QPen(QColor("#8B5CF6"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(divider_x, chart.top()), QPointF(divider_x, chart.bottom()))

        # Divider top pill badge
        pill_w, pill_h = 76, 18
        pill_rect = QRectF(divider_x - pill_w / 2, chart.top() + 2, pill_w, pill_h)
        painter.setBrush(QColor("#1E1B40"))
        painter.setPen(QPen(QColor("#8B5CF6"), 1))
        painter.drawRoundedRect(pill_rect, 4, 4)
        painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
        painter.setPen(QColor("#C4B5FD"))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, f"● {now:%H:%M} Hiện tại")

        # 4. Actual Traffic Curve (0% to 52%)
        n_act = len(self.actual)
        actual_points = [
            QPointF(
                chart.left() + (divider_x - chart.left()) * i / (n_act - 1),
                chart.bottom() - chart.height() * (val / max_y),
            )
            for i, val in enumerate(self.actual)
        ]

        if actual_points:
            act_path = QPainterPath(actual_points[0])
            for pt in actual_points[1:]:
                act_path.lineTo(pt)

            # Gradient area under actual curve
            act_area = QPainterPath(act_path)
            act_area.lineTo(divider_x, chart.bottom())
            act_area.lineTo(chart.left(), chart.bottom())
            act_area.closeSubpath()

            grad = QLinearGradient(0, chart.top(), 0, chart.bottom())
            grad.setColorAt(0.0, QColor(59, 130, 246, 120))
            grad.setColorAt(0.8, QColor(59, 130, 246, 20))
            grad.setColorAt(1.0, QColor(59, 130, 246, 0))
            painter.fillPath(act_area, grad)

            # Draw actual curve stroke
            painter.setPen(QPen(QColor("#3B82F6"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(act_path)

        # 5. Forecast 95% Confidence Interval Ribbon (52% to 100%)
        if not self.has_forecast:
            return

        n_fore = len(self.forecast)
        forecast_points = [
            QPointF(
                divider_x + (chart.right() - divider_x) * i / (n_fore - 1),
                chart.bottom() - chart.height() * (val / max_y),
            )
            for i, val in enumerate(self.forecast)
        ]

        if forecast_points:
            upper_pts = []
            lower_pts = []
            for i, pt in enumerate(forecast_points):
                expansion = 4.0 + 15.0 * (i / (n_fore - 1))
                upper_pts.append(QPointF(pt.x(), max(chart.top(), pt.y() - expansion)))
                lower_pts.append(QPointF(pt.x(), min(chart.bottom(), pt.y() + expansion)))

            band_path = QPainterPath(upper_pts[0])
            for pt in upper_pts[1:]:
                band_path.lineTo(pt)
            for pt in reversed(lower_pts):
                band_path.lineTo(pt)
            band_path.closeSubpath()

            # Soft lavender glow fill for confidence interval
            painter.fillPath(band_path, QColor(139, 92, 246, 45))
            painter.setPen(QPen(QColor(139, 92, 246, 85), 1, Qt.PenStyle.DashLine))
            painter.drawPath(band_path)

            # 6. Forecast Dashed Curve Stroke
            fore_path = QPainterPath(forecast_points[0])
            for pt in forecast_points[1:]:
                fore_path.lineTo(pt)

            painter.setPen(QPen(QColor("#FF5B79"), 2.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(fore_path)

            # Terminal Forecast Value Dot & Badge
            tip = forecast_points[-1]
            painter.setBrush(QColor("#FF5B79"))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.8))
            painter.drawEllipse(tip, 4.0, 4.0)

            tip_badge = QRectF(tip.x() - 44, tip.y() - 23, 44, 17)
            painter.setBrush(QColor("#251D42"))
            painter.setPen(QPen(QColor("#FF5B79"), 1))
            painter.drawRoundedRect(tip_badge, 4, 4)
            painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(tip_badge, Qt.AlignmentFlag.AlignCenter, f"{self.forecast[-1]}M")


class ComparisonChart(QWidget):
    """Dual-curve historical accuracy comparison comparing actual vs model predicted points."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.actual = [0.0] * 18
        self.predicted = [0.0] * 18
        self.has_prediction = False
        self.setMinimumHeight(165)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def append_actual(self, value: float) -> None:
        self.actual = [*self.actual[-17:], max(0.0, value)]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        chart = QRectF(38, 10, self.width() - 48, self.height() - 32)
        if chart.width() <= 10 or chart.height() <= 10:
            return

        # Grid lines (0, 65, 130, 195, 260)
        painter.setFont(QFont("Segoe UI", 8))
        max_v = 260.0
        for step in range(5):
            y = chart.bottom() - chart.height() * (step / 4)
            v = int(step * (max_v / 4))
            painter.setPen(QPen(QColor("#24204A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(0, y - 8, 32, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(v))

        # Time labels
        now = datetime.now()
        labels = [(now - timedelta(minutes=5 * (6 - index))).strftime("%H:%M") for index in range(7)]
        for idx, lbl in enumerate(labels):
            x = chart.left() + chart.width() * idx / (len(labels) - 1)
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(x - 18, chart.bottom() + 5, 36, 16), Qt.AlignmentFlag.AlignCenter, lbl)

        # Plot curves
        n = len(self.actual)
        act_pts = [
            QPointF(chart.left() + chart.width() * i / (n - 1), chart.bottom() - chart.height() * (v / max_v))
            for i, v in enumerate(self.actual)
        ]
        pred_pts = [
            QPointF(chart.left() + chart.width() * i / (n - 1), chart.bottom() - chart.height() * (v / max_v))
            for i, v in enumerate(self.predicted)
        ] if self.has_prediction else []

        # Actual area & line
        act_path = QPainterPath(act_pts[0])
        for p in act_pts[1:]:
            act_path.lineTo(p)

        act_area = QPainterPath(act_path)
        act_area.lineTo(chart.right(), chart.bottom())
        act_area.lineTo(chart.left(), chart.bottom())
        act_area.closeSubpath()
        painter.fillPath(act_area, QColor(59, 130, 246, 30))

        painter.setPen(QPen(QColor("#3B82F6"), 1.8))
        painter.drawPath(act_path)

        # Predicted line
        if pred_pts:
            pred_path = QPainterPath(pred_pts[0])
            for p in pred_pts[1:]:
                pred_path.lineTo(p)
            painter.setPen(QPen(QColor("#C084FC"), 1.8, Qt.PenStyle.DashLine))
            painter.drawPath(pred_path)


class PredictionSummary(QFrame):
    """Right-side rich AI forecast indicators & model performance cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("predictionSummary")
        self.setStyleSheet("""
            QFrame#predictionSummary {
                background: #1B1938;
                border: 1px solid #282452;
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header with AI Model Badge
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Chỉ số dự đoán AI")
        title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700;")
        sub = QLabel("Phân rã luồng & hiệu năng")
        sub.setStyleSheet("color: #8E8BA7; font-size: 10.5px;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box, 1)

        badge = QLabel("● Chưa kết nối mô hình")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.16); "
            "border: 1px solid rgba(139, 92, 246, 0.32); border-radius: 6px; "
            "padding: 2px 7px; font-size: 10.5px; font-weight: 700;"
        )
        header.addWidget(badge)
        layout.addLayout(header)

        # 3 Rich Metric Rows
        for icon_name, color, label_text, value, delta, pct in [
            ("arrow_down", "#3B82F6", "Dự đoán lưu lượng vào", "—", "Chưa có", 0),
            ("arrow_up", "#10B981", "Dự đoán lưu lượng ra", "—", "Chưa có", 0),
            ("database", "#8B5CF6", "Dự đoán số kết nối", "—", "Chưa có", 0),
        ]:
            card = QFrame()
            card.setStyleSheet("background: #201D42; border: 1px solid #2B2757; border-radius: 10px;")
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(10, 8, 10, 8)
            card_lay.setSpacing(8)

            # Icon container
            ico_lbl = QLabel()
            ico_lbl.setPixmap(icon(icon_name, color, 16).pixmap(16, 16))
            ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico_lbl.setFixedSize(34, 34)
            ico_lbl.setStyleSheet(f"background: rgba(255, 255, 255, 0.05); border: 1px solid {color}40; border-radius: 8px;")
            card_lay.addWidget(ico_lbl)

            info = QVBoxLayout()
            info.setSpacing(1)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #9E9BB5; font-size: 10.5px; font-weight: 500;")
            info.addWidget(lbl)

            val_lay = QHBoxLayout()
            val_lay.setSpacing(6)
            val = QLabel(value)
            val.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 700; letter-spacing: -0.3px;")
            val_lay.addWidget(val)

            d_lbl = QLabel(delta)
            d_lbl.setStyleSheet(f"color: {color}; font-size: 10.5px; font-weight: 600;")
            val_lay.addWidget(d_lbl)
            val_lay.addStretch()
            info.addLayout(val_lay)

            # Mini progress bar
            bar = QProgressBar()
            bar.setFixedHeight(3)
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{ background: #2D2859; border: none; border-radius: 1.5px; }}
                QProgressBar::chunk {{ background: {color}; border-radius: 1.5px; }}
            """)
            info.addWidget(bar)

            card_lay.addLayout(info, 1)
            layout.addWidget(card)

        # AI Model Evaluation Metrics (RMSE, MAE, R²)
        eval_box = QFrame()
        eval_box.setStyleSheet("background: #171530; border: 1px solid #26224E; border-radius: 8px;")
        eval_lay = QHBoxLayout(eval_box)
        eval_lay.setContentsMargins(10, 6, 10, 6)
        eval_lay.setSpacing(6)

        for label, val in [("RMSE", "—"), ("MAE", "—"), ("R² Score", "—")]:
            item = QVBoxLayout()
            item.setSpacing(1)
            item.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet("color: #7E7A9C; font-size: 9.5px; font-weight: 500;")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v = QLabel(val)
            v.setStyleSheet("color: #10B981; font-size: 11.5px; font-weight: 700;")
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item.addWidget(l)
            item.addWidget(v)
            eval_lay.addLayout(item)

        layout.addWidget(eval_box)
        layout.addStretch()


class PredictionPage(QScrollArea):
    """Modern AI Traffic Prediction page adhering to the Midnight Indigo SOC design system."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("predictionScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.collector = NetworkMetricsCollector()
        self._last_snapshot: NetworkSnapshot | None = None

        content = QWidget()
        content.setObjectName("predictionContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 12, 18, 16)
        root.setSpacing(12)

        # 1. Header & Controls
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 2)
        header.setSpacing(12)

        intro = QVBoxLayout()
        intro.setSpacing(2)
        heading = QLabel("Dự đoán lưu lượng")
        heading.setObjectName("predictionHeading")
        heading.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;")
        intro.addWidget(heading)

        subtitle = QLabel(
            "AI Time Series Forecasting • Dữ liệu hiện tại từ hệ điều hành • Không tạo dự báo giả lập"
        )
        subtitle.setObjectName("predictionSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
        header.addLayout(intro, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        ai_badge = QLabel("●  CHƯA KẾT NỐI MÔ HÌNH")
        ai_badge.setObjectName("liveBadge")
        ai_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: 700;"
        )
        controls.addWidget(ai_badge)

        self.date_button = QPushButton("  30 phút tới  ˅")
        self.date_button.setObjectName("dateRangeButton")
        self.date_button.setIcon(icon("clock", "#AFC7E4", 13))
        self.date_button.setFixedHeight(34)
        controls.addWidget(self.date_button)

        refresh = QPushButton("  Dự đoán lại")
        refresh.setObjectName("predictionRefresh")
        refresh.setIcon(icon("refresh", "#FFFFFF", 13))
        refresh.setFixedHeight(34)
        refresh.clicked.connect(self.refresh_all_predictions)
        controls.addWidget(refresh)

        header.addLayout(controls)
        root.addLayout(header)

        # 2. Hàng 1: 5 Thẻ chỉ số dự đoán (KPI Indicators)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metric_data = [
            MonitorMetric("Lưu lượng hiện tại", "—", "Live", "#3B82F6", "activity"),
            MonitorMetric("Dự đoán (30 phút)", "—", "Chưa có", "#8B5CF6", "trend"),
            MonitorMetric("Kết nối hiện tại", "—", "Live", "#10B981", "database"),
            MonitorMetric("Nguy cơ quá tải", "—", "Chưa có", "#FBBF24", "warning"),
            MonitorMetric("Cảnh báo sớm", "0", "Chưa có", "#FF5B79", "shield"),
        ]
        self.metric_cards: list[MetricCard] = []
        for column, data in enumerate(metric_data):
            card = MetricCard(data)
            self.metric_cards.append(card)
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        # 3. Hàng 2: Biểu đồ dự đoán chuỗi thời gian lớn (62%) & Thẻ phân rã chỉ số AI (38%)
        main_row = QGridLayout()
        main_row.setSpacing(12)

        # 3.1 Panel Biểu đồ dự đoán
        chart_extra = QWidget()
        chart_extra_lay = QHBoxLayout(chart_extra)
        chart_extra_lay.setContentsMargins(0, 0, 0, 0)
        chart_extra_lay.setSpacing(8)
        chart_extra_lay.addWidget(legend_chip("#3B82F6", "Thực tế"))
        chart_extra_lay.addWidget(legend_chip("#FF5B79", "Dự đoán"))
        chart_extra_lay.addWidget(legend_chip("#8B5CF6", "Khoảng 95%"))

        forecast_panel = Panel(
            "Dự đoán lưu lượng (Forecasting)",
            "Mô hình học sâu kết hợp khoảng tin cậy 95%",
            chart_extra,
        )
        self.forecast_chart = ForecastChart()
        forecast_panel.box.addWidget(self.forecast_chart, 1)
        main_row.addWidget(forecast_panel, 0, 0)

        # 3.2 Panel Chỉ số dự đoán AI
        self.summary_card = PredictionSummary()
        main_row.addWidget(self.summary_card, 0, 1)

        main_row.setColumnStretch(0, 62)
        main_row.setColumnStretch(1, 38)
        root.addLayout(main_row)

        # 4. Hàng 3: So sánh thực tế & dự đoán (50%) + Bảng xu hướng ngắn hạn (50%)
        middle_row = QGridLayout()
        middle_row.setSpacing(12)

        # 4.1 So sánh thực tế và dự đoán
        compare_extra = QWidget()
        compare_lay = QHBoxLayout(compare_extra)
        compare_lay.setContentsMargins(0, 0, 0, 0)
        compare_lay.setSpacing(8)
        compare_lay.addWidget(legend_chip("#3B82F6", "Thực tế"))
        compare_lay.addWidget(legend_chip("#C084FC", "Dự đoán"))

        compare_panel = Panel(
            "So sánh thực tế & dự đoán",
            "Độ hội tụ giữa dữ liệu quan trắc và AI",
            compare_extra,
        )
        self.compare_chart = ComparisonChart()
        compare_panel.box.addWidget(self.compare_chart, 1)
        middle_row.addWidget(compare_panel, 0, 0)

        # 4.2 Bảng xu hướng ngắn hạn 30 phút tới
        middle_row.addWidget(self._trend_table_panel(), 0, 1)

        middle_row.setColumnStretch(0, 1)
        middle_row.setColumnStretch(1, 1)
        root.addLayout(middle_row)

        # 5. Hàng 4: Bảng cảnh báo dự đoán sớm (66%) & Thiết lập dự đoán (34%)
        bottom_row = QGridLayout()
        bottom_row.setSpacing(12)

        bottom_row.addWidget(self._alerts_panel(), 0, 0)
        bottom_row.addWidget(self._settings_panel(), 0, 1)

        bottom_row.setColumnStretch(0, 66)
        bottom_row.setColumnStretch(1, 34)
        root.addLayout(bottom_row)

        self.setWidget(content)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.refresh_current_data)
        self.live_timer.start(1800)
        self.refresh_current_data()

    def _trend_table_panel(self) -> Panel:
        badge = QLabel("0 mốc")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Xu hướng ngắn hạn (30 phút tới)",
            "Dự báo chi tiết lưu lượng và kết nối theo từng mốc 10 phút",
            badge,
        )

        headers = ["Thời điểm", "Lưu lượng vào", "Lưu lượng ra", "Kết nối", "Tăng trưởng"]
        rows: list[list[str]] = []

        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("predictionTable")
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setMinimumWidth(220)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setFixedHeight(210)

        pal = table.palette()
        pal.setColor(table.palette().ColorGroup.All, table.palette().ColorRole.Highlight, QColor("#2D255E"))
        pal.setColor(table.palette().ColorGroup.All, table.palette().ColorRole.HighlightedText, QColor("#FFFFFF"))
        table.setPalette(pal)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if c in (0, 3, 4) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setHorizontalHeaderItem(c, item)

        hdr = table.horizontalHeader()
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
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)

        table.setColumnWidth(0, 75)   # Thời điểm
        # Col 1: Stretch (Lưu lượng vào co giãn tự nhiên)
        # Col 2: Stretch (Lưu lượng ra co giãn tự nhiên)
        table.setColumnWidth(3, 105)  # Kết nối
        table.setColumnWidth(4, 95)   # Tăng trưởng

        for r, row in enumerate(rows):
            table.setRowHeight(r, 34)
            table.setCellWidget(r, 0, make_text_cell(row[0], color="#9E9BB5", is_mono=True, align_center=True))
            table.setCellWidget(r, 1, make_text_cell(row[1], color="#60A5FA", is_mono=True, is_bold=True))
            table.setCellWidget(r, 2, make_text_cell(row[2], color="#34D399", is_mono=True))
            table.setCellWidget(r, 3, make_text_cell(row[3], color="#C4B5FD", is_mono=True, align_center=True))

            pct_val = row[4]
            num = float(pct_val.replace("↑", "").replace("%", "").strip())
            p_bg = "rgba(255, 91, 121, 0.15)" if num > 10.0 else "rgba(251, 191, 36, 0.15)"
            p_fg = "#FF5B79" if num > 10.0 else "#FBBF24"
            p_bd = "rgba(255, 91, 121, 0.3)" if num > 10.0 else "rgba(251, 191, 36, 0.3)"
            table.setCellWidget(r, 4, make_badge_cell(pct_val, p_bg, p_fg, p_bd))

        panel.box.addWidget(table)
        return panel

    def _alerts_panel(self) -> Panel:
        badge = QLabel("0 cảnh báo")
        badge.setStyleSheet(
            "color: #FF5B79; background: rgba(255, 91, 121, 0.15); "
            "border: 1px solid rgba(255, 91, 121, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Cảnh báo dự đoán sớm",
            "Mô hình AI phát hiện nguy cơ vượt ngưỡng băng thông hoặc quá tải kết nối trước khi xảy ra",
            badge,
        )

        headers = ["Thời gian", "Loại cảnh báo", "Giá trị dự đoán", "Ngưỡng", "Mức độ", "Trạng thái", "Hành động"]
        rows: list[list[str]] = []

        table = QTableWidget(len(rows), len(headers))
        self.alert_table = table
        table.setObjectName("predictionTable")
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setMinimumWidth(220)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setFixedHeight(175)

        pal = table.palette()
        pal.setColor(table.palette().ColorGroup.All, table.palette().ColorRole.Highlight, QColor("#2D255E"))
        pal.setColor(table.palette().ColorGroup.All, table.palette().ColorRole.HighlightedText, QColor("#FFFFFF"))
        table.setPalette(pal)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if c in (0, 4, 5, 6) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setHorizontalHeaderItem(c, item)

        hdr = table.horizontalHeader()
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

        table.setColumnWidth(0, 75)   # Thời gian
        # Col 1: Stretch (Loại cảnh báo)
        table.setColumnWidth(2, 100)  # Giá trị dự đoán
        table.setColumnWidth(3, 75)   # Ngưỡng
        table.setColumnWidth(4, 85)   # Mức độ
        table.setColumnWidth(5, 105)  # Trạng thái
        table.setColumnWidth(6, 82)   # Hành động luôn hiển thị đủ

        severity_colors = {
            "Cao": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Trung bình": ("rgba(251, 191, 36, 0.18)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
            "Thấp": ("rgba(16, 185, 129, 0.18)", "#34D399", "rgba(16, 185, 129, 0.35)"),
        }

        status_colors = {
            "Đang theo dõi": ("rgba(56, 189, 248, 0.18)", "#38BDF8", "rgba(56, 189, 248, 0.35)"),
            "Cần xử lý": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Đã xác nhận": ("rgba(139, 92, 246, 0.18)", "#C4B5FD", "rgba(139, 92, 246, 0.35)"),
            "Đã xử lý": ("rgba(16, 185, 129, 0.18)", "#10B981", "rgba(16, 185, 129, 0.35)"),
        }

        for r, row in enumerate(rows):
            table.setRowHeight(r, 36)

            # Col 0: Thời gian
            table.setCellWidget(r, 0, make_text_cell(row[0], color="#9E9BB5", align_center=True))

            # Col 1: Loại cảnh báo
            table.setCellWidget(r, 1, make_text_cell(row[1], color="#FFFFFF", is_bold=True))

            # Col 2: Giá trị dự đoán
            table.setCellWidget(r, 2, make_text_cell(row[2], color="#FF8A4C", is_mono=True, is_bold=True))

            # Col 3: Ngưỡng
            table.setCellWidget(r, 3, make_text_cell(row[3], color="#8E8BA7", is_mono=True))

            # Col 4: Mức độ
            s_bg, s_fg, s_bd = severity_colors.get(row[4], ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(r, 4, make_badge_cell(row[4], s_bg, s_fg, s_bd))

            # Col 5: Trạng thái
            st_bg, st_fg, st_bd = status_colors.get(row[5], ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(r, 5, make_badge_cell(row[5], st_bg, st_fg, st_bd))

            # Col 6: Hành động
            table.setCellWidget(r, 6, make_text_cell("◉  ⋮", color="#8E8BA7", align_center=True))

        panel.box.addWidget(table)
        return panel

    def _settings_panel(self) -> Panel:
        badge = QLabel("Cấu hình")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Thiết lập tham số AI", "Tùy chỉnh mô hình học sâu & khoảng dự báo", badge)

        form_box = QVBoxLayout()
        form_box.setSpacing(9)

        for label_text, values in [
            ("Mô hình AI:", ["LSTM (Deep Learning)", "GRU (Recurrent)", "ARIMA (Statistical)"]),
            ("Khoảng dự đoán:", ["30 phút tới", "1 giờ tới", "3 giờ tới"]),
            ("Chu kỳ cập nhật:", ["1 phút", "5 phút", "10 phút"]),
            ("Độ nhạy:", ["Tiêu chuẩn (95%)", "Nhạy cảm (90%)", "Nghiêm ngặt (99%)"]),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(label_text)
            label.setObjectName("settingLabel")
            label.setStyleSheet("color: #9E9BB5; font-size: 11px; font-weight: 600; min-width: 100px;")
            row.addWidget(label)

            combo = QComboBox()
            combo.setObjectName("predictionCombo")
            combo.addItems(values)
            combo.setFixedHeight(30)
            combo.setStyleSheet("""
                QComboBox {
                    background: #171530;
                    border: 1px solid #2B2757;
                    border-radius: 8px;
                    padding: 3px 8px;
                    color: #FFFFFF;
                    font-size: 11px;
                }
                QComboBox:hover {
                    border-color: #6C5DD3;
                }
                QComboBox QAbstractItemView {
                    background: #1B1938;
                    border: 1px solid #2D2958;
                    selection-background-color: #6C5DD3;
                    color: #FFFFFF;
                    padding: 4px;
                }
            """)
            row.addWidget(combo, 1)
            form_box.addLayout(row)

        panel.box.addLayout(form_box)

        self.start_button = QPushButton("  Chưa kết nối mô hình AI")
        self.start_button.setObjectName("startPredictionButton")
        self.start_button.setIcon(icon("trend", "#FFFFFF", 14))
        self.start_button.setFixedHeight(36)
        self.start_button.setStyleSheet("""
            QPushButton#startPredictionButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6C5DD3, stop:1 #8E59FF);
                border: 1px solid #7B61FF;
                border-radius: 10px;
                color: #FFFFFF;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton#startPredictionButton:hover {
                background: #7B61FF;
            }
            QPushButton#startPredictionButton:disabled {
                background: #25214E;
                color: #716C97;
                border-color: #38326D;
            }
        """)
        self.start_button.clicked.connect(self.start_prediction)
        self.start_button.setEnabled(False)
        panel.box.addWidget(self.start_button)

        return panel

    def refresh_current_data(self) -> None:
        snapshot = self.collector.sample()
        self._last_snapshot = snapshot
        if not snapshot.available:
            for card in self.metric_cards:
                card.set_data("—", "Offline", 0.0)
            return

        total_mbps = snapshot.incoming_mbps + snapshot.outgoing_mbps
        self.metric_cards[0].set_data(f"{total_mbps:.2f} Mbps", "Live", total_mbps)
        self.metric_cards[1].set_data("—", "Chưa có", 0.0)
        self.metric_cards[2].set_data(f"{snapshot.active_connections:,}", "Live", snapshot.active_connections)
        self.metric_cards[3].set_data("—", "Chưa có", 0.0)
        self.metric_cards[4].set_data("0", "Chưa có", 0.0)
        self.forecast_chart.append_actual(total_mbps)
        self.compare_chart.append_actual(total_mbps)

    def refresh_all_predictions(self) -> None:
        self.refresh_current_data()

    def start_prediction(self) -> None:
        self.refresh_current_data()

    def _prediction_finished(self) -> None:
        self.start_button.setText("  Chưa kết nối mô hình AI")
        self.start_button.setEnabled(False)
