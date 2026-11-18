"""Small local health server used by Traffic Generator connection checks."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from PySide6.QtCore import QObject, Signal

from app.services.live_detection import LiveDetectionService


class _HealthHandler(BaseHTTPRequestHandler):
    server_version = "CyberaIDS/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.rstrip("/") == "/api/flows":
            self._send_json(200, {"flows": self.server.live_service.snapshot()})
            return
        if self.path.rstrip("/") not in {"/health", "/api/health"}:
            self._send_json(404, {"status": "not_found"})
            return
        host, port = self.server.server_address
        self._send_json(
            200,
            {
                "status": "ok",
                "service": "AI-based Network IDS/IPS",
                "server_ip": host,
                "server_port": port,
                "live_flow_ingest": True,
                "batch_flow_ingest": True,
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.rstrip("/") != "/api/flows":
            self._send_json(404, {"detail": "not_found"})
            return
        token = os.getenv("IDS_INGEST_TOKEN", "")
        peer = self.client_address[0]
        if token:
            authorized = self.headers.get("Authorization", "") == f"Bearer {token}"
        else:
            authorized = peer in {"127.0.0.1", "::1", self.server.server_address[0]}
        if not authorized:
            self._send_json(403, {"detail": "Flow ingest chỉ nhận từ máy cục bộ hoặc token hợp lệ"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                raise ValueError("Kích thước flow không hợp lệ")
            payload = json.loads(self.rfile.read(length))
            result = (
                self.server.live_service.ingest_many(payload)
                if isinstance(payload, list) else self.server.live_service.ingest(payload)
            )
        except (ValueError, TypeError, KeyError, IndexError) as error:
            self._send_json(422, {"detail": str(error)})
            return
        except Exception as error:
            self._send_json(502, {"detail": f"AI inference thất bại: {error}"})
            return
        self._send_json(200, result)

    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args) -> None:
        del args


class WebServerController(QObject):
    """Start/stop a bounded local HTTP endpoint and test it asynchronously."""

    state_changed = Signal(bool, str)
    test_completed = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.live_service = LiveDetectionService(parent=self)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self, server_ip: str, server_port: int) -> bool:
        if self.is_running:
            self.state_changed.emit(True, "Server đang chạy")
            return True
        try:
            server = ThreadingHTTPServer((server_ip, int(server_port)), _HealthHandler)
            server.daemon_threads = True
            server.live_service = self.live_service
        except OSError as exc:
            self.state_changed.emit(False, f"Không thể mở server: {exc}")
            return False

        thread = threading.Thread(target=server.serve_forever, name="ids-health-server", daemon=True)
        self._server = server
        self._thread = thread
        thread.start()
        self.state_changed.emit(True, f"Server đang chạy tại http://{server_ip}:{server_port}")
        return True

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self.state_changed.emit(False, "Server đã dừng")

    def test_connection(self, server_ip: str, server_port: int) -> None:
        url = f"http://{server_ip}:{server_port}/api/health"

        def run() -> None:
            try:
                with urlopen(url, timeout=2.0) as response:
                    if response.status != 200:
                        raise HTTPError(url, response.status, "HTTP error", response.headers, None)
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") != "ok":
                    raise ValueError("Phản hồi health không hợp lệ")
                self.test_completed.emit(True, f"Kết nối thành công tới {url}")
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                self.test_completed.emit(False, f"Kết nối thất bại: {exc}")

        threading.Thread(target=run, name="ids-health-test", daemon=True).start()
