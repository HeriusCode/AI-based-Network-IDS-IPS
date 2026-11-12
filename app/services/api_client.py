"""REST API client for the IDS/IPS management plane."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ApiResult:
    ok: bool
    status_code: int | None
    message: str
    data: dict[str, Any] | None = None


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 3.0, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def configure(self, base_url: str, timeout: float, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def _request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> ApiResult:
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content = response.read().decode("utf-8", errors="replace")
                data = json.loads(content) if content else {}
                return ApiResult(True, response.status, "Connected Successfully", data)
        except urllib.error.HTTPError as exc:
            return ApiResult(False, exc.code, f"HTTP Error {exc.code}")
        except (TimeoutError, socket.timeout):
            return ApiResult(False, None, "Timeout")
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return ApiResult(False, None, "Timeout")
            return ApiResult(False, None, "Server Unavailable")
        except (json.JSONDecodeError, OSError) as exc:
            return ApiResult(False, None, f"Connection Failed: {exc}")

    def health(self) -> ApiResult:
        return self._request("GET", "/api/health")

    def start_remote_session(self, payload: dict[str, Any]) -> ApiResult:
        return self._request("POST", "/api/traffic/start", payload)

    def stop_remote_session(self) -> ApiResult:
        return self._request("POST", "/api/traffic/stop", {})

    def traffic_status(self) -> ApiResult:
        return self._request("GET", "/api/traffic/status")

    def traffic_statistics(self) -> ApiResult:
        return self._request("GET", "/api/traffic/statistics")
