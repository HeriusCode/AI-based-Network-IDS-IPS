"""Per-user Mininet agent connection settings."""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.runtime_paths import runtime_config_path


@dataclass(frozen=True, slots=True)
class MininetConfig:
    host: str = ""
    port: int = 9000
    user: str = "root"
    direct: bool = True

    @property
    def agent_url(self) -> str:
        return f"http://{self.host}:{self.port}" if self.direct and self.host else ""


def config_path() -> Path:
    override = os.getenv("MININET_CONFIG", "").strip()
    return Path(override).expanduser() if override else runtime_config_path("mininet_connection.json")


def load_mininet_config() -> MininetConfig:
    env_host = os.getenv("MININET_VM_IP", "").strip()
    env_port = os.getenv("MININET_AGENT_PORT", "").strip()
    env_user = os.getenv("MININET_VM_USER", "").strip()
    direct_url = os.getenv("MININET_AGENT_URL", "").strip().rstrip("/")
    if direct_url:
        from urllib.parse import urlsplit

        parsed = urlsplit(direct_url)
        if parsed.hostname:
            return MininetConfig(parsed.hostname, parsed.port or 80, env_user or "root", True)
    payload: dict = {}
    path = config_path()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError, TypeError):
            payload = {}
    host = env_host or str(payload.get("host") or "").strip()
    port = int(env_port or payload.get("port") or 9000)
    user = env_user or str(payload.get("user") or "root").strip()
    return MininetConfig(host, port, user, bool(payload.get("direct", True)))


def save_mininet_config(host: str, port: int, user: str = "root", *, direct: bool = True) -> MininetConfig:
    normalized_host = str(ipaddress.IPv4Address(host.strip()))
    normalized_port = int(port)
    if not 1 <= normalized_port <= 65535:
        raise ValueError("Agent port phải nằm trong khoảng 1–65535")
    normalized_user = user.strip() or "root"
    config = MininetConfig(normalized_host, normalized_port, normalized_user, direct)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return config
