"""Discover DHCP-assigned IDS and Mininet VM addresses on the local lab."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.server_config import primary_local_ipv4


@dataclass(frozen=True, slots=True)
class NetworkDiscoveryResult:
    server_ip: str
    vm_ip: str
    vm_hostname: str
    traffic_config_path: str


def traffic_generator_config_path() -> Path:
    configured = os.getenv("TRAFFIC_GENERATOR_CONFIG", "").strip()
    if configured:
        return Path(configured).expanduser()
    project_root = Path(__file__).resolve().parents[2]
    return project_root.parent / "Traffic Generator" / "data" / "config.json"


def _lease_candidates(hostname: str = "duy-server") -> list[str]:
    program_data = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData"))
    candidates: list[str] = []
    for path in (
        program_data / "VMware" / "vmnetdhcp.leases",
        program_data / "VMware" / "vmnetdhcp.leases~",
    ):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        blocks = re.findall(r"lease\s+(\d+\.\d+\.\d+\.\d+)\s*\{(.*?)\}", text, re.DOTALL)
        for ip, block in reversed(blocks):
            match = re.search(r'client-hostname\s+"([^"]+)"', block)
            if match and match.group(1).lower() == hostname.lower() and ip not in candidates:
                candidates.append(ip)
    return candidates


def _arp_candidates() -> list[str]:
    try:
        result = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    values = re.findall(r"\b192\.168\.201\.\d+\b", result.stdout)
    return list(dict.fromkeys(values))


def _saved_vm_candidate() -> str | None:
    path = traffic_generator_config_path()
    try:
        value = str(json.loads(path.read_text(encoding="utf-8")).get("vm_ip", ""))
    except (OSError, ValueError, TypeError):
        return None
    return value if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value) else None


def _verify_mininet_vm(ip: str, hostname: str = "duy-server") -> bool:
    key_path = Path(os.getenv("MININET_SSH_KEY", str(Path.home() / ".ssh" / "traffic-generator-vm"))).expanduser()
    if not key_path.is_file():
        raise RuntimeError(f"Không tìm thấy SSH key: {key_path}")
    command = [
        "ssh", "-i", str(key_path), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=2",
        f"root@{ip}",
        "printf '%s\\n' \"$(hostname)\"; curl -fsS --max-time 2 http://127.0.0.1:9000/api/health",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=6,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0].lower() != hostname.lower():
        return False
    try:
        health = json.loads(lines[-1])
    except (ValueError, TypeError):
        return False
    hosts = health.get("hosts")
    return health.get("status") == "ok" and isinstance(hosts, dict) and all(hosts.values())


def discover_network(hostname: str = "duy-server") -> NetworkDiscoveryResult:
    candidates: list[str] = []
    saved = _saved_vm_candidate()
    for value in ([saved] if saved else []) + _lease_candidates(hostname) + _arp_candidates():
        if value and value not in candidates and value not in {"192.168.201.1", "192.168.201.2", "192.168.201.254"}:
            candidates.append(value)
    for candidate in candidates:
        if _verify_mininet_vm(candidate, hostname):
            return NetworkDiscoveryResult(
                server_ip=primary_local_ipv4(), vm_ip=candidate,
                vm_hostname=hostname, traffic_config_path=str(traffic_generator_config_path()),
            )
    raise RuntimeError("Không tìm thấy VM 'duy-server' có Mininet agent trong DHCP lease/ARP của VMware VMnet8")


def sync_traffic_generator_config(result: NetworkDiscoveryResult, server_port: int = 8000) -> Path:
    path = Path(result.traffic_config_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError(f"Không đọc được cấu hình Traffic Generator: {path}") from error
    payload["server_ip"] = result.server_ip
    payload["api_port"] = int(server_port)
    payload["vm_ip"] = result.vm_ip
    updated = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if path.read_text(encoding="utf-8") != updated:
        path.write_text(updated, encoding="utf-8")
    return path
