from __future__ import annotations

import unittest

from app.services.mitigation_service import MitigationService


class MitigationPolicyTest(unittest.TestCase):
    def test_benign_flow_has_no_action(self) -> None:
        self.assertIsNone(MitigationService.policy_for({"label": "BENIGN"}))

    def test_low_confidence_attack_only_alerts(self) -> None:
        result = MitigationService.policy_for({
            "label": "ATTACK", "attack_score": 0.55, "attack_type": "DoS",
            "source_ip": "10.0.0.1", "destination_ip": "10.0.0.3",
            "protocol": "TCP", "destination_port": 80,
        })
        self.assertEqual(result["action"], "alert")

    def test_dos_is_rate_limited(self) -> None:
        result = MitigationService.policy_for({
            "label": "ATTACK", "attack_score": 0.95, "attack_type": "DoS",
            "source_ip": "10.0.0.1", "destination_ip": "10.0.0.3",
            "protocol": "UDP", "destination_port": 9999,
        })
        self.assertEqual(result["action"], "rate_limit")
        self.assertEqual(result["rate_kbps"], 256)

    def test_port_scan_requires_corroboration(self) -> None:
        result = MitigationService.policy_for({
            "label": "ATTACK", "attack_score": 0.9, "attack_type": "Port Scan",
            "source_ip": "10.0.0.1", "destination_ip": "10.0.0.3",
            "protocol": "TCP", "destination_port": 22,
        })
        self.assertEqual(result["action"], "defer_port_scan")


if __name__ == "__main__":
    unittest.main()
