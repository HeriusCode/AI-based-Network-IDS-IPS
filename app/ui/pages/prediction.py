"""Traffic forecasting page with AI time-series models and early-warning intelligence."""

from __future__ import annotations

from datetime import datetime, timedelta
import math

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
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
from app.services.ai_client import AiClient
from app.services.live_detection import LiveDetectionService
from app.services.network_metrics import NetworkMetricsCollector, NetworkSnapshot
from app.ui.pages.dashboard import make_badge_cell, make_text_cell
from app.ui.pages.monitoring import MetricCard, MonitorMetric, Panel, legend_chip


# Backward compatible alias
legend = legend_chip


class ForecastSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class ForecastWorker(QRunnable):
    def __init__(self, client: AiClient, history: list[dict], horizon: int = 3) -> None:
        super().__init__()
        self.client = client
        self.history = history
        self.horizon = horizon
        self.signals = ForecastSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.completed.emit(self.client.forecast_traffic(self.history, self.horizon))
        except Exception as error:
            self.signals.failed.emit(str(error))


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

    def set_forecast(self, values: list[float]) -> None:
        self.forecast = [max(0.0, float(value)) for value in values]
        self.has_forecast = bool(self.forecast)
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

    def set_forecast(self, values: list[float]) -> None:
        clean = [max(0.0, float(value)) for value in values]
        self.predicted = [*self.predicted[-max(0, 18 - len(clean)):], *clean][-18:]
        self.has_prediction = bool(clean)
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


def _parse_timestamp(value: object) -> datetime:
    text = str(value or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return datetime.now().astimezone()


def _nice_axis_max(value: float) -> float:
    value = max(0.0001, float(value) * 1.15)
    power = 10 ** math.floor(math.log10(value))
    normalized = value / power
    step = 1.0 if normalized <= 1 else 2.0 if normalized <= 2 else 5.0 if normalized <= 5 else 10.0
    return step * power


class AdaptiveForecastChart(QWidget):
    """Short-horizon chart using real timestamps, adaptive scale and model intervals."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.actual: list[tuple[datetime, float]] = []
        self.forecast: list[dict] = []
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def append_actual(self, value: float, timestamp: object = None) -> None:
        point_time = _parse_timestamp(timestamp)
        key = int(point_time.timestamp() * 1000)
        if self.actual and int(self.actual[-1][0].timestamp() * 1000) == key:
            self.actual[-1] = (point_time, max(0.0, float(value)))
        else:
            self.actual.append((point_time, max(0.0, float(value))))
            self.actual = self.actual[-60:]
        self.update()

    def set_forecast(self, rows: list[dict]) -> None:
        self.forecast = [dict(row) for row in rows]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(54, 12, self.width() - 66, self.height() - 42)
        if chart.width() <= 20 or chart.height() <= 20:
            return

        actual = self.actual[-32:]
        forecast = [
            (
                _parse_timestamp(row.get("timestamp")),
                max(0.0, float(row.get("mbps", 0))),
                max(0.0, float(row.get("lower_mbps", row.get("mbps", 0)))),
                max(0.0, float(row.get("upper_mbps", row.get("mbps", 0)))),
            )
            for row in self.forecast
        ]
        divider_time = actual[-1][0] if actual else datetime.now().astimezone()
        start_time = divider_time - timedelta(seconds=12)
        if actual:
            start_time = min(start_time, actual[0][0])
        end_time = forecast[-1][0] if forecast else divider_time + timedelta(seconds=3)
        if end_time <= divider_time:
            end_time = divider_time + timedelta(seconds=3)
        span = max(1.0, (end_time - start_time).total_seconds())
        values = [value for _, value in actual] + [upper for _, _, _, upper in forecast]
        max_y = _nice_axis_max(max(values, default=0.001))

        painter.setFont(QFont("Segoe UI", 8))
        decimals = 3 if max_y < 0.1 else 2 if max_y < 1 else 1
        for step in range(6):
            ratio = step / 5
            y = chart.bottom() - chart.height() * ratio
            value = max_y * ratio
            painter.setPen(QPen(QColor("#24204A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(0, y - 8, 48, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{value:.{decimals}f}")

        def x_at(moment: datetime) -> float:
            return chart.left() + chart.width() * max(0.0, min(1.0, (moment - start_time).total_seconds() / span))

        def y_at(value: float) -> float:
            return chart.bottom() - chart.height() * max(0.0, min(1.0, value / max_y))

        for index in range(6):
            moment = start_time + timedelta(seconds=span * index / 5)
            x = chart.left() + chart.width() * index / 5
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(x - 30, chart.bottom() + 6, 60, 16), Qt.AlignmentFlag.AlignCenter, moment.strftime("%H:%M:%S"))

        divider_x = x_at(divider_time)
        painter.fillRect(QRectF(divider_x, chart.top(), chart.right() - divider_x, chart.height()), QColor(108, 93, 211, 14))
        painter.setPen(QPen(QColor("#8B5CF6"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(divider_x, chart.top()), QPointF(divider_x, chart.bottom()))
        pill = QRectF(divider_x - 47, chart.top() + 2, 94, 19)
        painter.setBrush(QColor("#1E1B40"))
        painter.setPen(QPen(QColor("#8B5CF6"), 1))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setPen(QColor("#C4B5FD"))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, f"{divider_time:%H:%M:%S} hiện tại")

        visible_actual = [(moment, value) for moment, value in actual if moment >= start_time]
        if visible_actual:
            points = [QPointF(x_at(moment), y_at(value)) for moment, value in visible_actual]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.setPen(QPen(QColor("#3B82F6"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(path)

        if forecast:
            upper = [QPointF(x_at(moment), y_at(high)) for moment, _value, _low, high in forecast]
            lower = [QPointF(x_at(moment), y_at(low)) for moment, _value, low, _high in forecast]
            band = QPainterPath(upper[0])
            for point in upper[1:]:
                band.lineTo(point)
            for point in reversed(lower):
                band.lineTo(point)
            band.closeSubpath()
            painter.fillPath(band, QColor(139, 92, 246, 50))
            painter.setPen(QPen(QColor(139, 92, 246, 110), 1, Qt.PenStyle.DashLine))
            painter.drawPath(band)

            points = [QPointF(x_at(moment), y_at(value)) for moment, value, _low, _high in forecast]
            path = QPainterPath(QPointF(divider_x, y_at(actual[-1][1] if actual else forecast[0][1])))
            for point in points:
                path.lineTo(point)
            painter.setPen(QPen(QColor("#FF5B79"), 2.2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(path)
            tip = points[-1]
            painter.setBrush(QColor("#FF5B79"))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawEllipse(tip, 4, 4)
            badge = QRectF(max(chart.left(), tip.x() - 92), max(chart.top() + 22, tip.y() - 24), 90, 18)
            painter.setBrush(QColor("#251D42"))
            painter.setPen(QPen(QColor("#FF5B79"), 1))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, f"{forecast[-1][1]:.3f} Mbps")


class MatchedComparisonChart(QWidget):
    """Compare forecasts only after the matching actual timestamp arrives."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pending: dict[int, float] = {}
        self.pairs: list[tuple[datetime, float, float]] = []
        self.setMinimumHeight(165)

    def set_forecast(self, rows: list[dict]) -> None:
        for row in rows:
            self.pending[round(_parse_timestamp(row.get("timestamp")).timestamp())] = max(0.0, float(row.get("mbps", 0)))
        if len(self.pending) > 60:
            self.pending = dict(sorted(self.pending.items())[-60:])

    def append_actual(self, value: float, timestamp: object = None) -> None:
        moment = _parse_timestamp(timestamp)
        key = round(moment.timestamp())
        candidates = [candidate for candidate in self.pending if abs(candidate - key) <= 1]
        if candidates:
            matched = min(candidates, key=lambda candidate: abs(candidate - key))
            predicted = self.pending.pop(matched)
            self.pairs.append((moment, max(0.0, float(value)), predicted))
            self.pairs = self.pairs[-18:]
            self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(46, 10, self.width() - 58, self.height() - 34)
        if chart.width() <= 20 or chart.height() <= 20:
            return
        if not self.pairs:
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(chart, Qt.AlignmentFlag.AlignCenter, "Đang chờ actual tại đúng thời điểm dự báo…")
            return
        maximum = _nice_axis_max(max(max(actual, predicted) for _time, actual, predicted in self.pairs))
        for step in range(5):
            ratio = step / 4
            y = chart.bottom() - chart.height() * ratio
            painter.setPen(QPen(QColor("#24204A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(0, y - 8, 40, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{maximum * ratio:.3f}")
        count = len(self.pairs)
        actual_points = []
        predicted_points = []
        for index, (_time, actual, predicted) in enumerate(self.pairs):
            x = chart.left() + chart.width() * (index / max(1, count - 1))
            actual_points.append(QPointF(x, chart.bottom() - chart.height() * actual / maximum))
            predicted_points.append(QPointF(x, chart.bottom() - chart.height() * predicted / maximum))
        for points, color, style in (
            (actual_points, QColor("#3B82F6"), Qt.PenStyle.SolidLine),
            (predicted_points, QColor("#C084FC"), Qt.PenStyle.DashLine),
        ):
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.setPen(QPen(color, 2, style))
            painter.drawPath(path)
        for index in range(min(5, count)):
            pair_index = round(index * (count - 1) / max(1, min(5, count) - 1))
            x = chart.left() + chart.width() * pair_index / max(1, count - 1)
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(x - 25, chart.bottom() + 5, 50, 16), Qt.AlignmentFlag.AlignCenter, self.pairs[pair_index][0].strftime("%H:%M:%S"))


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
        sub = QLabel("Hai target thật của model & hiệu năng test")
        sub.setStyleSheet("color: #8E8BA7; font-size: 10.5px;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box, 1)

        badge = QLabel("● Chưa kết nối mô hình")
        self.badge = badge
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.16); "
            "border: 1px solid rgba(139, 92, 246, 0.32); border-radius: 6px; "
            "padding: 2px 7px; font-size: 10.5px; font-weight: 700;"
        )
        header.addWidget(badge)
        layout.addLayout(header)

        # 3 Rich Metric Rows
        self.value_labels: list[QLabel] = []
        self.delta_labels: list[QLabel] = []
        self.bars: list[QProgressBar] = []
        for icon_name, color, label_text, value, delta, pct in [
            ("arrow_down", "#3B82F6", "Throughput tổng dự báo", "—", "Chưa có", 0),
            ("arrow_up", "#10B981", "Packet rate dự báo", "—", "Chưa có", 0),
            ("warning", "#8B5CF6", "Mức rủi ro p95/p99", "—", "Chưa có", 0),
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
            self.value_labels.append(val)
            val.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 700; letter-spacing: -0.3px;")
            val_lay.addWidget(val)

            d_lbl = QLabel(delta)
            self.delta_labels.append(d_lbl)
            d_lbl.setStyleSheet(f"color: {color}; font-size: 10.5px; font-weight: 600;")
            val_lay.addWidget(d_lbl)
            val_lay.addStretch()
            info.addLayout(val_lay)

            # Mini progress bar
            bar = QProgressBar()
            self.bars.append(bar)
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

        self.evaluation_labels: list[QLabel] = []
        for label, val in [("RMSE", "—"), ("MAE", "—"), ("R² Score", "—")]:
            item = QVBoxLayout()
            item.setSpacing(1)
            item.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet("color: #7E7A9C; font-size: 9.5px; font-weight: 500;")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v = QLabel(val)
            self.evaluation_labels.append(v)
            v.setStyleSheet("color: #10B981; font-size: 11.5px; font-weight: 700;")
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item.addWidget(l)
            item.addWidget(v)
            eval_lay.addLayout(item)

        layout.addWidget(eval_box)
        layout.addStretch()

    def update_forecast(self, payload: dict, mbps: float, packets_per_second: float, risk: str) -> None:
        version = str(payload.get("model_version", "traffic-forecast"))
        horizon = int(payload.get("horizon", 0))
        self.badge.setText(f"● {version}")
        self.value_labels[0].setText(f"{mbps:.3f} Mbps")
        self.value_labels[1].setText(f"{packets_per_second:.1f} packet/s")
        self.value_labels[2].setText(risk)
        for label in self.delta_labels:
            label.setText(f"AI +{horizon}s")
        thresholds = payload.get("risk_thresholds", {})
        bytes_p99 = float(thresholds.get("bytes_per_second", {}).get("p99", 0) or 0)
        pps_p99 = float(thresholds.get("packets_per_second", {}).get("p99", 0) or 0)
        self.bars[0].setValue(min(100, round((mbps * 1_000_000 / 8) * 100 / bytes_p99)) if bytes_p99 else 0)
        self.bars[1].setValue(min(100, round(packets_per_second * 100 / pps_p99)) if pps_p99 else 0)
        self.bars[2].setValue({"LOW": 20, "MEDIUM": 60, "HIGH": 100}.get(risk, 0))
        metrics = payload.get("evaluation_metrics", {}).get("packets_per_second", {}).get("random_forest", {})
        self.evaluation_labels[0].setText(f"{float(metrics.get('rmse', 0)):.2f} pps")
        self.evaluation_labels[1].setText(f"{float(metrics.get('mae', 0)):.2f} pps")
        self.evaluation_labels[2].setText(f"{float(metrics.get('r2', 0)):.3f}")
        byte_metrics = payload.get("evaluation_metrics", {}).get("bytes_per_second", {}).get("random_forest", {})
        tooltip = (
            f"Bytes/s model — RMSE {float(byte_metrics.get('rmse', 0)):,.0f} B/s · "
            f"MAE {float(byte_metrics.get('mae', 0)):,.0f} B/s · R² {float(byte_metrics.get('r2', 0)):.3f}"
        )
        for label in self.evaluation_labels:
            label.setToolTip(tooltip)


class PredictionPage(QScrollArea):
    """Modern AI Traffic Prediction page adhering to the Midnight Indigo SOC design system."""

    def __init__(
        self,
        parent: QWidget | None = None,
        live_service: LiveDetectionService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.collector = NetworkMetricsCollector()
        self._last_snapshot: NetworkSnapshot | None = None
        self.live_service = live_service
        self.ai_client = AiClient(timeout=10.0)
        self.thread_pool = QThreadPool.globalInstance()
        self._forecast_running = False
        self.forecast_horizon = 3
        self.refresh_interval_ms = 2_000
        self._last_history_timestamp = ""
        self._alert_rows: list[list[str]] = []

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
            "Random Forest Forecasting • Dữ liệu flow live từ Mininet • 1 giây mỗi bước"
        )
        subtitle.setObjectName("predictionSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #8E8BA7; font-size: 11.5px; font-weight: 400;")
        intro.addWidget(subtitle)
        header.addLayout(intro, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        ai_badge = QLabel("●  ĐANG CHỜ FLOW MININET")
        self.ai_badge = ai_badge
        ai_badge.setObjectName("liveBadge")
        ai_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: 700;"
        )
        controls.addWidget(ai_badge)

        self.date_button = QPushButton("  3 giây tới  ˅")
        self.date_button.setObjectName("dateRangeButton")
        self.date_button.setIcon(icon("clock", "#AFC7E4", 13))
        self.date_button.setFixedHeight(34)
        horizon_menu = QMenu(self.date_button)
        for seconds in (3, 5, 10):
            action = horizon_menu.addAction(f"{seconds} giây tới")
            action.triggered.connect(lambda _checked=False, value=seconds: self._set_horizon(value))
        self.date_button.setMenu(horizon_menu)
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
            MonitorMetric("Dự đoán throughput", "—", "+3 giây", "#8B5CF6", "trend"),
            MonitorMetric("Packet rate hiện tại", "—", "Live", "#10B981", "database"),
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
        chart_extra_lay.addWidget(legend_chip("#8B5CF6", "Sai số 95% thực nghiệm"))

        forecast_panel = Panel(
            "Dự đoán lưu lượng (Forecasting)",
            "Random Forest học từ telemetry thật của các phiên Mininet",
            chart_extra,
        )
        self.forecast_chart = AdaptiveForecastChart()
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
            "Chỉ ghép forecast với actual tại cùng timestamp",
            compare_extra,
        )
        self.compare_chart = MatchedComparisonChart()
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
        self.live_timer.start(self.refresh_interval_ms)
        self.refresh_current_data()

    def _trend_table_panel(self) -> Panel:
        badge = QLabel("0 mốc")
        self.trend_badge = badge
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Xu hướng ngắn hạn",
            "Hai target model dự báo theo từng giây và mức rủi ro tương ứng",
            badge,
        )

        headers = ["Thời điểm", "Throughput", "Packet rate", "Rủi ro", "Tăng trưởng"]
        rows: list[list[str]] = []

        table = QTableWidget(len(rows), len(headers))
        self.trend_table = table
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
        table.setColumnWidth(3, 82)   # Rủi ro
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
        self.alert_badge = badge
        badge.setStyleSheet(
            "color: #FF5B79; background: rgba(255, 91, 121, 0.15); "
            "border: 1px solid rgba(255, 91, 121, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel(
            "Cảnh báo dự đoán sớm",
            "Mô hình AI cảnh báo trước khi throughput hoặc packet rate vượt p95/p99 của tập train",
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

        panel.box.addWidget(table)
        return panel

    def _settings_panel(self) -> Panel:
        badge = QLabel("Cấu hình")
        badge.setStyleSheet(
            "color: #C4B5FD; background: rgba(139, 92, 246, 0.15); "
            "border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        panel = Panel("Thiết lập tham số AI", "Mô hình lab và khoảng dự báo ngắn hạn", badge)

        form_box = QVBoxLayout()
        form_box.setSpacing(9)

        combo_specs = [
            ("Mô hình AI:", "model_combo", [("Random Forest (Mininet lab)", "random_forest")]),
            ("Khoảng dự đoán:", "horizon_combo", [("3 giây tới", 3), ("5 giây tới", 5), ("10 giây tới", 10)]),
            ("Chu kỳ cập nhật:", "interval_combo", [("Tự động 2 giây", 2_000), ("5 giây", 5_000), ("10 giây", 10_000)]),
            ("Độ nhạy:", "sensitivity_combo", [("Theo p95/p99 của train", "train_thresholds")]),
        ]
        for label_text, attribute, values in combo_specs:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(label_text)
            label.setObjectName("settingLabel")
            label.setStyleSheet("color: #9E9BB5; font-size: 11px; font-weight: 600; min-width: 100px;")
            row.addWidget(label)

            combo = QComboBox()
            combo.setObjectName("predictionCombo")
            for text_value, data_value in values:
                combo.addItem(text_value, data_value)
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
            setattr(self, attribute, combo)
            row.addWidget(combo, 1)
            form_box.addLayout(row)

        self.model_combo.setEnabled(False)
        self.sensitivity_combo.setEnabled(False)
        self.horizon_combo.currentIndexChanged.connect(
            lambda index: self._set_horizon(int(self.horizon_combo.itemData(index)))
        )
        self.interval_combo.currentIndexChanged.connect(
            lambda index: self._set_refresh_interval(int(self.interval_combo.itemData(index)))
        )

        panel.box.addLayout(form_box)

        self.start_button = QPushButton("  Chờ đủ dữ liệu Mininet")
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
        history = self.live_service.traffic_history() if self.live_service is not None else []
        if history:
            latest = history[-1]
            total_mbps = float(latest["bytes_per_second"]) * 8 / 1_000_000
            packets_per_second = float(latest["packets_per_second"])
            self.metric_cards[0].set_data(f"{total_mbps:.3f} Mbps", "Mininet live", total_mbps)
            self.metric_cards[2].set_data(f"{packets_per_second:.1f} pps", "Mininet live", packets_per_second)
            new_points = history
            if self._last_history_timestamp:
                new_points = [
                    point for point in history
                    if str(point.get("timestamp", "")) > self._last_history_timestamp
                ]
            for point in new_points:
                point_mbps = float(point.get("bytes_per_second", 0)) * 8 / 1_000_000
                timestamp = point.get("timestamp")
                self.forecast_chart.append_actual(point_mbps, timestamp)
                self.compare_chart.append_actual(point_mbps, timestamp)
            self._last_history_timestamp = str(latest.get("timestamp", self._last_history_timestamp))
            enough_history = len(history) >= 4
            self.start_button.setEnabled(enough_history and not self._forecast_running)
            self.start_button.setText("  Chạy dự báo AI" if enough_history else "  Chờ đủ 4 mốc Mininet")
            if enough_history and not self._forecast_running:
                self.start_prediction()
            return

        snapshot = self.collector.sample()
        self._last_snapshot = snapshot
        if snapshot.available:
            total_mbps = snapshot.incoming_mbps + snapshot.outgoing_mbps
            self.metric_cards[0].set_data(f"{total_mbps:.2f} Mbps", "Máy local", total_mbps)
            self.metric_cards[2].set_data("—", "Chỉ có trên Mininet", 0)
            now = datetime.now().astimezone()
            self.forecast_chart.append_actual(total_mbps, now)
            self.compare_chart.append_actual(total_mbps, now)
        else:
            for card in self.metric_cards:
                card.set_data("—", "Offline", 0.0)

    def refresh_all_predictions(self) -> None:
        self.refresh_current_data()
        if not self._forecast_running:
            self.start_prediction()

    def start_prediction(self) -> None:
        if self.live_service is None or self._forecast_running:
            return
        history = self.live_service.traffic_history()
        if len(history) < 4:
            self.start_button.setText("  Chờ đủ 4 mốc Mininet")
            self.start_button.setEnabled(False)
            return
        self._forecast_running = True
        self.start_button.setEnabled(False)
        self.start_button.setText("  AI đang dự báo...")
        worker = ForecastWorker(self.ai_client, history, horizon=self.forecast_horizon)
        worker.signals.completed.connect(self._forecast_completed)
        worker.signals.failed.connect(self._forecast_failed)
        self.thread_pool.start(worker)

    def _forecast_completed(self, result: object) -> None:
        self._forecast_running = False
        payload = result if isinstance(result, dict) else {}
        rows = payload.get("forecast", [])
        if not rows:
            self._forecast_failed("AI không trả điểm dự báo")
            return
        chart_rows: list[dict] = []
        for row in rows:
            point = dict(row)
            point["mbps"] = float(row.get("bytes_per_second", 0)) * 8 / 1_000_000
            point["lower_mbps"] = float(row.get("bytes_per_second_lower", row.get("bytes_per_second", 0))) * 8 / 1_000_000
            point["upper_mbps"] = float(row.get("bytes_per_second_upper", row.get("bytes_per_second", 0))) * 8 / 1_000_000
            chart_rows.append(point)
        mbps = [float(row["mbps"]) for row in chart_rows]
        packets = [float(row.get("packets_per_second", 0)) for row in chart_rows]
        risk = str(payload.get("risk_level", "LOW"))
        self.forecast_chart.set_forecast(chart_rows)
        self.compare_chart.set_forecast(chart_rows)
        horizon = int(payload.get("horizon", self.forecast_horizon))
        self.metric_cards[1].set_data(f"{mbps[-1]:.3f} Mbps", f"AI +{horizon} giây", mbps[-1])
        self.metric_cards[3].set_data(risk, "p95/p99 train", {"LOW": 20, "MEDIUM": 60, "HIGH": 100}.get(risk, 0))
        warning = int(risk in {"MEDIUM", "HIGH"})
        self.metric_cards[4].set_data(str(warning), "Dự báo sớm", warning * 100)
        self.summary_card.update_forecast(payload, mbps[-1], packets[-1], risk)
        model_version = str(payload.get("model_version", "traffic-forecast"))
        self.ai_badge.setText(f"●  AI ONLINE • {model_version}")
        self.start_button.setText("  Chạy dự báo lại")
        self.start_button.setEnabled(True)
        self._update_trend_table(chart_rows, payload)
        self._update_alerts(chart_rows, payload)

    def _forecast_failed(self, message: str) -> None:
        self._forecast_running = False
        self.ai_badge.setText("●  AI CHƯA ĐỦ DỮ LIỆU")
        self.start_button.setText(f"  {message[:48]}")
        self.start_button.setEnabled(True)

    def _update_trend_table(self, rows: list[dict], payload: dict) -> None:
        self.trend_badge.setText(f"{len(rows)} mốc")
        self.trend_table.setRowCount(len(rows))
        previous = None
        for row_index, row in enumerate(rows):
            timestamp = str(row.get("timestamp", ""))[11:19]
            mbps = float(row.get("mbps", 0))
            pps = float(row.get("packets_per_second", 0))
            growth = 0.0 if previous in (None, 0) else (mbps - previous) * 100 / previous
            previous = mbps
            point_risk = self._risk_for_row(row, payload)
            values = [timestamp, f"{mbps:.3f} Mbps", f"{pps:.1f} pps", point_risk, f"{growth:+.1f}%"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    item.setForeground(QColor({"LOW": "#34D399", "MEDIUM": "#FBBF24", "HIGH": "#FF5B79"}.get(value, "#FFFFFF")))
                self.trend_table.setItem(row_index, column, item)
            self.trend_table.setRowHeight(row_index, 34)

    @staticmethod
    def _risk_for_row(row: dict, payload: dict) -> str:
        model_risk = str(row.get("risk_level", "")).upper()
        if model_risk in {"LOW", "MEDIUM", "HIGH"}:
            return model_risk
        thresholds = payload.get("risk_thresholds", {})
        values = {
            "bytes_per_second": float(row.get("bytes_per_second", 0)),
            "packets_per_second": float(row.get("packets_per_second", 0)),
        }
        level = "LOW"
        for target, value in values.items():
            target_thresholds = thresholds.get(target, {})
            p95 = float(target_thresholds.get("p95", 0) or 0)
            p99 = float(target_thresholds.get("p99", 0) or 0)
            if p99 and value >= p99:
                return "HIGH"
            if p95 and value >= p95:
                level = "MEDIUM"
        return level

    def _update_alerts(self, rows: list[dict], payload: dict) -> None:
        risky = [(row, self._risk_for_row(row, payload)) for row in rows]
        risky = [(row, risk) for row, risk in risky if risk in {"MEDIUM", "HIGH"}]
        if risky:
            row, risk = max(risky, key=lambda item: {"MEDIUM": 1, "HIGH": 2}[item[1]])
            thresholds = payload.get("risk_thresholds", {})
            threshold_name = "p99" if risk == "HIGH" else "p95"
            candidates = []
            for target in ("bytes_per_second", "packets_per_second"):
                threshold = float(thresholds.get(target, {}).get(threshold_name, 0) or 0)
                value = float(row.get(target, 0) or 0)
                candidates.append((value / threshold if threshold else 0, target, value, threshold))
            _ratio, target, value, threshold = max(candidates)
            if target == "bytes_per_second":
                alert_type = f"Throughput vượt {threshold_name}"
                value_text = f"{value * 8 / 1_000_000:.3f} Mbps"
                threshold_text = f"{threshold * 8 / 1_000_000:.3f} Mbps"
            else:
                alert_type = f"Packet rate vượt {threshold_name}"
                value_text = f"{value:.1f} pps"
                threshold_text = f"{threshold:.1f} pps"
            timestamp = str(row.get("timestamp", ""))[11:19]
            new_alert = [
                timestamp,
                alert_type,
                value_text,
                threshold_text,
                "Cao" if risk == "HIGH" else "Trung bình",
                "Đang theo dõi",
                "Xem IPS",
            ]
            if not self._alert_rows or self._alert_rows[0][:2] != new_alert[:2]:
                self._alert_rows.insert(0, new_alert)
                self._alert_rows = self._alert_rows[:5]
        self.alert_badge.setText(f"{len(self._alert_rows)} cảnh báo")
        self.alert_table.setRowCount(len(self._alert_rows))
        severity_colors = {
            "Cao": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Trung bình": ("rgba(251, 191, 36, 0.18)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
        }
        for index, alert in enumerate(self._alert_rows):
            self.alert_table.setRowHeight(index, 36)
            for column in (0, 1, 2, 3, 6):
                color = "#FF8A4C" if column == 2 else "#FFFFFF" if column == 1 else "#9E9BB5"
                self.alert_table.setCellWidget(index, column, make_text_cell(alert[column], color=color, align_center=column in (0, 6)))
            bg, fg, border = severity_colors[alert[4]]
            self.alert_table.setCellWidget(index, 4, make_badge_cell(alert[4], bg, fg, border))
            self.alert_table.setCellWidget(index, 5, make_badge_cell(alert[5], "rgba(56, 189, 248, 0.18)", "#38BDF8", "rgba(56, 189, 248, 0.35)"))

    def _set_horizon(self, seconds: int) -> None:
        self.forecast_horizon = max(1, int(seconds))
        self.date_button.setText(f"  {self.forecast_horizon} giây tới")
        if hasattr(self, "horizon_combo"):
            index = self.horizon_combo.findData(self.forecast_horizon)
            if index >= 0 and index != self.horizon_combo.currentIndex():
                self.horizon_combo.blockSignals(True)
                self.horizon_combo.setCurrentIndex(index)
                self.horizon_combo.blockSignals(False)

    def _set_refresh_interval(self, milliseconds: int) -> None:
        self.refresh_interval_ms = max(500, int(milliseconds))
        if hasattr(self, "live_timer"):
            self.live_timer.setInterval(self.refresh_interval_ms)

    def _prediction_finished(self) -> None:
        self.start_button.setText("  Chạy dự báo AI")
        self.start_button.setEnabled(True)
