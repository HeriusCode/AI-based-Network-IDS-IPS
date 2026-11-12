"""Validated traffic generation configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.utils.constants import (
    MAX_CONNECTIONS,
    MAX_DURATION,
    MAX_PACKET_RATE,
    MAX_PACKET_SIZE,
    MIN_CONNECTIONS,
    MIN_DURATION,
    MIN_PACKET_RATE,
    MIN_PACKET_SIZE,
    SUPPORTED_PROTOCOLS,
    SUPPORTED_SCENARIOS,
)


@dataclass(slots=True)
class TrafficConfig:
    destination_ip: str
    destination_port: int
    protocol: str = "TCP"
    scenario: str = "NORMAL"
    duration: int = 30
    packet_rate: int = 100
    packet_size: int = 512
    number_connections: int = 10
    source_host: str = "Local"
    target_host: str = "Local"

    def normalized(self) -> "TrafficConfig":
        self.destination_ip = self.destination_ip.strip()
        self.protocol = self.protocol.strip().upper()
        self.scenario = self.scenario.strip().upper()
        self.source_host = self.source_host.strip() or "Local"
        self.target_host = self.target_host.strip() or "Local"
        return self

    def validate_ranges(self) -> list[str]:
        errors: list[str] = []
        if self.protocol not in SUPPORTED_PROTOCOLS:
            errors.append(f"Giao thức phải thuộc: {', '.join(SUPPORTED_PROTOCOLS)}")
        if self.scenario not in SUPPORTED_SCENARIOS:
            errors.append(f"Kịch bản phải thuộc: {', '.join(SUPPORTED_SCENARIOS)}")
        if not MIN_DURATION <= self.duration <= MAX_DURATION:
            errors.append(f"Thời lượng phải từ {MIN_DURATION} đến {MAX_DURATION} giây")
        if not MIN_PACKET_RATE <= self.packet_rate <= MAX_PACKET_RATE:
            errors.append(f"Tốc độ phải từ {MIN_PACKET_RATE} đến {MAX_PACKET_RATE} packet/s")
        if not MIN_PACKET_SIZE <= self.packet_size <= MAX_PACKET_SIZE:
            errors.append(f"Kích thước gói phải từ {MIN_PACKET_SIZE} đến {MAX_PACKET_SIZE} byte")
        if not MIN_CONNECTIONS <= self.number_connections <= MAX_CONNECTIONS:
            errors.append(f"Số kết nối phải từ {MIN_CONNECTIONS} đến {MAX_CONNECTIONS}")
        if self.protocol != "TCP" and self.scenario == "CONNECTION_BURST":
            errors.append("Connection Burst chỉ hỗ trợ TCP")
        return errors

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
