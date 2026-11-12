from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.traffic_session import TrafficSession
from app.services.log_service import LogService


class LogServiceTest(unittest.TestCase):
    def test_save_list_export_and_release_database_file(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            service = LogService(root / "traffic_logs.db")
            session = TrafficSession(
                "TESTSESSION",
                "2026-11-12T10:00:00+07:00",
                "2026-11-12T10:00:01+07:00",
                "127.0.0.1",
                8080,
                "UDP",
                "NORMAL",
                1,
                64,
                0,
                0,
                1.0,
                "Completed",
            )
            service.save_session(session)
            rows = service.list_sessions()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["session_id"], "TESTSESSION")
            export_path = root / "sessions.csv"
            service.export_csv(export_path, rows)
            self.assertTrue(export_path.exists())


if __name__ == "__main__":
    unittest.main()
