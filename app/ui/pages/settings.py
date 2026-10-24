"""System settings interface for the desktop demo."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon


class ToggleButton(QPushButton):
    def __init__(self, checked: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsToggle")
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(38, 21)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#168DFF" if self.isChecked() else "#455B73"))
        painter.drawRoundedRect(QRectF(0, 0, 38, 21), 10.5, 10.5)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(20 if self.isChecked() else 3, 3, 15, 15))


class PreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(76)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#071423"))
        painter.setPen(QPen(QColor("#1A3852"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.fillRect(8, 8, 38, self.height() - 16, QColor("#0D2134"))
        for y in range(14, self.height() - 8, 10):
            painter.fillRect(14, y, 25, 4, QColor("#244662"))
        colors = ["#2196F3", "#A650EF", "#FFA22F", "#FF4F5D"]
        for index, color in enumerate(colors):
            x = 55 + index * 54
            painter.fillRect(x, 10, 45, 21, QColor("#10263D"))
            painter.fillRect(x + 5, 15, 10, 10, QColor(color))
        points = [(55, 62), (75, 43), (96, 55), (117, 51), (138, 67), (159, 61), (180, 39), (202, 46), (225, 51), (248, 48), (275, 58), (300, 41)]
        painter.setPen(QPen(QColor("#2196F3"), 1.5))
        for first, second in zip(points, points[1:]):
            painter.drawLine(*first, *second)


class SettingsCard(QFrame):
    def __init__(self, title: str, icon_name: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(13, 11, 13, 12)
        self.box.setSpacing(7)
        header = QHBoxLayout()
        badge = QLabel()
        badge.setObjectName("settingsCardIcon")
        badge.setPixmap(icon(icon_name, color, 20).pixmap(20, 20))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(34, 34)
        header.addWidget(badge)
        title_label = QLabel(title)
        title_label.setObjectName("settingsCardTitle")
        header.addWidget(title_label)
        header.addStretch()
        self.box.addLayout(header)

    def add_row(self, label_text: str, widget: QWidget, stretch: int = 1) -> None:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("settingsLabel")
        row.addWidget(label)
        row.addStretch()
        if isinstance(widget, ToggleButton):
            widget.setAccessibleName(label_text)
            switch_group = QWidget()
            switch_layout = QHBoxLayout(switch_group)
            switch_layout.setContentsMargins(0, 0, 0, 0)
            switch_layout.setSpacing(8)
            switch_layout.addWidget(widget)
            state = QLabel("Bật" if widget.isChecked() else "Tắt")
            state.setObjectName("settingsToggleState")
            widget.toggled.connect(lambda checked, state=state: state.setText("Bật" if checked else "Tắt"))
            switch_layout.addWidget(state)
            row.addWidget(switch_group)
        else:
            row.addWidget(widget, stretch)
        self.box.addLayout(row)

    def minimumSizeHint(self) -> QSize:
        return QSize(220, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:
        return QSize(300, super().sizeHint().height())


def combo(items: list[str], width: int = 150) -> QComboBox:
    widget = QComboBox()
    widget.setObjectName("settingsCombo")
    widget.addItems(items)
    widget.setMinimumWidth(width)
    return widget


def input_field(text: str = "", placeholder: str = "") -> QLineEdit:
    widget = QLineEdit(text)
    widget.setObjectName("settingsInput")
    widget.setPlaceholderText(placeholder)
    return widget


class SettingsPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("settingsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 12, 16, 2)
        root.setSpacing(10)

        title = QLabel("Cài đặt hệ thống")
        title.setObjectName("settingsHeading")
        root.addWidget(title)
        subtitle = QLabel("Quản lý cấu hình hệ thống, mô hình AI, kết nối và các tùy chọn bảo mật")
        subtitle.setObjectName("settingsSubtitle")
        root.addWidget(subtitle)

        tabs = QHBoxLayout()
        tab_data = [("Tổng quan", "settings"), ("Giao diện", "palette"), ("Kết nối hệ thống", "nodes"), ("Giám sát mạng", "monitor"), ("Phát hiện bất thường", "shield"), ("Dự đoán lưu lượng", "trend"), ("Giảm thiểu rủi ro (IPS)", "lock")]
        for index, (text, icon_name) in enumerate(tab_data):
            button = QPushButton("  " + text)
            button.setObjectName("activeSettingsTab" if index == 0 else "settingsTab")
            button.setIcon(icon(icon_name, "#FFFFFF" if index == 0 else "#B5C9E3"))
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            tabs.addWidget(button, 1)
        root.addLayout(tabs)

        upper = QGridLayout()
        upper.setSpacing(10)
        upper.addWidget(self._system_info(), 0, 0)
        upper.addWidget(self._appearance(), 0, 1)
        upper.addWidget(self._connection(), 0, 2)
        for column in range(3):
            upper.setColumnStretch(column, 1)
        upper.setRowMinimumHeight(0, 325)
        root.addLayout(upper)

        lower = QGridLayout()
        lower.setSpacing(10)
        lower.addWidget(self._monitoring(), 0, 0)
        lower.addWidget(self._detection(), 0, 1)
        lower.addWidget(self._prediction(), 0, 2)
        lower.addWidget(self._ips(), 0, 3)
        for column in range(4):
            lower.setColumnStretch(column, 1)
        lower.setRowMinimumHeight(0, 310)
        root.addLayout(lower)

        footer = QHBoxLayout()
        restore = QPushButton("  Khôi phục cài đặt gốc")
        restore.setObjectName("settingsSecondaryButton")
        restore.setIcon(icon("refresh", "#B7CCE4"))
        restore.clicked.connect(self.restore_defaults)
        footer.addWidget(restore)
        footer.addStretch()
        validate = QPushButton("  Kiểm tra cấu hình")
        validate.setObjectName("settingsSecondaryButton")
        validate.setIcon(icon("check", "#B7CCE4"))
        validate.clicked.connect(lambda: self.show_status("Cấu hình hợp lệ.", True))
        footer.addWidget(validate)
        save = QPushButton("  Lưu cấu hình")
        save.setObjectName("saveSettingsButton")
        save.setIcon(icon("save", "#FFFFFF"))
        save.clicked.connect(lambda: self.show_status("Đã lưu cấu hình mô phỏng.", True))
        footer.addWidget(save)
        apply = QPushButton("  Áp dụng")
        apply.setObjectName("applySettingsButton")
        apply.setIcon(icon("check", "#FFFFFF"))
        apply.clicked.connect(lambda: self.show_status("Đã áp dụng cấu hình mô phỏng.", True))
        footer.addWidget(apply)
        root.addLayout(footer)
        self.status = QLabel("")
        self.status.setObjectName("settingsStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.status)
        self.setWidget(content)

    def _system_info(self) -> SettingsCard:
        card = SettingsCard("Thông tin hệ thống", "info", "#FFFFFF")
        card.add_row("Tên ứng dụng", input_field("AI Network IDS/IPS"))
        card.add_row("Phiên bản", input_field("v1.0.0"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Mô tả"))
        description = QTextEdit("Hệ thống giám sát, phát hiện bất thường, dự đoán và giảm thiểu rủi ro an ninh mạng sử dụng AI.")
        description.setObjectName("settingsText")
        description.setFixedHeight(76)
        row.addWidget(description, 1)
        card.box.addLayout(row)
        card.add_row("Ngôn ngữ", combo(["Tiếng Việt", "English"]))
        card.add_row("Khởi động cùng hệ thống", ToggleButton(True), 0)
        return card

    def _appearance(self) -> SettingsCard:
        card = SettingsCard("Cài đặt giao diện", "palette", "#B765F6")
        card.add_row("Chủ đề giao diện", combo(["Tối (Dark Mode)", "Sáng (Light Mode)"]))
        colors = QWidget()
        color_row = QHBoxLayout(colors)
        color_row.setContentsMargins(0, 0, 0, 0)
        for value in ("#168DFF", "#18D88B", "#FF4F5D", "#FFA22F", "#9A4BE7"):
            dot = QPushButton()
            dot.setObjectName("accentColor")
            dot.setFixedSize(25, 25)
            dot.setStyleSheet(f"background:{value}; border-radius:12px; border:2px solid {'#7EC4FF' if value == '#168DFF' else value};")
            color_row.addWidget(dot)
        card.add_row("Màu nhấn", colors)
        card.add_row("Kích thước font", combo(["Trung bình", "Nhỏ", "Lớn"]))
        card.add_row("Hiệu ứng chuyển trang", ToggleButton(True), 0)
        card.add_row("Hiển thị widget động", ToggleButton(True), 0)
        preview_label = QLabel("Xem trước giao diện")
        preview_label.setObjectName("settingsLabel")
        card.box.addWidget(preview_label)
        card.box.addWidget(PreviewWidget())
        return card

    def _connection(self) -> SettingsCard:
        card = SettingsCard("Kết nối hệ thống", "link", "#FFFFFF")
        card.add_row("Chế độ kết nối", combo(["Local (Mock Data)", "Remote API", "SDN Controller"]))
        self.api_input = input_field("http://127.0.0.1:8000")
        card.add_row("API Server URL", self.api_input)
        test = QPushButton("  Kiểm tra kết nối")
        test.setObjectName("connectionTestButton")
        test.setIcon(icon("link", "#FFFFFF"))
        test.clicked.connect(self.test_connection)
        card.box.addWidget(test, 0, Qt.AlignmentFlag.AlignRight)
        self.connection_status = QLabel("●  Đang kết nối")
        self.connection_status.setObjectName("connectionStatus")
        card.add_row("Trạng thái kết nối", self.connection_status, 0)
        response = QLabel("12 ms")
        response.setObjectName("settingsValue")
        card.add_row("Thời gian phản hồi", response, 0)
        card.add_row("Tự động kết nối", ToggleButton(True), 0)
        card.add_row("Khoảng thời gian kết nối lại", combo(["10 giây", "30 giây", "1 phút"]))
        return card

    def _monitoring(self) -> SettingsCard:
        card = SettingsCard("Cài đặt giám sát mạng", "activity", "#29E09A")
        card.add_row("Giao diện mạng", combo(["Tất cả giao diện", "eth0", "lo"], 125))
        card.add_row("Khoảng thời gian thu thập", combo(["1 giây", "5 giây", "10 giây"], 125))
        card.add_row("Kiểu thu thập dữ liệu", combo(["PCAP (Realtime)", "NetFlow", "sFlow"], 125))
        bpf = input_field(placeholder="Ví dụ: port 80 hoặc host 192.168.1.1")
        card.box.addWidget(QLabel("Bộ lọc gói tin (BPF)"))
        card.box.addWidget(bpf)
        card.add_row("Lưu dữ liệu thô", ToggleButton(True), 0)
        storage = QSpinBox()
        storage.setObjectName("settingsSpin")
        storage.setRange(1, 1000)
        storage.setValue(10)
        card.add_row("Giới hạn lưu trữ (GB)", storage)
        return card

    def _detection(self) -> SettingsCard:
        card = SettingsCard("Cài đặt phát hiện bất thường", "shield", "#B35BFA")
        card.add_row("Mô hình phát hiện", combo(["Random Forest", "Isolation Forest", "Autoencoder"], 130))
        for label_text, value in (("Ngưỡng phát hiện (threshold)", 70), ("Độ nhạy (sensitivity)", 80)):
            card.box.addWidget(QLabel(label_text))
            row = QHBoxLayout()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setObjectName("settingsSlider")
            slider.setValue(value)
            row.addWidget(slider, 1)
            number = QLabel(f"0.{value}")
            number.setObjectName("sliderValue")
            row.addWidget(number)
            card.box.addLayout(row)
        card.add_row("Cảnh báo khi phát hiện", ToggleButton(True), 0)
        card.add_row("Lưu kết quả phát hiện", ToggleButton(True), 0)
        history = QSpinBox()
        history.setObjectName("settingsSpin")
        history.setRange(1, 365)
        history.setValue(30)
        card.add_row("Thời gian lưu lịch sử (ngày)", history)
        self._reset_button(card)
        return card

    def _prediction(self) -> SettingsCard:
        card = SettingsCard("Cài đặt dự đoán lưu lượng", "trend", "#FFB13B")
        card.add_row("Mô hình dự đoán", combo(["LSTM (Time Series)", "GRU", "ARIMA"], 130))
        card.add_row("Thời gian dự đoán", combo(["30 phút", "1 giờ", "3 giờ"], 130))
        card.add_row("Khoảng thời gian cập nhật", combo(["1 phút", "5 phút", "10 phút"], 130))
        card.add_row("Độ dài chuỗi đầu vào", combo(["60", "120", "240"], 130))
        card.add_row("Hiển thị dự đoán trên biểu đồ", ToggleButton(True), 0)
        card.add_row("Lưu kết quả dự đoán", ToggleButton(True), 0)
        history = QSpinBox()
        history.setObjectName("settingsSpin")
        history.setRange(1, 365)
        history.setValue(30)
        card.add_row("Thời gian lưu lịch sử (ngày)", history)
        self._reset_button(card)
        return card

    def _ips(self) -> SettingsCard:
        card = SettingsCard("Cài đặt giảm thiểu rủi ro (IPS)", "shield", "#FF5260")
        card.add_row("Chế độ hoạt động", combo(["Chỉ cảnh báo (Simulation)", "Tự động chặn", "Thủ công"], 140))
        card.add_row("Hành động mặc định", combo(["Chặn lưu lượng", "Giới hạn tốc độ", "Ghi log"], 140))
        card.add_row("Thời gian chặn mặc định", combo(["5 phút", "30 phút", "1 giờ"], 140))
        card.add_row("Giới hạn tốc độ (Rate Limit)", combo(["10 Mbps", "5 Mbps", "2 Mbps"], 140))
        card.add_row("Tự động áp dụng rule", ToggleButton(True), 0)
        card.add_row("Ghi log hành động", ToggleButton(True), 0)
        card.add_row("Xác nhận trước khi chặn", ToggleButton(False), 0)
        self._reset_button(card)
        return card

    @staticmethod
    def _reset_button(card: SettingsCard) -> None:
        reset = QPushButton("  Đặt lại mặc định")
        reset.setObjectName("cardResetButton")
        reset.setIcon(icon("refresh", "#B7CCE4"))
        card.box.addWidget(reset)

    def test_connection(self) -> None:
        self.connection_status.setText("●  Đang kiểm tra...")
        QTimer.singleShot(500, lambda: self.connection_status.setText("●  Kết nối thành công (mô phỏng)"))

    def restore_defaults(self) -> None:
        self.api_input.setText("http://127.0.0.1:8000")
        self.show_status("Đã khôi phục cài đặt mặc định.", True)

    def show_status(self, message: str, success: bool) -> None:
        self.status.setText(message)
        self.status.setProperty("success", success)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
