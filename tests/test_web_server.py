from __future__ import annotations

import json
import unittest
from urllib.request import urlopen

from app.services.web_server import WebServerController


class WebServerControllerTest(unittest.TestCase):
    def test_health_endpoint_can_start_and_stop(self) -> None:
        controller = WebServerController()
        self.assertTrue(controller.start("127.0.0.1", 0))
        server = controller._server
        self.assertIsNotNone(server)
        port = server.server_address[1]

        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(controller.is_running)
        controller.stop()
        self.assertFalse(controller.is_running)


if __name__ == "__main__":
    unittest.main()
