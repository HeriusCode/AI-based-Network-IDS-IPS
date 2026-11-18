"""End-to-end HTTP ingest with a stub model and a real local server."""

import json
import unittest
from unittest.mock import Mock
from urllib.request import Request, urlopen

from PySide6.QtCore import QCoreApplication

from app.services.web_server import WebServerController


class LiveDetectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_ingest_and_snapshot(self) -> None:
        server = WebServerController()
        server.live_service._client.detect = Mock(return_value={
            "model_version": "test", "predictions": [{
                "label": "BENIGN", "attack_score": 0.12, "risk_level": "LOW",
            }],
        })
        self.assertTrue(server.start("127.0.0.1", 0))
        try:
            port = server._server.server_address[1]
            flow = {
                "source": "mininet-packet-capture", "session_id": "S1",
                "flow_id": "10.0.0.1:1000>10.0.0.3:8080/6",
                "source_ip": "10.0.0.1", "destination_ip": "10.0.0.3",
                "source_port": 1000, "destination_port": 8080,
                "protocol": "TCP", "packets": 5,
                "features": {"Protocol": 6, "Total Fwd Packets": 5},
            }
            request = Request(
                f"http://127.0.0.1:{port}/api/flows",
                data=json.dumps(flow).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=3) as response:
                posted = json.load(response)
            self.assertEqual(posted["label"], "BENIGN")
            with urlopen(f"http://127.0.0.1:{port}/api/flows", timeout=3) as response:
                snapshot = json.load(response)
            self.assertEqual(snapshot["flows"][0]["flow_id"], flow["flow_id"])
            self.assertEqual(len(snapshot["flows"]), 1)
            history = server.live_service.traffic_history()
            self.assertEqual(len(history), 1)
            self.assertGreater(history[0]["packets_per_second"], 0)
        finally:
            server.stop()

    def test_batch_ingest_uses_one_model_call(self) -> None:
        server = WebServerController()
        model = Mock(return_value={
            "model_version": "test", "predictions": [
                {"label": "BENIGN", "attack_score": 0.1, "risk_level": "LOW"},
                {"label": "BENIGN", "attack_score": 0.2, "risk_level": "LOW"},
            ],
        })
        server.live_service._client.detect = model
        self.assertTrue(server.start("127.0.0.1", 0))
        try:
            port = server._server.server_address[1]
            flows = [
                {"source": "mininet-packet-capture", "session_id": "S2",
                 "flow_id": f"F{index}", "features": {"Protocol": 17}}
                for index in (1, 2)
            ]
            request = Request(
                f"http://127.0.0.1:{port}/api/flows",
                data=json.dumps(flows).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urlopen(request, timeout=3) as response:
                results = json.load(response)
            self.assertEqual(len(results), 2)
            self.assertEqual(len(server.live_service.snapshot()), 2)
            model.assert_called_once()
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
