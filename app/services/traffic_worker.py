"""Qt thread wrapper around the blocking traffic engine."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.models.traffic_config import TrafficConfig
from app.models.traffic_session import TrafficSession
from app.services.traffic_engine import TrafficEngine


class TrafficWorker(QThread):
    stats_updated = Signal(dict)
    status_changed = Signal(str)
    session_finished = Signal(object)

    def __init__(self, engine: TrafficEngine, config: TrafficConfig) -> None:
        super().__init__()
        self.engine = engine
        self.config = config

    def run(self) -> None:
        session: TrafficSession = self.engine.run(
            self.config,
            self.stats_updated.emit,
            self.status_changed.emit,
        )
        self.session_finished.emit(session)

    def stop(self) -> None:
        self.engine.stop()
