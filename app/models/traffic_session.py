"""Traffic session result persisted after every run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(slots=True)
class TrafficSession:
    session_id: str
    started_at: str
    ended_at: str
    destination_ip: str
    destination_port: int
    protocol: str
    scenario: str
    total_packets: int
    total_bytes: int
    successful_connections: int
    failed_connections: int
    duration_seconds: float
    status: str
    error_message: str = ""

    @classmethod
    def new_id(cls) -> str:
        return uuid4().hex[:12].upper()

    @staticmethod
    def timestamp() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
