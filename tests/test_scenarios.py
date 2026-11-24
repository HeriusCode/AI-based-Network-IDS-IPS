"""Check lab scenario contracts and the raw SYN wire format."""

import socket
import struct
import unittest

from app.models.traffic_config import TrafficConfig
from app.utils.constants import SCENARIO_PRESETS, SCENARIO_PROTOCOLS
from app.utils.validators import ValidationError, validate_traffic_config
from app.services.remote_traffic_worker import agent_scenario
from vm_agent.mininet_worker import checksum, tcp_syn_packet


class ScenarioContractTest(unittest.TestCase):
    def test_presets_have_compatible_protocols(self) -> None:
        self.assertEqual(len(SCENARIO_PRESETS), 7)
        self.assertEqual(set(SCENARIO_PRESETS), set(SCENARIO_PROTOCOLS))
        for code, preset in SCENARIO_PRESETS.items():
            with self.subTest(code=code):
                config = TrafficConfig(
                    destination_ip="10.0.0.3", destination_port=8080,
                    protocol=str(preset["protocol"]), scenario=code,
                    duration=int(preset["duration"]),
                    packet_rate=int(preset["packet_rate"]),
                    packet_size=int(preset["packet_size"]),
                    number_connections=int(preset["connections"]),
                    source_host=str(preset["source"]), target_host=str(preset["target"]),
                )
                validate_traffic_config(config, ["10.0.0.0/8"], [22, 53, 80, 443, 8000, 8080])

    def test_custom_profiles_map_to_bounded_vm_primitives(self) -> None:
        constant = TrafficConfig(
            "10.0.0.3", 8000, protocol="TCP", scenario="CUSTOM",
            source_host="h1", target_host="h3", custom_pattern="CONSTANT",
        )
        udp_burst = TrafficConfig(
            "10.0.0.3", 53, protocol="UDP", scenario="CUSTOM",
            source_host="h1", target_host="h3", custom_pattern="RATE_BURST",
        )
        connection_burst = TrafficConfig(
            "10.0.0.3", 80, protocol="TCP", scenario="CUSTOM",
            source_host="h1", target_host="h3", custom_pattern="CONNECTION_BURST",
        )
        self.assertEqual(agent_scenario(constant), "NORMAL")
        self.assertEqual(agent_scenario(udp_burst), "UDP_FLOOD")
        self.assertEqual(agent_scenario(connection_burst), "CONNECTION_BURST")
        for config in (constant, udp_burst, connection_burst):
            validate_traffic_config(config, ["10.0.0.0/8"], [22, 53, 80, 443, 8000, 8080])

    def test_custom_rejects_incompatible_pattern(self) -> None:
        config = TrafficConfig(
            "10.0.0.3", 80, protocol="TCP", scenario="CUSTOM",
            source_host="h1", target_host="h3", custom_pattern="RATE_BURST",
        )
        with self.assertRaises(ValidationError):
            validate_traffic_config(config, ["10.0.0.0/8"], [80])

    def test_attack_scenario_requires_mininet_and_matching_protocol(self) -> None:
        local = TrafficConfig("127.0.0.1", 8080, scenario="DDOS", protocol="UDP")
        with self.assertRaises(ValidationError):
            validate_traffic_config(local, ["127.0.0.0/8"], [8080])
        wrong_protocol = TrafficConfig(
            "10.0.0.3", 8080, scenario="DOS", protocol="UDP",
            source_host="h1", target_host="h3",
        )
        with self.assertRaises(ValidationError):
            validate_traffic_config(wrong_protocol, ["10.0.0.0/8"], [8080])

    def test_syn_packet_has_valid_checksums_and_real_source(self) -> None:
        packet = tcp_syn_packet("10.0.0.1", "10.0.0.3", 40000, 8080, 12345)
        self.assertEqual(len(packet), 40)
        self.assertEqual(packet[12:16], socket.inet_aton("10.0.0.1"))
        self.assertEqual(packet[16:20], socket.inet_aton("10.0.0.3"))
        self.assertEqual(checksum(packet[:20]), 0)
        pseudo = packet[12:20] + struct.pack("!BBH", 0, 6, 20)
        self.assertEqual(checksum(pseudo + packet[20:]), 0)
        self.assertEqual(packet[33], 0x02)


if __name__ == "__main__":
    unittest.main()
