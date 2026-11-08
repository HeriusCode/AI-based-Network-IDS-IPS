"""Dashboard overview for the desktop IDS/IPS demo."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QDateTime, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.network_metrics import NetworkMetricsCollector, NetworkSnapshot
from app.ui.icons import icon


@dataclass(frozen=True)
class Metric:
    title: str
    value: str
    change: str
    color: str
    icon_name: str


class Sparkline(QWidget):
    def __init__(self, values: list[int], color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values = values
        self.color = QColor(color)
        self.setFixedHeight(20)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        count = len(self.values)
        if count == 0:
            return
        gap = 2.0
        width = max(2.0, (self.width() - gap * (count - 1)) / count)
        maximum = max(1.0, max(self.values))
        for index, value in enumerate(self.values):
            height = (value / maximum) * (self.height() - 2)
            rect = QRectF(index * (width + gap), self.height() - height, width, height)
            painter.setBrush(self.color)
            painter.drawRoundedRect(rect, 1.0, 1.0)

    def append_value(self, value: float) -> None:
        self.values = [*self.values[-11:], max(0.0, value)]
        self.update()


class MetricCard(QFrame):
    """Clean, balanced KPI card with subtle icon and prominent bold white digits."""

    def __init__(self, metric: Metric, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("subMetricCard")
        self.setFixedHeight(74)
        self.setMinimumWidth(125)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)

        # 1. Color-coded icon container for fast KPI recognition.
        badge = QLabel()
        badge.setObjectName("metricIcon")
        accent = QColor(metric.color)
        red, green, blue = accent.red(), accent.green(), accent.blue()
        badge.setStyleSheet(
            f"background: rgba({red}, {green}, {blue}, 0.16); "
            f"border: 1px solid rgba({red}, {green}, {blue}, 0.38); border-radius: 9px;"
        )
        badge.setPixmap(icon(metric.icon_name, metric.color, 17).pixmap(17, 17))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(32, 32)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Center: Title + Prominent Bold White Digits
        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(1)
        center.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = QLabel(metric.title)
        title.setObjectName("metricTitle")
        title.setStyleSheet("color: #9E9BB5; font-size: 11px; font-weight: 500;")
        center.addWidget(title)

        self.value_label = QLabel(metric.value)
        self.value_label.setObjectName("metricValue")
        self.value_label.setStyleSheet("color: #FFFFFF; font-size: 17px; font-weight: 700; letter-spacing: -0.3px;")
        center.addWidget(self.value_label)

        layout.addLayout(center, 1)

        # 3. Right: Trend pill on top + Sparkline below
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.change_label = QLabel(metric.change)
        self.change_label.setObjectName("metricChange")
        self.change_label.setStyleSheet(
            f"color: {metric.color}; background: rgba(255, 255, 255, 0.06); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 600;"
        )
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.change_label, 0, Qt.AlignmentFlag.AlignRight)

        self.sparkline = Sparkline([0.0] * 12, metric.color)
        self.sparkline.setFixedSize(42, 16)
        right.addWidget(self.sparkline, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)

    def set_data(self, value: str, change: str, spark_value: float) -> None:
        self.value_label.setText(value)
        self.change_label.setText(change)
        self.sparkline.append_value(spark_value)


class SystemCard(QFrame):
    """System health card matching the balanced layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("subMetricCard")
        self.setFixedHeight(74)
        self.setMinimumWidth(125)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)

        badge = QLabel()
        badge.setObjectName("metricIcon")
        badge.setStyleSheet(
            "background: rgba(59, 130, 246, 0.16); "
            "border: 1px solid rgba(59, 130, 246, 0.38); border-radius: 9px;"
        )
        badge.setPixmap(icon("shield", "#3B82F6", 17).pixmap(17, 17))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(32, 32)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(1)
        center.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("Trạng thái hệ thống")
        title.setObjectName("metricTitle")
        title.setStyleSheet("color: #9E9BB5; font-size: 11px; font-weight: 500;")
        center.addWidget(title)

        val_lbl = QLabel("Hoạt động tốt")
        val_lbl.setObjectName("systemGood")
        val_lbl.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 700;")
        center.addWidget(val_lbl)
        self.value_label = val_lbl

        layout.addLayout(center, 1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        pill = QLabel("● Live")
        pill.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 700;"
        )
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(pill, 0, Qt.AlignmentFlag.AlignRight)
        self.state_label = pill

        progress = QProgressBar()
        progress.setObjectName("healthProgress")
        progress.setRange(0, 100)
        progress.setValue(100)
        progress.setTextVisible(False)
        progress.setFixedSize(42, 5)
        right.addWidget(progress, 0, Qt.AlignmentFlag.AlignRight)
        self.progress = progress

        layout.addLayout(right)

    def set_available(self, available: bool) -> None:
        self.value_label.setText("Đang hoạt động" if available else "Không có dữ liệu")
        self.state_label.setText("● Live" if available else "● Offline")
        color = "#10B981" if available else "#FF5B79"
        self.state_label.setStyleSheet(
            f"color: {color}; background: rgba(255, 255, 255, 0.06); "
            "border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 700;"
        )
        self.progress.setValue(100 if available else 0)


class TrafficRangeCombo(QComboBox):
    """Time-range selector with a consistently visible down chevron."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#8EAED2"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center_x = self.width() - 17
        center_y = self.height() / 2
        painter.drawLine(QPointF(center_x - 4, center_y - 2), QPointF(center_x, center_y + 2))
        painter.drawLine(QPointF(center_x, center_y + 2), QPointF(center_x + 4, center_y - 2))


class TrafficChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history_seconds = 600
        self.window_seconds = 600
        self.incoming: list[float] = [0.0] * self.history_seconds
        self.outgoing: list[float] = [0.0] * self.history_seconds
        self.setMinimumHeight(280)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        left, top, right, bottom = 42, 28, 14, 24
        chart = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)
        visible_incoming = self.incoming[-self.window_seconds:]
        visible_outgoing = self.outgoing[-self.window_seconds:]
        raw_maximum = max([1.0, *visible_incoming, *visible_outgoing])
        maximum = max(1.0, math.ceil(raw_maximum / 10.0) * 10.0) if raw_maximum > 10 else max(1.0, math.ceil(raw_maximum * 2) / 2)

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#8E8BA7"))
        painter.drawText(QRectF(0, 2, left - 5, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "Mbps")
        for step in range(7):
            y = chart.bottom() - chart.height() * step / 6
            painter.setPen(QColor("#8E8BA7"))
            tick = maximum * step / 6
            tick_text = f"{tick:.1f}" if maximum < 10 else str(int(tick))
            painter.drawText(QRectF(0, y - 8, left - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, tick_text)
            painter.setPen(QPen(QColor("#282452"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

        now = QDateTime.currentDateTime()
        time_labels = [
            now.addSecs(-self.window_seconds + round(self.window_seconds * index / 5)).toString("HH:mm")
            for index in range(6)
        ]
        painter.setPen(QColor("#8E8BA7"))
        for step, label in enumerate(time_labels):
            x = chart.left() + chart.width() * step / (len(time_labels) - 1)
            if step == 0:
                label_rect = QRectF(x + 2, chart.bottom() + 5, 48, 16)
                alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            elif step == len(time_labels) - 1:
                label_rect = QRectF(x - 50, chart.bottom() + 5, 48, 16)
                alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            else:
                label_rect = QRectF(x - 24, chart.bottom() + 5, 48, 16)
                alignment = Qt.AlignmentFlag.AlignCenter
            painter.drawText(label_rect, alignment, label)
            painter.setPen(QPen(QColor("#282452"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(x, chart.top()), QPointF(x, chart.bottom()))
            painter.setPen(QColor("#8E8BA7"))

        self._draw_series(painter, chart, visible_outgoing, maximum, QColor("#10B981"), fill_alpha=65)
        self._draw_series(painter, chart, visible_incoming, maximum, QColor("#2F9BFF"), fill_alpha=45)

    @staticmethod
    def _draw_series(painter: QPainter, chart: QRectF, values: list[float], maximum: float, color: QColor, fill_alpha: int = 50) -> None:
        count = len(values)
        if count < 2:
            return
        points = [
            QPointF(chart.left() + chart.width() * i / (count - 1), chart.bottom() - chart.height() * value / maximum)
            for i, value in enumerate(values)
        ]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)

        area = QPainterPath(path)
        area.lineTo(chart.right(), chart.bottom())
        area.lineTo(chart.left(), chart.bottom())
        area.closeSubpath()

        gradient = QLinearGradient(0, chart.top(), 0, chart.bottom())
        gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), fill_alpha))
        gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 2))
        painter.fillPath(area, gradient)

        painter.setPen(QPen(color, 2.2))
        painter.drawPath(path)

    def append_sample(self, incoming_mbps: float, outgoing_mbps: float) -> None:
        self.incoming = [*self.incoming[-(self.history_seconds - 1):], max(0.0, incoming_mbps)]
        self.outgoing = [*self.outgoing[-(self.history_seconds - 1):], max(0.0, outgoing_mbps)]
        self.update()

    def set_window_seconds(self, seconds: int) -> None:
        self.window_seconds = max(60, min(self.history_seconds, seconds))
        self.update()


class DonutChart(QWidget):
    def __init__(self, segments: list[tuple[float, str]], center_top: str, center_value: str, center_bottom: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.segments = segments
        self.center_top = center_top
        self.center_value = center_value
        self.center_bottom = center_bottom
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, segments: list[tuple[float, str]], center_value: str, center_bottom: str | None = None) -> None:
        self.segments = segments
        self.center_value = center_value
        if center_bottom is not None:
            self.center_bottom = center_bottom
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 14
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        pen_width = max(14, int(side * 0.16))
        adjusted_rect = rect.adjusted(pen_width / 2, pen_width / 2, -pen_width / 2, -pen_width / 2)

        # Background track ring
        painter.setPen(QPen(QColor("#24204A"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(adjusted_rect, 0, 360 * 16)

        start = 90 * 16
        for percent, color in self.segments:
            painter.setPen(QPen(QColor(color), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            span = -percent * 360 * 16 / 100
            painter.drawArc(adjusted_rect, int(start), int(span))
            start += span

        center = rect.center()
        val_pt = max(11, int(side * 0.088))
        sub_pt = max(8, int(side * 0.062))

        val_font = QFont("Segoe UI", val_pt)
        val_font.setWeight(QFont.Weight.Bold)
        sub_font = QFont("Segoe UI", sub_pt)

        val_fm = QFontMetrics(val_font)
        sub_fm = QFontMetrics(sub_font)

        val_h = val_fm.height()
        sub_h = sub_fm.height()
        gap = 2

        if self.center_top and self.center_bottom:
            total_h = sub_h + gap + val_h + gap + sub_h
            start_y = center.y() - total_h / 2

            painter.setPen(QColor("#8E8BA7"))
            painter.setFont(sub_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y, side, sub_h), Qt.AlignmentFlag.AlignCenter, self.center_top)

            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(val_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y + sub_h + gap, side, val_h), Qt.AlignmentFlag.AlignCenter, self.center_value)

            painter.setPen(QColor("#8E8BA7"))
            painter.setFont(sub_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y + sub_h + gap + val_h + gap, side, sub_h), Qt.AlignmentFlag.AlignCenter, self.center_bottom)

        elif self.center_bottom:
            total_h = val_h + gap + sub_h
            start_y = center.y() - total_h / 2

            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(val_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y, side, val_h), Qt.AlignmentFlag.AlignCenter, self.center_value)

            painter.setPen(QColor("#8E8BA7"))
            painter.setFont(sub_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y + val_h + gap, side, sub_h), Qt.AlignmentFlag.AlignCenter, self.center_bottom)

        elif self.center_top:
            total_h = sub_h + gap + val_h
            start_y = center.y() - total_h / 2

            painter.setPen(QColor("#8E8BA7"))
            painter.setFont(sub_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y, side, sub_h), Qt.AlignmentFlag.AlignCenter, self.center_top)

            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(val_font)
            painter.drawText(QRectF(center.x() - side / 2, start_y + sub_h + gap, side, val_h), Qt.AlignmentFlag.AlignCenter, self.center_value)

        else:
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(val_font)
            painter.drawText(QRectF(center.x() - side / 2, center.y() - val_h / 2, side, val_h), Qt.AlignmentFlag.AlignCenter, self.center_value)


class Panel(QFrame):
    """Main card container for each dashboard block."""

    def __init__(self, title: str, subtitle: str = "", extra_header: QWidget | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardPanel")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(16, 14, 16, 16)
        self.box.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        left_box = QVBoxLayout()
        left_box.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700;")
        left_box.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("panelSubtitle")
            sub_label.setStyleSheet("color: #8E8BA7; font-size: 11px; font-weight: 400;")
            left_box.addWidget(sub_label)

        header_layout.addLayout(left_box, 1)

        if extra_header:
            header_layout.addWidget(extra_header, 0, Qt.AlignmentFlag.AlignVCenter)

        self.box.addLayout(header_layout)


def legend_row(color: str, label: str, value: str) -> QWidget:
    row = QWidget()
    row.setObjectName("legendRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background:{color}; border-radius:3px;")
    layout.addWidget(dot)
    text = QLabel(label)
    text.setObjectName("legendLabel")
    text.setStyleSheet("color: #8E8BA7; font-size: 11px;")
    layout.addWidget(text)
    layout.addStretch()
    number = QLabel(value)
    number.setObjectName("legendValue")
    number.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: 600;")
    layout.addWidget(number)
    return row


def protocol_bar_row(color: str, label: str, value: str, percent: float) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(6)

    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
    layout.addWidget(dot)

    name = QLabel(label)
    name.setObjectName("legendLabel")
    name.setFixedWidth(40)
    name.setStyleSheet("color: #CBD5E1; font-weight: 600; font-size: 11px;")
    layout.addWidget(name)

    bar = QProgressBar()
    bar.setFixedHeight(5)
    bar.setMinimumWidth(35)
    bar.setRange(0, 100)
    bar.setValue(int(percent))
    bar.setTextVisible(False)
    bar.setStyleSheet(f"""
        QProgressBar {{
            background: #25224D;
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 2px;
        }}
    """)
    layout.addWidget(bar, 1)

    val = QLabel(value)
    val.setObjectName("legendValue")
    val.setFixedWidth(38)
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 11px;")
    layout.addWidget(val)

    row.value_label = val
    row.progress_bar = bar

    return row


def ratio_stat_card(
    title: str,
    count_str: str,
    percent_str: str,
    color: str,
    percent_val: float,
    parent: QWidget | None = None,
) -> QWidget:
    accent = QColor(color)
    red, green, blue = accent.red(), accent.green(), accent.blue()
    readable_color = accent.lighter(155).name()
    card = QFrame(parent)
    card.setObjectName("ratioStatCard")
    card.setStyleSheet(f"""
        QFrame#ratioStatCard {{
            background: #14122A;
            border: 1px solid #282452;
            border-radius: 9px;
        }}
        QFrame#ratioStatCard:hover {{
            border-color: {color};
            background: #1A1738;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)

    # Dòng 1: [Chấm màu] Tên phân loại ............. [Huy hiệu %]
    top_line = QHBoxLayout()
    top_line.setContentsMargins(0, 0, 0, 0)
    top_line.setSpacing(6)

    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
    top_line.addWidget(dot)

    lbl = QLabel(title)
    lbl.setStyleSheet("color: #E2E8F0; font-size: 11px; font-weight: 600;")
    top_line.addWidget(lbl)

    top_line.addStretch(1)

    pill = QLabel(percent_str)
    pill.setStyleSheet(
        f"color: {readable_color}; font-weight: 700; font-size: 11px; "
        f"background: rgba({red}, {green}, {blue}, 0.20); "
        f"border: 1px solid rgba({red}, {green}, {blue}, 0.52); "
        f"border-radius: 4px; padding: 1px 6px;"
    )
    top_line.addWidget(pill)
    layout.addLayout(top_line)

    # Dòng 2: Số gói tin chi tiết
    mid_line = QHBoxLayout()
    mid_line.setContentsMargins(0, 0, 0, 0)
    mid_line.setSpacing(5)

    cnt = QLabel(count_str)
    cnt.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")
    mid_line.addWidget(cnt)

    unit = QLabel("gói tin")
    unit.setStyleSheet("color: #8E8BA7; font-size: 10px;")
    mid_line.addWidget(unit)

    mid_line.addStretch(1)
    layout.addLayout(mid_line)

    # Dòng 3: Thanh tiến trình mini trực quan
    bar = QProgressBar()
    bar.setFixedHeight(4)
    bar.setRange(0, 100)
    bar.setValue(int(percent_val))
    bar.setTextVisible(False)
    bar.setStyleSheet(f"""
        QProgressBar {{
            background: #232047;
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 2px;
        }}
    """)
    layout.addWidget(bar)

    card.count_label = cnt
    card.percent_label = pill
    card.progress_bar = bar
    card.accent_color = color

    return card


def make_badge_cell(text: str, bg: str, fg: str, border: str) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(2, 0, 2, 0)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 5px; padding: 3px 8px; font-weight: 700; font-size: 11px;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl)
    return w


def make_ip_progress_cell(percent_str: str) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(2, 0, 2, 0)
    lay.setSpacing(6)
    val = float(percent_str.replace("%", "").strip())
    bar = QProgressBar()
    bar.setFixedHeight(5)
    bar.setFixedWidth(36)
    bar.setRange(0, 100)
    bar.setValue(int(val))
    bar.setTextVisible(False)
    bar.setStyleSheet("""
        QProgressBar {
            background: #25224D;
            border: none;
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background: #8B5CF6;
            border-radius: 2px;
        }
    """)
    lbl = QLabel(percent_str)
    lbl.setStyleSheet("color: #E2E8F0; font-weight: 600; font-size: 11px;")
    lay.addWidget(bar)
    lay.addWidget(lbl)
    return w


def make_text_cell(text: str, color: str = "#CBD5E1", is_mono: bool = False, is_bold: bool = False, align_center: bool = False) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(6, 0, 6, 0)
    lbl = QLabel(text)
    if align_center:
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    else:
        lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    lbl.setWordWrap(False)
    font_family = "Consolas, Segoe UI Mono, monospace" if is_mono else "Segoe UI"
    font_weight = "700" if is_bold else "500"
    lbl.setStyleSheet(f"color: {color}; font-family: {font_family}; font-weight: {font_weight}; font-size: 11px;")
    lay.addWidget(lbl)
    return w


class StatusModule(QFrame):
    def __init__(self, title: str, subtitle: str, icon_name: str, meta_info: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("moduleCard")
        self.setFixedHeight(78)
        self.setMinimumWidth(140)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        badge = QLabel()
        badge.setObjectName("moduleIcon")
        badge.setPixmap(icon(icon_name, "#10B981", 20).pixmap(20, 20))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(40, 40)
        badge.setStyleSheet(
            "background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 10px;"
        )
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(1)
        copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name = QLabel(title)
        name.setObjectName("moduleTitle")
        name.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF;")
        copy.addWidget(name)

        sub = QLabel(subtitle)
        sub.setObjectName("moduleSubtitle")
        sub.setStyleSheet("font-size: 10px; color: #8E8BA7;")
        copy.addWidget(sub)

        if meta_info:
            meta = QLabel(meta_info)
            meta.setStyleSheet("color: #7E7A9C; font-size: 10px;")
            copy.addWidget(meta)

        layout.addLayout(copy, 1)

        state = QLabel("● Hoạt động")
        state.setObjectName("moduleState")
        state.setStyleSheet(
            "color: #34D399; font-weight: 600; font-size: 10px; background: rgba(52, 211, 153, 0.12); border-radius: 5px; padding: 3px 7px;"
        )
        layout.addWidget(state, 0, Qt.AlignmentFlag.AlignVCenter)


class DashboardPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.collector = NetworkMetricsCollector()
        self.setObjectName("dashboardScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("dashboardContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(14)

        # 1. Main Page Title Header
        header_box = QHBoxLayout()
        header_box.setContentsMargins(0, 0, 0, 2)
        header_box.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        heading = QLabel("Dashboard")
        heading.setObjectName("dashboardHeading")
        title_box.addWidget(heading)

        subheading = QLabel("Tổng quan hoạt động của hệ thống AI-based Network IDS/IPS  •  Dữ liệu thời gian thực")
        subheading.setObjectName("dashboardSubheading")
        title_box.addWidget(subheading)
        header_box.addLayout(title_box, 1)

        self.live_badge = QLabel("●  LIVE SYSTEM METRICS")
        self.live_badge.setObjectName("liveBadge")
        header_box.addWidget(self.live_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header_box)

        top_row = QGridLayout()
        top_row.setSpacing(12)

        # 2. Hàng trên kết hợp: Biểu đồ lưu lượng thời gian thực (phần lớn 60-65%) + Cột dọc các chỉ số & Tỷ lệ (35-40%)
        # Cột trái (phần lớn 62%): Lưu lượng mạng theo thời gian thực
        traffic_extra = QWidget()
        t_lay = QHBoxLayout(traffic_extra)
        t_lay.setContentsMargins(0, 0, 0, 0)
        self.traffic_range = TrafficRangeCombo()
        self.traffic_range.setObjectName("trafficRangeCombo")
        self.traffic_range.addItem("10 phút gần nhất", 600)
        self.traffic_range.addItem("5 phút gần nhất", 300)
        self.traffic_range.addItem("1 phút gần nhất", 60)
        self.traffic_range.setFixedWidth(155)
        t_lay.addWidget(self.traffic_range)
        self.speed_badge = QLabel("0.00 Mbps")
        self.speed_badge.setObjectName("panelChip")
        t_lay.addWidget(self.speed_badge)

        traffic_panel = Panel("Lưu lượng mạng theo thời gian thực", "", traffic_extra)
        traffic_legend = QWidget()
        traffic_legend.setMinimumWidth(0)
        traffic_legend.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        traffic_legend_layout = QHBoxLayout(traffic_legend)
        traffic_legend_layout.setContentsMargins(0, 0, 0, 0)
        traffic_legend_layout.setSpacing(24)
        traffic_legend_layout.addStretch(1)
        traffic_legend_layout.addWidget(legend_row("#2F9BFF", "Lưu lượng vào (Incoming)", ""))
        traffic_legend_layout.addWidget(legend_row("#10B981", "Lưu lượng ra (Outgoing)", ""))
        traffic_legend_layout.addStretch(1)
        traffic_panel.box.addWidget(traffic_legend)
        self.traffic_chart = TrafficChart()
        self.traffic_range.currentIndexChanged.connect(
            lambda index: self.traffic_chart.set_window_seconds(int(self.traffic_range.itemData(index)))
        )
        traffic_panel.box.addWidget(self.traffic_chart, 1)
        top_row.addWidget(traffic_panel, 0, 0)

        # Cột phải (38%): Cột dọc gom các phần trên ảnh (6 thẻ chỉ số + Tỷ lệ lưu lượng)
        # Khối 1: 6 Thẻ chỉ số cốt lõi (2 cột x 3 hàng)
        side_widget = QWidget()
        side_layout = QVBoxLayout(side_widget)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(10)

        metrics_grid = QGridLayout()
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(8)
        metrics_grid.setVerticalSpacing(8)

        data = [
            Metric("Tổng gói tin", "—", "OS", "#3B82F6", "box"),
            Metric("Lưu lượng mạng", "—", "Live", "#8B5CF6", "nodes"),
            Metric("Kết nối hoạt động", "—", "OS", "#10B981", "nodes"),
            Metric("Phát hiện bất thường", "0", "Chưa có IDS", "#FF5B79", "warning"),
            Metric("Luồng bị chặn", "0", "Chưa có IPS", "#FF8A4C", "blocked"),
        ]

        self.metric_cards = [MetricCard(metric) for metric in data]
        metrics_grid.addWidget(self.metric_cards[0], 0, 0)
        metrics_grid.addWidget(self.metric_cards[1], 0, 1)
        metrics_grid.addWidget(self.metric_cards[2], 1, 0)
        metrics_grid.addWidget(self.metric_cards[3], 1, 1)
        metrics_grid.addWidget(self.metric_cards[4], 2, 0)
        self.system_card = SystemCard()
        metrics_grid.addWidget(self.system_card, 2, 1)

        metrics_grid.setColumnStretch(0, 1)
        metrics_grid.setColumnStretch(1, 1)
        side_layout.addLayout(metrics_grid)

        # Khối 2: Tỷ lệ lưu lượng (Bố cục ngang cân đối, không còn khoảng trống thừa)
        self.ratio_badge = QLabel("Đang thu thập")
        self.ratio_badge.setObjectName("panelChip")
        self.ratio_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        ratio_panel = Panel("Tỷ lệ lưu lượng", "Chất lượng gói tin từ bộ đếm hệ điều hành", self.ratio_badge)

        ratio_body = QHBoxLayout()
        ratio_body.setContentsMargins(0, 4, 0, 0)
        ratio_body.setSpacing(12)

        self.ratio_donut = DonutChart([(100.0, "#8B5CF6"), (0.0, "#FF5B79")], "Tổng", "—", "gói tin")
        self.ratio_donut.setFixedSize(125, 125)
        ratio_body.addWidget(self.ratio_donut, 0, Qt.AlignmentFlag.AlignCenter)

        cards_col = QVBoxLayout()
        cards_col.setContentsMargins(0, 0, 0, 0)
        cards_col.setSpacing(8)
        self.normal_ratio_card = ratio_stat_card("Bình thường", "—", "—", "#8B5CF6", 0.0)
        self.error_ratio_card = ratio_stat_card("Lỗi / bị loại", "—", "—", "#FF5B79", 0.0)
        cards_col.addWidget(self.normal_ratio_card)
        cards_col.addWidget(self.error_ratio_card)
        ratio_body.addLayout(cards_col, 1)

        ratio_panel.box.addLayout(ratio_body)
        side_layout.addWidget(ratio_panel)

        top_row.addWidget(side_widget, 0, 1)
        top_row.setColumnStretch(0, 62)
        top_row.setColumnStretch(1, 38)
        root.addLayout(top_row)

        # 4. Hàng 3: Phân bố giao thức (50%) + Top 5 nguồn IP (50%)
        row3 = QGridLayout()
        row3.setSpacing(10)

        protocols_panel = Panel("Phân bố giao thức", "Tỷ trọng các giao thức truyền tải")
        proto_body = QHBoxLayout()
        proto_body.setSpacing(12)
        self.protocol_donut = DonutChart(
            [(0.0, "#2F9BFF"), (0.0, "#FF9B37"), (0.0, "#1ED28A"), (0.0, "#9551E8"), (0.0, "#F4C440"), (0.0, "#7671BF")],
            "Giao thức", "0", "kết nối"
        )
        proto_body.addWidget(self.protocol_donut, 1)
        proto_legend = QVBoxLayout()
        proto_legend.setSpacing(4)
        proto_legend.addStretch(1)
        self.protocol_specs = [
            ("TCP", "#2F9BFF"),
            ("UDP", "#FF9B37"),
            ("ICMP", "#1ED28A"),
            ("HTTP", "#9551E8"),
            ("DNS", "#F4C440"),
            ("Khác", "#7671BF"),
        ]
        self.protocol_rows = {}
        for label, color in self.protocol_specs:
            row = protocol_bar_row(color, label, "0.0%", 0.0)
            self.protocol_rows[label] = row
            proto_legend.addWidget(row)
        proto_legend.addStretch(1)
        proto_body.addLayout(proto_legend, 1)
        protocols_panel.box.addLayout(proto_body, 1)
        row3.addWidget(protocols_panel, 0, 0)

        top_ips_badge = QLabel("Top 5")
        top_ips_badge.setObjectName("panelChip")
        top_ips_panel = Panel("Top 5 IP theo kết nối", "Địa chỉ từ các kết nối mạng đang quan sát", top_ips_badge)
        self.ip_table = self._ip_table()
        top_ips_panel.box.addWidget(self.ip_table)
        row3.addWidget(top_ips_panel, 0, 1)

        row3.setColumnStretch(0, 1)
        row3.setColumnStretch(1, 1)
        root.addLayout(row3)

        # 5. Hàng 4: Bảng cảnh báo an ninh gần đây (Trải rộng Full Width)
        alerts_badge = QLabel("Real-time Log")
        alerts_badge.setObjectName("panelChip")
        alerts_panel = Panel("Cảnh báo an ninh gần đây", "Nhật ký phát hiện tấn công và hành vi khả nghi", alerts_badge)
        self.alert_table = self._alert_table()
        alerts_panel.box.addWidget(self.alert_table)
        root.addWidget(alerts_panel)

        # 6. Hàng 5: Trạng thái 4 thành phần hệ thống AI
        status_badge = QLabel("1 nguồn dữ liệu")
        status_badge.setObjectName("panelChip")
        status_panel = Panel("Trạng thái các thành phần hệ thống", "Sức khỏe hạ tầng mạng và động cơ trí tuệ nhân tạo", status_badge)
        modules = QHBoxLayout()
        modules.setSpacing(10)
        for args in [
            ("Giám sát mạng", "(Monitoring)", "activity", "Nguồn: hệ điều hành"),
            ("Phát hiện bất thường", "(Detection)", "shield", "Chưa kết nối IDS"),
            ("Dự đoán lưu lượng", "(Prediction)", "trend", "Chưa kết nối mô hình"),
            ("Giảm thiểu rủi ro", "(Mitigation)", "lock", "Chưa kết nối IPS"),
        ]:
            modules.addWidget(StatusModule(*args), 1)
        status_panel.box.addLayout(modules)
        root.addWidget(status_panel)

        self.setWidget(content)
        self.refresh_live_data()
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.refresh_live_data)
        self.live_timer.start(1000)

    def refresh_live_data(self) -> None:
        snapshot = self.collector.sample()
        self.system_card.set_available(snapshot.available)
        if not snapshot.available:
            self.live_badge.setText("●  KHÔNG CÓ DỮ LIỆU HỆ THỐNG")
            self.speed_badge.setText("— Mbps")
            return

        self.live_badge.setText("●  LIVE SYSTEM METRICS")
        total_mbps = snapshot.incoming_mbps + snapshot.outgoing_mbps
        self.speed_badge.setText(f"{total_mbps:.2f} Mbps")
        self.traffic_chart.append_sample(snapshot.incoming_mbps, snapshot.outgoing_mbps)

        previous_packets = getattr(self, "_last_total_packets", snapshot.total_packets)
        packet_delta = max(0, snapshot.total_packets - previous_packets)
        self._last_total_packets = snapshot.total_packets

        self.metric_cards[0].set_data(f"{snapshot.total_packets:,}", f"+{packet_delta:,}/s", float(packet_delta))
        self.metric_cards[1].set_data(f"{total_mbps:.2f} Mbps", "Live", total_mbps)
        self.metric_cards[2].set_data(f"{snapshot.active_connections:,}", "OS", float(snapshot.active_connections))
        self.metric_cards[3].set_data("0", "Chưa có IDS", 0.0)
        self.metric_cards[4].set_data("0", "Chưa có IPS", 0.0)

        rejected = snapshot.packet_errors + snapshot.dropped_packets
        valid_packets = max(0, snapshot.total_packets - rejected)
        valid_percent = (valid_packets / snapshot.total_packets * 100.0) if snapshot.total_packets else 0.0
        rejected_percent = max(0.0, 100.0 - valid_percent) if snapshot.total_packets else 0.0
        self.ratio_badge.setText(f"{valid_percent:.2f}% hợp lệ")
        self.ratio_donut.set_data(
            [(valid_percent, "#8B5CF6"), (rejected_percent, "#FF5B79")],
            self._compact_number(snapshot.total_packets),
        )
        self._update_ratio_card(self.normal_ratio_card, valid_packets, valid_percent)
        self._update_ratio_card(self.error_ratio_card, rejected, rejected_percent)

        counts = snapshot.protocol_counts
        total_connections = sum(counts.values())
        segments: list[tuple[float, str]] = []
        for label, color in self.protocol_specs:
            count = counts.get(label, 0)
            percent = count / total_connections * 100.0 if total_connections else 0.0
            segments.append((percent, color))
            row = self.protocol_rows[label]
            row.value_label.setText(f"{percent:.1f}%")
            row.progress_bar.setValue(round(percent))
        self.protocol_donut.set_data(segments, f"{total_connections:,}", "kết nối")
        self._update_ip_table(snapshot)

    @staticmethod
    def _compact_number(value: int) -> str:
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:,}"

    @staticmethod
    def _update_ratio_card(card: QWidget, count: int, percent: float) -> None:
        card.count_label.setText(f"{count:,}")
        card.percent_label.setText(f"{percent:.2f}%")
        card.progress_bar.setValue(round(percent))

    def _update_ip_table(self, snapshot: NetworkSnapshot) -> None:
        rows = snapshot.top_remote_ips
        total = sum(count for _, count in rows)
        self.ip_table.setRowCount(len(rows))
        for row_index, (address, count) in enumerate(rows):
            percent = count / total * 100.0 if total else 0.0
            self.ip_table.setRowHeight(row_index, 40)
            self.ip_table.setCellWidget(row_index, 0, make_text_cell(address, color="#FFFFFF", is_mono=True, is_bold=True))
            self.ip_table.setCellWidget(row_index, 1, make_text_cell(f"{count:,}", color="#CBD5E1", align_center=True))
            self.ip_table.setCellWidget(row_index, 2, make_ip_progress_cell(f"{percent:.1f}%"))
            self.ip_table.setCellWidget(
                row_index,
                3,
                make_badge_cell("Quan sát", "rgba(16, 185, 129, 0.18)", "#6EE7B7", "rgba(16, 185, 129, 0.35)"),
            )

    def _alert_table(self) -> QTableWidget:
        headers = ["Thời gian", "Loại cảnh báo", "Nguồn IP", "Đích IP", "Mức độ", "Trạng thái"]
        rows: list[list[str]] = []

        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("dashboardTable")
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(96)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            if c in (0, 4, 5):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setHorizontalHeaderItem(c, item)

        header = table.horizontalHeader()
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)

        table.setColumnWidth(0, 90)   # Thời gian
        # Col 1: Stretch (Loại cảnh báo co giãn theo bảng)
        table.setColumnWidth(2, 135)  # Nguồn IP
        table.setColumnWidth(3, 135)  # Đích IP
        table.setColumnWidth(4, 130)  # Mức độ (rộng 130px, "Nghiêm trọng" hiển thị trọn vẹn 100%)
        table.setColumnWidth(5, 125)  # Trạng thái (rộng 125px, "Chưa xử lý" hiển thị trọn vẹn 100%)

        severity_colors = {
            "Nghiêm trọng": ("rgba(255, 91, 121, 0.18)", "#FF5B79", "rgba(255, 91, 121, 0.35)"),
            "Cao": ("rgba(255, 138, 76, 0.18)", "#FF8A4C", "rgba(255, 138, 76, 0.35)"),
            "Trung bình": ("rgba(251, 191, 36, 0.18)", "#FBBF24", "rgba(251, 191, 36, 0.35)"),
            "Thấp": ("rgba(52, 211, 153, 0.18)", "#34D399", "rgba(52, 211, 153, 0.35)"),
        }

        status_colors = {
            "Chưa xử lý": ("rgba(139, 92, 246, 0.22)", "#C4B5FD", "rgba(139, 92, 246, 0.35)"),
            "Đã xử lý": ("rgba(16, 185, 129, 0.18)", "#6EE7B7", "rgba(16, 185, 129, 0.35)"),
        }

        for row_index, row in enumerate(rows):
            table.setRowHeight(row_index, 40)

            # Col 0: Thời gian
            table.setCellWidget(row_index, 0, make_text_cell(row[0], color="#8E8BA7", align_center=True))

            # Col 1: Loại cảnh báo
            table.setCellWidget(row_index, 1, make_text_cell(row[1], color="#FFFFFF", is_bold=True))

            # Col 2: Nguồn IP
            table.setCellWidget(row_index, 2, make_text_cell(row[2], color="#C4B5FD", is_mono=True))

            # Col 3: Đích IP
            table.setCellWidget(row_index, 3, make_text_cell(row[3], color="#9E9BB5", is_mono=True))

            # Col 4: Mức độ
            s_bg, s_fg, s_bd = severity_colors.get(row[4], ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(row_index, 4, make_badge_cell(row[4], s_bg, s_fg, s_bd))

            # Col 5: Trạng thái
            st_bg, st_fg, st_bd = status_colors.get(row[5], ("#25224D", "#FFFFFF", "#383466"))
            table.setCellWidget(row_index, 5, make_badge_cell(row[5], st_bg, st_fg, st_bd))

        return table

    def _ip_table(self) -> QTableWidget:
        headers = ["IP từ xa", "Kết nối", "Tỷ lệ", "Trạng thái"]
        rows: list[list[str]] = []

        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("dashboardTable")
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(236)

        for c, h in enumerate(headers):
            item = QTableWidgetItem(h)
            if c in (1, 2, 3):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setHorizontalHeaderItem(c, item)

        header = table.horizontalHeader()
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)

        table.setColumnWidth(1, 95)
        table.setColumnWidth(2, 115)
        table.setColumnWidth(3, 90)

        for row_index, row in enumerate(rows):
            table.setRowHeight(row_index, 40)

            # Col 0: IP nguồn
            table.setCellWidget(row_index, 0, make_text_cell(row[0], color="#FFFFFF", is_mono=True, is_bold=True))

            # Col 1: Gói tin
            table.setCellWidget(row_index, 1, make_text_cell(row[1], color="#CBD5E1", align_center=True))

            # Col 2: Lưu lượng (MB)
            table.setCellWidget(
                row_index, 2, make_badge_cell(f"{row[2]} MB", "rgba(139, 92, 246, 0.18)", "#C4B5FD", "rgba(139, 92, 246, 0.3)")
            )

            # Col 3: Tỷ lệ
            table.setCellWidget(row_index, 3, make_ip_progress_cell(row[3]))

        return table
