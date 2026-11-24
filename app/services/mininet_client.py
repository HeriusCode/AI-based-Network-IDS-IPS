"""Authenticated SSH tunnel to the VM's loopback-only Mininet agent."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


class MininetClientError(RuntimeError):
    pass


class MininetClient:
    def __init__(self, host: str, user: str, agent_port: int = 9000) -> None:
        if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
            raise MininetClientError("Tên SSH user không hợp lệ")
        self.host = host
        self.user = user
        self.key_path = Path.home() / ".ssh" / "traffic-generator-vm"
        self.agent_port = agent_port
        self.process: subprocess.Popen[bytes] | None = None
        self.base_url = ""

    def __enter__(self) -> "MininetClient":
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def connect(self) -> None:
        if self.process is not None:
            return
        if not self.key_path.is_file():
            raise MininetClientError(f"Không tìm thấy SSH key: {self.key_path}")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            local_port = probe.getsockname()[1]
        command = [
            "ssh", "-i", str(self.key_path), "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=5",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
            "-L", f"127.0.0.1:{local_port}:127.0.0.1:{self.agent_port}",
            "-N", f"{self.user}@{self.host}",
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, creationflags=flags,
            )
        except OSError as error:
            raise MininetClientError(f"Không khởi động được SSH: {error}") from error
        self.base_url = f"http://127.0.0.1:{local_port}"
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                details = self.process.stderr.read().decode("utf-8", "replace") if self.process.stderr else ""
                self.close()
                raise MininetClientError(f"SSH tới VM thất bại: {details.strip()[-300:]}")
            try:
                self._request("GET", "/api/health", timeout=0.5)
                return
            except MininetClientError:
                time.sleep(0.1)
        self.close()
        raise MininetClientError("SSH đã kết nối nhưng Mininet agent không phản hồi trên VM")

    def close(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stderr is not None:
            process.stderr.close()

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: float = 3) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            try:
                detail = json.loads(error.read().decode("utf-8", "replace")).get("detail")
            except (ValueError, OSError):
                detail = error.reason
            raise MininetClientError(f"VM trả HTTP {error.code}: {detail}") from error
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise MininetClientError(f"Không gọi được Mininet agent: {error}") from error

    def health(self) -> dict:
        result = self._request("GET", "/api/health")
        if not isinstance(result.get("hosts"), dict):
            raise MininetClientError(
                f"Cổng {self.agent_port} đang trả lời bằng API khác, không phải Mininet agent. "
                "Kiểm tra Agent Port (mặc định 9000)."
            )
        if result.get("status") != "ok":
            raise MininetClientError("Mininet agent đang chạy nhưng h1/h2/h3 chưa sẵn sàng")
        if not result.get("flow_capture"):
            raise MininetClientError(
                "Mininet agent chưa có packet capture live. Triển khai lại vm_agent/mininet_capture.py."
            )
        return result

    def start(self, payload: dict) -> dict:
        return self._request("POST", "/api/traffic/start", payload)

    def stop(self, session_id: str) -> dict:
        return self._request("POST", "/api/traffic/stop", {"session_id": session_id})

    def status(self) -> dict:
        return self._request("GET", "/api/traffic/status")

    def flows(self, since: int = 0) -> dict:
        return self._request("GET", f"/api/flows?since={int(since)}")
