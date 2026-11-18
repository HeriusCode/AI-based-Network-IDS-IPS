"""AI-driven mitigation policy engine backed by OS-Ken/OpenFlow."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.services.ips_client import IpsClient


class MitigationService(QObject):
    snapshot_changed = Signal(object)
    action_completed = Signal(bool, str)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.client = IpsClient()
        self.enabled = False
        self.connected = False
        self._operation_lock = threading.Lock()
        self._events: dict[tuple[str, str], deque[tuple[float, int]]] = defaultdict(lambda: deque(maxlen=30))
        self._last_action: dict[tuple[str, str], float] = {}

    def _background(self, operation: Callable[[], Any], *, refresh: bool = False,
                    success_message: str = "") -> None:
        def run() -> None:
            self._operation_lock.acquire()
            try:
                operation()
                if refresh:
                    snapshot = self.client.snapshot()
                    self.connected = True
                    self.enabled = bool(snapshot.get("health", {}).get("enabled"))
                    self.snapshot_changed.emit(snapshot)
                if success_message:
                    self.action_completed.emit(True, success_message)
            except Exception as exc:
                self.connected = False
                self.error.emit(str(exc))
                if success_message:
                    self.action_completed.emit(False, str(exc))
            finally:
                self._operation_lock.release()

        threading.Thread(target=run, name="ips-service", daemon=True).start()

    def refresh_async(self) -> None:
        self._background(lambda: None, refresh=True)

    def set_enabled_async(self, enabled: bool) -> None:
        def operation() -> None:
            self.client.set_enabled(enabled)
            self.enabled = enabled

        message = "Đã kích hoạt IPS tự động" if enabled else "Đã tạm dừng IPS tự động"
        self._background(operation, refresh=True, success_message=message)

    def add_rule_async(self, payload: dict, message: str = "Đã áp dụng chính sách OpenFlow") -> None:
        self._background(lambda: self.client.add_rule(payload), refresh=True, success_message=message)

    def delete_rule_async(self, rule_id: str) -> None:
        self._background(lambda: self.client.delete_rule(rule_id), refresh=True,
                         success_message="Đã gỡ chính sách khỏi Open vSwitch")

    def block_ip_async(self, source_ip: str, *, reason: str = "Analyst block from detection") -> None:
        self.add_rule_async({
            "action": "block_ip", "source_ip": source_ip, "protocol": "any",
            "duration": 60, "reason": reason, "origin": "analyst",
        }, f"Đã chặn {source_ip} trong 60 giây")

    @staticmethod
    def policy_for(flow: dict[str, Any]) -> dict[str, Any] | None:
        """Map an AI result to a bounded mitigation proposal."""
        if flow.get("label") != "ATTACK":
            return None
        score = float(flow.get("attack_score", 0.0))
        family = str(flow.get("attack_type") or "Chưa xác định").strip().lower()
        source = str(flow.get("source_ip") or "")
        destination = str(flow.get("destination_ip") or "")
        protocol = str(flow.get("protocol") or "any").lower()
        port = int(flow.get("destination_port") or 0)
        base = {
            "source_ip": source, "destination_ip": destination or None,
            "protocol": protocol if protocol in {"tcp", "udp", "icmp"} else "any",
            "destination_port": port or None, "duration": 60,
            "origin": "ai-policy", "reason": f"AI: {flow.get('attack_type')} score={score:.3f}",
        }
        if score < 0.65 or family in {"chưa xác định", "unknown", "benign"}:
            return {**base, "action": "alert"}
        if "ddos" in family or family == "dos" or "denial" in family:
            return {**base, "action": "rate_limit", "rate_kbps": 256}
        if "port scan" in family or "portscan" in family:
            return {**base, "action": "defer_port_scan"}
        if "brute" in family:
            return {**base, "action": "defer_brute_force"}
        if any(name in family for name in ("web", "botnet", "infiltration")):
            return {**base, "action": "block_flow"}
        return {**base, "action": "alert"}

    def evaluate_async(self, flow: dict[str, Any]) -> None:
        """Apply only high-confidence, corroborated AI decisions while IPS is enabled."""
        if not self.enabled:
            return
        proposal = self.policy_for(flow)
        if proposal is None:
            return
        source = str(proposal.get("source_ip") or "")
        family = str(flow.get("attack_type") or "unknown").lower()
        now = time.monotonic()
        key = (source, family)
        action = str(proposal["action"])
        if action == "defer_port_scan":
            queue = self._events[key]
            queue.append((now, int(flow.get("destination_port") or 0)))
            while queue and now - queue[0][0] > 15:
                queue.popleft()
            if len({port for _, port in queue if port}) < 3:
                return
            proposal["action"] = "block_ip"
            proposal["protocol"] = "any"
            proposal["destination_ip"] = None
            proposal["destination_port"] = None
        elif action == "defer_brute_force":
            queue = self._events[key]
            queue.append((now, int(flow.get("destination_port") or 0)))
            while queue and now - queue[0][0] > 30:
                queue.popleft()
            if len(queue) < 5:
                return
            proposal["action"] = "block_ip"
            proposal["protocol"] = "any"
            proposal["destination_ip"] = None
            proposal["destination_port"] = None
        if now - self._last_action.get(key, 0) < 30:
            return
        self._last_action[key] = now
        self.add_rule_async(proposal, f"AI đã áp dụng {proposal['action']} cho {source}")

    def close(self) -> None:
        self.client.close()

