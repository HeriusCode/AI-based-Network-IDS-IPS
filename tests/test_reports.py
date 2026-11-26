from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.ui.pages import reports


class FakeLiveService(QObject):
    changed = Signal(object)

    def __init__(self, flows: list[dict]) -> None:
        super().__init__()
        self.flows = flows

    def snapshot(self) -> list[dict]:
        return list(self.flows)


class FakeMitigationService(QObject):
    snapshot_changed = Signal(object)
    error = Signal(str)

    def __init__(self, snapshot: dict) -> None:
        super().__init__()
        self.snapshot = snapshot
        self.connected = False
        self.refresh_count = 0

    def refresh_async(self) -> None:
        self.refresh_count += 1
        self.connected = True
        self.snapshot_changed.emit(self.snapshot)


def flow(flow_id: str, *, attack: bool = False) -> dict:
    return {
        "session_id": "SESSION-1", "flow_id": flow_id,
        "timestamp": "2026-11-25T10:00:00+00:00",
        "source_ip": "10.0.0.1", "destination_ip": "10.0.0.2",
        "source_port": 12345, "destination_port": 80, "protocol": "TCP",
        "packets": 25, "flow_duration_us": 1_000_000,
        "bytes_per_second": 1024,
        "label": "ATTACK" if attack else "BENIGN",
        "attack_score": 0.94 if attack else 0.02,
        "risk_level": "HIGH" if attack else "LOW",
        "attack_type": "DDoS" if attack else "Chưa xác định",
        "model_version": "test-model",
    }


class ReportsPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_live_flows_ips_audit_report_and_csv(self) -> None:
        live = FakeLiveService([flow("F1"), flow("F2", attack=True)])
        mitigation = FakeMitigationService({
            "health": {"enabled": True},
            "rules": [],
            "audit": [{
                "timestamp": "2026-11-25T10:01:00+00:00",
                "event": "rule_created", "rule_id": "RULE-1",
                "action": "rate_limit", "source_ip": "10.0.0.1",
            }],
        })
        page = reports.ReportsPage(live_service=live, mitigation_service=mitigation)
        self.app.processEvents()

        self.assertEqual(len(reports.LOGS_DATA), 3)
        self.assertEqual(page.logs_table.rowCount(), 3)
        self.assertIn("AI LIVE", page.status_badge.text())
        self.assertIn("IPS KẾT NỐI", page.status_badge.text())
        self.assertEqual(page.metric_cards[1].value_label.text(), "1 Cảnh báo")
        self.assertEqual(page.metric_cards[2].value_label.text(), "1 OpenFlow")

        live.changed.emit(flow("F3", attack=True))
        self.app.processEvents()
        self.assertEqual(len(reports.LOGS_DATA), 4)
        self.assertEqual(page.logs_table.rowCount(), 4)

        page.create_report()
        self.assertEqual(len(reports.REPORTS_DATA), 1)
        self.assertEqual(page.reports_table.rowCount(), 1)
        self.assertEqual(reports.REPORTS_DATA[0][5], "4")

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "logs.csv"
            page._write_csv(str(target), ["ID", "Time"], [["LOG-1", "now"]])
            with target.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.reader(handle)), [["ID", "Time"], ["LOG-1", "now"]])


if __name__ == "__main__":
    unittest.main()
