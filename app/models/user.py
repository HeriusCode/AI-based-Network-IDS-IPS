"""User model representation for authentication and authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: Optional[int]
    username: str
    email: str
    full_name: str
    role: str = "Quản trị viên"
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

