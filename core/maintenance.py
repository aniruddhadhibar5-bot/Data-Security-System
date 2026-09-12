"""Maintenance jobs that keep local vault storage understandable and healthy."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.database import Database
from core.storage import VaultInventory


@dataclass(frozen=True)
class MaintenanceResult:
    name: str
    changed: int
    detail: str


class MaintenanceService:
    def __init__(self, database: Database, inventory: VaultInventory | None = None):
        self.database = database
        self.inventory = inventory or VaultInventory()

    def vacuum_database(self) -> MaintenanceResult:
        before = self.database.usage_bytes()
        self.database.connection.execute("VACUUM")
        self.database.update_integrity()
        after = self.database.usage_bytes()
        return MaintenanceResult("Database vacuum", max(0, before - after), f"Reduced database from {before} to {after} bytes")

    def orphaned_payloads(self) -> list[Path]:
        referenced = {row["payload"] for row in self.database.list_items("FILE")}
        return self.inventory.orphaned(referenced)

    def clean_orphaned_payloads(self) -> MaintenanceResult:
        orphaned = self.orphaned_payloads()
        removed = self.inventory.remove_orphaned({row["payload"] for row in self.database.list_items("FILE")})
        if removed:
            self.database.add_audit("MAINTENANCE", f"Removed {removed} orphaned encrypted payloads")
        return MaintenanceResult("Orphan cleanup", removed, f"Removed {removed} unused file payloads")

    def stale_audit_events(self, before: str) -> list[sqlite3.Row]:
        return list(self.database.connection.execute("SELECT * FROM audit WHERE created_at < ? ORDER BY id", (before,)))

    def count_stale_audit_events(self, before: str) -> int:
        return len(self.stale_audit_events(before))

    def compact_audit(self, before: str) -> MaintenanceResult:
        stale = self.count_stale_audit_events(before)
        self.database.connection.execute("DELETE FROM audit WHERE created_at < ?", (before,))
        self.database.connection.commit()
        self.database.update_integrity()
        if stale:
            self.database.add_audit("MAINTENANCE", f"Compacted {stale} old audit events")
        return MaintenanceResult("Audit compaction", stale, f"Removed {stale} events before {before}")

    def integrity_snapshot(self) -> dict[str, str | int]:
        return {
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "database_bytes": self.database.usage_bytes(),
            "database_digest": self.database.integrity_path.read_text(encoding="utf-8").strip() if self.database.integrity_path.exists() else "",
            "vault_files": len(self.inventory.files()),
            "vault_bytes": self.inventory.total_size(),
        }

    def maintenance_report(self) -> list[MaintenanceResult]:
        return [
            MaintenanceResult("Database", 0, f"{self.database.usage_bytes()} bytes"),
            MaintenanceResult("Encrypted payloads", 0, f"{len(self.inventory.files())} payloads"),
            MaintenanceResult("Orphaned payloads", len(self.orphaned_payloads()), "Ready for review"),
        ]
