"""Persistent application configuration with secrets kept out of plaintext files."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.utils.constants import DEFAULT_ALLOWED_NETWORKS, DEFAULT_APPROVED_PORTS


@dataclass(slots=True)
class AppConfig:
    server_ip: str = "127.0.0.1"
    api_port: int = 8000
    connection_timeout: float = 3.0
    default_duration: int = 30
    default_packet_rate: int = 100
    default_packet_size: int = 512
    allowed_networks: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_NETWORKS))
    approved_ports: list[int] = field(default_factory=lambda: list(DEFAULT_APPROVED_PORTS))
    logging_enabled: bool = True
    theme: str = "Dark"

    @property
    def api_base_url(self) -> str:
        return f"http://{self.server_ip}:{self.api_port}"

    @property
    def api_key(self) -> str:
        return os.getenv("TRAFFIC_GENERATOR_API_KEY", "")


class ConfigManager:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = self.load()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = set(AppConfig.__dataclass_fields__)
            values = {key: value for key, value in raw.items() if key in allowed}
            return AppConfig(**values)
        except (OSError, ValueError, TypeError):
            return AppConfig()

    def save(self, config: AppConfig | None = None) -> None:
        if config is not None:
            self.config = config
        payload = asdict(self.config)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
