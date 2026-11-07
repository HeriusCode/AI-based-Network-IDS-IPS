"""Traffic forecasting page with AI time-series models and early-warning intelligence."""

from __future__ import annotations

import random

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
from app.ui.pages.dashboard import make_badge_cell, make_text_cell
from app.ui.pages.monitoring import MetricCard, MonitorMetric, Panel, legend_chip


# Backward compatible alias
legend = legend_chip


class ForecastChart(QWidget):
    """High-fidelity Time Series Forecasting canvas with 95% Confidence Interval ribbon."""

    actual = [
        82, 70, 86, 93, 77, 68, 82, 113, 78, 94, 83, 72, 91, 100, 119, 98,
        76, 103, 84, 112, 138, 92, 104, 129, 111, 126, 126, 103, 111, 119, 108, 112,
    ]
    forecast = [
        114, 118, 124, 129, 135, 139, 143, 146, 150, 153, 157, 161, 164, 167, 170,
        173, 177, 181, 186, 192, 196, 199, 195, 189, 183, 178, 173, 169, 165, 162.8,
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self) -> None:
        factor = random.uniform(0.97, 1.04)
        self.forecast = [max(85.0, round(v * factor + random.uniform(-2.5, 2.5), 1)) for v in self.forecast]
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
        labels = ["12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"]
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
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "● 14:30 Hiện tại")

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

    actual = [126, 145, 133, 151, 139, 158, 147, 166, 153, 176, 161, 185, 170, 194, 176, 207, 188, 219]
    predicted = [122, 141, 136, 148, 142, 154, 150, 163, 156, 172, 164, 181, 173, 190, 179, 202, 191, 215]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(165)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self) -> None:
        self.predicted = [int(v * random.uniform(0.98, 1.02)) for v in self.predicted]
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
        labels = ["14:00", "14:05", "14:10", "14:15", "14:20", "14:25", "14:30"]
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
        ]

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

        badge = QLabel("● LSTM Active")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.16); "
            "border: 1px solid rgba(139, 92, 246, 0.32); border-radius: 6px; "
            "padding: 2px 7px; font-size: 10.5px; font-weight: 700;"
        )
        header.addWidget(badge)
        layout.addLayout(header)

        # 3 Rich Metric Rows
        for icon_name, color, label_text, value, delta, pct in [
            ("arrow_down", "#3B82F6", "Dự đoán lưu lượng vào", "162.8 Mbps", "↑ 12.1%", 65),
            ("arrow_up", "#10B981", "Dự đoán lưu lượng ra", "118.6 Mbps", "↑ 9.4%", 47),
            ("database", "#8B5CF6", "Dự đoán số kết nối", "1,485 conn", "↑ 12.0%", 58),
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

        for label, val in [("RMSE", "0.024"), ("MAE", "0.018"), ("R² Score", "97.4%")]:
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
            "AI Time Series Forecasting • Dự báo xu hướng lưu lượng mạng & cảnh báo sớm nguy cơ quá tải  •  Mô phỏng"
        )
        subtitle.setObjectName("predictionSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
        header.addLayout(intro, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        ai_badge = QLabel("●  LSTM ACTIVE")
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
            MonitorMetric("Lưu lượng hiện tại", "145.2 Mbps", "↑ 8.3%", "#3B82F6", "activity"),
            MonitorMetric("Dự đoán (30 phút)", "162.8 Mbps", "↑ 12.1%", "#8B5CF6", "trend"),
            MonitorMetric("Kết nối hiện tại", "1,326", "↑ 5.1%", "#10B981", "database"),
            MonitorMetric("Nguy cơ quá tải", "Trung bình", "● 61%", "#FBBF24", "warning"),
            MonitorMetric("Cảnh báo sớm", "3", "↑ 50%", "#FF5B79", "shield"),
        ]
        for column, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(data), 0, column)
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

    def _trend_table_panel(self) -> Panel:
        badge = QLabel("6 Mốc")
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
        rows = [
            ["14:40", "150.2 Mbps", "110.3 Mbps", "1,350 conn", "↑ 3.1%"],
            ["14:50", "154.6 Mbps", "113.2 Mbps", "1,372 conn", "↑ 6.5%"],
            ["15:00", "159.8 Mbps", "116.5 Mbps", "1,401 conn", "↑ 10.1%"],
            ["15:10", "162.8 Mbps", "118.6 Mbps", "1,430 conn", "↑ 12.1%"],
            ["15:20", "165.1 Mbps", "121.0 Mbps", "1,452 conn", "↑ 14.8%"],
            ["15:30", "167.3 Mbps", "124.2 Mbps", "1,485 conn", "↑ 17.2%"],
        ]

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
        badge = QLabel("4 Cảnh báo")
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
        rows = [
            ["24/04 14:32", "Lưu lượng tăng đột biến", "162.8 Mbps", "150 Mbps", "Trung bình", "Đang theo dõi"],
            ["24/04 14:25", "Nguy cơ quá tải kết nối", "1,485 conn", "1,400 conn", "Cao", "Cần xử lý"],
            ["24/04 14:18", "Lưu lượng bất thường", "180.2 Mbps", "160 Mbps", "Cao", "Đã xác nhận"],
            ["24/04 14:10", "Xu hướng tấn công DDoS", "195.6 Mbps", "170 Mbps", "Cao", "Đã xử lý"],
        ]

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

        table.setColumnWidth(0, 85)   # Thời gian
        # Col 1: Stretch (Loại cảnh báo)
        table.setColumnWidth(2, 105)  # Giá trị dự đoán
        table.setColumnWidth(3, 85)   # Ngưỡng
        table.setColumnWidth(4, 90)   # Mức độ (không bị cắt chữ)
        table.setColumnWidth(5, 110)  # Trạng thái (không bị cắt chữ)
        table.setColumnWidth(6, 45)   # Hành động

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

        self.start_button = QPushButton("  Chạy dự đoán AI")
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
        panel.box.addWidget(self.start_button)

        return panel

    def refresh_all_predictions(self) -> None:
        self.forecast_chart.refresh()
        self.compare_chart.refresh()

    def start_prediction(self) -> None:
        self.start_button.setText("  Đang tính toán mô hình AI...")
        self.start_button.setEnabled(False)
        self.forecast_chart.refresh()
        self.compare_chart.refresh()
        QTimer.singleShot(900, self._prediction_finished)

    def _prediction_finished(self) -> None:
        self.start_button.setText("  ✓ Dự đoán hoàn tất")
        self.start_button.setEnabled(True)
        QTimer.singleShot(2000, lambda: self.start_button.setText("  Chạy dự đoán AI"))
