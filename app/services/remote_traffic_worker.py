"""Qt worker that runs bounded traffic inside Mininet via an SSH tunnel."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal

from app.config import AppConfig
from app.models.traffic_config import TrafficConfig
from app.models.traffic_session import TrafficSession
from app.services.mininet_client import MininetClient, MininetClientError
from app.services.api_client import ApiClient
from app.utils.constants import PORT_SCAN_PORTS


def agent_scenario(config: TrafficConfig) -> str:
    """Translate desktop profiles to the bounded primitives supported by the VM agent."""
    if config.scenario == "DOS":
        return "SYN_FLOOD"
    if config.scenario != "CUSTOM":
        return config.scenario
    if config.custom_pattern == "RATE_BURST":
        return "UDP_FLOOD" if config.protocol == "UDP" else "ICMP_FLOOD"
    if config.custom_pattern == "CONNECTION_BURST":
        return "CONNECTION_BURST"
    return "NORMAL"


class RemoteTrafficWorker(QThread):
    stats_updated = Signal(dict)
    status_changed = Signal(str)
    session_finished = Signal(object)

    def __init__(self, config: TrafficConfig, app_config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.app_config = app_config
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        started_at = TrafficSession.timestamp()
        started = time.monotonic()
        session_id = TrafficSession.new_id()
        status = "Error"
        error_message = ""
        stats: dict = {
            "total_packets": 0, "total_bytes": 0, "packets_per_second": 0.0,
            "bytes_per_second": 0.0, "successful_connections": 0,
            "failed_connections": 0, "elapsed_seconds": 0.0,
        }
        try:
            ids_api = ApiClient(
                self.app_config.api_base_url,
                timeout=max(15.0, self.app_config.connection_timeout),
                api_key=self.app_config.api_key,
            )
            ids_health = ids_api.health()
            if (
                not ids_health.ok
                or not isinstance(ids_health.data, dict)
                or not ids_health.data.get("live_flow_ingest")
            ):
                raise MininetClientError(
                    "IDS/IPS chưa bật thu flow live. Hãy khởi động lại UI IDS/IPS bản mới."
                )
            supports_batch = bool(ids_health.data.get("batch_flow_ingest"))
            with MininetClient(
                self.app_config.vm_ip, self.app_config.vm_ssh_user,
                self.app_config.vm_agent_port,
            ) as client:
                client.health()
                payload = {
                    "source": self.config.source_host,
                    "target": self.config.target_host,
                    "protocol": self.config.protocol,
                    "scenario": agent_scenario(self.config),
                    "duration": self.config.duration,
                    "packet_rate": self.config.packet_rate,
                    "packet_size": self.config.packet_size,
                    "number_connections": self.config.number_connections,
                    "destination_port": self.config.destination_port,
                    "scan_ports": sorted(set(PORT_SCAN_PORTS) & set(self.app_config.approved_ports))
                    if self.config.scenario == "PORT_SCAN" else [],
                }
                result = client.start(payload)
                session_id = str(result["session_id"])
                self.config.destination_ip = str(result["destination_ip"])
                self.status_changed.emit("Running")
                stop_sent = False
                sequence = 0
                ingested = 0
                detection_error = ""
                while True:
                    if self._stop_event.is_set() and not stop_sent:
                        client.stop(session_id)
                        stop_sent = True
                    result = client.status()
                    if result.get("session_id") != session_id:
                        raise MininetClientError("Phiên Mininet đã bị thay thế trên VM")
                    remote_stats = result.get("stats")
                    if isinstance(remote_stats, dict) and remote_stats:
                        stats.update(remote_stats)
                    stats["received_bytes"] = int(result.get("received_bytes", 0))
                    stats["received_messages"] = int(result.get("received_messages", 0))
                    self.stats_updated.emit(dict(stats))
                    if not detection_error:
                        captured = client.flows(sequence)
                        if captured.get("session_id") != session_id:
                            raise MininetClientError("Flow capture thuộc phiên Mininet khác")
                        entries = captured.get("flows", [])
                        for offset in range(0, len(entries), 20):
                            chunk = entries[offset:offset + 20]
                            flows = [item["flow"] for item in chunk if isinstance(item.get("flow"), dict)]
                            if not flows:
                                sequence = int(chunk[-1]["sequence"])
                                continue
                            if len(flows) == 1 or not supports_batch:
                                for flow in flows:
                                    outcome = ids_api.ingest_flow(flow)
                                    if not outcome.ok:
                                        break
                            else:
                                outcome = ids_api.ingest_flows(flows)
                            if not outcome.ok:
                                detection_error = (
                                    f"IDS/IPS không nhận hoặc không phân tích được flow "
                                    f"(HTTP {outcome.status_code}): {outcome.message}"
                                )
                                break
                            sequence = int(chunk[-1]["sequence"])
                            ingested += len(flows)
                            stats["analyzed_flow_updates"] = ingested
                            self.stats_updated.emit(dict(stats))
                    status = str(result.get("status", "Error"))
                    if status in {"Completed", "Stopped", "Error"}:
                        error_message = str(result.get("error_message") or "")
                        if status == "Completed" and (detection_error or ingested == 0):
                            status = "Error"
                            error_message = detection_error or "Không bắt được packet trên Mininet host; IDS/IPS chưa có flow live"
                        if status == "Error" and not error_message:
                            error_message = "Phiên Mininet thất bại trên VM"
                        break
                    time.sleep(0.25)
        except (MininetClientError, OSError, KeyError, ValueError) as error:
            status = "Error"
            error_message = str(error)
        stats["elapsed_seconds"] = max(float(stats.get("elapsed_seconds", 0)), time.monotonic() - started)
        self.stats_updated.emit(dict(stats))
        self.session_finished.emit(TrafficSession(
            session_id=session_id,
            started_at=started_at,
            ended_at=TrafficSession.timestamp(),
            destination_ip=self.config.destination_ip,
            destination_port=self.config.destination_port,
            protocol=self.config.protocol,
            scenario=self.config.scenario,
            total_packets=int(stats.get("total_packets", 0)),
            total_bytes=int(stats.get("total_bytes", 0)),
            successful_connections=int(stats.get("successful_connections", 0)),
            failed_connections=int(stats.get("failed_connections", 0)),
            duration_seconds=round(float(stats.get("elapsed_seconds", 0)), 3),
            status=status,
            error_message=error_message,
        ))
