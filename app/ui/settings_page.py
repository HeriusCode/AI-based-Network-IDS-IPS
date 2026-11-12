"""System, IDS/IPS server and authorized-lab settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.ui.widgets import Card
from app.utils.network import local_ipv4_addresses, primary_local_ipv4
from app.utils.validators import ValidationError, validate_lab_target


class SettingsPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        cfg = controller.config_manager.config

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)

        title = QLabel("Cài đặt hệ thống")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Thiết lập địa chỉ Máy 1, máy chủ AI-based Network IDS/IPS và phạm vi lab được phép")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        columns = QGridLayout()
        columns.setHorizontalSpacing(14)
        columns.setVerticalSpacing(14)

        server = Card(
            "AI-based Network IDS/IPS Server",
            "Máy 2 nhận yêu cầu quản lý qua REST API. API Port không phải cổng tạo traffic.",
        )
        server_form = QFormLayout()
        server_form.setSpacing(11)

        self.local_ip = QLineEdit(primary_local_ipv4())
        self.local_ip.setReadOnly(True)
        self.local_ip.setObjectName("readOnlyInput")
        refresh_ip = QPushButton("Tự động lấy IP")
        refresh_ip.setObjectName("secondaryButton")
        refresh_ip.clicked.connect(self.refresh_local_ip)
        local_row = QWidget()
        local_layout = QHBoxLayout(local_row)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(8)
        local_layout.addWidget(self.local_ip, 1)
        local_layout.addWidget(refresh_ip)

        self.server_ip = QLineEdit(cfg.server_ip)
        self.server_ip.setPlaceholderText("Ví dụ: 192.168.1.20")
        use_local = QPushButton("Dùng IP máy này")
        use_local.setObjectName("secondaryButton")
        use_local.clicked.connect(self.use_local_as_server)
        server_row = QWidget()
        server_layout = QHBoxLayout(server_row)
        server_layout.setContentsMargins(0, 0, 0, 0)
        server_layout.setSpacing(8)
        server_layout.addWidget(self.server_ip, 1)
        server_layout.addWidget(use_local)

        self.api_port = QSpinBox()
        self.api_port.setRange(1, 65535)
        self.api_port.setValue(cfg.api_port)
        self.api_url = QLineEdit()
        self.api_url.setReadOnly(True)
        self.api_url.setObjectName("readOnlyInput")
        self.server_ip.textChanged.connect(self.sync_api_url)
        self.api_port.valueChanged.connect(self.sync_api_url)

        server_form.addRow("Local IP (Máy 1)", local_row)
        server_form.addRow("Server IP (Máy 2)", server_row)
        server_form.addRow("API Server Port", self.api_port)
        server_form.addRow("API Base URL", self.api_url)
        server.box.addLayout(server_form)

        defaults = Card("Mặc định tạo lưu lượng", "Các giá trị được dùng khi tạo một phiên traffic mới")
        defaults_form = QFormLayout()
        defaults_form.setSpacing(11)
        self.theme = QComboBox()
        self.theme.addItems(["Dark"])
        self.duration = QSpinBox()
        self.duration.setRange(5, 120)
        self.duration.setSuffix(" giây")
        self.duration.setValue(cfg.default_duration)
        self.rate = QSpinBox()
        self.rate.setRange(1, 1000)
        self.rate.setSuffix(" packet/s")
        self.rate.setValue(cfg.default_packet_rate)
        self.size = QSpinBox()
        self.size.setRange(32, 1472)
        self.size.setSuffix(" byte")
        self.size.setValue(cfg.default_packet_size)
        self.logging = QCheckBox("Lưu lịch sử phiên vào SQLite")
        self.logging.setChecked(cfg.logging_enabled)
        defaults_form.addRow("Giao diện", self.theme)
        defaults_form.addRow("Thời lượng", self.duration)
        defaults_form.addRow("Tốc độ gói tin", self.rate)
        defaults_form.addRow("Kích thước gói", self.size)
        defaults_form.addRow("Nhật ký", self.logging)
        defaults.box.addLayout(defaults_form)

        columns.addWidget(server, 0, 0)
        columns.addWidget(defaults, 0, 1)
        columns.setColumnStretch(0, 3)
        columns.setColumnStretch(1, 2)
        root.addLayout(columns)

        safety = Card(
            "Phạm vi Authorized Lab",
            "Traffic Engine chỉ cho phép các mạng và cổng bên dưới. Server IP cũng phải nằm trong phạm vi này.",
        )
        safety_form = QFormLayout()
        safety_form.setSpacing(11)
        self.networks = QLineEdit(", ".join(cfg.allowed_networks))
        self.ports = QLineEdit(", ".join(str(port) for port in cfg.approved_ports))
        safety_form.addRow("Allowed Networks (CIDR)", self.networks)
        safety_form.addRow("Approved Ports", self.ports)
        safety.box.addLayout(safety_form)

        actions = QHBoxLayout()
        save = QPushButton("Lưu cấu hình")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save)
        self.message = QLabel("")
        self.message.setObjectName("muted")
        actions.addWidget(save)
        actions.addWidget(self.message)
        actions.addStretch()
        safety.box.addLayout(actions)
        root.addWidget(safety)
        root.addStretch()

        controller.configuration_changed.connect(self.reload_configuration)
        self.refresh_local_ip()
        self.sync_api_url()

    def refresh_local_ip(self) -> None:
        addresses = local_ipv4_addresses()
        self.local_ip.setText(addresses[0])
        self.local_ip.setToolTip("IPv4 phát hiện được:\n" + "\n".join(addresses))

    def use_local_as_server(self) -> None:
        self.server_ip.setText(self.local_ip.text())

    def sync_api_url(self) -> None:
        self.api_url.setText(f"http://{self.server_ip.text().strip()}:{self.api_port.value()}")

    def reload_configuration(self) -> None:
        cfg = self.controller.config_manager.config
        self.server_ip.setText(cfg.server_ip)
        self.api_port.setValue(cfg.api_port)
        self.duration.setValue(cfg.default_duration)
        self.rate.setValue(cfg.default_packet_rate)
        self.size.setValue(cfg.default_packet_size)
        self.logging.setChecked(cfg.logging_enabled)
        self.networks.setText(", ".join(cfg.allowed_networks))
        self.ports.setText(", ".join(str(port) for port in cfg.approved_ports))
        self.refresh_local_ip()
        self.sync_api_url()

    def save(self) -> None:
        try:
            networks = [value.strip() for value in self.networks.text().split(",") if value.strip()]
            ports = sorted({int(value.strip()) for value in self.ports.text().split(",") if value.strip()})
            if not ports or any(port < 1 or port > 65535 for port in ports):
                raise ValidationError("Danh sách port phải chứa giá trị từ 1 đến 65535")
            validate_lab_target(self.server_ip.text(), networks)
        except (ValueError, ValidationError) as exc:
            self._show_message(str(exc), "errorText")
            return

        cfg = self.controller.config_manager.config
        cfg.server_ip = self.server_ip.text().strip()
        cfg.api_port = self.api_port.value()
        cfg.default_duration = self.duration.value()
        cfg.default_packet_rate = self.rate.value()
        cfg.default_packet_size = self.size.value()
        cfg.logging_enabled = self.logging.isChecked()
        cfg.allowed_networks = networks
        cfg.approved_ports = ports
        self.controller.config_manager.save(cfg)
        self.controller.configuration_saved()
        self._show_message("Đã lưu và đồng bộ IP/port tới toàn bộ ứng dụng", "successText")

    def _show_message(self, text: str, object_name: str) -> None:
        self.message.setObjectName(object_name)
        self.message.setText(text)
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
