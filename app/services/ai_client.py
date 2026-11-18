"""Small HTTP client for the separately running AI inference service."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AiApiError(RuntimeError):
    """Raised when the AI service cannot complete a request."""


class AiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or os.getenv("IDS_AI_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def detect(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", "/detect", records)

    def classify_attack(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", "/classify-attack", records)

    def forecast_traffic(self, history: list[dict[str, Any]], horizon: int = 1) -> dict[str, Any]:
        return self._request(
            "POST",
            "/forecast/traffic",
            {"history": history, "horizon": horizon},
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: object | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            message = error.reason
            try:
                detail = json.loads(error.read().decode("utf-8")).get("detail")
                if detail:
                    message = detail
            except (ValueError, UnicodeDecodeError, AttributeError):
                pass
            raise AiApiError(f"AI API trả HTTP {error.code}: {message}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise AiApiError(
                f"Không kết nối được AI API tại {self.base_url}: {getattr(error, 'reason', error)}"
            ) from error
        except (ValueError, UnicodeDecodeError) as error:
            raise AiApiError("AI API trả dữ liệu JSON không hợp lệ.") from error
