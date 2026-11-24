from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.ips_client import IpsClient


class IpsClientTest(unittest.TestCase):
    def test_direct_tunnel_url_skips_new_ssh_process(self) -> None:
        client = IpsClient()
        client.configure(
            host="100.104.102.46",
            user="trafficuser",
            agent_port=9000,
            direct_url="http://127.0.0.1:19000/",
        )
        with (
            patch.object(client, "_request", return_value={"status": "ok"}) as request,
            patch("app.services.ips_client.subprocess.Popen") as popen,
        ):
            client.connect()
        self.assertEqual(client.base_url, "http://127.0.0.1:19000")
        request.assert_called_once_with("GET", "/api/ips/health", timeout=1.5)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
