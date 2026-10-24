"""Traffic forecasting page with simulated time-series data."""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon
from app.ui.pages.monitoring import MetricCard, MonitorMetric, Panel, legend


class ForecastChart(QWidget):
    actual = [82, 70, 86, 93, 77, 68, 82, 113, 78, 94, 83, 72, 91, 100, 119, 98, 76, 103, 84, 112, 138, 92, 104, 129, 111, 126, 126, 103, 111, 119, 108, 112]
    forecast = [111, 119, 127, 132, 138, 141, 144, 146, 151, 156, 160, 166, 171, 167, 165, 171, 180, 194, 203, 211, 216, 210, 202, 198, 191, 185, 179, 173, 168, 163]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(190)

    def refresh(self) -> None:
        self.forecast = [max(80, int(value * random.uniform(0.96, 1.05))) for value in self.forecast]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(42, 8, self.width() - 51, self.height() - 31)
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(7):
            y = chart.bottom() - chart.height() * step / 6
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(0, y - 8, 35, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(step * 50))
            painter.setPen(QPen(QColor("#20364D"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
        labels = ["12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"]
        for index, label in enumerate(labels):
            x = chart.left() + chart.width() * index / (len(labels) - 1)
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(x - 24, chart.bottom() + 6, 48, 16), Qt.AlignmentFlag.AlignCenter, label)

        divider_x = chart.left() + chart.width() * 0.52
        painter.fillRect(QRectF(divider_x, chart.top(), chart.right() - divider_x, chart.height()), QColor(58, 50, 79, 52))
        painter.setPen(QPen(QColor("#D6E0EC"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(divider_x, chart.top()), QPointF(divider_x, chart.bottom()))

        actual_points = [QPointF(chart.left() + (divider_x - chart.left()) * i / (len(self.actual) - 1), chart.bottom() - chart.height() * value / 300) for i, value in enumerate(self.actual)]
        actual_path = QPainterPath(actual_points[0])
        for point in actual_points[1:]:
            actual_path.lineTo(point)
        actual_area = QPainterPath(actual_path)
        actual_area.lineTo(divider_x, chart.bottom())
        actual_area.lineTo(chart.left(), chart.bottom())
        actual_area.closeSubpath()
        gradient = QLinearGradient(0, chart.top(), 0, chart.bottom())
        gradient.setColorAt(0, QColor(32, 148, 255, 105))
        gradient.setColorAt(1, QColor(32, 148, 255, 4))
        painter.fillPath(actual_area, gradient)
        painter.setPen(QPen(QColor("#2196F3"), 2.3))
        painter.drawPath(actual_path)

        forecast_points = [QPointF(divider_x + (chart.right() - divider_x) * i / (len(self.forecast) - 1), chart.bottom() - chart.height() * value / 300) for i, value in enumerate(self.forecast)]
        upper = [QPointF(point.x(), point.y() - 24) for point in forecast_points]
        lower = [QPointF(point.x(), point.y() + 24) for point in forecast_points]
        confidence = QPainterPath(upper[0])
        for point in upper[1:]:
            confidence.lineTo(point)
        for point in reversed(lower):
            confidence.lineTo(point)
        confidence.closeSubpath()
        painter.fillPath(confidence, QColor(126, 105, 189, 65))
        forecast_path = QPainterPath(forecast_points[0])
        for point in forecast_points[1:]:
            forecast_path.lineTo(point)
        painter.setPen(QPen(QColor("#FF4C61"), 2.1, Qt.PenStyle.DashLine))
        painter.drawPath(forecast_path)
        painter.setPen(QColor("#9FB1C7"))
        painter.drawText(QRectF(chart.left(), chart.bottom() - 24, divider_x - chart.left(), 18), Qt.AlignmentFlag.AlignCenter, "Hiện tại")
        painter.drawText(QRectF(divider_x, chart.bottom() - 24, chart.right() - divider_x, 18), Qt.AlignmentFlag.AlignCenter, "Dự đoán")


class ComparisonChart(QWidget):
    actual = [126, 145, 133, 151, 139, 158, 147, 166, 153, 176, 161, 185, 170, 194, 176, 207, 188, 219]
    predicted = [164, 168, 170, 171, 174, 178, 181, 184, 188, 191, 195, 198, 201, 205, 208, 211, 214, 218]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(38, 8, self.width() - 46, self.height() - 27)
        for step in range(4):
            y = chart.bottom() - chart.height() * step / 3
            painter.setPen(QPen(QColor("#20364D"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
            painter.setPen(QColor("#8499B3"))
            painter.drawText(QRectF(0, y - 8, 31, 16), Qt.AlignmentFlag.AlignRight, str(step * 100))
        count = len(self.actual) + len(self.predicted)
        bar_width = max(3.0, chart.width() / count - 3)
        for index, value in enumerate(self.actual):
            x = chart.left() + index * chart.width() / count
            height = chart.height() * value / 300
            painter.fillRect(QRectF(x, chart.bottom() - height, bar_width, height), QColor("#2196F3"))
        split = chart.left() + len(self.actual) * chart.width() / count
        painter.fillRect(QRectF(split, chart.top(), chart.right() - split, chart.height()), QColor(114, 74, 155, 40))
        for index, value in enumerate(self.predicted):
            x = split + index * chart.width() / count
            height = chart.height() * value / 300
            painter.fillRect(QRectF(x, chart.bottom() - height, bar_width, height), QColor("#ED5064"))
        painter.setPen(QPen(QColor("#D6E0EC"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(split, chart.top()), QPointF(split, chart.bottom()))


class PredictionSummary(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("predictionSummary")
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 14, 12)
        header = QHBoxLayout()
        title = QLabel("Chỉ số dự đoán")
        title.setObjectName("predictionPanelTitle")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Mô hình:"))
        model = QComboBox()
        model.setObjectName("predictionCombo")
        model.addItems(["LSTM", "GRU", "ARIMA"])
        model.setFixedWidth(90)
        header.addWidget(model)
        box.addLayout(header)
        for icon_name, color, title_text, value, delta in [
            ("trend", "#2196F3", "Dự đoán lưu lượng vào", "162.8 Mbps", "↑ 12.1% so với hiện tại"),
            ("trend", "#16D88B", "Dự đoán lưu lượng ra", "118.6 Mbps", "↑ 9.4% so với hiện tại"),
            ("database", "#A654EF", "Dự đoán kết nối", "1,485", "↑ 12.0% so với hiện tại"),
        ]:
            row = QFrame()
            row.setObjectName("predictionSummaryRow")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(2, 9, 2, 9)
            badge = QLabel()
            badge.setObjectName("predictionIcon")
            badge.setPixmap(icon(icon_name, color, 25).pixmap(25, 25))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(52, 52)
            layout.addWidget(badge)
            copy = QVBoxLayout()
            label = QLabel(title_text)
            label.setObjectName("predictionLabel")
            copy.addWidget(label)
            number = QLabel(value)
            number.setObjectName("predictionValue")
            copy.addWidget(number)
            layout.addLayout(copy, 1)
            change = QLabel(delta)
            change.setObjectName("predictionDelta")
            change.setWordWrap(True)
            layout.addWidget(change)
            box.addWidget(row)


class PredictionPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("predictionScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("predictionContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 12, 18, 16)
        root.setSpacing(10)

        heading = QLabel("Dự đoán lưu lượng")
        heading.setObjectName("predictionHeading")
        root.addWidget(heading)
        subtitle = QLabel("Ứng dụng AI/Time Series Forecasting để dự đoán xu hướng lưu lượng mạng và hỗ trợ cảnh báo sớm nguy cơ an ninh mạng  •  Dữ liệu mô phỏng")
        subtitle.setObjectName("predictionSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        metrics = QGridLayout()
        metrics.setSpacing(10)
        metric_data = [
            MonitorMetric("Lưu lượng hiện tại", "145.2 Mbps", "↑ 8.3%", "#279FFF", "activity"),
            MonitorMetric("Dự đoán (30 phút)", "162.8 Mbps", "↑ 12.1%", "#A651EE", "trend"),
            MonitorMetric("Kết nối hiện tại", "1,326", "↑ 5.1%", "#17DA8C", "database"),
            MonitorMetric("Nguy cơ quá tải", "Trung bình", "●  61%", "#F7B83D", "warning"),
            MonitorMetric("Cảnh báo sớm", "3", "↑ 50%", "#FF5260", "shield"),
        ]
        for column, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(data), 0, column)
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        main = QGridLayout()
        main.setSpacing(10)
        forecast_panel = Panel("Dự đoán lưu lượng mạng (Time Series Forecasting)")
        controls = QHBoxLayout()
        controls.addStretch()
        for color, text in [("#2196F3", "Lưu lượng thực tế"), ("#FF4C61", "Dự đoán (30 phút)"), ("#645B87", "Khoảng tin cậy (95%)")]:
            controls.addWidget(legend(color, text))
        controls.addStretch()
        controls.addWidget(QLabel("Khoảng dự đoán:"))
        horizon = QComboBox()
        horizon.setObjectName("predictionCombo")
        horizon.addItems(["30 phút", "1 giờ", "3 giờ"])
        horizon.setFixedWidth(105)
        controls.addWidget(horizon)
        forecast_panel.box.addLayout(controls)
        self.forecast_chart = ForecastChart()
        forecast_panel.box.addWidget(self.forecast_chart, 1)
        main.addWidget(forecast_panel, 0, 0, 1, 3)
        main.addWidget(PredictionSummary(), 0, 3)
        main.setColumnStretch(0, 1)
        main.setColumnStretch(1, 1)
        main.setColumnStretch(2, 1)
        main.setColumnStretch(3, 1)
        main.setRowMinimumHeight(0, 270)
        root.addLayout(main)

        middle = QGridLayout()
        middle.setSpacing(10)
        compare = Panel("So sánh thực tế và dự đoán")
        compare_legend = QHBoxLayout()
        compare_legend.addStretch()
        compare_legend.addWidget(legend("#2196F3", "Thực tế"))
        compare_legend.addWidget(legend("#ED5064", "Dự đoán"))
        compare_legend.addWidget(legend("#5C4785", "Khoảng tin cậy"))
        compare.box.addLayout(compare_legend)
        compare.box.addWidget(ComparisonChart(), 1)
        middle.addWidget(compare, 0, 0)
        middle.addWidget(self._trend_table(), 0, 1)
        middle.setColumnStretch(0, 1)
        middle.setColumnStretch(1, 1)
        middle.setRowMinimumHeight(0, 190)
        root.addLayout(middle)

        bottom = QGridLayout()
        bottom.setSpacing(10)
        bottom.addWidget(self._alerts_panel(), 0, 0, 1, 3)
        bottom.addWidget(self._settings_panel(), 0, 3)
        bottom.setColumnStretch(0, 1)
        bottom.setColumnStretch(1, 1)
        bottom.setColumnStretch(2, 1)
        bottom.setColumnStretch(3, 1)
        root.addLayout(bottom)
        self.setWidget(content)

    @staticmethod
    def _table(headers: list[str], rows: list[list[str]], height: int) -> QTableWidget:
        table = QTableWidget(len(rows), len(headers))
        table.setObjectName("predictionTable")
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFixedHeight(height)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                if value.startswith("↑"):
                    item.setForeground(QColor("#FF5360"))
                table.setItem(r, c, item)
        return table

    def _trend_table(self) -> Panel:
        panel = Panel("Xu hướng ngắn hạn (30 phút tới)")
        rows = [
            ["14:40", "150.2", "110.3", "1,350", "↑ 3.1%"], ["14:50", "154.6", "113.2", "1,372", "↑ 6.5%"],
            ["15:00", "159.8", "116.5", "1,401", "↑ 10.1%"], ["15:10", "162.8", "118.6", "1,430", "↑ 12.1%"],
            ["15:20", "165.1", "121.0", "1,452", "↑ 14.8%"], ["15:30", "167.3", "124.2", "1,485", "↑ 17.2%"],
        ]
        panel.box.addWidget(self._table(["Thời điểm", "Lưu lượng vào (Mbps)", "Lưu lượng ra (Mbps)", "Kết nối dự kiến", ""], rows, 155))
        return panel

    def _alerts_panel(self) -> Panel:
        panel = Panel("Cảnh báo dự đoán")
        rows = [
            ["24/04 14:32", "Lưu lượng tăng đột biến", "162.8 Mbps", "150 Mbps", "Trung bình", "Đang theo dõi", "◉   ⋮"],
            ["24/04 14:25", "Nguy cơ quá tải kết nối", "1,485", "1,400", "Cao", "Cần xử lý", "◉   ⋮"],
            ["24/04 14:18", "Lưu lượng bất thường", "180.2 Mbps", "160 Mbps", "Cao", "Đã xác nhận", "◉   ⋮"],
            ["24/04 14:10", "Xu hướng tấn công DDoS", "195.6 Mbps", "170 Mbps", "Cao", "Đã xử lý", "◉   ⋮"],
        ]
        table = self._table(["Thời gian", "Loại cảnh báo", "Giá trị dự đoán", "Ngưỡng", "Mức độ", "Trạng thái", "Hành động"], rows, 132)
        for r in range(len(rows)):
            table.item(r, 4).setForeground(QColor("#FFB13B" if rows[r][4] == "Trung bình" else "#FF5360"))
            table.item(r, 5).setForeground(QColor("#FFB13B" if rows[r][5] == "Đang theo dõi" else "#FF5360" if rows[r][5] == "Cần xử lý" else "#1CDB8C"))
        panel.box.addWidget(table)
        return panel

    def _settings_panel(self) -> Panel:
        panel = Panel("Thiết lập dự đoán")
        for label_text, values in [
            ("Mô hình", ["LSTM (Time Series)", "GRU", "ARIMA"]),
            ("Khoảng dự đoán", ["30 phút", "1 giờ", "3 giờ"]),
            ("Chu kỳ cập nhật", ["1 phút", "5 phút", "10 phút"]),
        ]:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("settingLabel")
            row.addWidget(label)
            combo = QComboBox()
            combo.setObjectName("predictionCombo")
            combo.addItems(values)
            row.addWidget(combo, 1)
            panel.box.addLayout(row)
        self.start_button = QPushButton("  Bắt đầu dự đoán")
        self.start_button.setObjectName("startPredictionButton")
        self.start_button.setIcon(icon("trend", "#FFFFFF"))
        self.start_button.clicked.connect(self.start_prediction)
        panel.box.addWidget(self.start_button)
        return panel

    def start_prediction(self) -> None:
        self.start_button.setText("  Đang dự đoán...")
        self.start_button.setEnabled(False)
        self.forecast_chart.refresh()
        QTimer.singleShot(900, self._prediction_finished)

    def _prediction_finished(self) -> None:
        self.start_button.setText("  Dự đoán hoàn tất")
        self.start_button.setEnabled(True)
