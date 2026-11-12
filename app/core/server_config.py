"""Persistent endpoint configuration for the IDS/IPS API server."""

from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal


def local_ipv4_addresses() -> list[str]:
    """Return usable local IPv4 addresses with the active route first."""
    candidates: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            candidates.append(probe.getsockname()[0])
    except OSError:
        pass

    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.append(entry[4][0])
    except OSError:
        pass

    result: list[str] = []
    for value in candidates:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv4Address) and not address.is_unspecified and value not in result:
            result.append(value)

    result.sort(key=lambda value: ipaddress.ip_address(value).is_loopback)
    return result or ["127.0.0.1"]


def primary_local_ipv4() -> str:
    return local_ipv4_addresses()[0]


@dataclass(slots=True)
class ServerConfig:
    server_ip: str
    server_port: int = 8000

    @property
    def base_url(self) -> str:
        return f"http://{self.server_ip}:{self.server_port}"


class ServerConfigManager(QObject):
    """Load, validate and broadcast server endpoint changes."""

    changed = Signal(str, int)

    def __init__(self, path: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        project_root = Path(__file__).resolve().parents[2]
        self.path = path or project_root / "server_config.json"
        self.config = self._load()

    def _load(self) -> ServerConfig:
        fallback = ServerConfig(primary_local_ipv4(), 8000)
        if not self.path.exists():
            return fallback
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            server_ip = str(ipaddress.IPv4Address(str(payload.get("server_ip", fallback.server_ip))))
            server_port = int(payload.get("server_port", fallback.server_port))
            if not 1 <= server_port <= 65535:
                raise ValueError("Port ngoài phạm vi")
            return ServerConfig(server_ip, server_port)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return fallback

    def save(self, server_ip: str, server_port: int) -> ServerConfig:
        normalized_ip = str(ipaddress.IPv4Address(server_ip.strip()))
        normalized_port = int(server_port)
        if not 1 <= normalized_port <= 65535:
            raise ValueError("Port phải nằm trong khoảng 1–65535.")

        config = ServerConfig(normalized_ip, normalized_port)
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.config = config
        self.changed.emit(config.server_ip, config.server_port)
        return config
