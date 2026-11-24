from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from app.config import AppConfig
from app.controller import AppController


class ExternalConfigReloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_app = QCoreApplication.instance() or QCoreApplication([])

    def test_controller_reloads_dhcp_sync_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            config_path = data / "config.json"
            config_path.write_text(json.dumps(asdict(AppConfig())), encoding="utf-8")
            controller = AppController(root)
            payload = asdict(AppConfig())
            payload["server_ip"] = "192.168.1.12"
            payload["vm_ip"] = "192.168.201.130"
            config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            controller._reload_external_configuration()
            self.assertEqual(controller.config_manager.config.server_ip, "192.168.1.12")
            self.assertEqual(controller.config_manager.config.vm_ip, "192.168.201.130")


if __name__ == "__main__":
    unittest.main()
