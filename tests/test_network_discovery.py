from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.network_discovery import (
    NetworkDiscoveryResult,
    _lease_candidates,
    _tailscale_addresses,
    discover_network,
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
            self.assertEqual(payload["vm_ssh_user"], "root")
            self.assertIn("100.64.0.0/10", payload["allowed_networks"])

    def test_tailscale_status_finds_local_and_named_peer(self) -> None:
        status = {
            "TailscaleIPs": ["100.90.30.20", "fd7a:115c:a1e0::1"],
            "Peer": {
                "node-key": {
                    "HostName": "duy-server",
                    "DNSName": "duy-server.example.ts.net.",
                    "Online": True,
                    "TailscaleIPs": ["100.104.102.46"],
                },
            },
        }
        completed = Mock(returncode=0, stdout=json.dumps(status))
        with patch("app.services.network_discovery.subprocess.run", return_value=completed):
            self.assertEqual(
                _tailscale_addresses(),
                ("100.90.30.20", ["100.104.102.46"]),
            )

    def test_discovery_prefers_verified_tailscale_peer(self) -> None:
        missing_config = Path(tempfile.gettempdir()) / "missing-traffic-config.json"
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "app.services.network_discovery._tailscale_addresses",
                return_value=("100.90.30.20", ["100.104.102.46"]),
            ),
            patch("app.services.network_discovery._agent_health", return_value=False),
            patch("app.services.network_discovery._saved_vm_candidate", return_value=None),
            patch("app.services.network_discovery._lease_candidates", return_value=[]),
            patch("app.services.network_discovery._arp_candidates", return_value=[]),
            patch("app.services.network_discovery._verify_mininet_vm", return_value="trafficuser"),
            patch("app.services.network_discovery.traffic_generator_config_path", return_value=missing_config),
        ):
            result = discover_network()
        self.assertEqual(result.server_ip, "100.90.30.20")
        self.assertEqual(result.vm_ip, "100.104.102.46")
        self.assertEqual(result.vm_user, "trafficuser")
        self.assertEqual(result.connection_source, "tailscale")
        self.assertEqual(result.traffic_config_path, "")

    def test_missing_remote_traffic_config_is_optional(self) -> None:
        result = NetworkDiscoveryResult(
            "100.90.30.20",
            "100.104.102.46",
            "duy-server",
            "",
            "trafficuser",
        )
        self.assertIsNone(sync_traffic_generator_config(result))


if __name__ == "__main__":
    unittest.main()
