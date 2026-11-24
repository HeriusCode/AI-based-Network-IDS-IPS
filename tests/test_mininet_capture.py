"""Verify wire packets become measured flow features."""

import socket
import struct
import unittest

from vm_agent.mininet_capture import Flow, parse_packet


def tcp_frame(source: str, target: str, source_port: int, target_port: int, payload: bytes) -> bytes:
    ethernet = b"\x00" * 12 + b"\x08\x00"
    ip = bytearray(20)
    ip[0] = 0x45
    struct.pack_into("!H", ip, 2, 40 + len(payload))
    ip[9] = 6
    ip[12:16] = socket.inet_aton(source)
    ip[16:20] = socket.inet_aton(target)
    tcp = bytearray(20)
    struct.pack_into("!HH", tcp, 0, source_port, target_port)
    tcp[12] = 0x50
    tcp[13] = 0x18
    struct.pack_into("!H", tcp, 14, 8192)
    return ethernet + ip + tcp + payload


class MininetCaptureTest(unittest.TestCase):
    def test_forward_and_backward_packet_features(self) -> None:
        outgoing = parse_packet(tcp_frame("10.0.0.1", "10.0.0.3", 54321, 8080, b"hello"), 1.0)
        incoming = parse_packet(tcp_frame("10.0.0.3", "10.0.0.1", 8080, 54321, b"ok"), 1.1)
        self.assertIsNotNone(outgoing)
        self.assertIsNotNone(incoming)
        flow = Flow(outgoing, "10.0.0.1", "10.0.0.3", "S1")
        flow.add(incoming)
        record = flow.record()
        features = record["features"]
        self.assertEqual(record["source"], "mininet-packet-capture")
        self.assertEqual(record["source_port"], 54321)
        self.assertEqual(features["Total Fwd Packets"], 1)
        self.assertEqual(features["Total Backward Packets"], 1)
        self.assertEqual(features["Fwd Packets Length Total"], 5)
        self.assertEqual(features["Bwd Packets Length Total"], 2)
        self.assertEqual(len(features), 77)


if __name__ == "__main__":
    unittest.main()
