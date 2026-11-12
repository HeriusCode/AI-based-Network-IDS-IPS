"""SQLite persistence for traffic sessions."""

from __future__ import annotations

import csv
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.models.traffic_session import TrafficSession


class LogService:
    COLUMNS = (
        "session_id",
        "started_at",
        "ended_at",
        "destination_ip",
        "destination_port",
        "protocol",
        "scenario",
        "total_packets",
        "total_bytes",
        "successful_connections",
        "failed_connections",
        "duration_seconds",
        "status",
        "error_message",
    )

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS traffic_sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    destination_ip TEXT NOT NULL,
                    destination_port INTEGER NOT NULL,
                    protocol TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    total_packets INTEGER NOT NULL,
                    total_bytes INTEGER NOT NULL,
                    successful_connections INTEGER NOT NULL,
                    failed_connections INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.commit()

    def save_session(self, session: TrafficSession) -> None:
        values = session.to_dict()
        placeholders = ", ".join("?" for _ in self.COLUMNS)
        with closing(self._connect()) as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO traffic_sessions ({', '.join(self.COLUMNS)}) VALUES ({placeholders})",
                tuple(values[column] for column in self.COLUMNS),
            )
            connection.commit()

    def list_sessions(
        self,
        search: str = "",
        protocol: str = "Tất cả",
        status: str = "Tất cả",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if search.strip():
            term = f"%{search.strip()}%"
            clauses.append("(session_id LIKE ? OR destination_ip LIKE ? OR scenario LIKE ?)")
            parameters.extend([term, term, term])
        if protocol != "Tất cả":
            clauses.append("protocol = ?")
            parameters.append(protocol)
        if status != "Tất cả":
            clauses.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM traffic_sessions {where} ORDER BY started_at DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def clear(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM traffic_sessions")
            connection.commit()

    def export_csv(self, path: Path, rows: list[dict[str, Any]] | None = None) -> None:
        records = rows if rows is not None else self.list_sessions(limit=10_000)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.COLUMNS)
            writer.writeheader()
            writer.writerows(records)
