"""Authenticated client for the loopback-only Mininet IPS agent."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


class IpsClientError(RuntimeError):
    pass


class IpsClient:
    def __init__(self) -> None:
        self.host = os.getenv("MININET_VM_IP", "192.168.201.130")
        self.user = os.getenv("MININET_VM_USER", "root")
        self.agent_port = int(os.getenv("MININET_AGENT_PORT", "9000"))
        self.direct_url = os.getenv("MININET_AGENT_URL", "").strip().rstrip("/")
        key_value = os.getenv("MININET_SSH_KEY", str(Path.home() / ".ssh" / "traffic-generator-vm"))
        self.key_path = Path(key_value).expanduser()
        self.process: subprocess.Popen[bytes] | None = None
        self.base_url = ""

    def configure(
        self,
        *,
        host: str,
        user: str,
        agent_port: int,
        direct_url: str = "",
    ) -> None:
        """Apply a discovered connection without requiring an application restart."""
        self.close()
        self.host = host
        self.user = user
        self.agent_port = int(agent_port)
        self.direct_url = direct_url.strip().rstrip("/")
        self.base_url = self.direct_url

    def connect(self) -> None:
        if self.direct_url:
            self.base_url = self.direct_url
            self._request("GET", "/api/ips/health", timeout=1.5)
            return
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        if not re.fullmatch(r"[a-z_][a-z0-9_-]*", self.user):
            raise IpsClientError("Tên SSH user không hợp lệ")
        if not self.key_path.is_file():
            raise IpsClientError(f"Không tìm thấy SSH key: {self.key_path}")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            local_port = int(probe.getsockname()[1])
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
            raise IpsClientError(f"Không khởi động được SSH tunnel: {error}") from error
        self.base_url = f"http://127.0.0.1:{local_port}"
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                details = self.process.stderr.read().decode("utf-8", "replace") if self.process.stderr else ""
                self.close()
                raise IpsClientError(f"SSH tới VM thất bại: {details.strip()[-300:]}")
            try:
                self._request("GET", "/api/ips/health", timeout=0.7)
                return
            except IpsClientError:
                time.sleep(0.12)
        self.close()
        raise IpsClientError("SSH đã kết nối nhưng IPS agent cổng 9000 không phản hồi")

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

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: float = 4) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            try:
                detail = json.loads(error.read().decode("utf-8", "replace")).get("detail", error.reason)
            except (ValueError, OSError):
                detail = error.reason
            raise IpsClientError(f"IPS trả HTTP {error.code}: {detail}") from error
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise IpsClientError(f"Không gọi được IPS agent: {error}") from error
        if not isinstance(result, dict):
            raise IpsClientError("IPS agent trả dữ liệu không hợp lệ")
        return result

    def health(self) -> dict:
        self.connect()
        return self._request("GET", "/api/ips/health")

    def snapshot(self) -> dict:
        self.connect()
        health = self._request("GET", "/api/ips/health")
        rules = self._request("GET", "/api/ips/rules")
        audit = self._request("GET", "/api/ips/audit")
        return {"health": health, "rules": rules.get("rules", []), "audit": audit.get("events", [])}

    def set_enabled(self, enabled: bool) -> dict:
        self.connect()
        return self._request("POST", "/api/ips/mode", {"enabled": enabled})

    def add_rule(self, payload: dict) -> dict:
        self.connect()
        return self._request("POST", "/api/ips/rules", payload)

    def delete_rule(self, rule_id: str) -> dict:
        self.connect()
        return self._request("DELETE", f"/api/ips/rules/{rule_id}")

