from __future__ import annotations

import ipaddress
import tempfile
import unittest
from pathlib import Path

from app.core.server_config import ServerConfigManager, primary_local_ipv4


class ServerConfigTest(unittest.TestCase):
    def test_detected_address_is_ipv4(self) -> None:
        self.assertIsInstance(ipaddress.ip_address(primary_local_ipv4()), ipaddress.IPv4Address)

    def test_saved_endpoint_is_loaded_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server_config.json"
            manager = ServerConfigManager(path)
            manager.save("192.168.10.25", 8123)

            loaded = ServerConfigManager(path).config
            self.assertEqual(loaded.server_ip, "192.168.10.25")
            self.assertEqual(loaded.server_port, 8123)
            self.assertEqual(loaded.base_url, "http://192.168.10.25:8123")


if __name__ == "__main__":
    unittest.main()
