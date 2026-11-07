"""Dashboard overview for the desktop IDS/IPS demo."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
        maximum = max(self.values)
        for index, value in enumerate(self.values):
            height = (value / maximum) * (self.height() - 2)
            rect = QRectF(index * (width + gap), self.height() - height, width, height)
            painter.setBrush(self.color)
            painter.drawRoundedRect(rect, 1.0, 1.0)


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

        # 1. Subtle, neutral icon container
        badge = QLabel()
        badge.setObjectName("metricIcon")
        badge.setStyleSheet("background: #232047; border: 1px solid #322D60; border-radius: 9px;")
        badge.setPixmap(icon(metric.icon_name, "#9E9BB5", 15).pixmap(15, 15))
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

        val_lbl = QLabel(metric.value)
        val_lbl.setObjectName("metricValue")
        val_lbl.setStyleSheet("color: #FFFFFF; font-size: 17px; font-weight: 700; letter-spacing: -0.3px;")
        center.addWidget(val_lbl)

        layout.addLayout(center, 1)

        # 3. Right: Trend pill on top + Sparkline below
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        pill = QLabel(metric.change)
        pill.setObjectName("metricChange")
        pill.setStyleSheet(
            f"color: {metric.color}; background: rgba(255, 255, 255, 0.06); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 600;"
        )
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(pill, 0, Qt.AlignmentFlag.AlignRight)

        spark = Sparkline([2, 4, 3, 7, 5, 9, 7, 12, 9, 14, 10, 18], metric.color)
        spark.setFixedSize(42, 16)
        right.addWidget(spark, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)


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
        badge.setStyleSheet("background: #232047; border: 1px solid #322D60; border-radius: 9px;")
        badge.setPixmap(icon("shield", "#9E9BB5", 15).pixmap(15, 15))
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

        layout.addLayout(center, 1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        pill = QLabel("● 94%")
        pill.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 700;"
        )
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(pill, 0, Qt.AlignmentFlag.AlignRight)

        progress = QProgressBar()
        progress.setObjectName("healthProgress")
        progress.setRange(0, 100)
        progress.setValue(94)
        progress.setTextVisible(False)
        progress.setFixedSize(42, 5)
        right.addWidget(progress, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)


class TrafficChart(QWidget):
    incoming = [72, 112, 88, 148, 105, 120, 169, 143, 204, 129, 111, 134, 149, 113, 89, 137, 126, 158, 181, 175, 204, 119, 142, 163, 165, 116, 139, 121, 133, 110, 201, 148, 127, 142]
    outgoing = [51, 79, 93, 82, 122, 111, 75, 60, 83, 126, 89, 102, 77, 105, 84, 59, 96, 75, 101, 72, 137, 116, 81, 103, 114, 87, 75, 106, 93, 82, 139, 111, 75, 108]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        left, top, right, bottom = 38, 14, 10, 24
        chart = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)

        painter.setFont(QFont("Segoe UI", 8))
        for step in range(7):
            y = chart.bottom() - chart.height() * step / 6
            painter.setPen(QColor("#8E8BA7"))
            painter.drawText(QRectF(0, y - 8, left - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(step * 50))
            painter.setPen(QPen(QColor("#282452"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

        time_labels = ["10:14", "10:16", "10:18", "10:20", "10:22", "10:24"]
        painter.setPen(QColor("#8E8BA7"))
        for step, label in enumerate(time_labels):
            x = chart.left() + chart.width() * step / (len(time_labels) - 1)
            painter.drawText(QRectF(x - 22, chart.bottom() + 5, 44, 16), Qt.AlignmentFlag.AlignCenter, label)

        self._draw_series(painter, chart, self.outgoing, QColor("#10B981"), fill_alpha=65)
        self._draw_series(painter, chart, self.incoming, QColor("#8B5CF6"), fill_alpha=45)

    @staticmethod
    def _draw_series(painter: QPainter, chart: QRectF, values: list[int], color: QColor, fill_alpha: int = 50) -> None:
        count = len(values)
        if count < 2:
            return
        points = [
            QPointF(chart.left() + chart.width() * i / (count - 1), chart.bottom() - chart.height() * value / 300)
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


class DonutChart(QWidget):
    def __init__(self, segments: list[tuple[float, str]], center_top: str, center_value: str, center_bottom: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.segments = segments
        self.center_top = center_top
        self.center_value = center_value
        self.center_bottom = center_bottom
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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

    return row


def ratio_stat_card(
    title: str,
    count_str: str,
    percent_str: str,
    color: str,
    percent_val: float,
    parent: QWidget | None = None,
) -> QWidget:
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
        f"color: {color}; font-weight: 700; font-size: 11px; "
        f"background: {color}1F; border: 1px solid {color}33; "
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

        live_badge = QLabel("●  AI DEFENSE: ACTIVE")
        live_badge.setObjectName("liveBadge")
        header_box.addWidget(live_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header_box)

        # 2. Hàng trên kết hợp: Biểu đồ lưu lượng thời gian thực (phần lớn 60-65%) + Cột dọc các chỉ số & Tỷ lệ (35-40%)
        top_row = QGridLayout()
        top_row.setSpacing(12)

        # Cột trái (phần lớn 62%): Lưu lượng mạng theo thời gian thực
        traffic_extra = QWidget()
        t_lay = QHBoxLayout(traffic_extra)
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.setSpacing(10)
        t_lay.addWidget(legend_row("#8B5CF6", "Vào", ""))
        t_lay.addWidget(legend_row("#10B981", "Ra", ""))
        speed_badge = QLabel("142 Mbps")
        speed_badge.setObjectName("panelChip")
        t_lay.addWidget(speed_badge)

        traffic_panel = Panel("Lưu lượng mạng theo thời gian thực", "Băng thông trực tiếp", traffic_extra)
        traffic_chart = TrafficChart()
        traffic_panel.box.addWidget(traffic_chart, 1)
        top_row.addWidget(traffic_panel, 0, 0)

        # Cột phải (38%): Cột dọc gom các phần trên ảnh (6 thẻ chỉ số + Tỷ lệ lưu lượng)
        side_widget = QWidget()
        side_layout = QVBoxLayout(side_widget)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(10)

        # Khối 1: 6 Thẻ chỉ số cốt lõi (2 cột x 3 hàng)
        metrics_grid = QGridLayout()
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(8)
        metrics_grid.setVerticalSpacing(8)

        data = [
            Metric("Tổng gói tin", "1,248,536", "↑ 12.5%", "#8B5CF6", "box"),
            Metric("Lưu lượng mạng", "245.6 Mbps", "↑ 8.3%", "#A78BFA", "nodes"),
            Metric("Kết nối hoạt động", "1,326", "↑ 5.1%", "#10B981", "nodes"),
            Metric("Phát hiện bất thường", "27", "↑ 3.2%", "#FF5B79", "warning"),
            Metric("Luồng bị chặn", "12", "20.0%", "#FF8A4C", "blocked"),
        ]

        metrics_grid.addWidget(MetricCard(data[0]), 0, 0)
        metrics_grid.addWidget(MetricCard(data[1]), 0, 1)
        metrics_grid.addWidget(MetricCard(data[2]), 1, 0)
        metrics_grid.addWidget(MetricCard(data[3]), 1, 1)
        metrics_grid.addWidget(MetricCard(data[4]), 2, 0)
        metrics_grid.addWidget(SystemCard(), 2, 1)

        metrics_grid.setColumnStretch(0, 1)
        metrics_grid.setColumnStretch(1, 1)
        side_layout.addLayout(metrics_grid)

        # Khối 2: Tỷ lệ lưu lượng (Bố cục ngang cân đối, không còn khoảng trống thừa)
        ratio_badge = QLabel("92.4% An toàn")
        ratio_badge.setObjectName("panelChip")
        ratio_badge.setStyleSheet(
            "color: #10B981; background: rgba(16, 185, 129, 0.12); "
            "border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        ratio_panel = Panel("Tỷ lệ lưu lượng", "Đánh giá an toàn gói tin mạng", ratio_badge)

        ratio_body = QHBoxLayout()
        ratio_body.setContentsMargins(0, 4, 0, 0)
        ratio_body.setSpacing(12)

        donut_widget = DonutChart([(92.4, "#8B5CF6"), (7.6, "#FF5B79")], "Tổng", "1.25M", "gói tin")
        donut_widget.setFixedSize(125, 125)
        ratio_body.addWidget(donut_widget, 0, Qt.AlignmentFlag.AlignCenter)

        cards_col = QVBoxLayout()
        cards_col.setContentsMargins(0, 0, 0, 0)
        cards_col.setSpacing(8)
        cards_col.addWidget(ratio_stat_card("Bình thường", "1,153,647", "92.4%", "#8B5CF6", 92.4))
        cards_col.addWidget(ratio_stat_card("Bất thường", "94,889", "7.6%", "#FF5B79", 7.6))
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
        proto_body.addWidget(
            DonutChart(
                [(48.2, "#2F9BFF"), (32.7, "#FF9B37"), (8.1, "#1ED28A"), (6.3, "#9551E8"), (2.8, "#F4C440"), (1.9, "#7671BF")],
                "Giao thức", "6 loại", "1.25M gói"
            ),
            1
        )
        proto_legend = QVBoxLayout()
        proto_legend.setSpacing(4)
        for color, label, value, percent in [
            ("#2F9BFF", "TCP", "48.2%", 48.2),
            ("#FF9B37", "UDP", "32.7%", 32.7),
            ("#1ED28A", "ICMP", "8.1%", 8.1),
            ("#9551E8", "HTTP", "6.3%", 6.3),
            ("#F4C440", "DNS", "2.8%", 2.8),
            ("#7671BF", "Khác", "1.9%", 1.9),
        ]:
            proto_legend.addWidget(protocol_bar_row(color, label, value, percent))
        proto_legend.addStretch()
        proto_body.addLayout(proto_legend, 1)
        protocols_panel.box.addLayout(proto_body, 1)
        row3.addWidget(protocols_panel, 0, 0)

        top_ips_badge = QLabel("Top 5")
        top_ips_badge.setObjectName("panelChip")
        top_ips_panel = Panel("Top 5 nguồn IP theo lưu lượng", "Địa chỉ IP tiêu thụ băng thông lớn", top_ips_badge)
        top_ips_panel.box.addWidget(self._ip_table())
        row3.addWidget(top_ips_panel, 0, 1)

        row3.setColumnStretch(0, 1)
        row3.setColumnStretch(1, 1)
        root.addLayout(row3)

        # 5. Hàng 4: Bảng cảnh báo an ninh gần đây (Trải rộng Full Width)
        alerts_badge = QLabel("Real-time Log")
        alerts_badge.setObjectName("panelChip")
        alerts_panel = Panel("Cảnh báo an ninh gần đây", "Nhật ký phát hiện tấn công và hành vi khả nghi", alerts_badge)
        alerts_panel.box.addWidget(self._alert_table())
        root.addWidget(alerts_panel)

        # 6. Hàng 5: Trạng thái 4 thành phần hệ thống AI
        status_badge = QLabel("4 Active")
        status_badge.setObjectName("panelChip")
        status_panel = Panel("Trạng thái các thành phần hệ thống", "Sức khỏe hạ tầng mạng và động cơ trí tuệ nhân tạo", status_badge)
        modules = QHBoxLayout()
        modules.setSpacing(10)
        for args in [
            ("Giám sát mạng", "(Monitoring)", "activity", "Băng thông: 10 Gbps"),
            ("Phát hiện bất thường", "(Detection)", "shield", "AI Model: Active"),
            ("Dự đoán lưu lượng", "(Prediction)", "trend", "Dự báo: 5m tới"),
            ("Giảm thiểu rủi ro", "(Mitigation)", "lock", "Quy tắc: 24 active"),
        ]:
            modules.addWidget(StatusModule(*args), 1)
        status_panel.box.addLayout(modules)
        root.addWidget(status_panel)

        self.setWidget(content)

    def _alert_table(self) -> QTableWidget:
        headers = ["Thời gian", "Loại cảnh báo", "Nguồn IP", "Đích IP", "Mức độ", "Trạng thái"]
        rows = [
            ["10:24:12", "⚠  Port Scan", "192.168.1.100", "192.168.1.10", "Cao", "Chưa xử lý"],
            ["10:23:45", "⚡  DDoS Attack", "10.0.0.23", "192.168.1.10", "Nghiêm trọng", "Chưa xử lý"],
            ["10:22:18", "📈  Abnormal Traffic", "192.168.1.50", "8.8.8.8", "Trung bình", "Đã xử lý"],
            ["10:21:05", "🔒  Brute Force", "203.113.5.21", "192.168.1.10", "Cao", "Chưa xử lý"],
            ["10:19:37", "🌐  Suspicious DNS", "192.168.1.77", "1.1.1.1", "Thấp", "Đã xử lý"],
        ]

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
        headers = ["IP nguồn", "Gói tin", "Lưu lượng (MB)", "Tỷ lệ"]
        rows = [
            ["192.168.1.100", "245,632", "125.6", "19.7%"],
            ["10.0.0.23", "198,456", "98.2", "15.9%"],
            ["192.168.1.50", "156,789", "76.3", "12.6%"],
            ["203.113.5.21", "123,567", "60.1", "9.9%"],
            ["192.168.1.77", "98,234", "45.7", "7.9%"],
        ]

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

        table.setColumnWidth(1, 95)   # Gói tin
        table.setColumnWidth(2, 115)  # Lưu lượng (MB)
        table.setColumnWidth(3, 90)   # Tỷ lệ

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
