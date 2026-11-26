from __future__ import annotations

import unittest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.ui.pages import alerts


class FakeLiveService(QObject):
    changed = Signal(object)

    def __init__(self, flows: list[dict]) -> None:
        super().__init__()
        self.flows = flows

    def snapshot(self) -> list[dict]:
        return list(self.flows)


class FakeMitigationService(QObject):
    action_completed = Signal(bool, str)

    def __init__(self) -> None:
        super().__init__()
        self.blocked: list[tuple[str, str]] = []

    def block_ip_async(self, source_ip: str, *, reason: str = "") -> None:
        self.blocked.append((source_ip, reason))


def attack(flow_id: str, attack_type: str = "DDoS", score: float = 0.95) -> dict:
    return {
        "session_id": "S1", "flow_id": flow_id, "timestamp": "2026-11-25T10:00:00+00:00",
        "source_ip": "10.0.0.1", "destination_ip": "10.0.0.2",
        "source_port": 12345, "destination_port": 8080, "protocol": "UDP",
        "packets": 100, "flow_duration_us": 1_000_000, "bytes_per_second": 64_000,
        "label": "ATTACK", "attack_score": score, "risk_level": "HIGH",
        "attack_type": attack_type, "type_confidence": 0.88,
        "feature_quality": "approximate", "model_version": "test-model",
    }


class AlertsPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_live_alert_filter_resolve_and_real_ips_action(self) -> None:
        live = FakeLiveService([
            attack("F1"),
            {**attack("BENIGN"), "label": "BENIGN"},
        ])
        mitigation = FakeMitigationService()
        page = alerts.AlertsPage(live_service=live, mitigation_service=mitigation)

        self.assertEqual(len(alerts.ALERTS), 1)
        self.assertEqual(alerts.ALERTS[0][4], "DDoS Attack")
        self.assertEqual(page.table.rowCount(), 1)
        self.assertIn("IDS/IPS LIVE", page.status_badge.text())

        live.changed.emit(attack("F2", "Port Scan", 0.8))
        self.app.processEvents()
        self.assertEqual(len(alerts.ALERTS), 2)
        page.combo_attack.setCurrentText("Port Scan")
        page.apply_filters()
        self.assertFalse(page.table.isRowHidden(0))
        self.assertTrue(page.table.isRowHidden(1))

        page.combo_attack.setCurrentIndex(0)
        page._select_row(0)
        alert_id = alerts.ALERTS[0][0]
        page.block_ip()
        self.assertEqual(mitigation.blocked[0][0], "10.0.0.1")
        self.assertEqual(page.alert_status[alert_id], "Đang xử lý")
        mitigation.action_completed.emit(True, "ok")
        self.app.processEvents()
        self.assertEqual(page.alert_status[alert_id], "Đã xử lý")

        page._select_row(1)
        second_id = alerts.ALERTS[1][0]
        page.resolve_alert()
        self.assertEqual(page.alert_status[second_id], "Đã xử lý")


if __name__ == "__main__":
    unittest.main()
