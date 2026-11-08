"""PostgreSQL database connection and management service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

CONFIG_FILE = Path(__file__).resolve().parents[2] / "db_config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "host": "localhost",
    "port": 5432,
    "database": "ids_ips_db",
    "user": "postgres",
    "password": "your_password",
}

_CONNECTION_POOL = None
_CONNECTION_POOL_KEY: tuple[Any, ...] | None = None
_CONNECTION_POOL_LOCK = Lock()


def get_db_config() -> dict[str, Any]:
    """Retrieve database connection settings from db_config.json or environment."""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                loaded = json.load(file)
                if isinstance(loaded, dict):
                    config.update(loaded)
        except Exception as error:
            print(f"[Database] Warning: Failed to read {CONFIG_FILE}: {error}")

    # Environment variables take precedence if present
    if "DB_HOST" in os.environ:
        config["host"] = os.environ["DB_HOST"]
    if "DB_PORT" in os.environ:
        try:
            config["port"] = int(os.environ["DB_PORT"])
        except ValueError:
            pass
    if "DB_NAME" in os.environ:
        config["database"] = os.environ["DB_NAME"]
    if "DB_USER" in os.environ:
        config["user"] = os.environ["DB_USER"]
    if "DB_PASSWORD" in os.environ:
        config["password"] = os.environ["DB_PASSWORD"]

    return config


def save_db_config(new_config: dict[str, Any]) -> bool:
    """Save database connection settings to db_config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(new_config, file, indent=2, ensure_ascii=False)
        return True
    except Exception as error:
        print(f"[Database] Failed to write config: {error}")
        return False


def get_connection():
    """Borrow a PostgreSQL connection from a small thread-safe pool."""
    global _CONNECTION_POOL, _CONNECTION_POOL_KEY

    try:
        from psycopg2.pool import ThreadedConnectionPool
    except ImportError as error:
        raise RuntimeError(
            "Chưa cài đặt thư viện psycopg2. Vui lòng chạy lệnh:\n"
            "pip install psycopg2-binary"
        ) from error

    config = get_db_config()
    pool_key = (
        config["host"],
        config["port"],
        config["database"],
        config["user"],
        config["password"],
        config.get("sslmode"),
    )
    with _CONNECTION_POOL_LOCK:
        if _CONNECTION_POOL is None or _CONNECTION_POOL_KEY != pool_key:
            if _CONNECTION_POOL is not None:
                _CONNECTION_POOL.closeall()
            connection_options = {
                "host": config["host"],
                "port": config["port"],
                "dbname": config["database"],
                "user": config["user"],
                "password": config["password"],
                "connect_timeout": 5,
            }
            if config.get("sslmode"):
                connection_options["sslmode"] = config["sslmode"]
            _CONNECTION_POOL = ThreadedConnectionPool(1, 4, **connection_options)
            _CONNECTION_POOL_KEY = pool_key
        connection = _CONNECTION_POOL.getconn()
        connection.autocommit = False
        return connection


def release_connection(connection) -> None:
    """Return a borrowed connection to the pool in a clean transaction state."""
    if connection is None:
        return
    with _CONNECTION_POOL_LOCK:
        if _CONNECTION_POOL is None:
            connection.close()
            return
        try:
            if not connection.closed:
                connection.rollback()
            _CONNECTION_POOL.putconn(connection, close=bool(connection.closed))
        except Exception:
            connection.close()


def ensure_database_exists() -> tuple[bool, str]:
    """Ensure the target database exists; if not, connect to 'postgres' and create it."""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError as error:
        return False, f"Chưa cài đặt thư viện psycopg2: {error}"

    config = get_db_config()
    target_db = config["database"]

    # Try connecting directly
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname=target_db,
            user=config["user"],
            password=config["password"],
            connect_timeout=5,
        )
        conn.close()
        return True, f"Cơ sở dữ liệu '{target_db}' đã sẵn sàng."
    except Exception as err:
        err_msg = str(err).lower()
        if f'database "{target_db.lower()}" does not exist' in err_msg or "does not exist" in err_msg:
            # Target DB doesn't exist yet -> connect to maintenance DB 'postgres' to create it
            try:
                admin_conn = psycopg2.connect(
                    host=config["host"],
                    port=config["port"],
                    dbname="postgres",
                    user=config["user"],
                    password=config["password"],
                    connect_timeout=5,
                )
                admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with admin_conn.cursor() as cur:
                    cur.execute(f'CREATE DATABASE "{target_db}";')
                admin_conn.close()
                return True, f"Đã tự động tạo cơ sở dữ liệu '{target_db}'."
            except Exception as create_err:
                return False, f"Không thể tự động tạo database '{target_db}': {create_err}"
        return False, str(err)


def test_connection() -> tuple[bool, str]:
    """Test connection to the PostgreSQL server and database."""
    conn = None
    try:
        ensure_ok, ensure_msg = ensure_database_exists()
        if not ensure_ok:
            return False, f"Lỗi cơ sở dữ liệu: {ensure_msg}"

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
        return True, f"Kết nối thành công! Phiên bản: {version.split(',')[0]}"
    except Exception as error:
        return False, f"Lỗi kết nối cơ sở dữ liệu: {error}"
    finally:
        release_connection(conn)


def init_db() -> tuple[bool, str]:
    """Ensure the database and required tables/indexes exist in PostgreSQL."""
    # Ensure database exists first
    db_ok, db_msg = ensure_database_exists()
    if not db_ok:
        return False, db_msg

    schema_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        full_name VARCHAR(100) NOT NULL,
        password_hash VARCHAR(128) NOT NULL,
        salt VARCHAR(64) NOT NULL,
        role VARCHAR(50) DEFAULT 'Quản trị viên',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP WITH TIME ZONE
    );

    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """
    conn = None
    try:
        conn = get_connection()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        return True, "Khởi tạo bảng cơ sở dữ liệu thành công."
    except Exception as error:
        return False, f"Không thể khởi tạo cơ sở dữ liệu: {error}"
    finally:
        release_connection(conn)
