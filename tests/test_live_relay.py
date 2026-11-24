"""A captured VM flow must reach the IDS/IPS ingestion endpoint."""

import unittest
from unittest.mock import call, patch

from PySide6.QtCore import QCoreApplication

from app.config import AppConfig
from app.models.traffic_config import TrafficConfig
from app.services.api_client import ApiResult
from app.services.remote_traffic_worker import RemoteTrafficWorker


class LiveRelayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    @patch("app.services.remote_traffic_worker.ApiClient")
    @patch("app.services.remote_traffic_worker.MininetClient")
    def test_completed_session_relays_captured_flow(self, client_class, api_class) -> None:
        client = client_class.return_value.__enter__.return_value
        client.health.return_value = {"status": "ok", "flow_capture": True}
        client.start.return_value = {
            "session_id": "S1", "status": "Preparing", "destination_ip": "10.0.0.3",
        }
        client.status.return_value = {
            "session_id": "S1", "status": "Completed", "stats": {"total_packets": 5},
        }
        flow = {"source": "mininet-packet-capture", "session_id": "S1", "flow_id": "F1"}
        second = {"source": "mininet-packet-capture", "session_id": "S1", "flow_id": "F2"}
        client.flows.return_value = {
            "session_id": "S1", "sequence": 2,
            "flows": [{"sequence": 1, "flow": flow}, {"sequence": 2, "flow": second}],
        }
        api = api_class.return_value
        api.health.return_value = ApiResult(True, 200, "ok", {"live_flow_ingest": True})
        api.ingest_flow.return_value = ApiResult(True, 200, "ok", {"label": "BENIGN"})

        config = TrafficConfig("10.0.0.3", 8080, source_host="h1", target_host="h3")
        worker = RemoteTrafficWorker(config, AppConfig())
        finished = []
        worker.session_finished.connect(finished.append)
        worker.run()

        api.ingest_flow.assert_has_calls([call(flow), call(second)])
        self.assertEqual(api.ingest_flow.call_count, 2)
        api.ingest_flows.assert_not_called()
        self.assertEqual(finished[0].status, "Completed")


if __name__ == "__main__":
    unittest.main()
