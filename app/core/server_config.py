"""Persistent endpoint configuration for the IDS/IPS API server."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.runtime_paths import runtime_config_path


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

    def __init__(
        self,
        path: Path | None = None,
        parent: QObject | None = None,
        *,
        require_local_address: bool | None = None,
    ) -> None:
        super().__init__(parent)
        configured = os.getenv("IDS_SERVER_CONFIG", "").strip()
        self.path = path or (Path(configured).expanduser() if configured else runtime_config_path("server_config.json"))
        self.require_local_address = (path is None) if require_local_address is None else require_local_address
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
            if self.require_local_address and server_ip not in {*local_ipv4_addresses(), "127.0.0.1"}:
                # A repository copied from another computer or a DHCP change
                # must never make this process bind to a foreign address.
                return fallback
            return ServerConfig(server_ip, server_port)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return fallback

    def save(self, server_ip: str, server_port: int) -> ServerConfig:
        normalized_ip = str(ipaddress.IPv4Address(server_ip.strip()))
        normalized_port = int(server_port)
        if not 1 <= normalized_port <= 65535:
            raise ValueError("Port phải nằm trong khoảng 1–65535.")

        config = ServerConfig(normalized_ip, normalized_port)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.config = config
        self.changed.emit(config.server_ip, config.server_port)
        return config
