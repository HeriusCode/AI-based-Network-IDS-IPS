"""Machine 2 REST API connection settings."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.services.api_client import ApiClient, ApiResult
from app.ui.widgets import Card, StatusPill
from app.utils.validators import ValidationError, validate_lab_target


class HealthWorker(QThread):
    finished_result = Signal(object)

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        self.finished_result.emit(self.client.health())


class ConnectionPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.health_worker: HealthWorker | None = None
        cfg = controller.config_manager.config

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)
        title = QLabel("Connection Settings")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Cấu hình kênh REST API quản lý tới Máy 2; API port không phải traffic port")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        card = Card("Kết nối tới AI-based Network IDS/IPS", "Endpoint kiểm tra: GET /api/health")
        form = QFormLayout()
        form.setSpacing(12)
        self.server_ip = QLineEdit(cfg.server_ip)
        self.server_port = QSpinBox()
        self.server_port.setRange(1, 65535)
        self.server_port.setValue(cfg.api_port)
        self.api_url = QLineEdit(cfg.api_base_url)
        self.api_url.setReadOnly(True)
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0.5, 30.0)
        self.timeout.setSuffix(" giây")
        self.timeout.setValue(cfg.connection_timeout)
        self.server_ip.textChanged.connect(self._sync_url)
        self.server_port.valueChanged.connect(self._sync_url)
        form.addRow("Server IP Address", self.server_ip)
        form.addRow("Server API Port", self.server_port)
        form.addRow("API Base URL", self.api_url)
        form.addRow("Connection Timeout", self.timeout)
        card.box.addLayout(form)

        actions = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.setObjectName("primaryButton")
        self.test_button.clicked.connect(self.test_connection)
        save = QPushButton("Save Configuration")
        save.setObjectName("successButton")
        save.clicked.connect(self.save_configuration)
        disconnect = QPushButton("Disconnect")
        disconnect.setObjectName("dangerButton")
        disconnect.clicked.connect(self.disconnect)
        actions.addWidget(self.test_button)
        actions.addWidget(save)
        actions.addWidget(disconnect)
        actions.addStretch()
        card.box.addLayout(actions)

        status_row = QHBoxLayout()
        self.status = StatusPill("Disconnected")
        self.message = QLabel("Chưa kiểm tra kết nối")
        self.message.setObjectName("muted")
        status_row.addWidget(self.status)
        status_row.addWidget(self.message)
        status_row.addStretch()
        card.box.addLayout(status_row)
        root.addWidget(card)

        note = Card("Bảo mật thông tin xác thực")
        note.box.addWidget(QLabel("API key chỉ được đọc từ biến môi trường TRAFFIC_GENERATOR_API_KEY và không lưu vào config.json."))
        root.addWidget(note)
        root.addStretch()
        controller.configuration_changed.connect(self.reload_configuration)

    def _sync_url(self) -> None:
        self.api_url.setText(f"http://{self.server_ip.text().strip()}:{self.server_port.value()}")

    def _validate_server(self) -> None:
        validate_lab_target(self.server_ip.text(), self.controller.config_manager.config.allowed_networks)

    def save_configuration(self) -> None:
        try:
            self._validate_server()
        except ValidationError as exc:
            self.message.setText(str(exc))
            self.status.set_status("Error")
            return
        cfg = self.controller.config_manager.config
        cfg.server_ip = self.server_ip.text().strip()
        cfg.api_port = self.server_port.value()
        cfg.connection_timeout = self.timeout.value()
        self.controller.config_manager.save(cfg)
        self.controller.configuration_saved()
        self.message.setText("Đã lưu cấu hình")

    def reload_configuration(self) -> None:
        cfg = self.controller.config_manager.config
        self.server_ip.setText(cfg.server_ip)
        self.server_port.setValue(cfg.api_port)
        self.timeout.setValue(cfg.connection_timeout)
        self._sync_url()

    def test_connection(self) -> None:
        try:
            self._validate_server()
        except ValidationError as exc:
            self._handle_result(ApiResult(False, None, str(exc)))
            return
        client = ApiClient(
            self.api_url.text(),
            self.timeout.value(),
            self.controller.config_manager.config.api_key,
        )
        self.test_button.setEnabled(False)
        self.message.setText("Đang kiểm tra /api/health...")
        self.health_worker = HealthWorker(client)
        self.health_worker.finished_result.connect(self._handle_result)
        self.health_worker.finished.connect(self._cleanup_worker)
        self.health_worker.start()

    def _handle_result(self, result: ApiResult) -> None:
        self.test_button.setEnabled(True)
        self.controller.connected = result.ok
        self.status.set_status("Connected" if result.ok else "Disconnected")
        self.message.setText(result.message)
        self.controller.connection_changed.emit(result.ok, result.message)

    def _cleanup_worker(self) -> None:
        worker = self.health_worker
        self.health_worker = None
        if worker is not None:
            worker.deleteLater()

    def disconnect(self) -> None:
        self.controller.connected = False
        self.status.set_status("Disconnected")
        self.message.setText("Đã ngắt trạng thái kết nối quản lý")
        self.controller.connection_changed.emit(False, "Disconnected")
