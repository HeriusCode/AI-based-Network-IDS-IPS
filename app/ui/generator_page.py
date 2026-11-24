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
from app.utils.constants import (
    MAX_CONNECTIONS, MAX_DURATION, MAX_PACKET_RATE, MAX_PACKET_SIZE,
    PORT_SCAN_PORTS, SCENARIO_PRESETS,
)
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
        self._local_destination = self.destination_ip.text()
        self.target_host.currentTextChanged.connect(self._sync_target_ip)
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
        for code, preset in SCENARIO_PRESETS.items():
            self.scenario.addItem(str(preset["title"]), code)
        self.custom_pattern_label = QLabel("Custom Pattern")
        self.custom_pattern = QComboBox()
        self.custom_pattern.addItem("Constant Stream", "CONSTANT")
        self.custom_pattern.addItem("Rate Burst (UDP/ICMP)", "RATE_BURST")
        self.custom_pattern.addItem("Connection Burst (TCP)", "CONNECTION_BURST")
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
        traffic_form.addRow(self.custom_pattern_label, self.custom_pattern)
        traffic_form.addRow("Duration", self.duration)
        traffic_form.addRow("Packet Rate", self.packet_rate)
        traffic_form.addRow("Rate Slider", self.rate_slider)
        traffic_form.addRow("Packet Size", self.packet_size)
        traffic_form.addRow("Number of Connections", self.connections)
        self.scenario_note = QLabel("Chọn kịch bản để nạp thông số lab mẫu")
        self.scenario_note.setObjectName("hint")
        self.scenario_note.setWordWrap(True)
        traffic_form.addRow(self.scenario_note)
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
        self.target_summary = QLabel("Target: —")
        self.target_summary.setObjectName("hint")
        self.target_summary.setWordWrap(True)
        controls.box.addWidget(self.target_summary)
        self.expected_summary = QLabel("AI expected: —")
        self.expected_summary.setObjectName("hint")
        self.expected_summary.setWordWrap(True)
        controls.box.addWidget(self.expected_summary)
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
        self.scenario.currentIndexChanged.connect(self._apply_scenario_preset)
        self.custom_pattern.currentIndexChanged.connect(self._update_custom_controls)
        self.protocol.currentTextChanged.connect(self._update_custom_controls)
        self.source_host.currentTextChanged.connect(self._update_profile_summary)
        self.target_host.currentTextChanged.connect(self._update_profile_summary)
        self.destination_port.valueChanged.connect(self._update_profile_summary)
        self.protocol.currentTextChanged.connect(self._update_profile_summary)
        self._apply_scenario_preset()

    def set_scenario(self, scenario: str) -> None:
        index = self.scenario.findData(scenario)
        if index >= 0:
            if index == self.scenario.currentIndex():
                self._apply_scenario_preset()
            else:
                self.scenario.setCurrentIndex(index)

    def _apply_scenario_preset(self, _index: int = -1) -> None:
        code = str(self.scenario.currentData())
        preset = SCENARIO_PRESETS.get(code)
        if preset is None:
            return
        self.protocol.setCurrentText(str(preset["protocol"]))
        self.duration.setValue(int(preset["duration"]))
        self.packet_rate.setValue(int(preset["packet_rate"]))
        self.packet_size.setValue(int(preset["packet_size"]))
        self.connections.setValue(int(preset["connections"]))
        self.source_host.setCurrentText(str(preset["source"]))
        self.target_host.setCurrentText(str(preset["target"]))
        ports = sorted(set(PORT_SCAN_PORTS) & set(self.controller.config_manager.config.approved_ports))
        default_port = int(preset.get("port", 8080))
        self.destination_port.setValue(default_port if code != "PORT_SCAN" else (8080 if 8080 in ports else (ports[0] if ports else 8080)))
        custom = code == "CUSTOM"
        self.custom_pattern_label.setVisible(custom)
        self.custom_pattern.setVisible(custom)
        self.protocol.setEnabled(code in {"NORMAL", "CUSTOM"})
        self.packet_rate.setEnabled(True)
        self.rate_slider.setEnabled(True)
        self.packet_size.setEnabled(code not in {"DOS", "PORT_SCAN"})
        self.connections.setEnabled(False)
        self.destination_port.setEnabled(code != "PORT_SCAN")
        self.source_host.setEnabled(code != "DDOS")
        self.target_host.setEnabled(True)
        if code == "PORT_SCAN":
            note = f"Thử các port lab: {', '.join(map(str, ports)) or 'chưa có port được phê duyệt'}"
        elif code == "DOS":
            note = "DoS: một host gửi SYN không hoàn tất handshake; gói IP/TCP 40 byte."
        elif code == "DDOS":
            note = "DDoS: h1 và h2 đồng thời gửi UDP burst tới h3; rate được chia đều giữa hai nguồn."
        elif code == "BRUTE_FORCE":
            note = "Brute Force: gửi nhiều lần đăng nhập giả lập tới TCP/22 trong mạng Mininet."
        elif code == "WEB_ATTACK":
            note = "Web Attack: HTTP request SQLi/XSS mẫu chỉ được gửi tới receiver lab trên TCP/8080."
        elif code == "CUSTOM":
            note = "Custom: tự chọn thông số trong giới hạn lab; Constant hỗ trợ mọi protocol, Rate Burst hỗ trợ UDP/ICMP, Connection Burst hỗ trợ TCP."
        else:
            note = str(preset["description"])
        self.scenario_note.setText(note)
        self._update_custom_controls()
        self._update_profile_summary()

    def _update_custom_controls(self, *_args) -> None:
        custom = str(self.scenario.currentData()) == "CUSTOM"
        if not custom:
            self.connections.setEnabled(False)
            return
        protocol = self.protocol.currentText()
        pattern = str(self.custom_pattern.currentData())
        if protocol == "TCP" and pattern == "RATE_BURST":
            self.custom_pattern.setCurrentIndex(self.custom_pattern.findData("CONSTANT"))
            pattern = "CONSTANT"
        elif protocol in {"UDP", "ICMP"} and pattern == "CONNECTION_BURST":
            self.custom_pattern.setCurrentIndex(self.custom_pattern.findData("CONSTANT"))
            pattern = "CONSTANT"
        connection_burst = pattern == "CONNECTION_BURST"
        self.connections.setEnabled(connection_burst)
        self.packet_rate.setEnabled(not connection_burst)
        self.rate_slider.setEnabled(not connection_burst)
        self.destination_port.setEnabled(protocol != "ICMP")
        self._update_profile_summary()

    def _update_profile_summary(self, *_args) -> None:
        if not hasattr(self, "target_summary"):
            return
        code = str(self.scenario.currentData())
        preset = SCENARIO_PRESETS.get(code, {})
        if code == "DDOS":
            target = self.target_host.currentText()
            sources = [host for host in ("h1", "h2", "h3") if host != target]
            source = "+".join(sources)
            if self.source_host.currentText() == target and sources:
                self.source_host.setCurrentText(sources[0])
        else:
            source = self.source_host.currentText()
        port = "ICMP" if self.protocol.currentText() == "ICMP" else str(self.destination_port.value())
        self.target_summary.setText(
            f"Target thực thi: {source} → {self.target_host.currentText()} · {self.protocol.currentText()}/{port}"
        )
        expected = str(preset.get("expected_label", "Phụ thuộc cấu hình"))
        if code == "CUSTOM":
            expected += f" · {self.custom_pattern.currentText()}"
        self.expected_summary.setText(f"AI expected: {expected}")

    def _sync_target_ip(self, target: str) -> None:
        target_ips = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3"}
        if target == "Local":
            self.destination_ip.setReadOnly(False)
            self.destination_ip.setText(self._local_destination)
        else:
            if not self.destination_ip.isReadOnly():
                self._local_destination = self.destination_ip.text()
            self.destination_ip.setText(target_ips[target])
            self.destination_ip.setReadOnly(True)

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
            custom_pattern=str(self.custom_pattern.currentData()),
        )

    def test_configuration(self) -> bool:
        try:
            config = self.build_config()
            remote = config.source_host != "Local" or config.target_host != "Local"
            if remote and (config.source_host == "Local" or config.target_host == "Local"):
                raise ValidationError("Chọn cả Source Host và Target Host trong Mininet")
            if remote and config.source_host == config.target_host:
                raise ValidationError("Host nguồn và đích Mininet phải khác nhau")
            cfg = self.controller.config_manager.config
            validate_traffic_config(config, cfg.allowed_networks, cfg.approved_ports)
        except ValidationError as exc:
            self.status.set_status("Error")
            self.message.setText(str(exc))
            return False
        self.status.set_status("Idle")
        self.message.setText("Cấu hình Mininet hợp lệ" if remote else "Cấu hình hợp lệ và nằm trong phạm vi lab")
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
        if error:
            self.message.setText(error)
        elif self.controller.last_config and self.controller.last_config.source_host != "Local":
            scenario = self.controller.last_config.scenario
            if scenario == "DOS":
                self.message.setText(
                    f"Phiên {getattr(session, 'session_id', '')} kết thúc · "
                    f"đã gửi {int(self.controller.current_stats.get('total_packets', 0))} SYN"
                )
            elif scenario == "PORT_SCAN":
                self.message.setText(
                    f"Phiên {getattr(session, 'session_id', '')} kết thúc · "
                    f"đã thử {int(self.controller.current_stats.get('total_packets', 0))} lần kết nối"
                )
            elif self.controller.last_config.protocol == "ICMP":
                self.message.setText(
                    f"Phiên {getattr(session, 'session_id', '')} kết thúc · "
                    f"đã gửi {int(self.controller.current_stats.get('total_packets', 0))} ICMP Echo"
                )
            else:
                received = self.controller.current_stats.get("received_bytes", 0)
                self.message.setText(
                    f"Phiên {getattr(session, 'session_id', '')} kết thúc · "
                    f"host đích nhận {format_bytes(float(received))}"
                )
        else:
            self.message.setText(f"Phiên {getattr(session, 'session_id', '')} đã kết thúc")

    def update_stats(self, stats: dict) -> None:
        self.sent_packets.set_value(f"{int(stats.get('total_packets', 0)):,}")
        self.sent_bytes.set_value(format_bytes(float(stats.get("total_bytes", 0))))
        self.current_rate.set_value(f"{float(stats.get('packets_per_second', 0)):,.1f} packet/s")
        self.elapsed.set_value(f"{float(stats.get('elapsed_seconds', 0)):.1f} s")
