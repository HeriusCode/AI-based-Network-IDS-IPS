"""Local-only Mininet control API. Access it through an authenticated SSH tunnel.

Run as root inside the VM with Mininet already started.  Only the three known
Mininet hosts and bounded traffic parameters are accepted.
"""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


HOSTS = ("h1", "h2", "h3")
SCAN_PORTS = {22, 53, 80, 443, 8000, 8080}
SCENARIO_PROTOCOLS = {
    "NORMAL": "TCP UDP ICMP", "SYN_FLOOD": "TCP", "UDP_FLOOD": "UDP",
    "ICMP_FLOOD": "ICMP", "PORT_SCAN": "TCP", "CONNECTION_BURST": "TCP",
    "DDOS": "UDP",
    "BRUTE_FORCE": "TCP", "WEB_ATTACK": "TCP",
}
WORKER = Path(__file__).with_name("mininet_worker.py")
CAPTURE = Path(__file__).with_name("mininet_capture.py")
MNEXEC = "/usr/bin/mnexec"
PYTHON = "/usr/bin/python3"
IPS_BASE_URL = "http://127.0.0.1:8080"
app = FastAPI(title="Mininet Traffic Agent")
lock = threading.Lock()


class TrafficRequest(BaseModel):
    source: Literal["h1", "h2", "h3"]
    target: Literal["h1", "h2", "h3"]
    protocol: Literal["TCP", "UDP", "ICMP"] = "TCP"
    scenario: Literal[
        "NORMAL", "SYN_FLOOD", "UDP_FLOOD", "ICMP_FLOOD", "PORT_SCAN", "CONNECTION_BURST", "DDOS",
        "BRUTE_FORCE", "WEB_ATTACK"
    ] = "NORMAL"
    duration: int = Field(ge=5, le=120)
    packet_rate: int = Field(ge=1, le=1000)
    packet_size: int = Field(ge=32, le=1472)
    number_connections: int = Field(ge=1, le=50)
    destination_port: int = Field(ge=1, le=65535)
    scan_ports: list[int] = Field(default_factory=list)


class StopRequest(BaseModel):
    session_id: str = ""


class IpsModeRequest(BaseModel):
    enabled: bool


class IpsRuleRequest(BaseModel):
    action: Literal["alert", "block_ip", "block_flow", "rate_limit"]
    source_ip: str
    destination_ip: str | None = None
    protocol: Literal["any", "tcp", "udp", "icmp"] = "any"
    destination_port: int | None = Field(default=None, ge=1, le=65535)
    duration: int = Field(default=60, ge=5, le=3600)
    rate_kbps: int = Field(default=256, ge=64, le=100000)
    reason: str = Field(default="Manual IPS policy", max_length=240)
    origin: str = Field(default="manual", max_length=32)


state: dict[str, object] = {
    "session_id": "",
    "status": "Idle",
    "destination_ip": "",
    "error_message": "",
    "stats": {},
    "received_bytes": 0,
    "received_messages": 0,
    "stop_requested": False,
    "sender": None,
    "receiver": None,
    "capture": None,
    "flow_sequence": 0,
    "flows": [],
}


def _host_pid(host: str) -> int | None:
    matches: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except (OSError, PermissionError):
            continue
        if f"mininet:{host}" in command and "bash --norc" in command:
            matches.append(int(entry.name))
    return matches[0] if len(matches) == 1 else None


def _host_ip(pid: int) -> str:
    result = subprocess.run(
        [MNEXEC, "-a", str(pid), "ip", "-j", "-4", "address", "show"],
        capture_output=True, text=True, timeout=3, check=True,
    )
    for interface in json.loads(result.stdout):
        for address in interface.get("addr_info", []):
            value = address.get("local", "")
            if value.startswith("10."):
                return value
    raise RuntimeError("Không tìm thấy IP 10.0.0.x của host Mininet")


def _snapshot() -> dict[str, object]:
    with lock:
        return {
            key: state[key]
            for key in (
                "session_id", "status", "destination_ip", "error_message", "stats",
                "received_bytes", "received_messages",
            )
        }


def _ips_request(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    """Proxy only the fixed IPS API to the loopback-bound OS-Ken service."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(IPS_BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8", "replace")).get("detail", error.reason)
        except (ValueError, OSError):
            detail = error.reason
        raise HTTPException(error.code, str(detail)) from error
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise HTTPException(503, f"OS-Ken IPS API không phản hồi: {error}") from error
    if not isinstance(result, dict):
        raise HTTPException(502, "OS-Ken IPS API trả dữ liệu không hợp lệ")
    return result


def _terminate(process: subprocess.Popen[str] | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()


def _terminate_processes(value: object) -> None:
    processes = value if isinstance(value, list) else [value]
    for process in processes:
        _terminate(process if isinstance(process, subprocess.Popen) else None)


def _run(request: TrafficRequest, source_pid: int, target_pid: int, source_ip: str, target_ip: str) -> None:
    sender: subprocess.Popen[str] | None = None
    receiver: subprocess.Popen[str] | None = None
    capture: subprocess.Popen[str] | None = None
    capture_thread: threading.Thread | None = None
    finished_status = "Completed"
    try:
        with lock:
            session_id = str(state["session_id"])
        ports = request.scan_ports if request.scenario == "PORT_SCAN" else [request.destination_port]
        capture = subprocess.Popen(
            [MNEXEC, "-a", str(source_pid), PYTHON, "-u", str(CAPTURE),
             "--interface", f"{request.source}-eth0", "--source-ip", source_ip,
             "--target-ip", target_ip, "--protocol", request.protocol,
             "--ports", ",".join(map(str, ports)), "--session-id", session_id],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        with lock:
            state["capture"] = capture
        assert capture.stdout is not None
        ready, _, _ = select.select([capture.stdout], [], [], 3)
        if not ready or json.loads(capture.stdout.readline()).get("event") != "ready":
            raise RuntimeError("Packet capture trên Mininet host không khởi động được")

        def read_capture() -> None:
            assert capture is not None and capture.stdout is not None
            for line in capture.stdout:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event") == "flow" and isinstance(event.get("flow"), dict):
                    with lock:
                        state["flow_sequence"] = int(state["flow_sequence"]) + 1
                        flows = state["flows"]
                        assert isinstance(flows, list)
                        flows.append({"sequence": state["flow_sequence"], "flow": event["flow"]})
                        del flows[:-500]

        capture_thread = threading.Thread(target=read_capture, daemon=True)
        capture_thread.start()

        if request.scenario != "PORT_SCAN" and request.protocol in {"TCP", "UDP"}:
            receiver = subprocess.Popen(
                [MNEXEC, "-a", str(target_pid), PYTHON, "-u", str(WORKER), "receive",
                 "--protocol", request.protocol, "--port", str(request.destination_port)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            with lock:
                state["receiver"] = receiver
            assert receiver.stdout is not None
            ready, _, _ = select.select([receiver.stdout], [], [], 3)
            if not ready or json.loads(receiver.stdout.readline()).get("event") != "ready":
                raise RuntimeError("Receiver trên host đích không khởi động được")

        with lock:
            if state["stop_requested"]:
                state["status"] = "Stopped"
                return

        sender = subprocess.Popen(
            [MNEXEC, "-a", str(source_pid), PYTHON, "-u", str(WORKER), "send",
             "--protocol", request.protocol, "--port", str(request.destination_port),
             "--target-ip", target_ip, "--source-ip", source_ip,
             "--ports", ",".join(map(str, ports)), "--scenario", request.scenario,
             "--duration", str(request.duration), "--packet-rate", str(request.packet_rate),
             "--packet-size", str(request.packet_size), "--connections", str(request.number_connections)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        with lock:
            state["sender"] = sender
            state["status"] = "Running"
            should_stop = bool(state["stop_requested"])
        if should_stop:
            _terminate(sender)

        assert sender.stdout is not None
        for line in sender.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            with lock:
                if isinstance(event.get("stats"), dict):
                    state["stats"] = event["stats"]
                if event.get("event") == "finished":
                    finished_status = str(event.get("status", "Completed"))
        sender.wait(timeout=3)
        with lock:
            if sender.returncode != 0:
                finished_status = "Stopped" if state["stop_requested"] else "Error"
                if finished_status == "Error":
                    state["error_message"] = (sender.stderr.read() if sender.stderr else "")[-500:]
    except Exception as error:
        with lock:
            state["status"] = "Error"
            state["error_message"] = str(error)
    finally:
        _terminate(sender)
        _terminate(receiver)
        if receiver is not None:
            try:
                output, error = receiver.communicate(timeout=2)
                for line in output.splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("event") == "receiver_stopped":
                        with lock:
                            state["received_bytes"] = int(event.get("received_bytes", 0))
                            state["received_messages"] = int(event.get("received_messages", 0))
                if receiver.returncode not in (0, -signal.SIGTERM) and error:
                    with lock:
                        state["error_message"] = (str(state["error_message"]) + " " + error[-300:]).strip()
            except subprocess.TimeoutExpired:
                receiver.kill()
                receiver.communicate()
        _terminate(capture)
        if capture is not None:
            try:
                capture.wait(timeout=3)
            except subprocess.TimeoutExpired:
                capture.kill()
                capture.wait()
            if capture_thread is not None:
                capture_thread.join(timeout=2)
            if capture.stderr is not None:
                capture_error = capture.stderr.read()[-400:]
                if capture.returncode not in (0, -signal.SIGTERM) and capture_error:
                    with lock:
                        state["error_message"] = (str(state["error_message"]) + " " + capture_error).strip()
            if capture.stdout is not None:
                capture.stdout.close()
        with lock:
            if state["status"] in {"Running", "Stopping"}:
                state["status"] = "Stopped" if state["stop_requested"] else finished_status
            state["sender"] = None
            state["receiver"] = None
            state["capture"] = None


def _run_ddos(request: TrafficRequest, target_pid: int, target_ip: str) -> None:
    """Run a bounded two-source UDP burst and merge both capture streams."""
    source_names = [name for name in HOSTS if name != request.target]
    sources: list[tuple[str, int, str]] = []
    captures: list[subprocess.Popen[str]] = []
    capture_threads: list[threading.Thread] = []
    senders: list[subprocess.Popen[str]] = []
    sender_threads: list[threading.Thread] = []
    receiver: subprocess.Popen[str] | None = None
    finished = ["Completed"] * len(source_names)
    latest_stats: list[dict[str, float]] = [{} for _ in source_names]

    def update_aggregate() -> None:
        additive = (
            "total_packets", "total_bytes", "packets_per_second", "bytes_per_second",
            "successful_connections", "failed_connections",
        )
        aggregate = {key: sum(float(item.get(key, 0)) for item in latest_stats) for key in additive}
        aggregate["elapsed_seconds"] = max(
            (float(item.get("elapsed_seconds", 0)) for item in latest_stats), default=0.0
        )
        aggregate["source_count"] = len(source_names)
        aggregate["total_packets"] = int(aggregate["total_packets"])
        aggregate["total_bytes"] = int(aggregate["total_bytes"])
        aggregate["successful_connections"] = int(aggregate["successful_connections"])
        aggregate["failed_connections"] = int(aggregate["failed_connections"])
        state["stats"] = aggregate

    try:
        with lock:
            session_id = str(state["session_id"])
        for name in source_names:
            pid = _host_pid(name)
            if pid is None:
                raise RuntimeError(f"Không tìm thấy host nguồn DDoS {name}")
            sources.append((name, pid, _host_ip(pid)))

        receiver = subprocess.Popen(
            [MNEXEC, "-a", str(target_pid), PYTHON, "-u", str(WORKER), "receive",
             "--protocol", "UDP", "--port", str(request.destination_port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        with lock:
            state["receiver"] = receiver
        assert receiver.stdout is not None
        ready, _, _ = select.select([receiver.stdout], [], [], 3)
        if not ready or json.loads(receiver.stdout.readline()).get("event") != "ready":
            raise RuntimeError("Receiver DDoS trên host đích không khởi động được")

        for name, pid, source_ip in sources:
            capture = subprocess.Popen(
                [MNEXEC, "-a", str(pid), PYTHON, "-u", str(CAPTURE),
                 "--interface", f"{name}-eth0", "--source-ip", source_ip,
                 "--target-ip", target_ip, "--protocol", "UDP",
                 "--ports", str(request.destination_port), "--session-id", session_id],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            captures.append(capture)
            assert capture.stdout is not None
            ready, _, _ = select.select([capture.stdout], [], [], 3)
            if not ready or json.loads(capture.stdout.readline()).get("event") != "ready":
                raise RuntimeError(f"Packet capture DDoS trên {name} không khởi động được")

            def read_capture(process: subprocess.Popen[str] = capture) -> None:
                assert process.stdout is not None
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("event") == "flow" and isinstance(event.get("flow"), dict):
                        with lock:
                            state["flow_sequence"] = int(state["flow_sequence"]) + 1
                            flows = state["flows"]
                            assert isinstance(flows, list)
                            flows.append({"sequence": state["flow_sequence"], "flow": event["flow"]})
                            del flows[:-500]

            thread = threading.Thread(target=read_capture, daemon=True)
            thread.start()
            capture_threads.append(thread)

        per_source_rate = max(1, request.packet_rate // len(sources))
        for index, (_name, pid, source_ip) in enumerate(sources):
            sender = subprocess.Popen(
                [MNEXEC, "-a", str(pid), PYTHON, "-u", str(WORKER), "send",
                 "--protocol", "UDP", "--port", str(request.destination_port),
                 "--target-ip", target_ip, "--source-ip", source_ip,
                 "--scenario", "UDP_FLOOD", "--duration", str(request.duration),
                 "--packet-rate", str(per_source_rate), "--packet-size", str(request.packet_size),
                 "--connections", "1", "--ports", str(request.destination_port)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            senders.append(sender)

            def read_sender(position: int = index, process: subprocess.Popen[str] = sender) -> None:
                assert process.stdout is not None
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    with lock:
                        if isinstance(event.get("stats"), dict):
                            latest_stats[position] = event["stats"]
                            update_aggregate()
                        if event.get("event") == "finished":
                            finished[position] = str(event.get("status", "Completed"))
                process.wait(timeout=3)
                if process.returncode != 0:
                    with lock:
                        finished[position] = "Stopped" if state["stop_requested"] else "Error"

            thread = threading.Thread(target=read_sender, daemon=True)
            thread.start()
            sender_threads.append(thread)

        with lock:
            state["sender"] = senders
            state["capture"] = captures
            state["status"] = "Running"
            should_stop = bool(state["stop_requested"])
        if should_stop:
            _terminate_processes(senders)
        for thread in sender_threads:
            thread.join(request.duration + 6)
        if any(thread.is_alive() for thread in sender_threads):
            raise RuntimeError("Sender DDoS không kết thúc đúng thời hạn")
    except Exception as error:
        with lock:
            state["status"] = "Error"
            state["error_message"] = str(error)
    finally:
        _terminate_processes(senders)
        _terminate(receiver)
        if receiver is not None:
            try:
                output, error = receiver.communicate(timeout=2)
                for line in output.splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("event") == "receiver_stopped":
                        with lock:
                            state["received_bytes"] = int(event.get("received_bytes", 0))
                            state["received_messages"] = int(event.get("received_messages", 0))
                if error and receiver.returncode not in (0, -signal.SIGTERM):
                    with lock:
                        state["error_message"] = (str(state["error_message"]) + " " + error[-300:]).strip()
            except subprocess.TimeoutExpired:
                receiver.kill()
                receiver.communicate()
        _terminate_processes(captures)
        for capture in captures:
            try:
                capture.wait(timeout=3)
            except subprocess.TimeoutExpired:
                capture.kill()
                capture.wait()
        for thread in capture_threads:
            thread.join(timeout=2)
        with lock:
            if state["status"] in {"Running", "Stopping"}:
                if state["stop_requested"]:
                    state["status"] = "Stopped"
                else:
                    state["status"] = "Error" if "Error" in finished else "Completed"
            state["sender"] = None
            state["receiver"] = None
            state["capture"] = None


@app.get("/api/health")
def health() -> dict[str, object]:
    hosts = {name: _host_pid(name) is not None for name in HOSTS}
    return {"status": "ok" if all(hosts.values()) else "mininet_unavailable",
            "hosts": hosts, "flow_capture": CAPTURE.is_file()}


@app.post("/api/traffic/start")
def start(request: TrafficRequest) -> dict[str, object]:
    if os.geteuid() != 0:
        raise HTTPException(503, "Agent cần chạy với quyền root trong VM")
    if request.source == request.target:
        raise HTTPException(422, "Host nguồn và đích phải khác nhau")
    if request.protocol not in SCENARIO_PROTOCOLS[request.scenario].split():
        raise HTTPException(422, "Giao thức không khớp kịch bản")
    if request.scenario == "PORT_SCAN":
        ports = request.scan_ports
        if len(ports) < 2 or len(ports) > 6 or len(set(ports)) != len(ports) or not set(ports) <= SCAN_PORTS:
            raise HTTPException(422, "Port Scan chỉ hỗ trợ 2–6 port lab được phê duyệt")
    elif request.scan_ports:
        raise HTTPException(422, "scan_ports chỉ dành cho Port Scan")
    source_pid, target_pid = _host_pid(request.source), _host_pid(request.target)
    if source_pid is None or target_pid is None:
        raise HTTPException(503, "Mininet chưa chạy hoặc không tìm thấy host được chọn")
    try:
        source_ip = _host_ip(source_pid)
        target_ip = _host_ip(target_pid)
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as error:
        raise HTTPException(503, str(error)) from error
    with lock:
        if state["status"] in {"Preparing", "Running", "Stopping"}:
            raise HTTPException(409, "Đang có một phiên traffic chạy")
        state.update(
            session_id=uuid.uuid4().hex[:12].upper(), status="Preparing",
            destination_ip=target_ip, error_message="", stats={},
            received_bytes=0, received_messages=0, stop_requested=False,
            sender=None, receiver=None,
            capture=None, flow_sequence=0, flows=[],
        )
        session_id = str(state["session_id"])
    if request.scenario == "DDOS":
        threading.Thread(target=_run_ddos, args=(request, target_pid, target_ip), daemon=True).start()
    else:
        threading.Thread(target=_run, args=(request, source_pid, target_pid, source_ip, target_ip), daemon=True).start()
    return {"session_id": session_id, "status": "Preparing", "destination_ip": target_ip}


@app.post("/api/traffic/stop")
def stop(request: StopRequest) -> dict[str, object]:
    with lock:
        if request.session_id and request.session_id != state["session_id"]:
            raise HTTPException(409, "Session ID không khớp")
        if state["status"] not in {"Preparing", "Running", "Stopping"}:
            return _snapshot_unlocked()
        state["stop_requested"] = True
        state["status"] = "Stopping"
        sender = state["sender"]
    _terminate_processes(sender)
    return _snapshot()


def _snapshot_unlocked() -> dict[str, object]:
    return {
        key: state[key]
        for key in ("session_id", "status", "destination_ip", "error_message", "stats", "received_bytes", "received_messages")
    }


@app.get("/api/traffic/status")
def status() -> dict[str, object]:
    return _snapshot()


@app.get("/api/traffic/statistics")
def statistics() -> dict[str, object]:
    return _snapshot()


@app.get("/api/flows")
def flows(since: int = Query(default=0, ge=0)) -> dict[str, object]:
    with lock:
        entries = state["flows"]
        assert isinstance(entries, list)
        return {"session_id": state["session_id"], "sequence": state["flow_sequence"],
                "flows": [item for item in entries if int(item["sequence"]) > since]}


@app.get("/api/ips/health")
def ips_health() -> dict[str, object]:
    return _ips_request("GET", "/ips/health")


@app.post("/api/ips/mode")
def ips_mode(request: IpsModeRequest) -> dict[str, object]:
    return _ips_request("POST", "/ips/mode", request.dict())


@app.get("/api/ips/rules")
def ips_rules() -> dict[str, object]:
    return _ips_request("GET", "/ips/rules")


@app.post("/api/ips/rules")
def ips_add_rule(request: IpsRuleRequest) -> dict[str, object]:
    return _ips_request("POST", "/ips/rules", request.dict(exclude_none=True))


@app.delete("/api/ips/rules/{rule_id}")
def ips_delete_rule(rule_id: str) -> dict[str, object]:
    if not rule_id.isalnum() or len(rule_id) > 32:
        raise HTTPException(422, "IPS rule ID không hợp lệ")
    return _ips_request("DELETE", f"/ips/rules/{rule_id}")


@app.get("/api/ips/audit")
def ips_audit() -> dict[str, object]:
    return _ips_request("GET", "/ips/audit")
