from __future__ import annotations

import socket
import sys
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.traffic_config import TrafficConfig
from app.services.traffic_engine import TrafficEngine
from app.utils.validators import ValidationError, validate_traffic_config


class TrafficEngineTest(unittest.TestCase):
    def test_public_target_is_rejected(self) -> None:
        config = TrafficConfig("8.8.8.8", 53, protocol="UDP", duration=5)
        with self.assertRaises(ValidationError):
            validate_traffic_config(config, ["192.168.0.0/16"], [53])

    def test_bounded_udp_session_can_stop(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        port = receiver.getsockname()[1]
        config = TrafficConfig(
            "127.0.0.1",
            port,
            protocol="UDP",
            scenario="NORMAL",
            duration=5,
            packet_rate=20,
            packet_size=64,
        )
        engine = TrafficEngine(["127.0.0.0/8"], [port])
        sessions: list[object] = []
        worker = threading.Thread(
            target=lambda: sessions.append(engine.run(config, lambda _: None, lambda _: None)),
            daemon=True,
        )
        worker.start()
        data, _ = receiver.recvfrom(1024)
        self.assertEqual(len(data), 64)
        time.sleep(0.1)
        engine.stop()
        worker.join(timeout=2)
        receiver.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(getattr(sessions[0], "status"), "Stopped")
        self.assertGreater(getattr(sessions[0], "total_packets"), 0)


if __name__ == "__main__":
    unittest.main()
