from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.network_metrics import NetworkMetricsCollector


class NetworkMetricsFallbackTest(unittest.TestCase):
    def test_local_topology_remains_available_without_psutil(self) -> None:
        with patch("app.services.network_metrics.psutil", None):
            snapshot = NetworkMetricsCollector().sample()
        self.assertTrue(snapshot.available)
        self.assertTrue(snapshot.interfaces)
        self.assertIn("psutil", snapshot.error)


if __name__ == "__main__":
    unittest.main()
