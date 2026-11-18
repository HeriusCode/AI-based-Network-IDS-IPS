"""Service layer for database operations, authentication, and backend integrations."""

from app.services.auth_service import authenticate_user, ensure_default_admin, register_user
from app.services.database import get_connection, get_db_config, init_db, save_db_config, test_connection

__all__ = [
    "authenticate_user",
    "ensure_default_admin",
    "get_connection",
    "get_db_config",
    "init_db",
    "register_user",
    "save_db_config",
    "test_connection",
]
