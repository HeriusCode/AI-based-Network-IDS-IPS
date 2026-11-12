"""Bounded TCP, UDP and ICMP traffic generation for authorized lab networks."""

from __future__ import annotations

import os
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Iterable

from app.models.traffic_config import TrafficConfig
from app.models.traffic_session import TrafficSession
from app.services.statistics_service import StatisticsService
from app.utils.constants import STATUS_COMPLETED, STATUS_ERROR, STATUS_STOPPED
from app.utils.validators import validate_traffic_config

StatsCallback = Callable[[dict[str, float | int]], None]
StatusCallback = Callable[[str], None]


class TrafficEngine:
    """Runs one explicitly bounded traffic session at a time."""

    def __init__(self, allowed_networks: Iterable[str], approved_ports: Iterable[int]) -> None:
        self.allowed_networks = list(allowed_networks)
        self.approved_ports = list(approved_ports)
        self._stop_event = threading.Event()
        self._active_socket: socket.socket | None = None

    def stop(self) -> None:
        self._stop_event.set()
        active = self._active_socket
        if active is not None:
            try:
                active.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                active.close()
            except OSError:
                pass

    @staticmethod
    def _checksum(data: bytes) -> int:
        if len(data) % 2:
            data += b"\x00"
        total = sum(struct.unpack(f"!{len(data) // 2}H", data))
        total = (total >> 16) + (total & 0xFFFF)
        total += total >> 16
        return (~total) & 0xFFFF

    def _icmp_packet(self, payload_size: int, sequence: int) -> bytes:
        payload = os.urandom(max(0, payload_size - 8))
        header = struct.pack("!BBHHH", 8, 0, 0, os.getpid() & 0xFFFF, sequence & 0xFFFF)
        checksum = self._checksum(header + payload)
        return struct.pack("!BBHHH", 8, 0, checksum, os.getpid() & 0xFFFF, sequence & 0xFFFF) + payload

    def _connection_attempt(self, config: TrafficConfig, payload: bytes) -> tuple[bool, int]:
        if self._stop_event.is_set():
            return False, 0
        try:
            with socket.create_connection(
                (config.destination_ip, config.destination_port), timeout=0.5
            ) as connection:
                connection.settimeout(0.5)
                connection.sendall(payload)
            return True, len(payload)
        except OSError:
            return False, 0

    def _run_connection_burst(
        self,
        config: TrafficConfig,
        stats: StatisticsService,
        started: float,
        callback: StatsCallback,
    ) -> None:
        payload = os.urandom(config.packet_size)
        next_batch = started
        with ThreadPoolExecutor(max_workers=config.number_connections) as executor:
            while not self._stop_event.is_set() and time.monotonic() - started < config.duration:
                now = time.monotonic()
                if now < next_batch:
                    self._stop_event.wait(min(0.05, next_batch - now))
                    continue
                futures = [
                    executor.submit(self._connection_attempt, config, payload)
                    for _ in range(config.number_connections)
                ]
                for future in futures:
                    if self._stop_event.is_set():
                        break
                    success, byte_count = future.result()
                    stats.record_connection(success)
                    if success:
                        stats.record_packet(byte_count)
                callback(stats.snapshot())
                next_batch = time.monotonic() + 1.0

    def _current_rate(self, config: TrafficConfig, elapsed: float) -> int:
        if config.scenario != "BURST":
            return config.packet_rate
        progress = min(1.0, elapsed / max(1, config.duration))
        if progress < 0.25:
            factor = 0.5 + progress * 2
        elif progress < 0.75:
            factor = 2.0
        else:
            factor = max(0.5, 2.0 - (progress - 0.75) * 6)
        return max(1, min(1_000, int(config.packet_rate * factor)))

    def _run_packet_stream(
        self,
        config: TrafficConfig,
        stats: StatisticsService,
        started: float,
        callback: StatsCallback,
    ) -> None:
        payload = os.urandom(config.packet_size)
        sequence = 0
        last_update = started
        next_send = started
        transport: socket.socket | None = None

        try:
            if config.protocol == "UDP":
                transport = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                transport.settimeout(0.5)
            elif config.protocol == "ICMP":
                transport = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                transport.settimeout(0.5)
            self._active_socket = transport

            while not self._stop_event.is_set():
                now = time.monotonic()
                elapsed = now - started
                if elapsed >= config.duration:
                    break
                rate = self._current_rate(config, elapsed)
                interval = 1.0 / rate
                if now < next_send:
                    self._stop_event.wait(min(0.02, next_send - now))
                    continue
                try:
                    if config.protocol == "UDP":
                        assert transport is not None
                        sent = transport.sendto(payload, (config.destination_ip, config.destination_port))
                    elif config.protocol == "ICMP":
                        assert transport is not None
                        packet = self._icmp_packet(config.packet_size, sequence)
                        sent = transport.sendto(packet, (config.destination_ip, 0))
                    else:
                        if transport is None:
                            transport = socket.create_connection(
                                (config.destination_ip, config.destination_port), timeout=0.5
                            )
                            transport.settimeout(0.5)
                            self._active_socket = transport
                            stats.record_connection(True)
                        transport.sendall(payload)
                        sent = len(payload)
                    stats.record_packet(sent)
                    sequence += 1
                except OSError:
                    if config.protocol == "TCP":
                        stats.record_connection(False)
                        if transport is not None:
                            try:
                                transport.close()
                            except OSError:
                                pass
                        transport = None
                        self._active_socket = None
                    if self._stop_event.wait(0.05):
                        break
                next_send = max(next_send + interval, time.monotonic())
                if time.monotonic() - last_update >= 0.25:
                    callback(stats.snapshot())
                    last_update = time.monotonic()
        finally:
            self._active_socket = None
            if transport is not None:
                try:
                    transport.close()
                except OSError:
                    pass

    def run(
        self,
        config: TrafficConfig,
        stats_callback: StatsCallback,
        status_callback: StatusCallback,
    ) -> TrafficSession:
        validate_traffic_config(config, self.allowed_networks, self.approved_ports)
        self._stop_event.clear()
        stats = StatisticsService()
        session_id = TrafficSession.new_id()
        started_at = TrafficSession.timestamp()
        started = time.monotonic()
        status = STATUS_COMPLETED
        error_message = ""
        try:
            status_callback("Running")
            if config.scenario == "CONNECTION_BURST":
                if config.protocol != "TCP":
                    raise ValueError("Connection Burst chỉ hỗ trợ TCP")
                self._run_connection_burst(config, stats, started, stats_callback)
            else:
                self._run_packet_stream(config, stats, started, stats_callback)
            if self._stop_event.is_set():
                status = STATUS_STOPPED
        except PermissionError as exc:
            status = STATUS_ERROR
            error_message = "ICMP raw socket yêu cầu quyền Administrator"
            status_callback(error_message)
        except Exception as exc:  # worker boundary: persist every failure
            status = STATUS_ERROR
            error_message = str(exc)
            status_callback(error_message)
        final = stats.snapshot()
        stats_callback(final)
        ended_at = TrafficSession.timestamp()
        return TrafficSession(
            session_id=session_id,
            started_at=started_at,
            ended_at=ended_at,
            destination_ip=config.destination_ip,
            destination_port=config.destination_port,
            protocol=config.protocol,
            scenario=config.scenario,
            total_packets=int(final["total_packets"]),
            total_bytes=int(final["total_bytes"]),
            successful_connections=int(final["successful_connections"]),
            failed_connections=int(final["failed_connections"]),
            duration_seconds=round(float(final["elapsed_seconds"]), 3),
            status=status,
            error_message=error_message,
        )
