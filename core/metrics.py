"""Privacy-preserving workspace metrics for dashboard summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.audit import AuditService
from core.database import Database
from core.storage import VaultInventory


@dataclass(frozen=True)
class WorkspaceMetrics:
    total_items: int
    password_items: int
    note_items: int
    file_items: int
    encrypted_file_bytes: int
    audit_events: int
    failed_logins: int
    integrity_verified: bool
    captured_at: str

    @property
    def human_item_summary(self) -> str:
        return f"{self.total_items} encrypted item{'s' if self.total_items != 1 else ''}"

    @property
    def human_file_summary(self) -> str:
        return f"{self.file_items} file payload{'s' if self.file_items != 1 else ''}"


class MetricsService:
    def __init__(self, database: Database, inventory: VaultInventory | None = None, audit: AuditService | None = None):
        self.database = database
        self.inventory = inventory or VaultInventory()
        self.audit = audit or AuditService(database)

    def collect(self) -> WorkspaceMetrics:
        total = self.database.count_items()
        passwords = self.database.count_items("PASSWORD")
        notes = self.database.count_items("NOTE")
        files = self.database.count_items("FILE")
        summary = self.audit.security_summary()
        return WorkspaceMetrics(
            total_items=total,
            password_items=passwords,
            note_items=notes,
            file_items=files,
            encrypted_file_bytes=self.inventory.total_size(),
            audit_events=int(summary["events"]),
            failed_logins=int(summary["failed_logins"]),
            integrity_verified=self.database.integrity_ok(),
            captured_at=datetime.now().isoformat(timespec="seconds"),
        )

    def cards(self) -> list[tuple[str, str, str]]:
        metrics = self.collect()
        return [
            ("Vault items", str(metrics.total_items), "Encrypted records"),
            ("Credentials", str(metrics.password_items), "Password records"),
            ("Secure notes", str(metrics.note_items), "Encrypted text records"),
            ("Files", str(metrics.file_items), metrics.human_file_summary),
            ("Payload storage", self._size(metrics.encrypted_file_bytes), "Encrypted file bytes"),
            ("Audit events", str(metrics.audit_events), "Recorded operations"),
        ]

    def health(self) -> str:
        metrics = self.collect()
        if not metrics.integrity_verified:
            return "Review database integrity"
        if metrics.failed_logins >= 5:
            return "Review failed login activity"
        return "Workspace healthy"

    def health_details(self) -> dict[str, str | bool]:
        metrics = self.collect()
        return {
            "status": self.health(),
            "integrity": "verified" if metrics.integrity_verified else "failed",
            "failed_logins": str(metrics.failed_logins),
            "encrypted_items": str(metrics.total_items),
        }

    def _size(self, value: int) -> str:
        amount = float(value)
        for unit in ("B", "KB", "MB", "GB"):
            if amount < 1024 or unit == "GB":
                return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
            amount /= 1024
        return f"{amount:.1f} GB"
