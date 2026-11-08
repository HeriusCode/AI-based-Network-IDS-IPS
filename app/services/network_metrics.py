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
class NetworkSnapshot:
    available: bool
    total_packets: int = 0
    total_bytes: int = 0
    incoming_mbps: float = 0.0
    outgoing_mbps: float = 0.0
    active_connections: int = 0
    packet_errors: int = 0
    dropped_packets: int = 0
    protocol_counts: dict[str, int] = field(default_factory=dict)
    top_remote_ips: tuple[tuple[str, int], ...] = ()
    error: str = ""


class NetworkMetricsCollector:
    """Calculate rates from cumulative OS counters without fabricated samples."""

    CONNECTION_SCAN_INTERVAL = 5.0

    def __init__(self) -> None:
        self._previous_io = None
        self._previous_at = time.monotonic()
        self._last_connection_scan = 0.0
        self._connection_count = 0
        self._protocol_counts: dict[str, int] = {}
        self._top_remote_ips: tuple[tuple[str, int], ...] = ()

    def sample(self) -> NetworkSnapshot:
        if psutil is None:
            return NetworkSnapshot(False, error="Thiếu thư viện psutil")

        try:
            now = time.monotonic()
            io = psutil.net_io_counters()
            elapsed = max(0.001, now - self._previous_at)
            incoming = outgoing = 0.0
            if self._previous_io is not None:
                incoming = max(0, io.bytes_recv - self._previous_io.bytes_recv) * 8 / elapsed / 1_000_000
                outgoing = max(0, io.bytes_sent - self._previous_io.bytes_sent) * 8 / elapsed / 1_000_000

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
                active_connections=self._connection_count,
                packet_errors=io.errin + io.errout,
                dropped_packets=io.dropin + io.dropout,
                protocol_counts=dict(self._protocol_counts),
                top_remote_ips=self._top_remote_ips,
            )
        except Exception as error:
            return NetworkSnapshot(False, error=str(error))

    def _scan_connections(self) -> None:
        protocol_counts: Counter[str] = Counter()
        remote_ips: Counter[str] = Counter()
        active = 0

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
                protocol_counts["DNS"] += 1
            elif ports.intersection({80, 443, 8080, 8443}):
                protocol_counts["HTTP"] += 1
            elif connection.type == socket.SOCK_DGRAM:
                protocol_counts["UDP"] += 1
            elif connection.type == socket.SOCK_STREAM:
                protocol_counts["TCP"] += 1
            else:
                protocol_counts["Khác"] += 1

            remote_ip = getattr(connection.raddr, "ip", "")
            if remote_ip:
                remote_ips[remote_ip] += 1

        self._connection_count = active
        self._protocol_counts = dict(protocol_counts)
        self._top_remote_ips = tuple(remote_ips.most_common(5))
