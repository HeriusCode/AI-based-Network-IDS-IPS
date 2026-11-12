"""Main traffic configuration and control page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.models.traffic_config import TrafficConfig
from app.ui.widgets import Card, MetricCard, StatusPill, format_bytes
from app.utils.constants import MAX_CONNECTIONS, MAX_DURATION, MAX_PACKET_RATE, MAX_PACKET_SIZE
from app.utils.validators import ValidationError, validate_traffic_config


class GeneratorPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        cfg = controller.config_manager.config
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)
        title = QLabel("Traffic Generator")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Tạo lưu lượng giới hạn trong mạng lab; STOP có hiệu lực ngay lập tức")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(14)
        target = Card("A. Target Configuration")
        target_form = QFormLayout()
        target_form.setSpacing(10)
        self.destination_ip = QLineEdit("127.0.0.1")
        self.destination_port = QSpinBox()
        self.destination_port.setRange(1, 65535)
        self.destination_port.setValue(8080)
        self.protocol = QComboBox()
        self.protocol.addItems(["TCP", "UDP", "ICMP"])
        self.source_host = QComboBox()
        self.source_host.addItems(["Local", "h1", "h2", "h3"])
        self.target_host = QComboBox()
        self.target_host.addItems(["Local", "h1", "h2", "h3"])
        target_form.addRow("Destination IP", self.destination_ip)
        target_form.addRow("Destination Port", self.destination_port)
        target_form.addRow("Protocol", self.protocol)
        target_form.addRow("Source Host", self.source_host)
        target_form.addRow("Target Host", self.target_host)
        target.box.addLayout(target_form)

        traffic = Card("B. Traffic Configuration")
        traffic_form = QFormLayout()
        traffic_form.setSpacing(10)
        self.scenario = QComboBox()
        self.scenario.addItem("Normal Traffic", "NORMAL")
        self.scenario.addItem("Traffic Burst", "BURST")
        self.scenario.addItem("Connection Burst", "CONNECTION_BURST")
        self.scenario.addItem("Custom Traffic", "CUSTOM")
        self.duration = QSpinBox()
        self.duration.setRange(5, MAX_DURATION)
        self.duration.setSuffix(" giây")
        self.duration.setValue(cfg.default_duration)
        self.packet_rate = QSpinBox()
        self.packet_rate.setRange(1, MAX_PACKET_RATE)
        self.packet_rate.setSuffix(" packet/s")
        self.packet_rate.setValue(cfg.default_packet_rate)
        self.packet_size = QSpinBox()
        self.packet_size.setRange(32, MAX_PACKET_SIZE)
        self.packet_size.setSuffix(" byte")
        self.packet_size.setValue(cfg.default_packet_size)
        self.connections = QSpinBox()
        self.connections.setRange(1, MAX_CONNECTIONS)
        self.connections.setValue(10)
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(1, MAX_PACKET_RATE)
        self.rate_slider.setValue(cfg.default_packet_rate)
        self.rate_slider.valueChanged.connect(self.packet_rate.setValue)
        self.packet_rate.valueChanged.connect(self.rate_slider.setValue)
        traffic_form.addRow("Traffic Type", self.scenario)
        traffic_form.addRow("Duration", self.duration)
        traffic_form.addRow("Packet Rate", self.packet_rate)
        traffic_form.addRow("Rate Slider", self.rate_slider)
        traffic_form.addRow("Packet Size", self.packet_size)
        traffic_form.addRow("Number of Connections", self.connections)
        traffic.box.addLayout(traffic_form)

        controls = Card("C. Control Panel")
        buttons = QGridLayout()
        self.start_button = QPushButton("START")
        self.start_button.setObjectName("successButton")
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setEnabled(False)
        self.reset_button = QPushButton("RESET")
        self.test_button = QPushButton("TEST")
        self.test_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(controller.stop_traffic)
        self.reset_button.clicked.connect(controller.reset_statistics)
        self.test_button.clicked.connect(self.test_configuration)
        buttons.addWidget(self.start_button, 0, 0)
        buttons.addWidget(self.stop_button, 0, 1)
        buttons.addWidget(self.reset_button, 1, 0)
        buttons.addWidget(self.test_button, 1, 1)
        controls.box.addLayout(buttons)
        self.status = StatusPill(controller.current_status)
        self.message = QLabel("Sẵn sàng kiểm tra cấu hình")
        self.message.setObjectName("muted")
        controls.box.addWidget(self.status)
        controls.box.addWidget(self.message)
        limit = QLabel("Giới hạn: 1.000 packet/s · 120 giây · 1.472 byte · 50 kết nối")
        limit.setObjectName("hint")
        limit.setWordWrap(True)
        controls.box.addWidget(limit)

        grid.addWidget(target, 0, 0)
        grid.addWidget(traffic, 0, 1)
        grid.addWidget(controls, 0, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        root.addLayout(grid)

        stats = QGridLayout()
        self.sent_packets = MetricCard("Packets Sent", "0", "#38BDF8")
        self.sent_bytes = MetricCard("Bytes Sent", "0 B", "#34D399")
        self.current_rate = MetricCard("Current Rate", "0 packet/s", "#A78BFA")
        self.elapsed = MetricCard("Duration", "0.0 s", "#FBBF24")
        for index, card in enumerate((self.sent_packets, self.sent_bytes, self.current_rate, self.elapsed)):
            stats.addWidget(card, 0, index)
            stats.setColumnStretch(index, 1)
        root.addLayout(stats)
        root.addStretch()

        controller.stats_updated.connect(self.update_stats)
        controller.traffic_status_changed.connect(self._status_changed)
        controller.session_finished.connect(self._session_finished)

    def set_scenario(self, scenario: str) -> None:
        index = self.scenario.findData(scenario)
        if index >= 0:
            self.scenario.setCurrentIndex(index)

    def build_config(self) -> TrafficConfig:
        return TrafficConfig(
            destination_ip=self.destination_ip.text(),
            destination_port=self.destination_port.value(),
            protocol=self.protocol.currentText(),
            scenario=str(self.scenario.currentData()),
            duration=self.duration.value(),
            packet_rate=self.packet_rate.value(),
            packet_size=self.packet_size.value(),
            number_connections=self.connections.value(),
            source_host=self.source_host.currentText(),
            target_host=self.target_host.currentText(),
        )

    def test_configuration(self) -> bool:
        try:
            config = self.build_config()
            if config.source_host != "Local" or config.target_host != "Local":
                raise ValidationError(
                    "Mininet chỉ khả dụng khi Máy 2 triển khai backend điều khiển được xác thực"
                )
            cfg = self.controller.config_manager.config
            validate_traffic_config(config, cfg.allowed_networks, cfg.approved_ports)
        except ValidationError as exc:
            self.status.set_status("Error")
            self.message.setText(str(exc))
            return False
        self.status.set_status("Idle")
        self.message.setText("Cấu hình hợp lệ và nằm trong phạm vi lab")
        return True

    def start(self) -> None:
        if not self.test_configuration():
            return
        try:
            self.controller.start_traffic(self.build_config())
        except ValidationError as exc:
            self.status.set_status("Error")
            self.message.setText(str(exc))

    def _status_changed(self, status: str) -> None:
        self.status.set_status(status)
        self.start_button.setEnabled(not self.controller.is_running)
        self.test_button.setEnabled(not self.controller.is_running)
        self.stop_button.setEnabled(self.controller.is_running)

    def _session_finished(self, session: object) -> None:
        self.start_button.setEnabled(True)
        self.test_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        error = getattr(session, "error_message", "")
        self.message.setText(error or f"Phiên {getattr(session, 'session_id', '')} đã kết thúc")

    def update_stats(self, stats: dict) -> None:
        self.sent_packets.set_value(f"{int(stats.get('total_packets', 0)):,}")
        self.sent_bytes.set_value(format_bytes(float(stats.get("total_bytes", 0))))
        self.current_rate.set_value(f"{float(stats.get('packets_per_second', 0)):,.1f} packet/s")
        self.elapsed.set_value(f"{float(stats.get('elapsed_seconds', 0)):.1f} s")
