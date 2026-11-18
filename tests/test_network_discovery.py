from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.network_discovery import (
    NetworkDiscoveryResult,
    _lease_candidates,
    sync_traffic_generator_config,
)


class NetworkDiscoveryTest(unittest.TestCase):
    def test_latest_vmware_lease_is_first_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vmware = Path(directory) / "VMware"
            vmware.mkdir()
            (vmware / "vmnetdhcp.leases~").write_text(
                'lease 192.168.201.129 { client-hostname "duy-server"; }\n'
                'lease 192.168.201.130 { client-hostname "duy-server"; }\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"PROGRAMDATA": directory}):
                self.assertEqual(_lease_candidates(), ["192.168.201.130", "192.168.201.129"])

    def test_sync_updates_both_dhcp_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"server_ip": "old", "api_port": 1, "vm_ip": "old"}), encoding="utf-8")
            result = NetworkDiscoveryResult("192.168.1.12", "192.168.201.130", "duy-server", str(path))
            sync_traffic_generator_config(result, 8000)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["server_ip"], "192.168.1.12")
            self.assertEqual(payload["vm_ip"], "192.168.201.130")
            self.assertEqual(payload["api_port"], 8000)


if __name__ == "__main__":
    unittest.main()
