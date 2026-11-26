"""Discover the IDS endpoint and Mininet VM across Tailscale or local VMware."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import psutil

from app.core.server_config import primary_local_ipv4


@dataclass(frozen=True, slots=True)
class NetworkDiscoveryResult:
    server_ip: str
    vm_ip: str
    vm_hostname: str
    traffic_config_path: str = ""
    vm_user: str = "root"
    agent_port: int = 9000
    connection_source: str = "ssh"
    agent_url: str = ""


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
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        blocks = re.findall(r"lease\s+(\d+\.\d+\.\d+\.\d+)\s*\{(.*?)\}", content, re.DOTALL)
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


def _vmrun_executable() -> str:
    configured = os.getenv("VMRUN_CLI", "").strip()
    if configured:
        return str(Path(configured).expanduser())
    located = shutil.which("vmrun")
    if located:
        return located
    for candidate in (
        Path(r"D:\VMware\vmrun.exe"),
        Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "VMware" / "VMware Workstation" / "vmrun.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return "vmrun"


def _vmware_tools_candidates() -> list[str]:
    """Read current guest IPs from running VMware VMs, including bridged DHCP."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        running = subprocess.run(
            [_vmrun_executable(), "list"], capture_output=True, text=True, timeout=5,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if running.returncode != 0:
        return []
    candidates: list[str] = []
    for line in running.stdout.splitlines()[1:]:
        vmx = line.strip()
        if not vmx.lower().endswith(".vmx"):
            continue
        try:
            result = subprocess.run(
                [_vmrun_executable(), "getGuestIPAddress", vmx, "-wait"],
                capture_output=True, text=True, timeout=7, creationflags=flags,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        value = result.stdout.strip()
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if result.returncode == 0 and isinstance(address, ipaddress.IPv4Address):
            text = str(address)
            if text not in candidates:
                candidates.append(text)
    return candidates


def _saved_vm_candidate() -> str | None:
    path = traffic_generator_config_path()
    try:
        value = str(json.loads(path.read_text(encoding="utf-8")).get("vm_ip", ""))
    except (OSError, ValueError, TypeError):
        return None
    return value if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value) else None


def _ipv4_values(values: object) -> list[str]:
    result: list[str] = []
    if not isinstance(values, list):
        return result
    for value in values:
        try:
            address = ipaddress.ip_address(str(value))
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv4Address):
            result.append(str(address))
    return result


def _tailscale_executable() -> str:
    configured = os.getenv("TAILSCALE_CLI", "").strip()
    if configured:
        return str(Path(configured).expanduser())
    located = shutil.which("tailscale")
    if located:
        return located
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        root = os.getenv(variable, "").strip()
        if not root:
            continue
        candidate = Path(root) / "Tailscale" / "tailscale.exe"
        if candidate.is_file():
            return str(candidate)
    return "tailscale"


def _local_tailscale_ip() -> str | None:
    """Read the Tailscale adapter when its CLI is unavailable on Windows."""
    network = ipaddress.ip_network("100.64.0.0/10")
    try:
        interfaces = psutil.net_if_addrs()
    except (psutil.Error, OSError):
        return None
    for name, addresses in interfaces.items():
        if "tailscale" not in name.lower():
            continue
        for entry in addresses:
            try:
                address = ipaddress.IPv4Address(entry.address)
            except ValueError:
                continue
            if address in network:
                return str(address)
    return None


def _tailscale_addresses(hostname: str = "duy-server") -> tuple[str | None, list[str]]:
    """Return this machine's Tailscale IPv4 and matching online peer addresses."""
    try:
        result = subprocess.run(
            [_tailscale_executable(), "status", "--json"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return _local_tailscale_ip(), []
    if result.returncode != 0:
        return _local_tailscale_ip(), []
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError):
        return _local_tailscale_ip(), []

    local_addresses = _ipv4_values(payload.get("TailscaleIPs"))
    peers = payload.get("Peer", {})
    matches: list[str] = []
    entries = peers.values() if isinstance(peers, dict) else peers if isinstance(peers, list) else []
    wanted = hostname.rstrip(".").lower()
    for peer in entries:
        if not isinstance(peer, dict) or peer.get("Online") is False:
            continue
        names = {
            str(peer.get("HostName", "")).rstrip(".").lower(),
            str(peer.get("DNSName", "")).rstrip(".").lower(),
        }
        if not any(name == wanted or name.startswith(wanted + ".") for name in names if name):
            continue
        for address in _ipv4_values(peer.get("TailscaleIPs")):
            if address not in matches:
                matches.append(address)
    return (local_addresses[0] if local_addresses else _local_tailscale_ip()), matches


def _agent_health(base_url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(base_url.rstrip("/") + "/api/health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, TypeError):
        return False
    hosts = payload.get("hosts") if isinstance(payload, dict) else None
    return (
        payload.get("status") in {"ok", "mininet_unavailable"}
        and isinstance(hosts, dict)
        and {"h1", "h2", "h3"}.issubset(hosts)
    )


def _ssh_users() -> list[str]:
    configured = os.getenv("MININET_VM_USER", "").strip()
    return list(dict.fromkeys(value for value in (configured, "trafficuser", "root") if value))


def _tunnel_ssh_destination(local_port: int, agent_port: int) -> tuple[str, str] | None:
    """Find the VM address and SSH user for an active local agent tunnel."""
    try:
        processes = psutil.process_iter(["name", "cmdline"])
        for process in processes:
            try:
                name = str(process.info["name"] or "").lower()
                args = [str(arg) for arg in process.info["cmdline"] or []]
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            if name not in {"ssh", "ssh.exe"}:
                continue
            forwardings = [
                args[index + 1] if arg == "-L" and index + 1 < len(args) else arg[2:]
                for index, arg in enumerate(args)
                if arg == "-L" or arg.startswith("-L")
            ]
            target = f"127.0.0.1:{local_port}:127.0.0.1:{agent_port}"
            if target not in forwardings:
                continue
            for arg in reversed(args):
                if "@" not in arg:
                    continue
                user, host = arg.rsplit("@", 1)
                if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
                    continue
                try:
                    address = ipaddress.IPv4Address(host)
                except ValueError:
                    continue
                return str(address), user
    except (psutil.Error, OSError):
        return None
    return None


def _verify_mininet_vm(
    ip: str,
    hostname: str = "duy-server",
    agent_port: int = 9000,
) -> str | None:
    """Return the first SSH user that verifies the expected VM and agent."""
    key_path = Path(
        os.getenv("MININET_SSH_KEY", str(Path.home() / ".ssh" / "traffic-generator-vm"))
    ).expanduser()
    if not key_path.is_file():
        return None
    for user in _ssh_users():
        command = [
            "ssh", "-i", str(key_path), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=3",
            f"{user}@{ip}",
            (
                "printf '%s\\n' \"$(hostname)\"; "
                f"curl -fsS --max-time 2 http://127.0.0.1:{agent_port}/api/health"
            ),
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=7,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) < 2 or lines[0].lower() != hostname.lower():
            continue
        try:
            health = json.loads(lines[-1])
        except (ValueError, TypeError):
            continue
        hosts = health.get("hosts")
        if (
            health.get("status") in {"ok", "mininet_unavailable"}
            and isinstance(hosts, dict)
            and {"h1", "h2", "h3"}.issubset(hosts)
        ):
            return user
    return None


def discover_network(hostname: str = "duy-server") -> NetworkDiscoveryResult:
    """Discover Tailscale first, then fall back to saved and VMware addresses."""
    agent_port = int(os.getenv("MININET_AGENT_PORT", "9000"))
    local_tailscale_ip, tailscale_peers = _tailscale_addresses(hostname)
    server_ip = local_tailscale_ip or primary_local_ipv4()
    config_path = traffic_generator_config_path()
    shared_config = str(config_path) if config_path.is_file() else ""

    configured_url = os.getenv("MININET_AGENT_URL", "").strip().rstrip("/")
    local_urls = [configured_url] if configured_url else []
    if "http://127.0.0.1:19000" not in local_urls:
        local_urls.append("http://127.0.0.1:19000")
    for url in local_urls:
        if url and _agent_health(url):
            tunnel_destination = (
                _tunnel_ssh_destination(19000, agent_port)
                if url == "http://127.0.0.1:19000" else None
            )
            vm_ip = os.getenv("MININET_VM_IP", "").strip()
            if not vm_ip:
                vm_ip = (
                    (tunnel_destination[0] if tunnel_destination else "")
                    or (tailscale_peers[0] if tailscale_peers else "")
                    or _saved_vm_candidate()
                    or ""
                )
            if not vm_ip:
                raise RuntimeError(
                    "Tunnel Mininet đang hoạt động nhưng không xác định được IP VM. "
                    "Hãy đặt MININET_VM_IP hoặc nhập IP Tailscale VM trong Cài đặt."
                )
            return NetworkDiscoveryResult(
                server_ip=server_ip,
                vm_ip=vm_ip,
                vm_hostname=hostname,
                traffic_config_path=shared_config,
                vm_user=os.getenv(
                    "MININET_VM_USER",
                    tunnel_destination[1] if tunnel_destination else "trafficuser",
                ),
                agent_port=agent_port,
                connection_source="local_tunnel",
                agent_url=url,
            )

    candidates: list[tuple[str, str]] = []
    configured_ip = os.getenv("MININET_VM_IP", "").strip()
    sources = (
        [(configured_ip, "environment")] if configured_ip else []
    ) + [(value, "tailscale") for value in tailscale_peers]
    sources.extend((value, "vmware_tools") for value in _vmware_tools_candidates())
    saved = _saved_vm_candidate()
    if saved:
        sources.append((saved, "saved"))
    sources.extend((value, "vmware_dhcp") for value in _lease_candidates(hostname))
    sources.extend((value, "vmware_arp") for value in _arp_candidates())
    for value, source in sources:
        if value and value not in {item[0] for item in candidates}:
            candidates.append((value, source))

    for candidate, source in candidates:
        direct_url = f"http://{candidate}:{agent_port}"
        if _agent_health(direct_url, timeout=1.5):
            return NetworkDiscoveryResult(
                server_ip=server_ip,
                vm_ip=candidate,
                vm_hostname=hostname,
                traffic_config_path=shared_config,
                vm_user=os.getenv("MININET_VM_USER", "root"),
                agent_port=agent_port,
                connection_source="direct_agent",
                agent_url=direct_url,
            )
        user = _verify_mininet_vm(candidate, hostname, agent_port)
        if user:
            return NetworkDiscoveryResult(
                server_ip=server_ip,
                vm_ip=candidate,
                vm_hostname=hostname,
                traffic_config_path=shared_config,
                vm_user=user,
                agent_port=agent_port,
                connection_source=source,
            )
    raise RuntimeError(
        "Không tìm thấy VM 'duy-server'. Hãy bật Tailscale trên hai máy hoặc mở tunnel "
        "127.0.0.1:19000 và kiểm tra SSH key traffic-generator-vm."
    )


def sync_traffic_generator_config(
    result: NetworkDiscoveryResult,
    server_port: int = 8000,
) -> Path | None:
    """Update a colocated Traffic Generator config; remote installations are optional."""
    if not result.traffic_config_path:
        return None
    path = Path(result.traffic_config_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError(f"Không đọc được cấu hình Traffic Generator: {path}") from error
    payload["server_ip"] = result.server_ip
    payload["api_port"] = int(server_port)
    payload["vm_ip"] = result.vm_ip
    payload["vm_ssh_user"] = result.vm_user
    networks = [str(value) for value in payload.get("allowed_networks", [])]
    if "100.64.0.0/10" not in networks:
        networks.append("100.64.0.0/10")
    payload["allowed_networks"] = networks
    updated = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if path.read_text(encoding="utf-8") != updated:
        path.write_text(updated, encoding="utf-8")
    return path
