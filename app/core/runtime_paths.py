"""Portable per-user paths for runtime configuration.

Runtime settings must not live in the Git checkout: that makes a cloned copy
inherit another computer's IP addresses and credentials.
"""

from __future__ import annotations

import os
from pathlib import Path


def user_config_dir() -> Path:
    """Return the platform-appropriate writable configuration directory."""
    override = os.getenv("IDS_IPS_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "AI-based Network IDS-IPS"
    root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "ai-network-ids-ips"


def runtime_config_path(filename: str) -> Path:
    return user_config_dir() / filename
