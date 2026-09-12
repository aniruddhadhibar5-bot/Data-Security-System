"""SQLite persistence with encrypted payloads and integrity monitoring."""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DATABASE_PATH, INTEGRITY_PATH


class Database:
    def __init__(self, path: Path = DATABASE_PATH):
        self.path = path
        self.integrity_path = path.with_suffix(path.suffix + ".sha256") if path != DATABASE_PATH else INTEGRITY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.startup_integrity_ok = self.integrity_ok()
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL,
                wrapped_key TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
                detail TEXT NOT NULL, created_at TEXT NOT NULL
            );
        """)
        self.connection.commit()
        self.update_integrity()

    def get_metadata(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        self.connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", (key, value))
        self.connection.commit()
        self.update_integrity()

    def add_item(self, kind: str, title: str, payload: str, wrapped_key: str) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.connection.execute(
            "INSERT INTO items(kind, title, payload, wrapped_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, title, payload, wrapped_key, now, now),
        )
        self.connection.commit()
        self.update_integrity()
        return int(cursor.lastrowid)

    def list_items(self, kind: str | None = None) -> list[sqlite3.Row]:
        if kind:
            return list(self.connection.execute("SELECT * FROM items WHERE kind = ? ORDER BY updated_at DESC", (kind,)))
        return list(self.connection.execute("SELECT * FROM items ORDER BY updated_at DESC"))

    def get_item(self, item_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    def update_item(self, item_id: int, title: str, payload: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.connection.execute("UPDATE items SET title = ?, payload = ?, updated_at = ? WHERE id = ?", (title, payload, now, item_id))
        self.connection.commit()
        self.update_integrity()

    def count_items(self, kind: str | None = None) -> int:
        if kind:
            return int(self.connection.execute("SELECT COUNT(*) FROM items WHERE kind = ?", (kind,)).fetchone()[0])
        return int(self.connection.execute("SELECT COUNT(*) FROM items").fetchone()[0])

    def delete_item(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self.connection.commit()
        self.update_integrity()

    def add_audit(self, event: str, detail: str) -> None:
        self.connection.execute(
            "INSERT INTO audit(event, detail, created_at) VALUES (?, ?, ?)",
            (event, detail, datetime.now().isoformat(timespec="seconds")),
        )
        self.connection.commit()
        self.update_integrity()

    def recent_audit(self, limit: int = 8) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)))

    def audit_between(self, start: str, end: str) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM audit WHERE created_at >= ? AND created_at <= ? ORDER BY id DESC", (start, end)))

    def usage_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def integrity_ok(self) -> bool:
        if not self.integrity_path.exists() or not self.path.exists():
            return True
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        return digest == self.integrity_path.read_text(encoding="utf-8").strip()

    def update_integrity(self) -> None:
        if self.path.exists():
            self.integrity_path.write_text(hashlib.sha256(self.path.read_bytes()).hexdigest(), encoding="utf-8")

    def export_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def close(self) -> None:
        self.connection.close()
