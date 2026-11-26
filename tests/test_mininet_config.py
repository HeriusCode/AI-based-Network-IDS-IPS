from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.mininet_config import load_mininet_config, save_mininet_config


class MininetConfigTest(unittest.TestCase):
    def test_connection_is_saved_per_workstation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mininet.json"
            environment = {
                "MININET_CONFIG": str(path),
                "MININET_VM_IP": "",
                "MININET_AGENT_PORT": "",
                "MININET_VM_USER": "",
                "MININET_AGENT_URL": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                saved = save_mininet_config("192.168.1.15", 9000)
                loaded = load_mininet_config()
            self.assertEqual(saved, loaded)
            self.assertEqual(loaded.agent_url, "http://192.168.1.15:9000")


if __name__ == "__main__":
    unittest.main()
