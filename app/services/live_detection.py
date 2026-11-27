"""Thread-safe, bounded results from actual Mininet packet captures."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.services.ai_client import AiApiError, AiClient


class LiveDetectionService(QObject):
    changed = Signal(object)
    heartbeat = Signal(object)

    ACTIVE_FLOW_TTL_SECONDS = 5.0
    HEARTBEAT_INTERVAL_MS = 1_000

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}
        self._order: deque[str] = deque()
        self._limit = 500
        self._client = AiClient(timeout=10.0)
        self._traffic_points: deque[dict[str, Any]] = deque(maxlen=600)
        self._flow_counters: dict[str, tuple[int, float, float]] = {}
        self._flow_seen_at: dict[str, float] = {}
        self._last_ingest_at = 0.0
        self._telemetry_started = False
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(self.HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._heartbeat_tick)
        self._heartbeat_timer.start()

    def ingest(self, flow: dict[str, Any]) -> dict[str, Any]:
        return self.ingest_many([flow])[0]

    def ingest_many(self, flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(flows, list) or not 1 <= len(flows) <= 20:
            raise ValueError("Mỗi batch cần 1–20 flow")
        for flow in flows:
            if not isinstance(flow, dict) or not isinstance(flow.get("features"), dict):
                raise ValueError("Flow thiếu features")
            if flow.get("source") != "mininet-packet-capture":
                raise ValueError("Nguồn flow không hợp lệ")
            session_id = str(flow.get("session_id", ""))
            flow_id = str(flow.get("flow_id", ""))
            if not session_id or not flow_id or len(session_id) > 64 or len(flow_id) > 128:
                raise ValueError("Session/flow ID không hợp lệ")
            if len(flow["features"]) > 100 or len(str(flow)) > 30000:
                raise ValueError("Flow vượt giới hạn")

        features = [flow["features"] for flow in flows]
        detection = self._client.detect(features)
        predictions = detection["predictions"]
        if len(predictions) != len(flows):
            raise ValueError("AI API trả sai số lượng kết quả")
        attack_indexes = [i for i, item in enumerate(predictions) if item.get("label") == "ATTACK"]
        classifications: dict[int, dict[str, Any]] = {}
        if attack_indexes:
            try:
                response = self._client.classify_attack([features[i] for i in attack_indexes])
                classifications = dict(zip(attack_indexes, response["predictions"]))
            except (AiApiError, KeyError, IndexError, ValueError):
                pass

        results: list[dict[str, Any]] = []
        packets_per_second = 0.0
        bytes_per_second = 0.0
        observed_at = time.monotonic()
        with self._lock:
            self._last_ingest_at = observed_at
            self._telemetry_started = True
        for index, (flow, prediction) in enumerate(zip(flows, predictions, strict=True)):
            features = flow["features"]
            classification = classifications.get(index, {})
            if (
                str(classification.get("label", "")).lower() == "benign"
                or float(classification.get("confidence", 0)) < 0.5
            ):
                classification = {}
            result = {
                "session_id": str(flow["session_id"]),
                "flow_id": str(flow["flow_id"]),
                "timestamp": str(flow.get("timestamp", "")),
                "source_ip": str(flow.get("source_ip", "")),
                "destination_ip": str(flow.get("destination_ip", "")),
                "source_port": int(flow.get("source_port", 0)),
                "destination_port": int(flow.get("destination_port", 0)),
                "protocol": str(flow.get("protocol", "")),
                "packets": int(flow.get("packets", 0)),
                "flow_duration_us": float(features.get("Flow Duration", 0) or 0),
                "bytes_per_second": float(features.get("Flow Bytes/s", 0) or 0),
                "packets_per_second": float(features.get("Flow Packets/s", 0) or 0),
                "feature_quality": str(flow.get("feature_quality", "approximate")),
                "label": str(prediction.get("label", "")),
                "attack_score": float(prediction.get("attack_score", 0)),
                "risk_level": str(prediction.get("risk_level", "")),
                "attack_type": str(classification.get("label") or "Chưa xác định"),
                "type_confidence": float(classification.get("confidence", 0)),
                "model_version": str(detection.get("model_version", "unknown")),
            }
            key = f"{result['session_id']}:{result['flow_id']}"
            packet_count = max(0, int(flow.get("packets", 0)))
            byte_count = max(
                0.0,
                float(features.get("Fwd Packets Length Total", 0) or 0)
                + float(features.get("Bwd Packets Length Total", 0) or 0),
            )
            with self._lock:
                previous = self._flow_counters.get(key)
                if previous is None:
                    elapsed = max(0.25, float(features.get("Flow Duration", 0) or 0) / 1_000_000)
                    delta_packets, delta_bytes = packet_count, byte_count
                else:
                    previous_packets, previous_bytes, previous_at = previous
                    elapsed = max(0.001, observed_at - previous_at)
                    delta_packets = max(0, packet_count - previous_packets)
                    delta_bytes = max(0.0, byte_count - previous_bytes)
                packets_per_second += delta_packets / elapsed
                bytes_per_second += delta_bytes / elapsed
                self._flow_counters[key] = (packet_count, byte_count, observed_at)
                self._flow_seen_at[key] = observed_at
                if key in self._items:
                    self._order.remove(key)
                elif len(self._order) >= self._limit:
                    expired_key = self._order.popleft()
                    self._items.pop(expired_key, None)
                    self._flow_counters.pop(expired_key, None)
                    self._flow_seen_at.pop(expired_key, None)
                self._order.append(key)
                self._items[key] = result
            self.changed.emit(dict(result))
            results.append(result)
        point = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "packets_per_second": packets_per_second,
            "bytes_per_second": bytes_per_second,
        }
        with self._lock:
            self._traffic_points.append(point)
        return results

    def _heartbeat_tick(self) -> None:
        """Advance live time while Mininet is idle without fabricating a flow."""
        now = time.monotonic()
        with self._lock:
            if not self._telemetry_started:
                return
            if now - self._last_ingest_at < self.HEARTBEAT_INTERVAL_MS / 1000 * 0.75:
                return
            point = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "packets_per_second": 0.0,
                "bytes_per_second": 0.0,
                "idle": True,
            }
            self._traffic_points.append(point)
            active_flows = sum(
                seen_at >= now - self.ACTIVE_FLOW_TTL_SECONDS
                for seen_at in self._flow_seen_at.values()
            )
        self.heartbeat.emit({**point, "active_flows": active_flows})

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(self._items[key]) for key in reversed(self._order)]

    def active_snapshot(self, max_age_seconds: float | None = None) -> list[dict[str, Any]]:
        """Return only flows that still belong to the current live window."""
        max_age = self.ACTIVE_FLOW_TTL_SECONDS if max_age_seconds is None else max(0.1, max_age_seconds)
        cutoff = time.monotonic() - max_age
        with self._lock:
            return [
                dict(self._items[key])
                for key in reversed(self._order)
                if self._flow_seen_at.get(key, 0.0) >= cutoff
            ]

    def traffic_history(self, limit: int = 120) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in list(self._traffic_points)[-max(1, limit):]]
