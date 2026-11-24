"""Machine 2 REST API connection settings."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.services.api_client import ApiClient, ApiResult
from app.services.mininet_client import MininetClient, MininetClientError
from app.ui.widgets import Card, StatusPill
from app.utils.validators import ValidationError, validate_lab_target


class HealthWorker(QThread):
    finished_result = Signal(object)

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        self.finished_result.emit(self.client.health())


class VmHealthWorker(QThread):
    finished_result = Signal(bool, str)

    def __init__(self, host: str, user: str, agent_port: int) -> None:
        super().__init__()
        self.host, self.user, self.agent_port = host, user, agent_port

    def run(self) -> None:
        try:
            with MininetClient(self.host, self.user, self.agent_port) as client:
                result = client.health()
            hosts = ", ".join(name for name, ready in result["hosts"].items() if ready)
            self.finished_result.emit(True, f"Mininet VM sẵn sàng: {hosts}")
        except (MininetClientError, KeyError, OSError) as error:
            self.finished_result.emit(False, str(error))


class ConnectionPage(QScrollArea):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.health_worker: HealthWorker | None = None
        self.vm_health_worker: VmHealthWorker | None = None
        cfg = controller.config_manager.config

        self.setObjectName("connectionScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("connectionContent")
        root = QVBoxLayout(content)
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

        vm_card = Card("Mininet VM", "SSH tunnel tới agent chỉ nghe trên localhost của VM")
        vm_form = QFormLayout()
        self.vm_ip = QLineEdit(cfg.vm_ip)
        self.vm_user = QLineEdit(cfg.vm_ssh_user)
        self.vm_port = QSpinBox()
        self.vm_port.setRange(1, 65535)
        self.vm_port.setValue(cfg.vm_agent_port)
        vm_form.addRow("VM IP Address", self.vm_ip)
        vm_form.addRow("SSH User", self.vm_user)
        vm_form.addRow("Agent Port (VM localhost)", self.vm_port)
        vm_card.box.addLayout(vm_form)
        vm_actions = QHBoxLayout()
        self.vm_test_button = QPushButton("Test Mininet VM")
        self.vm_test_button.setObjectName("primaryButton")
        self.vm_test_button.clicked.connect(self.test_vm_connection)
        vm_actions.addWidget(self.vm_test_button)
        vm_save_button = QPushButton("Save VM Configuration")
        vm_save_button.setObjectName("successButton")
        vm_save_button.clicked.connect(self.save_configuration)
        vm_actions.addWidget(vm_save_button)
        vm_actions.addStretch()
        vm_card.box.addLayout(vm_actions)
        vm_status_row = QHBoxLayout()
        self.vm_status = StatusPill("Disconnected")
        self.vm_message = QLabel("Chưa kiểm tra VM")
        self.vm_message.setObjectName("muted")
        self.vm_message.setWordWrap(True)
        vm_status_row.addWidget(self.vm_status)
        vm_status_row.addWidget(self.vm_message)
        vm_status_row.addStretch()
        vm_card.box.addLayout(vm_status_row)
        root.addWidget(vm_card)

        note = Card("Bảo mật thông tin xác thực")
        note_text = QLabel("API key chỉ được đọc từ biến môi trường TRAFFIC_GENERATOR_API_KEY và không lưu vào config.json.")
        note_text.setWordWrap(True)
        note.box.addWidget(note_text)
        root.addWidget(note)
        root.addStretch()
        self.setWidget(content)
        controller.configuration_changed.connect(self.reload_configuration)

    def _sync_url(self) -> None:
        self.api_url.setText(f"http://{self.server_ip.text().strip()}:{self.server_port.value()}")

    def _validate_server(self) -> None:
        validate_lab_target(self.server_ip.text(), self.controller.config_manager.config.allowed_networks)

    def save_configuration(self) -> None:
        try:
            self._validate_server()
            validate_lab_target(self.vm_ip.text(), self.controller.config_manager.config.allowed_networks)
        except ValidationError as exc:
            self.message.setText(str(exc))
            self.status.set_status("Error")
            return
        cfg = self.controller.config_manager.config
        cfg.server_ip = self.server_ip.text().strip()
        cfg.api_port = self.server_port.value()
        cfg.connection_timeout = self.timeout.value()
        cfg.vm_ip = self.vm_ip.text().strip()
        cfg.vm_ssh_user = self.vm_user.text().strip()
        cfg.vm_agent_port = self.vm_port.value()
        self.controller.config_manager.save(cfg)
        self.controller.configuration_saved()
        self.message.setText("Đã lưu cấu hình")
        self.vm_message.setText("Đã lưu cấu hình VM")

    def reload_configuration(self) -> None:
        cfg = self.controller.config_manager.config
        self.server_ip.setText(cfg.server_ip)
        self.server_port.setValue(cfg.api_port)
        self.timeout.setValue(cfg.connection_timeout)
        self.vm_ip.setText(cfg.vm_ip)
        self.vm_user.setText(cfg.vm_ssh_user)
        self.vm_port.setValue(cfg.vm_agent_port)
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

    def test_vm_connection(self) -> None:
        try:
            validate_lab_target(self.vm_ip.text(), self.controller.config_manager.config.allowed_networks)
        except ValidationError as error:
            self._handle_vm_result(False, str(error))
            return
        self.vm_test_button.setEnabled(False)
        self.vm_message.setText("Đang kiểm tra Mininet VM...")
        worker = VmHealthWorker(
            self.vm_ip.text().strip(), self.vm_user.text().strip(),
            self.vm_port.value(),
        )
        self.vm_health_worker = worker
        worker.finished_result.connect(self._handle_vm_result)
        worker.finished.connect(self._cleanup_vm_worker)
        worker.start()

    def _handle_vm_result(self, ok: bool, message: str) -> None:
        self.vm_test_button.setEnabled(True)
        self.vm_status.set_status("Connected" if ok else "Disconnected")
        self.vm_message.setText(message)

    def _cleanup_vm_worker(self) -> None:
        worker, self.vm_health_worker = self.vm_health_worker, None
        if worker is not None:
            worker.deleteLater()
