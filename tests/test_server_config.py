from __future__ import annotations

import ipaddress
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_foreign_machine_address_falls_back_to_current_local_ip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server_config.json"
            path.write_text('{"server_ip": "192.168.1.37", "server_port": 8000}', encoding="utf-8")
            with patch("app.core.server_config.local_ipv4_addresses", return_value=["10.20.30.40"]):
                manager = ServerConfigManager(path, require_local_address=True)
            self.assertEqual(manager.config.server_ip, "10.20.30.40")
            self.assertEqual(manager.config.server_port, 8000)


if __name__ == "__main__":
    unittest.main()
