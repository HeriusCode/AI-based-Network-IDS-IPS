from __future__ import annotations

import unittest

from app.ui.pages import topology
from app.services.network_metrics import NetworkInterface, NetworkSnapshot


class TopologyMappingTest(unittest.TestCase):
    @staticmethod
    def _payload() -> dict:
        return {
            "nodes": [
                {"id": "os-ken", "name": "OS-Ken", "type": "controller", "status": "online", "ip": "127.0.0.1", "openflow": "OpenFlow 1.3"},
                {"id": "s1", "name": "s1", "type": "switch", "status": "online", "openflow": "1.3", "port_count": 3, "flow_count": 5},
                {"id": "h1", "name": "h1", "type": "host", "status": "online", "ip": "10.0.0.1", "rx_bps": 1_000_000, "tx_bps": 2_000_000},
            ],
            "links": [
                {"source": "os-ken", "target": "s1", "type": "control", "status": "online", "label": "OpenFlow 1.3"},
                {"source": "h1", "target": "s1", "type": "data", "status": "online", "label": "s1-eth1"},
            ],
        }

    def test_sdn_payload_replaces_operating_system_interfaces(self) -> None:
        topology._load_sdn_topology(self._payload())

        self.assertEqual([device.key for device in topology.DEVICES], ["os-ken", "s1", "h1"])
        self.assertEqual(topology.DEVICES[1].kind, "Open vSwitch")
        self.assertEqual(topology.DEVICES[1].flows, "5 flow")
        self.assertEqual(topology.DEVICES[2].incoming, "1.000 Mbps")
        self.assertEqual(len(topology.TOPOLOGY_LINKS), 2)
        self.assertEqual(topology.TOPOLOGY_LINKS[1][4], "s1-eth1")

    def test_combined_topology_keeps_windows_interfaces_and_sdn_nodes(self) -> None:
        snapshot = NetworkSnapshot(
            True,
            interfaces=(
                NetworkInterface("Wi-Fi", 1.2, 0.8, True, "192.168.1.25", "aa:bb:cc:dd:ee:ff"),
                NetworkInterface("VMware Network Adapter VMnet8", 0.2, 0.1, True, "192.168.201.1", "00:50:56:00:00:08"),
            ),
        )

        topology._load_combined_topology(snapshot, self._payload())

        keys = {device.key for device in topology.DEVICES}
        names = {device.name for device in topology.DEVICES}
        self.assertTrue({"local-host", "interface-0", "interface-1", "os-ken", "s1", "h1"}.issubset(keys))
        self.assertIn("Wi-Fi", names)
        self.assertIn("VMware Network Adapter VMnet8", names)
        self.assertTrue(any(link[0] == "local-host" and link[1] == "os-ken" for link in topology.TOPOLOGY_LINKS))


if __name__ == "__main__":
    unittest.main()
