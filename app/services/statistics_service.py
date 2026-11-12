"""Thread-safe rolling statistics for the current traffic session."""

from __future__ import annotations

import threading
import time


class StatisticsService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self.started_monotonic = time.monotonic()
            self.total_packets = 0
            self.total_bytes = 0
            self.successful_connections = 0
            self.failed_connections = 0
            self._last_packets = 0
            self._last_bytes = 0
            self._last_sample = self.started_monotonic

    def record_packet(self, byte_count: int) -> None:
        with self._lock:
            self.total_packets += 1
            self.total_bytes += max(0, byte_count)

    def record_connection(self, success: bool) -> None:
        with self._lock:
            if success:
                self.successful_connections += 1
            else:
                self.failed_connections += 1

    def snapshot(self) -> dict[str, float | int]:
        now = time.monotonic()
        with self._lock:
            delta = max(0.001, now - self._last_sample)
            packets_per_second = (self.total_packets - self._last_packets) / delta
            bytes_per_second = (self.total_bytes - self._last_bytes) / delta
            self._last_packets = self.total_packets
            self._last_bytes = self.total_bytes
            self._last_sample = now
            return {
                "total_packets": self.total_packets,
                "total_bytes": self.total_bytes,
                "packets_per_second": packets_per_second,
                "bytes_per_second": bytes_per_second,
                "successful_connections": self.successful_connections,
                "failed_connections": self.failed_connections,
                "elapsed_seconds": max(0.0, now - self.started_monotonic),
            }
