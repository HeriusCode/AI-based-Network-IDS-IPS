"""Live network counters collected from the local operating system."""

from __future__ import annotations

import socket
import time
from collections import Counter
from dataclasses import dataclass, field

try:
    import psutil
except ImportError:  # The UI remains usable and reports the missing collector.
    psutil = None


@dataclass(frozen=True)
class NetworkConnection:
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    protocol: str
    status: str


@dataclass(frozen=True)
class NetworkInterface:
    name: str
    incoming_mbps: float
    outgoing_mbps: float
    is_up: bool
    ip: str = "—"
    mac: str = "—"


@dataclass(frozen=True)
class NetworkSnapshot:
    available: bool
    total_packets: int = 0
    total_bytes: int = 0
    incoming_mbps: float = 0.0
    outgoing_mbps: float = 0.0
    incoming_pps: float = 0.0
    outgoing_pps: float = 0.0
    active_connections: int = 0
    packet_errors: int = 0
    dropped_packets: int = 0
    protocol_counts: dict[str, int] = field(default_factory=dict)
    top_remote_ips: tuple[tuple[str, int], ...] = ()
    connections: tuple[NetworkConnection, ...] = ()
    interfaces: tuple[NetworkInterface, ...] = ()
    error: str = ""


class NetworkMetricsCollector:
    """Calculate rates from cumulative OS counters without fabricated samples."""

    CONNECTION_SCAN_INTERVAL = 5.0

    def __init__(self) -> None:
        self._previous_io = None
        self._previous_interface_io: dict[str, object] = {}
        self._previous_at = time.monotonic()
        self._last_connection_scan = 0.0
        self._connection_count = 0
        self._protocol_counts: dict[str, int] = {}
        self._top_remote_ips: tuple[tuple[str, int], ...] = ()
        self._connections: tuple[NetworkConnection, ...] = ()

    def sample(self) -> NetworkSnapshot:
        if psutil is None:
            return NetworkSnapshot(False, error="Thiếu thư viện psutil")

        try:
            now = time.monotonic()
            io = psutil.net_io_counters()
            elapsed = max(0.001, now - self._previous_at)
            incoming = outgoing = incoming_pps = outgoing_pps = 0.0
            if self._previous_io is not None:
                incoming = max(0, io.bytes_recv - self._previous_io.bytes_recv) * 8 / elapsed / 1_000_000
                outgoing = max(0, io.bytes_sent - self._previous_io.bytes_sent) * 8 / elapsed / 1_000_000
                incoming_pps = max(0, io.packets_recv - self._previous_io.packets_recv) / elapsed
                outgoing_pps = max(0, io.packets_sent - self._previous_io.packets_sent) / elapsed

            interfaces = self._sample_interfaces(elapsed)

            self._previous_io = io
            self._previous_at = now

            if now - self._last_connection_scan >= self.CONNECTION_SCAN_INTERVAL:
                self._scan_connections()
                self._last_connection_scan = now

            return NetworkSnapshot(
                available=True,
                total_packets=io.packets_recv + io.packets_sent,
                total_bytes=io.bytes_recv + io.bytes_sent,
                incoming_mbps=incoming,
                outgoing_mbps=outgoing,
                incoming_pps=incoming_pps,
                outgoing_pps=outgoing_pps,
                active_connections=self._connection_count,
                packet_errors=io.errin + io.errout,
                dropped_packets=io.dropin + io.dropout,
                protocol_counts=dict(self._protocol_counts),
                top_remote_ips=self._top_remote_ips,
                connections=self._connections,
                interfaces=interfaces,
            )
        except Exception as error:
            return NetworkSnapshot(False, error=str(error))

    def _scan_connections(self) -> None:
        protocol_counts: Counter[str] = Counter()
        remote_ips: Counter[str] = Counter()
        active = 0
        sampled_connections: list[NetworkConnection] = []

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, OSError):
            connections = []

        for connection in connections:
            has_remote = bool(connection.raddr)
            if connection.status == getattr(psutil, "CONN_ESTABLISHED", "ESTABLISHED") or (
                connection.type == socket.SOCK_DGRAM and has_remote
            ):
                active += 1

            # Protocol and peer rankings describe actual remote conversations,
            # not local LISTEN sockets that have no traffic counterpart yet.
            if not has_remote:
                continue

            local_port = getattr(connection.laddr, "port", 0) if connection.laddr else 0
            remote_port = getattr(connection.raddr, "port", 0) if connection.raddr else 0
            ports = {local_port, remote_port}

            if 53 in ports:
                protocol = "DNS"
            elif ports.intersection({80, 443, 8080, 8443}):
                protocol = "HTTP"
            elif connection.type == socket.SOCK_DGRAM:
                protocol = "UDP"
            elif connection.type == socket.SOCK_STREAM:
                protocol = "TCP"
            else:
                protocol = "Khác"
            protocol_counts[protocol] += 1

            remote_ip = getattr(connection.raddr, "ip", "")
            if remote_ip:
                remote_ips[remote_ip] += 1

            local_ip = getattr(connection.laddr, "ip", "") if connection.laddr else ""
            sampled_connections.append(
                NetworkConnection(
                    local_ip=local_ip or "—",
                    local_port=local_port,
                    remote_ip=remote_ip or "—",
                    remote_port=remote_port,
                    protocol=protocol,
                    status=str(connection.status or "ACTIVE"),
                )
            )

        self._connection_count = active
        self._protocol_counts = dict(protocol_counts)
        self._top_remote_ips = tuple(remote_ips.most_common(5))
        self._connections = tuple(sampled_connections[:50])

    def _sample_interfaces(self, elapsed: float) -> tuple[NetworkInterface, ...]:
        counters = psutil.net_io_counters(pernic=True)
        try:
            stats = psutil.net_if_stats()
        except (OSError, AttributeError):
            stats = {}
        try:
            addresses = psutil.net_if_addrs()
        except (OSError, AttributeError):
            addresses = {}

        interfaces: list[NetworkInterface] = []
        for name, current in counters.items():
            previous = self._previous_interface_io.get(name)
            incoming = outgoing = 0.0
            if previous is not None:
                incoming = max(0, current.bytes_recv - previous.bytes_recv) * 8 / elapsed / 1_000_000
                outgoing = max(0, current.bytes_sent - previous.bytes_sent) * 8 / elapsed / 1_000_000
            ip_address = "—"
            mac_address = "—"
            for address in addresses.get(name, ()):
                family = getattr(address, "family", None)
                if family == socket.AF_INET and ip_address == "—":
                    ip_address = address.address
                elif family in (getattr(psutil, "AF_LINK", object()), getattr(socket, "AF_PACKET", object())):
                    mac_address = address.address
            interfaces.append(
                NetworkInterface(
                    name=name,
                    incoming_mbps=incoming,
                    outgoing_mbps=outgoing,
                    is_up=bool(getattr(stats.get(name), "isup", True)),
                    ip=ip_address,
                    mac=mac_address,
                )
            )
        self._previous_interface_io = dict(counters)
        return tuple(interfaces)
