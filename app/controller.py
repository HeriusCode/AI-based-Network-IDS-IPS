"""Application controller shared by all pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.config import ConfigManager
from app.models.traffic_config import TrafficConfig
from app.models.traffic_session import TrafficSession
from app.services.api_client import ApiClient
from app.services.log_service import LogService
from app.services.traffic_engine import TrafficEngine
from app.services.traffic_worker import TrafficWorker
from app.utils.constants import STATUS_IDLE, STATUS_PREPARING
from app.utils.validators import ValidationError, validate_traffic_config


class AppController(QObject):
    stats_updated = Signal(dict)
    traffic_status_changed = Signal(str)
    session_finished = Signal(object)
    connection_changed = Signal(bool, str)
    configuration_changed = Signal()
    logs_changed = Signal()

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.config_manager = ConfigManager(project_root / "data" / "config.json")
        self.log_service = LogService(project_root / "data" / "traffic_logs.db")
        cfg = self.config_manager.config
        self.api_client = ApiClient(cfg.api_base_url, cfg.connection_timeout, cfg.api_key)
        self.worker: TrafficWorker | None = None
        self.current_status = STATUS_IDLE
        self.current_stats = self.empty_stats()
        self.last_config: TrafficConfig | None = None
        self.connected = False

    @staticmethod
    def empty_stats() -> dict[str, float | int]:
        return {
            "total_packets": 0,
            "total_bytes": 0,
            "packets_per_second": 0.0,
            "bytes_per_second": 0.0,
            "successful_connections": 0,
            "failed_connections": 0,
            "elapsed_seconds": 0.0,
        }

    @property
    def is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def start_traffic(self, config: TrafficConfig) -> None:
        if self.is_running:
            raise ValidationError("Đang có một phiên traffic chạy")
        if config.source_host != "Local" or config.target_host != "Local":
            raise ValidationError(
                "Host Mininet yêu cầu backend điều khiển được xác thực trên Máy 2; "
                "phiên bản hiện tại chỉ chạy traffic trực tiếp từ máy local"
            )
        cfg = self.config_manager.config
        validate_traffic_config(config, cfg.allowed_networks, cfg.approved_ports)
        self.last_config = config
        self.reset_statistics()
        self._set_status(STATUS_PREPARING)
        engine = TrafficEngine(cfg.allowed_networks, cfg.approved_ports)
        self.worker = TrafficWorker(engine, config)
        self.worker.stats_updated.connect(self._on_stats)
        self.worker.status_changed.connect(self._set_status)
        self.worker.session_finished.connect(self._on_session_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def stop_traffic(self) -> None:
        if self.worker is not None:
            self.worker.stop()

    def reset_statistics(self) -> None:
        if self.is_running:
            return
        self.current_stats = self.empty_stats()
        self.stats_updated.emit(dict(self.current_stats))

    def _set_status(self, status: str) -> None:
        self.current_status = status
        self.traffic_status_changed.emit(status)

    def _on_stats(self, stats: dict) -> None:
        self.current_stats = dict(stats)
        self.stats_updated.emit(dict(stats))

    def _on_session_finished(self, session: TrafficSession) -> None:
        if self.config_manager.config.logging_enabled:
            self.log_service.save_session(session)
            self.logs_changed.emit()
        self._set_status(session.status)
        self.session_finished.emit(session)
        self.worker = None

    def update_api_client(self) -> None:
        cfg = self.config_manager.config
        self.api_client.configure(cfg.api_base_url, cfg.connection_timeout, cfg.api_key)

    def configuration_saved(self) -> None:
        self.update_api_client()
        self.configuration_changed.emit()
