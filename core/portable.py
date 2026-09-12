"""Encrypted portable record packages.

A portable package is useful for moving one password, note, or catalog entry
between local workspaces. The package is encrypted with the authenticated master
key and contains no plaintext secret until it is explicitly imported.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.catalog import CatalogService
from core.database import Database
from core.security import EncryptedValue, SecurityManager
from core.vault import VaultService


@dataclass(frozen=True)
class PortablePackage:
    format: str
    version: int
    created_at: str
    kind: str
    title: str
    payload: str
    wrapped_key: str
    tags: tuple[str, ...]
    favorite: bool

    def as_dict(self) -> dict:
        return {
            "format": self.format,
            "version": self.version,
            "created_at": self.created_at,
            "kind": self.kind,
            "title": self.title,
            "payload": self.payload,
            "wrapped_key": self.wrapped_key,
            "tags": list(self.tags),
            "favorite": self.favorite,
        }


class PortableRecordService:
    FORMAT = "dss-record"
    VERSION = 1

    def __init__(self, database: Database, vault: VaultService, catalog: CatalogService | None = None):
        self.database = database
        self.vault = vault
        self.catalog = catalog or CatalogService(database)
        self.security = vault.security

    def _key(self) -> bytes:
        if self.vault.master_key is None:
            raise PermissionError("Vault is locked")
        return self.vault.master_key

    def package(self, item_id: int) -> PortablePackage:
        row = self.database.get_item(item_id)
        if row is None:
            raise KeyError(f"Unknown item: {item_id}")
        flags = self.catalog.flags_for(item_id)
        return PortablePackage(self.FORMAT, self.VERSION, datetime.now().isoformat(timespec="seconds"), row["kind"], row["title"], row["payload"], row["wrapped_key"], self.catalog.tags_for(item_id), flags["favorite"])

    def export(self, item_id: int, destination: Path) -> Path:
        package = self.package(item_id)
        plaintext = json.dumps(package.as_dict(), sort_keys=True).encode("utf-8")
        encrypted = self.security.encrypt(plaintext, self._key(), b"dss-record-v1")
        destination.write_bytes(encrypted.nonce + encrypted.ciphertext)
        self.database.add_audit("EXPORT_ITEM", f"Encrypted record exported: {package.title}")
        return destination

    def decrypt_package(self, source: Path) -> dict:
        raw = source.read_bytes()
        if len(raw) <= 12:
            raise ValueError("Record package is incomplete")
        encrypted = EncryptedValue(raw[:12], raw[12:])
        value = self.security.decrypt(encrypted, self._key(), b"dss-record-v1")
        package = json.loads(value.decode("utf-8"))
        self.validate(package)
        return package

    def validate(self, package: dict) -> None:
        if package.get("format") != self.FORMAT:
            raise ValueError("Unsupported record package format")
        if package.get("version") != self.VERSION:
            raise ValueError("Unsupported record package version")
        required = {"kind", "title", "payload", "wrapped_key", "tags", "favorite"}
        missing = required.difference(package)
        if missing:
            raise ValueError(f"Record package is missing: {', '.join(sorted(missing))}")
        if not isinstance(package["tags"], list):
            raise ValueError("Record package tags must be a list")

    def import_record(self, source: Path, title_override: str | None = None) -> int:
        package = self.decrypt_package(source)
        title = title_override.strip() if title_override else package["title"]
        if not title:
            raise ValueError("Imported records require a title")
        item_id = self.database.add_item(package["kind"], title, package["payload"], package["wrapped_key"])
        self.catalog.set_tags(item_id, package["tags"])
        if package.get("favorite"):
            self.catalog.toggle_favorite(item_id)
        self.database.add_audit("IMPORT_ITEM", f"Encrypted record imported: {title}")
        return item_id

    def preview(self, source: Path) -> dict[str, str | int | list]:
        package = self.decrypt_package(source)
        return {"format": package["format"], "version": package["version"], "kind": package["kind"], "title": package["title"], "tags": package["tags"]}

    def rewrap(self, item_id: int) -> None:
        row = self.database.get_item(item_id)
        if row is None:
            raise KeyError(f"Unknown item: {item_id}")
        item_key = self.security.decrypt(self.security.unpack(row["wrapped_key"]), self._key())
        replacement = self.security.encrypt(item_key, self._key())
        self.database.update_item(item_id, row["title"], row["payload"])
        self.database.connection.execute("UPDATE items SET wrapped_key = ? WHERE id = ?", (self.security.pack(replacement), item_id))
        self.database.connection.commit()
        self.database.update_integrity()
        self.database.add_audit("REWRAP", f"Rewrapped item key: {row['title']}")

    def package_as_json(self, item_id: int) -> str:
        return json.dumps(self.package(item_id).as_dict(), indent=2, sort_keys=True)

    def package_digest(self, item_id: int) -> str:
        package = self.package_as_json(item_id).encode("utf-8")
        return self.security.fingerprint(package)
