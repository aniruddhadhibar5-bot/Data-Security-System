"""Encrypted item catalog, tags, favorites, and archive views.

The catalog stores only non-sensitive organization metadata. Secret payloads remain
inside the encrypted vault service. Tags are normalized and persisted separately so
users can organize records without changing their cryptographic payloads.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from core.database import Database


@dataclass(frozen=True)
class CatalogItem:
    item_id: int
    kind: str
    title: str
    tags: tuple[str, ...]
    favorite: bool
    archived: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CatalogSummary:
    total: int
    favorites: int
    archived: int
    tagged: int
    tag_counts: dict[str, int]


class CatalogService:
    def __init__(self, database: Database):
        self.database = database
        self._create_schema()

    def _create_schema(self) -> None:
        self.database.connection.executescript("""
            CREATE TABLE IF NOT EXISTS item_labels (
                item_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                PRIMARY KEY (item_id, label),
                FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS item_flags (
                item_id INTEGER PRIMARY KEY,
                favorite INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE
            );
        """)
        self.database.connection.commit()
        self.database.update_integrity()

    def normalize_tag(self, tag: str) -> str:
        normalized = re.sub(r"[^a-z0-9_-]+", "-", tag.casefold().strip())
        return normalized.strip("-")[:48]

    def normalize_tags(self, tags: Iterable[str]) -> tuple[str, ...]:
        clean = {self.normalize_tag(tag) for tag in tags}
        return tuple(sorted(tag for tag in clean if tag))

    def set_tags(self, item_id: int, tags: Iterable[str]) -> tuple[str, ...]:
        clean = self.normalize_tags(tags)
        self.database.connection.execute("DELETE FROM item_labels WHERE item_id = ?", (item_id,))
        self.database.connection.executemany("INSERT INTO item_labels(item_id, label) VALUES (?, ?)", [(item_id, tag) for tag in clean])
        self.database.connection.commit()
        self.database.update_integrity()
        self.database.add_audit("TAG", f"Updated labels for item {item_id}")
        return clean

    def add_tag(self, item_id: int, tag: str) -> tuple[str, ...]:
        current = set(self.tags_for(item_id))
        current.add(tag)
        return self.set_tags(item_id, current)

    def remove_tag(self, item_id: int, tag: str) -> tuple[str, ...]:
        current = set(self.tags_for(item_id))
        current.discard(self.normalize_tag(tag))
        return self.set_tags(item_id, current)

    def tags_for(self, item_id: int) -> tuple[str, ...]:
        rows = self.database.connection.execute("SELECT label FROM item_labels WHERE item_id = ? ORDER BY label", (item_id,))
        return tuple(row["label"] for row in rows)

    def all_tags(self) -> list[str]:
        rows = self.database.connection.execute("SELECT label FROM item_labels GROUP BY label ORDER BY label")
        return [row["label"] for row in rows]

    def toggle_favorite(self, item_id: int) -> bool:
        current = self.flags_for(item_id)
        favorite = not current["favorite"]
        self._save_flags(item_id, favorite, current["archived"])
        self.database.add_audit("FAVORITE", f"Item {item_id} favorite set to {favorite}")
        return favorite

    def toggle_archive(self, item_id: int) -> bool:
        current = self.flags_for(item_id)
        archived = not current["archived"]
        self._save_flags(item_id, current["favorite"], archived)
        self.database.add_audit("ARCHIVE", f"Item {item_id} archived set to {archived}")
        return archived

    def flags_for(self, item_id: int) -> dict[str, bool]:
        row = self.database.connection.execute("SELECT favorite, archived FROM item_flags WHERE item_id = ?", (item_id,)).fetchone()
        return {"favorite": bool(row["favorite"]), "archived": bool(row["archived"])} if row else {"favorite": False, "archived": False}

    def _save_flags(self, item_id: int, favorite: bool, archived: bool) -> None:
        self.database.connection.execute("INSERT OR REPLACE INTO item_flags(item_id, favorite, archived) VALUES (?, ?, ?)", (item_id, int(favorite), int(archived)))
        self.database.connection.commit()
        self.database.update_integrity()

    def catalog_items(self, kind: str | None = None, tag: str | None = None, include_archived: bool = False) -> list[CatalogItem]:
        rows = self.database.list_items(kind)
        result = []
        normalized_tag = self.normalize_tag(tag) if tag else None
        for row in rows:
            flags = self.flags_for(row["id"])
            tags = self.tags_for(row["id"])
            if not include_archived and flags["archived"]:
                continue
            if normalized_tag and normalized_tag not in tags:
                continue
            result.append(CatalogItem(row["id"], row["kind"], row["title"], tags, flags["favorite"], flags["archived"], row["created_at"], row["updated_at"]))
        return result

    def summary(self) -> CatalogSummary:
        items = self.catalog_items(include_archived=True)
        counts: dict[str, int] = {}
        for item in items:
            for tag in item.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return CatalogSummary(len(items), sum(item.favorite for item in items), sum(item.archived for item in items), sum(bool(item.tags) for item in items), counts)

    def export_catalog(self) -> list[dict]:
        return [{"id": item.item_id, "kind": item.kind, "title": item.title, "tags": list(item.tags), "favorite": item.favorite, "archived": item.archived, "created_at": item.created_at, "updated_at": item.updated_at} for item in self.catalog_items(include_archived=True)]

    def import_catalog(self, records: Iterable[dict]) -> int:
        updated = 0
        for record in records:
            item_id = int(record.get("id", 0))
            if not self.database.get_item(item_id):
                continue
            self.set_tags(item_id, record.get("tags", []))
            if bool(record.get("favorite")) != self.flags_for(item_id)["favorite"]:
                self.toggle_favorite(item_id)
            if bool(record.get("archived")) != self.flags_for(item_id)["archived"]:
                self.toggle_archive(item_id)
            updated += 1
        return updated

    def clear_item(self, item_id: int) -> None:
        self.database.connection.execute("DELETE FROM item_labels WHERE item_id = ?", (item_id,))
        self.database.connection.execute("DELETE FROM item_flags WHERE item_id = ?", (item_id,))
        self.database.connection.commit()
        self.database.update_integrity()

    def remove_deleted_items(self) -> int:
        rows = self.database.connection.execute("SELECT item_id FROM item_labels UNION SELECT item_id FROM item_flags").fetchall()
        removed = 0
        for row in rows:
            if not self.database.get_item(row["item_id"]):
                self.clear_item(row["item_id"])
                removed += 1
        return removed
